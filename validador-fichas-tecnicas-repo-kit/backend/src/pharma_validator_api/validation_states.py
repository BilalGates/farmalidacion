"""Estados internos de validación conformes con ADR-0004 (DEV-506 preparatorio)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ValidationState = Literal[
    "pendiente",
    "confirmado",
    "corregido",
    "no_consta",
    "no_aplica",
    "descartado",
    "revision_pendiente",
]
ReviewerRole = Literal["farmaceutico", "otro"]
RESOLVED_STATES: frozenset[str] = frozenset({"confirmado", "corregido", "no_consta", "no_aplica"})


class ValidationStateError(RuntimeError):
    """Decisión o transición interna no permitida."""


@dataclass(frozen=True)
class ValidationDecision:
    field_name: str
    state: ValidationState
    final_value: str | None
    reviewer_id: str
    reviewer_role: ReviewerRole
    applicable_sources: tuple[str, ...] = ()
    required_sources: tuple[str, ...] = ()
    reviewed_sources: tuple[str, ...] = ()
    field_required: bool = False
    is_second_validation: bool = False
    comment: str | None = None
    seconds_spent: int | None = None

    def __post_init__(self) -> None:
        if not self.field_name:
            raise ValueError("La decisión requiere campo.")
        if not self.reviewer_id:
            raise ValueError("La decisión requiere revisor identificado.")
        if self.seconds_spent is not None and self.seconds_spent < 0:
            raise ValueError("El tiempo empleado no puede ser negativo.")
        _require_unique("fuentes aplicables", self.applicable_sources)
        _require_unique("fuentes obligatorias", self.required_sources)
        _require_unique("fuentes revisadas", self.reviewed_sources)
        applicable = set(self.applicable_sources)
        if not set(self.required_sources) <= applicable:
            raise ValueError("Toda fuente obligatoria debe ser aplicable al campo.")
        if not set(self.reviewed_sources) <= applicable:
            raise ValueError("No puede revisarse una fuente no aplicable al campo.")

    @property
    def is_resolved(self) -> bool:
        return self.state in RESOLVED_STATES


def _require_unique(label: str, values: tuple[str, ...]) -> None:
    if any(not value for value in values) or len(values) != len(set(values)):
        raise ValueError(f"{label.capitalize()} contiene valores vacíos o duplicados.")


def is_resolved(state: ValidationState) -> bool:
    """Indica resolución interna; no define serialización del proveedor."""
    return state in RESOLVED_STATES


def validate_decision(decision: ValidationDecision) -> None:
    if decision.state in ("confirmado", "corregido"):
        if decision.final_value is None:
            raise ValidationStateError(f"El estado {decision.state} exige un valor final.")
    elif decision.final_value is not None:
        raise ValidationStateError(f"El estado {decision.state} no admite valor final.")

    comment = (decision.comment or "").strip()
    if decision.state == "pendiente" and decision.comment is not None:
        raise ValidationStateError("El estado pendiente no registra comentario.")

    if decision.state in ("no_consta", "no_aplica") and decision.reviewer_role != "farmaceutico":
        raise ValidationStateError(
            f"El estado {decision.state} solo puede decidirlo un farmacéutico."
        )

    if decision.state == "no_consta":
        missing = sorted(set(decision.required_sources) - set(decision.reviewed_sources))
        if missing:
            raise ValidationStateError(
                "no_consta exige revisar todas las fuentes obligatorias: " + ", ".join(missing)
            )
        if decision.field_required and not comment:
            raise ValidationStateError("no_consta en un campo obligatorio exige comentario.")

    if decision.state == "no_aplica" and not comment:
        raise ValidationStateError("no_aplica exige comentario del farmacéutico.")


def assert_transition_allowed(
    current: ValidationState, target: ValidationState, comment: str | None = None
) -> None:
    if current == target:
        return
    if target == "pendiente":
        raise ValidationStateError(
            "Una decisión resuelta no vuelve a pendiente; se registra otra decisión."
        )
    if current == "revision_pendiente" and target != "revision_pendiente":
        if not (comment or "").strip():
            raise ValidationStateError("Salir de revision_pendiente exige comentario del revisor.")
        return
    if (
        current in ("no_consta", "no_aplica")
        and target in ("confirmado", "corregido")
        and not (comment or "").strip()
    ):
        raise ValidationStateError(f"Revertir {current} exige comentario del revisor.")


def mark_pending_review(state: ValidationState) -> ValidationState:
    if state == "pendiente":
        return "pendiente"
    return "revision_pendiente"


@dataclass(frozen=True)
class ReviewCompleteness:
    resolved: tuple[str, ...]
    withheld: tuple[tuple[str, ValidationState], ...]

    @property
    def is_record_complete(self) -> bool:
        return not self.withheld


def evaluate_review_completeness(
    decisions: tuple[ValidationDecision, ...],
    unresolved_double_validation: tuple[str, ...] = (),
) -> ReviewCompleteness:
    """Evalúa cierre interno; no traduce estados al contrato del proveedor."""
    resolved: list[str] = []
    withheld: list[tuple[str, ValidationState]] = []
    blocked = set(unresolved_double_validation)
    for decision in sorted(decisions, key=lambda item: item.field_name):
        validate_decision(decision)
        if decision.field_name in blocked or not decision.is_resolved:
            withheld.append((decision.field_name, decision.state))
        else:
            resolved.append(decision.field_name)
    return ReviewCompleteness(tuple(resolved), tuple(withheld))
