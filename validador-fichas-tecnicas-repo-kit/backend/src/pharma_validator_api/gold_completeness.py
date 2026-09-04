"""Completitud y consistencia estructural del conjunto oro (DEV-407).

Responde a una única pregunta: **¿está el conjunto oro listo para evaluar?**
No juzga calidad clínica. No decide si un valor anotado es correcto, no compara
contra ninguna verdad externa y no resuelve desacuerdos: eso pertenece a los
dos farmacéuticos y a la sesión de conciliación.

Lo que sí verifica es lo que puede comprobarse sin criterio clínico:

- que estén las 20 fichas de la selección;
- que cada anotador cubra las unidades esperadas;
- que ninguna unidad quede en `pending`;
- que la evidencia exigida exista y reproduzca sus desplazamientos;
- que no haya desacuerdos sin conciliar.

Módulo puro: no abre archivos ni red.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from pharma_validator_api.gold_annotations import (
    GoldAnnotation,
    GoldAnnotationError,
    validate_annotation,
)

CHECK_VERSION = "gold-completeness-v1"


@dataclass(frozen=True)
class AnnotatorProgress:
    annotator_id: str
    annotated_units: int
    finished_units: int
    pending_units: int
    documents_touched: int


@dataclass
class GoldCompletenessReport:
    """Estado estructural del conjunto oro en un instante."""

    expected_documents: int = 0
    annotated_documents: int = 0
    expected_units: int = 0
    completed_units: int = 0
    pending_units: int = 0
    comparable_units: int = 0
    single_annotator_units: int = 0
    open_disagreements: int = 0
    annotators: tuple[AnnotatorProgress, ...] = ()
    structural_errors: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    documents_without_annotations: tuple[str, ...] = ()

    @property
    def progress(self) -> float:
        """Fracción de unidades esperadas ya terminadas por ambos anotadores."""
        if self.expected_units == 0:
            return 0.0
        return self.completed_units / self.expected_units

    @property
    def is_ready(self) -> bool:
        """El conjunto oro sólo está listo si nada queda abierto.

        Deliberadamente estricto: un conjunto oro parcial produciría métricas
        que parecen válidas y no lo son. Cualquier duda se resuelve como "no
        listo".
        """
        return (
            self.expected_units > 0
            and self.pending_units == 0
            and self.completed_units == self.expected_units
            and not self.structural_errors
            and not self.missing_evidence
            and not self.documents_without_annotations
            and self.open_disagreements == 0
            and self.single_annotator_units == 0
        )


def _expected_documents(selection: Mapping[str, object]) -> set[tuple[str, str]]:
    items = cast(list[dict[str, Any]], selection.get("items", []))
    return {
        (str(item["nregistro"]), str(item["document_version_hash"])) for item in items
    }


def check_gold_completeness(
    selection: Mapping[str, object],
    annotations: tuple[GoldAnnotation, ...],
    section_contents: Mapping[tuple[str, str], str],
    *,
    expected_units_per_document: int | None = None,
) -> GoldCompletenessReport:
    """Evalúa completitud estructural sin emitir ningún juicio clínico.

    `expected_units_per_document` permite fijar el alcance de campos acordado.
    Cuando no se aporta, el universo esperado son las unidades realmente
    anotadas: sirve para vigilar consistencia y doble cobertura, pero no puede
    detectar un campo que nadie anotó. La diferencia se refleja en el informe.
    """
    expected_docs = _expected_documents(selection)
    report = GoldCompletenessReport(expected_documents=len(expected_docs))
    if not expected_docs:
        return GoldCompletenessReport(
            structural_errors=("La selección oro está vacía.",)
        )

    structural: list[str] = []
    missing_evidence: list[str] = []

    seen: set[tuple[tuple[str, str, str, int, str], str]] = set()
    units: dict[tuple[str, str, str, int, str], list[GoldAnnotation]] = defaultdict(list)
    per_annotator: dict[str, list[GoldAnnotation]] = defaultdict(list)

    for annotation in annotations:
        document = (annotation.nregistro, annotation.document_version_hash)
        if document not in expected_docs:
            structural.append(
                f"{annotation.nregistro}: la anotación no pertenece a la selección oro."
            )
            continue
        try:
            validate_annotation(annotation, section_contents)
        except GoldAnnotationError as error:
            # Se acumula en lugar de abortar: un informe de completitud debe
            # enumerar todo lo que falta, no detenerse en el primer defecto.
            structural.append(f"{_unit_label(annotation)}: {error}")
            continue

        identity = (annotation.unit_key, annotation.annotator_id)
        if identity in seen:
            structural.append(
                f"{_unit_label(annotation)}: anotación duplicada de "
                f"{annotation.annotator_id}."
            )
            continue
        seen.add(identity)
        units[annotation.unit_key].append(annotation)
        per_annotator[annotation.annotator_id].append(annotation)

        if annotation.state == "valued" and annotation.evidence is None:
            missing_evidence.append(_unit_label(annotation))

    annotated_docs = {
        (item.nregistro, item.document_version_hash)
        for values in units.values()
        for item in values
    }
    without = sorted(
        nregistro for nregistro, _ in expected_docs - annotated_docs
    )

    pending = sum(
        1 for values in units.values() for item in values if item.state == "pending"
    )
    comparable = sum(1 for values in units.values() if len(values) >= 2)
    single = sum(1 for values in units.values() if len(values) == 1)
    disagreements = sum(
        1
        for values in units.values()
        if len(values) == 2
        and (values[0].state, values[0].literal_value)
        != (values[1].state, values[1].literal_value)
    )
    completed = sum(
        1
        for values in units.values()
        if len(values) >= 2 and all(item.state != "pending" for item in values)
    )

    if expected_units_per_document is not None:
        expected_units = expected_units_per_document * len(expected_docs)
        if len(units) != expected_units:
            structural.append(
                f"Se esperaban {expected_units} unidades y hay {len(units)}."
            )
    else:
        expected_units = len(units)

    progress = tuple(
        AnnotatorProgress(
            annotator_id=annotator,
            annotated_units=len(values),
            finished_units=sum(1 for item in values if item.state != "pending"),
            pending_units=sum(1 for item in values if item.state == "pending"),
            documents_touched=len({item.nregistro for item in values}),
        )
        for annotator, values in sorted(per_annotator.items())
    )
    if len(progress) not in (0, 2):
        # El contrato exige exactamente dos anotadores independientes. Con uno
        # no hay doble anotación; con tres, la comparación por pares deja de
        # estar definida.
        structural.append(
            f"El contrato exige exactamente dos anotadores; hay {len(progress)}."
        )

    report = GoldCompletenessReport(
        expected_documents=len(expected_docs),
        annotated_documents=len(annotated_docs),
        expected_units=expected_units,
        completed_units=completed,
        pending_units=pending,
        comparable_units=comparable,
        single_annotator_units=single,
        open_disagreements=disagreements,
        annotators=progress,
        structural_errors=tuple(structural),
        missing_evidence=tuple(missing_evidence),
        documents_without_annotations=tuple(without),
    )
    return report


def _unit_label(annotation: GoldAnnotation) -> str:
    return (
        f"{annotation.nregistro}/{annotation.block_type}"
        f"[{annotation.occurrence}]/{annotation.field_name}"
    )


def render_report(report: GoldCompletenessReport) -> str:
    """Informe legible para operación diaria."""
    lines = [
        f"# Completitud del conjunto oro ({CHECK_VERSION})",
        "",
        f"- Fichas esperadas: {report.expected_documents}",
        f"- Fichas con anotaciones: {report.annotated_documents}",
        f"- Unidades esperadas: {report.expected_units}",
        f"- Unidades completadas por ambos: {report.completed_units}",
        f"- Unidades en pending: {report.pending_units}",
        f"- Unidades con un solo anotador: {report.single_annotator_units}",
        f"- Desacuerdos abiertos: {report.open_disagreements}",
        f"- Progreso: {report.progress:.2%}",
        "",
        "## Anotadores",
        "",
    ]
    if report.annotators:
        lines.extend(
            f"- `{item.annotator_id}`: {item.finished_units} terminadas, "
            f"{item.pending_units} pendientes, {item.documents_touched} fichas"
            for item in report.annotators
        )
    else:
        lines.append("- Ninguno: no existe anotación real todavía.")

    for title, values in (
        ("Fichas sin anotación", report.documents_without_annotations),
        ("Evidencia ausente", report.missing_evidence),
        ("Errores estructurales", report.structural_errors),
    ):
        lines.extend(["", f"## {title}", ""])
        if values:
            lines.extend(f"- {value}" for value in values)
        else:
            lines.append("- Ninguno.")

    lines.extend(
        [
            "",
            "## Veredicto",
            "",
            (
                "GOLD LISTO para evaluación."
                if report.is_ready
                else "GOLD NO LISTO para evaluación."
            ),
            "",
        ]
    )
    return "\n".join(lines)
