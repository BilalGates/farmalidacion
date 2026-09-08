"""Doble validacion: comparacion y conciliacion entre dos revisores (DEV-510).

La especificacion exige que ciertos campos los validen dos personas de forma
**independiente**. Este modulo compara sus decisiones y clasifica el resultado;
no las concilia por su cuenta.

Regla que gobierna todo lo demas: ante una discrepancia **no se elige ganador
automaticamente**. Elegir por antiguedad, por rol o por orden de llegada seria
inventar criterio clinico. La discrepancia se declara y espera a una persona.

Modulo puro: sin base de datos, sin reloj y sin red.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pharma_validator_api.validation_states import RESOLVED_STATES, ValidationState

AgreementKind = Literal[
    "acuerdo",
    "discrepancia_estado",
    "discrepancia_valor",
    "pendiente_segunda_revision",
    "pendiente_primera_revision",
]

#: Una discrepancia solo puede cerrarla una persona, con estas salidas.
ResolutionChoice = Literal["revisor_a", "revisor_b", "valor_nuevo"]


class DoubleReviewError(RuntimeError):
    """Comparacion o conciliacion mal planteada."""


@dataclass(frozen=True)
class ReviewerDecision:
    """Decision de un revisor sobre un campo concreto."""

    reviewer_id: str
    state: ValidationState
    final_value: str | None = None

    def __post_init__(self) -> None:
        if not self.reviewer_id:
            raise ValueError("Una decision requiere revisor identificado.")

    @property
    def is_resolved(self) -> bool:
        return self.state in RESOLVED_STATES


@dataclass(frozen=True)
class FieldComparison:
    field_name: str
    kind: AgreementKind
    decision_a: ReviewerDecision | None
    decision_b: ReviewerDecision | None

    @property
    def is_disagreement(self) -> bool:
        return self.kind in ("discrepancia_estado", "discrepancia_valor")

    @property
    def is_agreement(self) -> bool:
        return self.kind == "acuerdo"


def compare_field(
    field_name: str,
    decision_a: ReviewerDecision | None,
    decision_b: ReviewerDecision | None,
) -> FieldComparison:
    """Compara las decisiones de dos revisores sobre un campo.

    Un campo sin las dos decisiones no es acuerdo ni discrepancia: esta
    incompleto, y confundir eso con acuerdo daria por validado lo que solo ha
    visto una persona.
    """
    if not field_name:
        raise ValueError("La comparacion requiere campo.")
    if (
        decision_a is not None
        and decision_b is not None
        and decision_a.reviewer_id == decision_b.reviewer_id
    ):
        raise DoubleReviewError(
            "La doble validacion exige dos revisores distintos; "
            f"{decision_a.reviewer_id} no puede validarse a si mismo."
        )

    if decision_a is None and decision_b is None:
        kind: AgreementKind = "pendiente_primera_revision"
    elif decision_a is None or decision_b is None:
        kind = "pendiente_segunda_revision"
    elif decision_a.state != decision_b.state:
        kind = "discrepancia_estado"
    elif decision_a.final_value != decision_b.final_value:
        # Mismo estado y distinto valor sigue siendo desacuerdo: dos personas
        # que confirman cosas distintas no han confirmado lo mismo.
        kind = "discrepancia_valor"
    else:
        kind = "acuerdo"
    return FieldComparison(field_name, kind, decision_a, decision_b)


@dataclass(frozen=True)
class DoubleReviewSummary:
    comparisons: tuple[FieldComparison, ...]

    @property
    def agreement_count(self) -> int:
        return sum(1 for c in self.comparisons if c.is_agreement)

    @property
    def disagreements(self) -> tuple[FieldComparison, ...]:
        return tuple(c for c in self.comparisons if c.is_disagreement)

    @property
    def pending(self) -> tuple[FieldComparison, ...]:
        return tuple(
            c
            for c in self.comparisons
            if c.kind in ("pendiente_primera_revision", "pendiente_segunda_revision")
        )

    @property
    def is_complete(self) -> bool:
        """Completa significa que ambas revisiones existen para cada campo."""
        return not self.pending

    @property
    def is_reconciled(self) -> bool:
        """Conciliada significa completa y sin discrepancias abiertas."""
        return self.is_complete and not self.disagreements

    def agreement_rate(self) -> float | None:
        """Sobre campos con doble decision. Sin ellos no hay tasa que dar."""
        comparable = self.agreement_count + len(self.disagreements)
        if not comparable:
            return None
        return self.agreement_count / comparable


def compare_reviews(
    decisions_a: dict[str, ReviewerDecision],
    decisions_b: dict[str, ReviewerDecision],
) -> DoubleReviewSummary:
    """Compara dos revisiones completas campo a campo."""
    names = sorted(set(decisions_a) | set(decisions_b))
    return DoubleReviewSummary(
        tuple(compare_field(n, decisions_a.get(n), decisions_b.get(n)) for n in names)
    )


@dataclass(frozen=True)
class Reconciliation:
    """Cierre humano de una discrepancia. Exige justificacion siempre."""

    field_name: str
    choice: ResolutionChoice
    resolved_by: str
    comment: str
    final_value: str | None = None

    def __post_init__(self) -> None:
        if not self.resolved_by:
            raise ValueError("Conciliar exige persona identificada.")
        if not (self.comment or "").strip():
            raise DoubleReviewError(
                "Conciliar una discrepancia exige justificacion: sin ella no queda "
                "constancia de por que se descarto la otra lectura."
            )
        if self.choice == "valor_nuevo" and self.final_value is None:
            raise DoubleReviewError("Elegir un valor nuevo exige indicarlo.")


def resolve(comparison: FieldComparison, reconciliation: Reconciliation) -> ReviewerDecision:
    """Aplica una conciliacion humana a una discrepancia.

    No se concilia lo que no discrepa: hacerlo permitiria reescribir un acuerdo
    sin dejar constancia de que hubo dos lecturas iguales.
    """
    if not comparison.is_disagreement:
        raise DoubleReviewError(
            f"El campo {comparison.field_name} no presenta discrepancia que conciliar."
        )
    if reconciliation.field_name != comparison.field_name:
        raise DoubleReviewError("La conciliacion no corresponde al campo comparado.")

    if reconciliation.choice == "revisor_a":
        chosen = comparison.decision_a
    elif reconciliation.choice == "revisor_b":
        chosen = comparison.decision_b
    else:
        chosen = None

    if reconciliation.choice in ("revisor_a", "revisor_b"):
        if chosen is None:
            raise DoubleReviewError("No existe decision del revisor elegido.")
        return ReviewerDecision(
            reviewer_id=reconciliation.resolved_by,
            state=chosen.state,
            final_value=chosen.final_value,
        )

    # `valor_nuevo`: la persona que concilia introduce un valor distinto de los
    # dos propuestos. El estado se marca como corregido, porque lo es.
    return ReviewerDecision(
        reviewer_id=reconciliation.resolved_by,
        state="corregido",
        final_value=reconciliation.final_value,
    )
