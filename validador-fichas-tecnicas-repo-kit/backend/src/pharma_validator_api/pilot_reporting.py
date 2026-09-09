"""Informe reproducible del conjunto de medida (DEV-511).

Módulo puro: agrega observaciones ya verificadas, pero nunca fabrica ni deduce
mediciones. Un informe incompleto se devuelve como tal y no como resultado.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Literal

WorkflowMode = Literal["manual", "asistida"]
REPORT_STATES = ("confirmado", "corregido", "no_consta")


class PilotReportingError(ValueError):
    pass


@dataclass(frozen=True)
class PilotObservation:
    record_id: str
    entity_type: str
    mode: WorkflowMode
    minutes: float
    decision_states: tuple[str, ...]
    proposed_count: int = 0
    corrected_proposal_count: int = 0
    double_review_count: int = 0
    disagreement_count: int = 0

    def __post_init__(self) -> None:
        if not self.record_id or not self.entity_type:
            raise PilotReportingError("Cada observación exige ficha y entidad.")
        if self.mode not in ("manual", "asistida"):
            raise PilotReportingError(f"Modo de trabajo desconocido: {self.mode}.")
        if self.minutes < 0:
            raise PilotReportingError("El tiempo no puede ser negativo.")
        counts = (
            self.proposed_count,
            self.corrected_proposal_count,
            self.double_review_count,
            self.disagreement_count,
        )
        if any(value < 0 for value in counts):
            raise PilotReportingError("Los recuentos no pueden ser negativos.")
        if self.corrected_proposal_count > self.proposed_count:
            raise PilotReportingError("No puede haber más correcciones que propuestas.")
        if self.disagreement_count > self.double_review_count:
            raise PilotReportingError("No puede haber más discrepancias que dobles revisiones.")
        unknown = set(self.decision_states) - set(REPORT_STATES)
        if unknown:
            raise PilotReportingError(f"Estados no reportables: {sorted(unknown)}.")


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def build_pilot_report(
    observations: tuple[PilotObservation, ...], *, expected_records: int = 50
) -> dict[str, object]:
    if expected_records <= 0:
        raise PilotReportingError("El tamaño esperado debe ser positivo.")
    seen_pairs: set[tuple[str, str]] = set()
    modes_by_record: dict[str, set[str]] = defaultdict(set)
    minutes: dict[tuple[str, str], list[float]] = defaultdict(list)
    states: Counter[str] = Counter()
    proposed = corrected = double = disagreements = 0
    for item in observations:
        pair = (item.record_id, item.mode)
        if pair in seen_pairs:
            raise PilotReportingError(
                f"Observación duplicada para {item.record_id} en modo {item.mode}."
            )
        seen_pairs.add(pair)
        modes_by_record[item.record_id].add(item.mode)
        minutes[(item.entity_type, item.mode)].append(item.minutes)
        states.update(item.decision_states)
        proposed += item.proposed_count
        corrected += item.corrected_proposal_count
        double += item.double_review_count
        disagreements += item.disagreement_count

    incomplete = sorted(
        record_id
        for record_id, modes in modes_by_record.items()
        if modes != {"manual", "asistida"}
    )
    record_count = len(modes_by_record)
    ready = record_count == expected_records and not incomplete
    return {
        "schema_version": "pilot-measurement-report-v1",
        "ready": ready,
        "expected_records": expected_records,
        "observed_records": record_count,
        "incomplete_records": incomplete,
        "minutes_per_record": [
            {
                "entity_type": entity,
                "mode": mode,
                "record_count": len(values),
                "mean_minutes": sum(values) / len(values),
            }
            for (entity, mode), values in sorted(minutes.items())
        ],
        "decision_states": {state: states[state] for state in REPORT_STATES},
        "proposal_correction": {
            "proposed": proposed,
            "corrected": corrected,
            "rate": _rate(corrected, proposed),
        },
        "double_review": {
            "compared": double,
            "disagreements": disagreements,
            "rate": _rate(disagreements, double),
        },
    }
