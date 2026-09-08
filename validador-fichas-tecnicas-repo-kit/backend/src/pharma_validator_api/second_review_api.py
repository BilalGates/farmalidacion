"""API de segunda revisión: respuestas explícitas y transacciones atómicas."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.double_review import DoubleReviewError, Reconciliation
from pharma_validator_api.models import FieldValue, SecondReviewAssignment
from pharma_validator_api.queue_api import SettingsDependency
from pharma_validator_api.records import DirectoryDependency, SessionDependency
from pharma_validator_api.second_review_store import (
    SecondReviewConflict,
    SecondReviewError,
    blind_view,
    claim_second_review,
    comparison_for,
    open_second_review,
    reconcile,
    submit_second_review,
)
from pharma_validator_api.validation_states import (
    ValidationDecision,
    ValidationState,
    ValidationStateError,
)

router = APIRouter(prefix="/second-reviews", tags=["segunda revisión"])


@contextmanager
def translated(session: Session) -> Iterator[None]:
    """Traduce los errores de dominio al código HTTP que les corresponde.

    Sin esto, una barrera clínica legítima —«no_aplica exige comentario»— llega
    al cliente como un 500, indistinguible de un fallo del servidor. El mensaje
    se conserva literal: explica *por qué* la decisión no es admisible.

    La sesión se deshace antes de responder. Una petición rechazada no puede
    dejar escrita media operación: la lectura y el resultado de compararla se
    escriben juntos o no se escriben.
    """
    try:
        yield
    except SecondReviewConflict as error:
        session.rollback()
        raise HTTPException(409, str(error)) from error
    except (SecondReviewError, DoubleReviewError, ValidationStateError) as error:
        session.rollback()
        raise HTTPException(400, str(error)) from error


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer_id: str = Field(min_length=1)
    expected_version: int | None = Field(default=None, ge=1)
    state: ValidationState = "confirmado"
    final_value: str | None = None
    comment: str | None = None
    choice: Literal["revisor_a", "revisor_b", "valor_nuevo"] = "revisor_a"
    required_sources: list[str] = []
    reviewed_sources: list[str] = []
    applicable_sources: list[str] = []
    field_required: bool = False


def view(row: SecondReviewAssignment) -> dict[str, Any]:
    return dict(
        id=row.id,
        field_value_id=row.field_value_id,
        target_record_id=row.target_record_id,
        state=row.state,
        version=row.version,
        second_reviewer_id=row.second_reviewer_id,
    )


def enabled(settings: Any) -> None:
    if not settings.enable_second_review:
        raise HTTPException(404, "La segunda revisión está desactivada.")


def assignment(session: Session, assignment_id: str) -> SecondReviewAssignment:
    row = session.get(SecondReviewAssignment, assignment_id)
    if row is None:
        raise HTTPException(404, "Asignación no encontrada.")
    return row


@router.get("")
def listing(
    reviewer_id: str,
    session: SessionDependency,
    directory: DirectoryDependency,
    settings: SettingsDependency,
) -> list[dict[str, Any]]:
    enabled(settings)
    directory.resolve(reviewer_id)
    return [
        view(row)
        for row in session.scalars(
            select(SecondReviewAssignment).order_by(
                SecondReviewAssignment.created_at, SecondReviewAssignment.id
            )
        )
        if row.revealed
        or (row.first_reviewer_id != reviewer_id and row.second_reviewer_id in (None, reviewer_id))
    ]


@router.post("/fields/{field_id}", status_code=201)
def opening(
    field_id: str,
    payload: Action,
    session: SessionDependency,
    directory: DirectoryDependency,
    settings: SettingsDependency,
) -> dict[str, Any]:
    enabled(settings)
    actor = directory.resolve(payload.reviewer_id)
    with translated(session):
        row = open_second_review(
            session, field_value_id=field_id, actor_id=actor.identifier
        )
        session.commit()
    return view(row)


@router.get("/{assignment_id}/blind")
def blind(
    assignment_id: str,
    reviewer_id: str,
    session: SessionDependency,
    directory: DirectoryDependency,
    settings: SettingsDependency,
) -> dict[str, Any]:
    enabled(settings)
    directory.resolve(reviewer_id)
    with translated(session):
        result = asdict(blind_view(session, assignment_id, reviewer_id))
    result["version"] = assignment(session, assignment_id).version
    return result


@router.get("/{assignment_id}/comparison")
def comparison(
    assignment_id: str,
    reviewer_id: str,
    session: SessionDependency,
    directory: DirectoryDependency,
    settings: SettingsDependency,
) -> dict[str, Any]:
    enabled(settings)
    directory.resolve(reviewer_id)
    with translated(session):
        return asdict(comparison_for(session, assignment_id))


@router.post("/{assignment_id}/{operation}")
def mutate(
    assignment_id: str,
    operation: Literal["claim", "decisions", "reconcile"],
    payload: Action,
    session: SessionDependency,
    directory: DirectoryDependency,
    settings: SettingsDependency,
) -> dict[str, Any]:
    enabled(settings)
    actor = directory.resolve(payload.reviewer_id)
    row = assignment(session, assignment_id)
    value = session.get(FieldValue, row.field_value_id)
    assert value is not None
    with translated(session):
        return _apply(
            session,
            operation=operation,
            assignment_id=assignment_id,
            payload=payload,
            actor_id=actor.identifier,
            field_name=value.field_name,
            directory=directory,
            row=row,
        )


def _apply(
    session: Session,
    *,
    operation: str,
    assignment_id: str,
    payload: "Action",
    actor_id: str,
    field_name: str,
    directory: Any,
    row: SecondReviewAssignment,
) -> dict[str, Any]:
    if operation == "claim":
        row = claim_second_review(
            session,
            assignment_id=assignment_id,
            reviewer_id=actor_id,
            expected_version=payload.expected_version,
        )
    elif operation == "decisions":
        row = submit_second_review(
            session,
            assignment_id=assignment_id,
            decision=ValidationDecision(
                field_name=field_name,
                state=payload.state,
                reviewer_id=actor_id,
                reviewer_role="farmaceutico",
                final_value=payload.final_value,
                comment=payload.comment,
                required_sources=tuple(payload.required_sources),
                reviewed_sources=tuple(payload.reviewed_sources),
                applicable_sources=tuple(payload.applicable_sources),
                field_required=payload.field_required,
            ),
            directory=directory,
            expected_version=payload.expected_version,
        )
    else:
        reconcile(
            session,
            assignment_id=assignment_id,
            reconciliation=Reconciliation(
                field_name=field_name,
                choice=payload.choice,
                resolved_by=actor_id,
                comment=payload.comment or "",
                final_value=payload.final_value,
            ),
            directory=directory,
            expected_version=payload.expected_version,
        )
        session.refresh(row)
    session.commit()
    return view(row)
