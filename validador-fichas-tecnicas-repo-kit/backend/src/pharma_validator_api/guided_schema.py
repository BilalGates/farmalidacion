"""Esquema JSON de salida guiada para el extractor (DEV-403).

La especificación 8.3 exige decodificación guiada por esquema —guided decoding
en vLLM, gramáticas GBNF en llama.cpp— y advierte de que no hay que confiar en
pedir JSON en el prompt y luego parsear: con modelos locales pequeños eso falla
lo bastante a menudo como para envenenar el proceso por lotes.

Este módulo construye el esquema a partir del catálogo y valida una respuesta
contra él. No llama al modelo y no verifica la evidencia: eso es DEV-405, que
se aplica después sobre cada propuesta ya bien formada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from pharma_validator_api.evidence_verification import (
    MAX_EVIDENCE_LENGTH,
    MIN_EVIDENCE_LENGTH,
    ProposedExtraction,
)
from pharma_validator_api.extractor import FieldRequest

SCHEMA_VERSION = "guided-extraction-v1"

_CHAR = re.compile(r"^CHAR\((\d+)\)$", re.IGNORECASE)
_DECIMAL = re.compile(r"^DECIMAL\((\d+),\s*(\d+)\)$", re.IGNORECASE)
_BIT = re.compile(r"^BIT$", re.IGNORECASE)

_STATES = ("encontrado", "no_encontrado", "ambiguo")


class GuidedSchemaError(RuntimeError):
    """La respuesta no se ajusta al esquema declarado."""


@dataclass(frozen=True)
class TypeConstraint:
    """Restricción derivada de `tipo_dato`, no reinterpretada.

    El límite de longitud se deriva del tipo declarado en el catálogo. No se
    trunca nunca: un valor que excede se rechaza con un error legible, según la
    especificación 12.3.
    """

    declared_type: str
    max_length: int | None = None
    decimal_precision: int | None = None
    decimal_scale: int | None = None
    is_boolean: bool = False


def constraint_for(declared_type: str) -> TypeConstraint:
    text = declared_type.strip()
    char = _CHAR.match(text)
    if char:
        return TypeConstraint(text, max_length=int(char.group(1)))
    decimal = _DECIMAL.match(text)
    if decimal:
        return TypeConstraint(
            text,
            decimal_precision=int(decimal.group(1)),
            decimal_scale=int(decimal.group(2)),
        )
    if _BIT.match(text):
        return TypeConstraint(text, is_boolean=True)
    # Un tipo no reconocido no se adivina ni se relaja a texto libre.
    return TypeConstraint(text)


def build_schema(fields: tuple[FieldRequest, ...]) -> dict[str, Any]:
    """Construye el esquema JSON que gobierna la decodificación.

    El esquema es cerrado: `additionalProperties` es falso y `required` cubre
    todos los campos de cada resultado, de modo que el motor no pueda emitir
    claves no previstas ni omitir la cita.
    """
    if not fields:
        raise ValueError("El esquema requiere al menos un campo.")
    names = [item.field_name for item in fields]
    if len(set(names)) != len(names):
        raise ValueError("Los campos del esquema deben ser únicos.")

    result_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "campo",
            "estado",
            "valor",
            "opciones",
            "evidencia_texto",
            "evidencia_ini",
            "evidencia_fin",
            "confianza",
        ],
        "properties": {
            "campo": {"type": "string", "enum": sorted(names)},
            "estado": {"type": "string", "enum": list(_STATES)},
            "valor": {"type": ["string", "null"]},
            "opciones": {"type": ["array", "null"], "items": {"type": "string"}},
            "evidencia_texto": {
                "type": ["string", "null"],
                "minLength": MIN_EVIDENCE_LENGTH,
                "maxLength": MAX_EVIDENCE_LENGTH,
            },
            "evidencia_ini": {"type": ["integer", "null"], "minimum": 0},
            "evidencia_fin": {"type": ["integer", "null"], "minimum": 0},
            "confianza": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": SCHEMA_VERSION,
        "type": "object",
        "additionalProperties": False,
        "required": ["resultados"],
        "properties": {
            "resultados": {
                "type": "array",
                "minItems": len(fields),
                "maxItems": len(fields),
                "items": result_schema,
            }
        },
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GuidedSchemaError(message)


def validate_value_against_type(value: str, constraint: TypeConstraint) -> None:
    """Valida sin convertir, redondear ni truncar."""
    if constraint.max_length is not None and len(value) > constraint.max_length:
        raise GuidedSchemaError(
            f"El valor mide {len(value)} caracteres y {constraint.declared_type} "
            f"admite {constraint.max_length}; no se trunca."
        )
    if constraint.is_boolean and value not in ("0", "1"):
        raise GuidedSchemaError(f"El tipo BIT solo admite 0 o 1; se recibió {value!r}.")
    if constraint.decimal_precision is not None:
        try:
            number = Decimal(value)
        except InvalidOperation as error:
            raise GuidedSchemaError(f"El valor {value!r} no es decimal.") from error
        sign, digits, exponent = number.as_tuple()
        if not isinstance(exponent, int):
            raise GuidedSchemaError(f"El valor {value!r} no es decimal finito.")
        scale = max(0, -exponent)
        if constraint.decimal_scale is not None and scale > constraint.decimal_scale:
            raise GuidedSchemaError(
                f"El valor {value!r} tiene {scale} decimales y el tipo admite "
                f"{constraint.decimal_scale}; no se redondea."
            )
        if len(digits) > constraint.decimal_precision:
            raise GuidedSchemaError(
                f"El valor {value!r} excede la precisión {constraint.decimal_precision}."
            )


def parse_response(
    payload: dict[str, Any], fields: tuple[FieldRequest, ...], section: str
) -> tuple[ProposedExtraction, ...]:
    """Convierte una respuesta del modelo en propuestas bien formadas.

    Una respuesta malformada es un error explícito, nunca una propuesta
    parcialmente reconstruida: reparar aquí introduciría un valor que el modelo
    no emitió.

    La sección la aporta quien hizo la petición, no el modelo: el esquema agrupa
    por apartado y pedirle que la repita permitiría citar una sección distinta
    de la que se le dio.
    """
    if not section:
        raise ValueError("La respuesta requiere el apartado citado.")
    by_name = {item.field_name: item for item in fields}
    _require("resultados" in payload, "La respuesta no contiene 'resultados'.")
    results = payload["resultados"]
    _require(isinstance(results, list), "'resultados' debe ser una lista.")

    proposals: list[ProposedExtraction] = []
    seen: set[str] = set()
    for entry in results:
        _require(isinstance(entry, dict), "Cada resultado debe ser un objeto.")
        name = entry.get("campo")
        _require(isinstance(name, str) and name in by_name, f"Campo desconocido: {name!r}.")
        _require(name not in seen, f"El campo {name} aparece más de una vez.")
        seen.add(name)

        state = entry.get("estado")
        _require(state in _STATES, f"Estado no admitido: {state!r}.")

        value = entry.get("valor")
        _require(value is None or isinstance(value, str), "'valor' debe ser texto o nulo.")
        if isinstance(value, str):
            validate_value_against_type(value, constraint_for(by_name[name].data_type))

        raw_options = entry.get("opciones")
        _require(
            raw_options is None or isinstance(raw_options, list),
            "'opciones' debe ser lista o nulo.",
        )
        options: tuple[str, ...] = ()
        if isinstance(raw_options, list):
            _require(
                all(isinstance(item, str) for item in raw_options),
                "Las opciones deben ser texto.",
            )
            options = tuple(raw_options)

        evidence = entry.get("evidencia_texto")
        _require(
            evidence is None or isinstance(evidence, str),
            "'evidencia_texto' debe ser texto o nulo.",
        )
        start, end = entry.get("evidencia_ini"), entry.get("evidencia_fin")
        for offset in (start, end):
            _require(
                offset is None or (isinstance(offset, int) and not isinstance(offset, bool)),
                "Los desplazamientos deben ser enteros o nulos.",
            )

        proposals.append(
            ProposedExtraction(
                field_name=name,
                state=state,
                proposed_value=value,
                options=options,
                evidence_section=None if evidence is None else section,
                evidence_text=evidence,
                evidence_start=start,
                evidence_end=end,
            )
        )

    missing = sorted(set(by_name) - seen)
    _require(not missing, f"Faltan resultados para: {', '.join(missing)}.")
    return tuple(sorted(proposals, key=lambda item: item.field_name))
