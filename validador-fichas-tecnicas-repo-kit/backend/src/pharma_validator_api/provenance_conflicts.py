from dataclasses import dataclass
from typing import Literal

SourceRole = Literal[
    "master_baseline",
    "cima_structured",
    "technical_sheet",
    "pharmacist_decision",
    "authorized_transformation",
    "external_source",
]
LogicalState = Literal[
    "valued",
    "empty",
    "pending",
    "no_consta",
    "no_aplica",
]
RuleStatus = Literal["pending_human_validation", "accepted"]
ConflictStatus = Literal[
    "no_assertions",
    "consistent_pending_priority",
    "unresolved_pending_priority",
    "human_action_required",
    "unresolved_no_applicable_source",
    "unresolved_authoritative_ambiguity",
    "resolved_by_accepted_priority",
]


@dataclass(frozen=True, order=True)
class FieldIdentity:
    catalog_ordinal: int
    entity: str
    block: str
    field_name: str

    def __post_init__(self) -> None:
        if self.catalog_ordinal < 1:
            raise ValueError("catalog_ordinal debe ser positivo.")
        if not self.entity or not self.block or not self.field_name:
            raise ValueError("La identidad de campo debe estar completa.")


@dataclass(frozen=True)
class SourceAssertion:
    assertion_id: str
    literal_value: str | None
    logical_state: LogicalState
    source_role: SourceRole
    source_version_id: str
    source_locator: str

    def __post_init__(self) -> None:
        if not self.assertion_id:
            raise ValueError("La afirmación requiere assertion_id.")
        if not self.source_version_id or not self.source_locator:
            raise ValueError("La afirmación requiere versión y localizador de procedencia.")

    @property
    def exact_claim(self) -> tuple[LogicalState, str | None]:
        return self.logical_state, self.literal_value


@dataclass(frozen=True)
class FieldPriorityRule:
    field_identity: FieldIdentity
    status: RuleStatus
    source_order: tuple[SourceRole, ...] = ()
    decision_reference: str | None = None
    automatic_resolution_allowed: bool = True

    def __post_init__(self) -> None:
        if self.status == "pending_human_validation":
            if self.source_order or self.decision_reference is not None:
                raise ValueError("Una regla pendiente no puede contener prioridad aceptada.")
            return
        if not self.source_order:
            raise ValueError("Una regla aceptada requiere al menos una fuente priorizada.")
        if len(set(self.source_order)) != len(self.source_order):
            raise ValueError("Una regla aceptada no puede repetir fuentes.")
        if not self.decision_reference:
            raise ValueError("Una regla aceptada requiere una decisión de autorización.")


@dataclass(frozen=True)
class ConflictEvaluation:
    field_identity: FieldIdentity
    status: ConflictStatus
    has_conflict: bool
    assertions: tuple[SourceAssertion, ...]
    distinct_claims: tuple[tuple[LogicalState, str | None], ...]
    selected_assertion_ids: tuple[str, ...] = ()
    selected_claim: tuple[LogicalState, str | None] | None = None
    applied_decision_reference: str | None = None


def _claim_sort_key(claim: tuple[LogicalState, str | None]) -> tuple[str, int, str]:
    state, literal = claim
    return state, 0 if literal is None else 1, literal or ""


def evaluate_conflict(
    field_identity: FieldIdentity,
    assertions: tuple[SourceAssertion, ...],
    rule: FieldPriorityRule | None = None,
) -> ConflictEvaluation:
    if rule is not None and rule.field_identity != field_identity:
        raise ValueError("La regla no pertenece al campo evaluado.")

    ordered_assertions = tuple(sorted(assertions, key=lambda item: item.assertion_id))
    if len({item.assertion_id for item in ordered_assertions}) != len(ordered_assertions):
        raise ValueError("assertion_id debe ser único dentro de una evaluación.")
    distinct_claims = tuple(
        sorted({item.exact_claim for item in ordered_assertions}, key=_claim_sort_key)
    )
    if not ordered_assertions:
        return ConflictEvaluation(
            field_identity,
            "no_assertions",
            False,
            ordered_assertions,
            distinct_claims,
        )

    has_conflict = len(distinct_claims) > 1
    if not has_conflict:
        return ConflictEvaluation(
            field_identity,
            "consistent_pending_priority",
            False,
            ordered_assertions,
            distinct_claims,
        )

    if rule is None or rule.status == "pending_human_validation":
        return ConflictEvaluation(
            field_identity,
            "unresolved_pending_priority",
            True,
            ordered_assertions,
            distinct_claims,
        )
    if not rule.automatic_resolution_allowed:
        return ConflictEvaluation(
            field_identity,
            "human_action_required",
            True,
            ordered_assertions,
            distinct_claims,
            applied_decision_reference=rule.decision_reference,
        )

    ranks = {source: rank for rank, source in enumerate(rule.source_order)}
    applicable = [item for item in ordered_assertions if item.source_role in ranks]
    if not applicable:
        return ConflictEvaluation(
            field_identity,
            "unresolved_no_applicable_source",
            True,
            ordered_assertions,
            distinct_claims,
            applied_decision_reference=rule.decision_reference,
        )
    best_rank = min(ranks[item.source_role] for item in applicable)
    selected = tuple(item for item in applicable if ranks[item.source_role] == best_rank)
    selected_claims = {item.exact_claim for item in selected}
    if len(selected_claims) != 1:
        return ConflictEvaluation(
            field_identity,
            "unresolved_authoritative_ambiguity",
            True,
            ordered_assertions,
            distinct_claims,
            applied_decision_reference=rule.decision_reference,
        )
    selected_claim = next(iter(selected_claims))
    return ConflictEvaluation(
        field_identity,
        "resolved_by_accepted_priority",
        True,
        ordered_assertions,
        distinct_claims,
        tuple(item.assertion_id for item in selected),
        selected_claim,
        rule.decision_reference,
    )
