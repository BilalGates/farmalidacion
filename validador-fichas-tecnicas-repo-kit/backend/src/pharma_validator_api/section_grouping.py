"""Agrupación de campos por apartado de la ficha técnica (DEV-404).

La especificación 8 exige agrupar las llamadas: reunir todos los campos que
dependen de un apartado y resolverlos en una sola petición. Con ~150 campos
extraíbles y ~12 apartados relevantes, eso reduce de unas 150 llamadas por
documento a unas 15, que es la diferencia entre un proceso de horas y uno de
días.

El módulo es puro. No llama al modelo, no persiste y no reinterpreta el
catálogo: lee `ft_section_literal` tal como se importó en DEV-302 y solo
reconoce las formas que el catálogo realmente contiene.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pharma_validator_api.evidence_verification import DocumentSection, PrefillPolicy
from pharma_validator_api.extractor import FieldRequest, SectionRequest

# Un apartado es un número con subniveles separados por puntos: 4, 4.2, 6.6.
# El nivel superior nunca es 0: la hoja de resumen del catálogo contiene ratios
# como 0.375 y aceptarlos como apartado convertiría una celda mal leída en una
# petición contra una sección inexistente.
_SECTION = re.compile(r"^[1-9]\d*(?:\.\d+)*$")
# El catálogo separa apartados múltiples con barra: "4.2 / 6.6".
_SEPARATOR = "/"
# Marcas literales de ausencia observadas en el catálogo.
_ABSENT = {"", "-", "–", "—"}


@dataclass(frozen=True)
class CatalogField:
    """Definición de campo tal como la importó DEV-302, sin reinterpretar."""

    field_name: str
    description: str
    data_type: str
    policy: PrefillPolicy
    ft_section_literal: str | None

    def __post_init__(self) -> None:
        if not self.field_name:
            raise ValueError("La definición requiere nombre de campo.")


@dataclass(frozen=True)
class GroupingDiagnostic:
    """Campo que no puede agruparse, con el literal que lo impide."""

    field_name: str
    reason: str
    literal: str | None


@dataclass(frozen=True)
class GroupingResult:
    requests: tuple[SectionRequest, ...]
    diagnostics: tuple[GroupingDiagnostic, ...]

    @property
    def call_count(self) -> int:
        return len(self.requests)


def parse_sections(literal: str | None) -> tuple[str, ...]:
    """Extrae los apartados citados por un literal del catálogo.

    Devuelve una tupla vacía cuando el literal declara ausencia. Un literal que
    no encaja en las formas conocidas produce un error, nunca una suposición:
    adivinar el apartado enviaría al modelo un texto que el catálogo no pidió.
    """
    if literal is None or literal.strip() in _ABSENT:
        return ()
    parts = [part.strip() for part in literal.split(_SEPARATOR)]
    if any(not _SECTION.match(part) for part in parts):
        raise ValueError(f"Apartado no reconocido en el literal {literal!r}.")
    # El orden del literal no es significativo: "6.6 / 4.2" y "4.2 / 6.6" citan
    # los mismos apartados. Se ordena para que la agrupación sea reproducible.
    return tuple(sorted(set(parts), key=section_sort_key))


def section_sort_key(section: str) -> tuple[int, ...]:
    return tuple(int(part) for part in section.split("."))


def group_fields_by_section(
    fields: tuple[CatalogField, ...],
    sections: tuple[DocumentSection, ...],
    document_version_id: str,
    medication_name: str,
) -> GroupingResult:
    """Agrupa los campos extraíbles en una petición por apartado.

    Un campo citado en varios apartados genera una entrada en cada uno: la
    evidencia puede estar en cualquiera de ellos y descartar apartados
    silenciosamente perdería la cita.
    """
    available = {item.section: item for item in sections}
    if len(available) != len(sections):
        raise ValueError("Las secciones deben ser únicas.")

    grouped: dict[str, list[FieldRequest]] = {}
    diagnostics: list[GroupingDiagnostic] = []

    for field in sorted(fields, key=lambda item: item.field_name):
        if field.policy == "oculto":
            # 6: `no_disponible` no aparece en esta pantalla y no se pide.
            continue
        try:
            targets = parse_sections(field.ft_section_literal)
        except ValueError as error:
            diagnostics.append(
                GroupingDiagnostic(field.field_name, str(error), field.ft_section_literal)
            )
            continue
        if not targets:
            diagnostics.append(
                GroupingDiagnostic(
                    field.field_name,
                    "El catálogo no declara apartado de ficha técnica.",
                    field.ft_section_literal,
                )
            )
            continue
        for section in targets:
            if section not in available:
                diagnostics.append(
                    GroupingDiagnostic(
                        field.field_name,
                        f"El apartado {section} no existe en esta versión documental.",
                        field.ft_section_literal,
                    )
                )
                continue
            bucket = grouped.setdefault(section, [])
            # El catálogo conserva identidades (bloque, campo) repetidas: DEV-302
            # documentó cinco pares y prohíbe fusionarlos. Una petición no puede
            # llevar el mismo nombre dos veces, porque la respuesta del modelo no
            # sería atribuible a una de las dos definiciones. Se informa la
            # repetición y se pide una sola vez; no se deduplica el catálogo.
            if any(item.field_name == field.field_name for item in bucket):
                diagnostics.append(
                    GroupingDiagnostic(
                        field.field_name,
                        f"El campo se repite en el apartado {section}; "
                        "se solicita una vez y la repetición queda sin resolver.",
                        field.ft_section_literal,
                    )
                )
                continue
            bucket.append(
                FieldRequest(
                    field.field_name, field.description, field.data_type, field.policy
                )
            )

    requests = tuple(
        SectionRequest(
            document_version_id,
            medication_name,
            available[section],
            tuple(grouped[section]),
        )
        for section in sorted(grouped, key=section_sort_key)
    )
    return GroupingResult(requests, tuple(diagnostics))
