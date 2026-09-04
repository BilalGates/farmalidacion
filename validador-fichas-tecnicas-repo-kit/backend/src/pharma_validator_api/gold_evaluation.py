"""Evaluación del extractor contra el conjunto oro (DEV-408).

Calcula las métricas que exige la puerta de salida de Fase 4 comparando lo que
el extractor propuso con lo que dos farmacéuticos anotaron. No decide política
de pre-relleno (D-015) ni elige modelo (D-014): produce la evidencia con la que
esas decisiones se tomarán.

Reglas que gobiernan el cálculo y que no son negociables:

- Una unidad con desacuerdo humano sin conciliar **no puntúa**. Medir contra una
  verdad en disputa produce un número que parece una métrica y no lo es.
- La comparación de valores es exacta sobre el literal, con el criterio de
  DEV-307: espacios y mayúsculas diferencian. La coincidencia normalizada se
  informa **aparte**, nunca sustituyendo a la exacta.
- Una propuesta cuya evidencia no fue admitida por el verificador literal cuenta
  como evidencia inválida, con independencia de si el valor acertó. Un valor
  correcto por azar con cita inventada es un fallo, no un acierto.

Módulo puro: no abre archivos ni red.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pharma_validator_api.gold_annotations import GoldAnnotation

EVALUATION_VERSION = "gold-evaluation-v1"

#: Clasificación exigida por el plan. Cada unidad puntuada cae en exactamente
#: una categoría, de modo que los recuentos siempre suman.
Outcome = Literal[
    "correcta",
    "parcial",
    "incorrecta",
    "no_localizada",
    "evidencia_invalida",
    "no_parseable",
    "alucinacion",
]

UnitKey = tuple[str, str, str, int, str]


@dataclass(frozen=True)
class ExtractorProposal:
    """Lo que el extractor propuso para una unidad, ya verificado.

    `evidence_admitted` lo dicta el verificador literal de DEV-405; este módulo
    no revalida evidencia, la consume.
    """

    unit_key: UnitKey
    field_name: str
    state: str
    proposed_value: str | None
    evidence_admitted: bool
    evidence_text: str | None = None
    parse_failed: bool = False
    latency_seconds: float | None = None


@dataclass(frozen=True)
class GoldTruth:
    """Verdad de referencia consolidada para una unidad."""

    unit_key: UnitKey
    field_name: str
    state: str
    literal_value: str | None


@dataclass(frozen=True)
class FieldMetrics:
    """Métricas de un campo. `support` es cuántas unidades puntuaron."""

    field_name: str
    support: int
    correct: int
    partial: int
    incorrect: int
    not_found: int
    invalid_evidence: int
    unparseable: int
    hallucinations: int
    normalized_matches: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.support if self.support else 0.0

    @property
    def coverage(self) -> float:
        """Fracción de unidades en las que el extractor propuso algo."""
        attempted = self.support - self.not_found
        return attempted / self.support if self.support else 0.0

    @property
    def precision(self) -> float:
        """De lo propuesto, qué fracción acertó."""
        proposed = self.correct + self.partial + self.incorrect + self.hallucinations
        return self.correct / proposed if proposed else 0.0

    @property
    def recall(self) -> float:
        return self.correct / self.support if self.support else 0.0

    @property
    def f1(self) -> float:
        precision, recall = self.precision, self.recall
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    @property
    def valid_evidence_rate(self) -> float:
        proposed = self.support - self.not_found
        if not proposed:
            return 0.0
        return (proposed - self.invalid_evidence) / proposed

    @property
    def requires_human_review(self) -> float:
        """Fracción que una persona tendría que corregir o completar."""
        if not self.support:
            return 0.0
        return (self.support - self.correct) / self.support


@dataclass(frozen=True)
class EvaluationReport:
    model: str
    scored_units: int
    excluded_disagreements: int
    excluded_pending: int
    per_field: tuple[FieldMetrics, ...]
    outcomes: Mapping[Outcome, int]
    latency_seconds: tuple[float, ...] = ()

    @property
    def overall(self) -> FieldMetrics:
        """Agregado sobre todos los campos, con el mismo criterio por unidad."""
        return FieldMetrics(
            field_name="__global__",
            support=sum(item.support for item in self.per_field),
            correct=sum(item.correct for item in self.per_field),
            partial=sum(item.partial for item in self.per_field),
            incorrect=sum(item.incorrect for item in self.per_field),
            not_found=sum(item.not_found for item in self.per_field),
            invalid_evidence=sum(item.invalid_evidence for item in self.per_field),
            unparseable=sum(item.unparseable for item in self.per_field),
            hallucinations=sum(item.hallucinations for item in self.per_field),
            normalized_matches=sum(item.normalized_matches for item in self.per_field),
        )

    @property
    def mean_latency(self) -> float | None:
        if not self.latency_seconds:
            return None
        return sum(self.latency_seconds) / len(self.latency_seconds)

    @property
    def throughput_units_per_second(self) -> float | None:
        total = sum(self.latency_seconds)
        if not total:
            return None
        return len(self.latency_seconds) / total


def normalize_for_comparison(value: str) -> str:
    """Normalización explícita y sólo para la métrica secundaria.

    Nunca se usa para admitir un valor: colapsa espacios, unifica mayúsculas y
    aplica NFKC. Sirve para saber cuánto del error es puramente de formato.
    """
    folded = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(folded.split())


def consolidate_gold(
    annotations: tuple[GoldAnnotation, ...],
) -> tuple[dict[UnitKey, GoldTruth], set[UnitKey], set[UnitKey]]:
    """Reduce la doble anotación a una verdad por unidad.

    Devuelve además las unidades excluidas: las que están en desacuerdo y las
    que siguen `pending`. Excluir es deliberado y se informa; silenciarlas
    inflaría artificialmente el denominador o la exactitud.
    """
    grouped: dict[UnitKey, list[GoldAnnotation]] = defaultdict(list)
    for annotation in annotations:
        grouped[annotation.unit_key].append(annotation)

    truth: dict[UnitKey, GoldTruth] = {}
    disagreements: set[UnitKey] = set()
    pending: set[UnitKey] = set()

    for key, items in grouped.items():
        if any(item.state == "pending" for item in items):
            pending.add(key)
            continue
        if len(items) < 2:
            # Una sola anotación no es doble anotación: no es verdad de
            # referencia y no puede puntuar.
            pending.add(key)
            continue
        first, second = items[0], items[1]
        if (first.state, first.literal_value) != (second.state, second.literal_value):
            disagreements.add(key)
            continue
        truth[key] = GoldTruth(
            unit_key=key,
            field_name=first.field_name,
            state=first.state,
            literal_value=first.literal_value,
        )
    return truth, disagreements, pending


def classify(proposal: ExtractorProposal | None, truth: GoldTruth) -> Outcome:
    """Clasifica una unidad en exactamente una categoría."""
    if proposal is None:
        return "no_localizada"
    if proposal.parse_failed:
        return "no_parseable"

    proposed_something = proposal.proposed_value is not None and proposal.proposed_value != ""

    # La evidencia manda: una cita no admitida invalida la propuesta aunque el
    # valor coincida. Sin cita válida no hay trazabilidad, y sin trazabilidad
    # la propuesta no puede persistirse.
    if proposed_something and not proposal.evidence_admitted:
        return "evidencia_invalida"

    if truth.state != "valued":
        # El oro dice que aquí no hay valor. Proponer uno es una alucinación,
        # no un error de transcripción.
        if proposed_something:
            return "alucinacion"
        return "correcta" if proposal.state == truth.state else "incorrecta"

    if not proposed_something:
        return "no_localizada"
    if proposal.proposed_value == truth.literal_value:
        return "correcta"
    if truth.literal_value is not None and normalize_for_comparison(
        proposal.proposed_value or ""
    ) == normalize_for_comparison(truth.literal_value):
        # Coincide salvo formato. Es un acierto degradado, no un acierto: el
        # contrato exige literalidad.
        return "parcial"
    return "incorrecta"


def evaluate(
    proposals: tuple[ExtractorProposal, ...],
    annotations: tuple[GoldAnnotation, ...],
    *,
    model: str,
) -> EvaluationReport:
    """Compara propuestas contra el conjunto oro y calcula las métricas."""
    if not model.strip():
        raise ValueError("Una evaluación sin modelo atribuido no es interpretable.")

    truth, disagreements, pending = consolidate_gold(annotations)
    by_unit = {item.unit_key: item for item in proposals}

    counters: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    outcomes: dict[Outcome, int] = defaultdict(int)
    latencies: list[float] = []

    for key, expected in truth.items():
        proposal = by_unit.get(key)
        outcome = classify(proposal, expected)
        outcomes[outcome] += 1
        bucket = counters[expected.field_name]
        bucket["support"] += 1
        bucket[outcome] += 1
        if proposal is not None:
            if proposal.latency_seconds is not None:
                latencies.append(proposal.latency_seconds)
            if (
                outcome != "correcta"
                and expected.literal_value is not None
                and proposal.proposed_value is not None
                and normalize_for_comparison(proposal.proposed_value)
                == normalize_for_comparison(expected.literal_value)
            ):
                bucket["normalized"] += 1

    per_field = tuple(
        FieldMetrics(
            field_name=name,
            support=bucket["support"],
            correct=bucket["correcta"],
            partial=bucket["parcial"],
            incorrect=bucket["incorrecta"],
            not_found=bucket["no_localizada"],
            invalid_evidence=bucket["evidencia_invalida"],
            unparseable=bucket["no_parseable"],
            hallucinations=bucket["alucinacion"],
            normalized_matches=bucket["normalized"],
        )
        for name, bucket in sorted(counters.items())
    )

    return EvaluationReport(
        model=model,
        scored_units=len(truth),
        excluded_disagreements=len(disagreements),
        excluded_pending=len(pending),
        per_field=per_field,
        outcomes=dict(outcomes),
        latency_seconds=tuple(latencies),
    )


def render_evaluation(report: EvaluationReport) -> str:
    """Informe legible, con las exclusiones siempre visibles."""
    overall = report.overall
    lines = [
        f"# Evaluación del extractor ({EVALUATION_VERSION})",
        "",
        f"- Modelo: `{report.model}`",
        f"- Unidades puntuadas: {report.scored_units}",
        f"- Excluidas por desacuerdo humano: {report.excluded_disagreements}",
        f"- Excluidas por pending / anotación única: {report.excluded_pending}",
        "",
        "## Global",
        "",
        f"- Exactitud: {overall.accuracy:.4f}",
        f"- Precisión: {overall.precision:.4f}",
        f"- Recall: {overall.recall:.4f}",
        f"- F1: {overall.f1:.4f}",
        f"- Cobertura: {overall.coverage:.4f}",
        f"- Evidencia válida: {overall.valid_evidence_rate:.4f}",
        f"- Requiere revisión humana: {overall.requires_human_review:.4f}",
        f"- Alucinaciones: {overall.hallucinations}",
        "",
        "## Desglose por resultado",
        "",
        *(f"- `{key}`: {report.outcomes[key]}" for key in sorted(report.outcomes)),
        "",
        "## Por campo",
        "",
        "| Campo | N | Exactitud | Precisión | Recall | F1 | Evidencia válida | Alucinaciones |",
        "|---|---|---|---|---|---|---|---|",
        *(
            f"| {item.field_name} | {item.support} | {item.accuracy:.3f} | "
            f"{item.precision:.3f} | {item.recall:.3f} | {item.f1:.3f} | "
            f"{item.valid_evidence_rate:.3f} | {item.hallucinations} |"
            for item in report.per_field
        ),
        "",
    ]
    if report.mean_latency is not None:
        lines.extend(
            [
                "## Rendimiento",
                "",
                f"- Latencia media: {report.mean_latency:.3f} s",
                f"- Throughput: {report.throughput_units_per_second:.3f} unidades/s",
                "",
            ]
        )
    return "\n".join(lines)
