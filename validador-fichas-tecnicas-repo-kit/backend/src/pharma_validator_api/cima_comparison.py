"""Comparación literal y conservadora de campos del maestro con la FT CIMA.

El catálogo de 353 campos es el único mapa de secciones disponible. La
comparación solo lo usa cuando la entidad, bloque y nombre coinciden sin
ambigüedad. Las clasificaciones parciales o interpretables siempre exigen
criterio humano; no se calculan ni normalizan valores.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class CimaSection:
    locator: str
    literal_text: str


@dataclass(frozen=True)
class CimaDocument:
    document_name: str
    document_version_id: str
    source_version: str | None
    content_hash: str
    sections: tuple[CimaSection, ...]


@dataclass(frozen=True)
class CatalogField:
    id: str
    entity: str
    block: str
    name: str
    from_ft: str | None
    sections: str | None


@dataclass(frozen=True)
class MasterField:
    id: str
    entity_type: str
    block_type: str
    ordinal: int
    source_column_index: int | None
    name: str
    value: str | None


@dataclass(frozen=True)
class CimaFieldComparison:
    field_value_id: str
    block_type: str
    occurrence: int
    field_name: str
    source_column_index: int | None
    master_value: str | None
    catalog_field_id: str | None
    catalog_classification: str | None
    document_name: str | None
    document_version_id: str | None
    source_version: str | None
    content_hash: str | None
    status: str
    reason: str
    section_locators: tuple[str, ...]


ENTITY_LABELS = {
    "active_ingredient": "1. Principio Activo",
    "medication": "2. Medicamento",
    "specialty": "3. Especialidad",
}

BLOCK_LABELS = {
    ("active_ingredient", "active_ingredient_general"): "Principio activo - General+DMAX",
    ("medication", "medication_general"): "Medicamento - General",
    ("medication", "medication_composition"): "Medicamento - Composición",
    ("medication", "medication_indication"): "Medicamento - Indicaciones",
    ("medication", "medication_frequency"): "Medicamento - Frecuencias",
    ("medication", "medication_route"): "Medicamento - Vías",
    ("medication", "medication_prescription"): "Medicamento - Info prescripción",
    ("medication", "medication_link"): "Medicamento - Links",
    ("specialty", "specialty_general"): "Especialidad - General",
    ("specialty", "specialty_excipient"): "Especialidad - Excipientes",
}

_SECTION = re.compile(r"^[1-9]\d*(?:\.\d+)*$")
_SECTION_SPLIT = re.compile(r"\s*(?:/|\+)\s*")
_EMPTY = {"", "-", "–", "—"}


def _fold(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    ).casefold()


def _target_sections(literal: str | None) -> tuple[str, ...] | None:
    if literal is None or literal.strip() in _EMPTY:
        return None
    parts = tuple(part.strip() for part in _SECTION_SPLIT.split(literal.strip()))
    if not parts or any(not _SECTION.fullmatch(part) for part in parts):
        return None
    return tuple(dict.fromkeys(parts))


def compare_master_fields(
    fields: tuple[MasterField, ...],
    definitions: tuple[CatalogField, ...],
    documents: tuple[CimaDocument, ...],
) -> tuple[CimaFieldComparison, ...]:
    """Produce resultados textuales enlazados a una versión documental exacta."""
    results: list[CimaFieldComparison] = []
    for field in fields:
        entity = ENTITY_LABELS.get(field.entity_type)
        block = BLOCK_LABELS.get((field.entity_type, field.block_type))
        candidates = (
            [
                item
                for item in definitions
                if item.entity == entity and item.block == block and item.name == field.name
            ]
            if entity and block
            else []
        )

        if len(candidates) != 1:
            reason = (
                "La definición campo→apartado no existe para esta columna del maestro."
                if not candidates
                else "Hay varias definiciones posibles; no se elige una automáticamente."
            )
            results.extend(
                _result(field, None, document, "no_comparable", reason, ())
                for document in (documents or (None,))
            )
            continue

        definition = candidates[0]
        category = _fold(definition.from_ft)
        target_sections = _target_sections(definition.sections)
        if category == "no" or not category:
            status, reason = (
                "no_comparable",
                "El catálogo marca el campo como ajeno a la ficha técnica.",
            )
        elif target_sections is None:
            status, reason = (
                "no_comparable",
                "El catálogo no indica apartados CIMA válidos.",
            )
        elif field.value is None or field.value == "":
            status, reason = (
                "falta_registro",
                "Falta el valor de trabajo en el maestro.",
            )
        elif "parcial" in category or "interpretacion" in category:
            status, reason = (
                "requiere_criterio",
                "El campo es parcial o requiere criterio farmacéutico.",
            )
        elif "directo" not in category:
            status, reason = (
                "no_comparable",
                "La clasificación no permite comparación literal.",
            )
        else:
            status, reason = (
                "difiere",
                "El valor no aparece literalmente en los apartados candidatos.",
            )

        field_docs: tuple[CimaDocument | None, ...] = documents or (None,)
        for document in field_docs:
            locators: tuple[str, ...] = ()
            row_status, row_reason = status, reason
            if row_status in {
                "coincide",
                "difiere",
                "falta_registro",
                "falta_cima",
                "requiere_criterio",
            }:
                if document is None:
                    if row_status != "falta_registro":
                        row_status, row_reason = (
                            "falta_cima",
                            "No hay ficha técnica CIMA vinculada a este registro.",
                        )
                else:
                    available = {section.locator: section for section in document.sections}
                    locators = tuple(item for item in target_sections or () if item in available)
                    missing = tuple(item for item in target_sections or () if item not in available)
                    if not locators:
                        row_status, row_reason = (
                            "falta_cima",
                            "La versión no contiene los apartados declarados por el catálogo.",
                        )
                    elif row_status == "falta_registro":
                        row_reason = "El apartado existe en CIMA; falta valor en el maestro."
                    elif row_status == "requiere_criterio":
                        row_reason = "Hay texto candidato; requiere criterio farmacéutico."
                    elif row_status == "difiere":
                        found = any(
                            field.value in available[item].literal_text for item in locators
                        )
                        if found:
                            row_status, row_reason = (
                                "coincide",
                                "El valor aparece literalmente en el apartado.",
                            )
                        elif missing:
                            row_status, row_reason = (
                                "falta_cima",
                                "Faltan apartados candidatos; no se declara diferencia.",
                            )
            results.append(_result(field, definition, document, row_status, row_reason, locators))
    return tuple(results)


def _result(
    field: MasterField,
    definition: CatalogField | None,
    document: CimaDocument | None,
    status: str,
    reason: str,
    locators: tuple[str, ...],
) -> CimaFieldComparison:
    return CimaFieldComparison(
        field_value_id=field.id,
        block_type=field.block_type,
        occurrence=field.ordinal,
        field_name=field.name,
        source_column_index=field.source_column_index,
        master_value=field.value,
        catalog_field_id=definition.id if definition else None,
        catalog_classification=definition.from_ft if definition else None,
        document_name=document.document_name if document else None,
        document_version_id=document.document_version_id if document else None,
        source_version=document.source_version if document else None,
        content_hash=document.content_hash if document else None,
        status=status,
        reason=reason,
        section_locators=locators,
    )
