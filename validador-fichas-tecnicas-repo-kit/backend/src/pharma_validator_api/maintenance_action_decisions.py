"""Decisiones humanas sobre las acciones de novedades CIMA (ADR-0019).

Nada de lo que propone `maintenance_actions` se aplica sin pasar por aquí. Una
decisión es una fila append-only; solo `aceptada` escribe en el catálogo, y lo
hace con los mismos servicios y el mismo historial que la edición manual:
archivar (`catalog_store.revise_identity`), `ACTIVO = N`
(`field_maintenance_revision`) o el borrador de un alta (identidad nueva en la
cola de Revisión).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_validator_api import audit_store, review_queue_store
from pharma_validator_api.catalog_domain import CatalogDomainError, CatalogIdentity
from pharma_validator_api.catalog_store import (
    CatalogStoreError,
    create_identity,
    revise_identity,
)
from pharma_validator_api.data_origin import DataOrigin
from pharma_validator_api.maintenance_actions import (
    DIAG_CIMA_NO_DISPONIBLE,
    RULE_ALTA_NOMBRE,
    RULE_BAJA_ACTIVO,
    SPECIALTY_BLOCK,
    current_state,
    master_activo,
)
from pharma_validator_api.models import (
    BlockInstance,
    FieldMaintenanceRevision,
    FieldValue,
    MaintenanceAction,
    MaintenanceActionDecision,
    MedicationCatalogIdentity,
    MedicationCatalogRevision,
    ReviewQueueEntry,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
)
from pharma_validator_api.national_code import NationalCodeError, parse_national_code
from pharma_validator_api.reviewer_identity import Reviewer

# `enviada_revision` solo nace en `send_to_review`, que es lo que encola el registro.
DECISIONS = ("aceptada", "descartada", "reabierta")
CLOSED = ("aceptada", "descartada")
DRAFT_SOURCE_SYSTEM = "cima_novedades_alta"


class ActionError(ValueError):
    """La decisión no es válida (400)."""


class ActionNotFound(ActionError):
    """La acción no existe (404)."""


class ActionConflict(ActionError):
    """La acción cambió o no admite esta transición (409)."""


def decide(
    session: Session,
    *,
    action_id: str,
    decision: str,
    reason: str,
    expected_sequence: int,
    reviewer: Reviewer,
) -> MaintenanceActionDecision:
    if decision not in DECISIONS:
        raise ActionError("Decisión desconocida.")
    action = session.get(MaintenanceAction, action_id)
    if action is None:
        raise ActionNotFound("Acción de novedad no encontrada.")
    state = current_state(session, [action_id])[action_id]
    if expected_sequence != state.sequence:
        raise ActionConflict("La acción cambió desde que la abriste. Recarga antes de decidir.")
    reason = reason.strip()
    if decision in ("descartada", "reabierta") and not reason:
        raise ActionError("Indica la justificación de la decisión.")
    if decision == "aceptada" and action.kind == "revisar_archivo" and not reason:
        raise ActionError("Indica la justificación para archivar.")
    last = state.decision.decision if state.decision else None
    if decision == "reabierta" and last not in CLOSED:
        raise ActionConflict("Solo se puede reabrir una acción aceptada o descartada.")
    if decision != "reabierta" and last in CLOSED:
        raise ActionConflict("La acción ya está decidida; reábrela antes de decidir de nuevo.")
    if decision == "aceptada" and action.diagnostic_code == DIAG_CIMA_NO_DISPONIBLE:
        raise ActionConflict(
            "Pendiente de consultar CIMA: no se puede aceptar hasta que CIMA responda."
        )
    revision_id: str | None = None
    field_revision_id: str | None = None
    queue_target: str | None = None
    if decision == "aceptada":
        try:
            revision_id, field_revision_id, queue_target = _apply(
                session, action, reviewer, reason
            )
        except ActionError:
            session.rollback()
            raise
        except IntegrityError as error:
            session.rollback()
            raise ActionConflict(
                "No se pudo aplicar la decisión: el catálogo cambió o ya existe el registro."
            ) from error
        except (KeyError, TypeError, ValueError) as error:
            session.rollback()
            raise ActionError(
                "No se pudo aplicar la decisión: datos de la acción incompletos."
            ) from error
    row = _append(
        session, action, decision, reason, state.sequence + 1, reviewer,
        applied_revision_id=revision_id, applied_field_revision_id=field_revision_id,
    )
    try:
        session.flush()
        if queue_target is not None:
            review_queue_store.enqueue(session, queue_target, review_set="corpus")
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ActionConflict(
            "La acción se decidió en paralelo. Recarga antes de decidir."
        ) from error
    return row


def _append(
    session: Session,
    action: MaintenanceAction,
    decision: str,
    reason: str,
    sequence: int,
    reviewer: Reviewer,
    *,
    applied_revision_id: str | None = None,
    applied_field_revision_id: str | None = None,
) -> MaintenanceActionDecision:
    row = MaintenanceActionDecision(
        action_id=action.id,
        sequence=sequence,
        decision=decision,
        reason=reason,
        applied_revision_id=applied_revision_id,
        applied_field_revision_id=applied_field_revision_id,
        actor_id=reviewer.identifier,
        actor_assurance=reviewer.assurance,
        recorded_at=datetime.now(UTC),
    )
    session.add(row)
    audit_store.record_event(
        session,
        entity_type="maintenance_action",
        entity_id=action.id,
        action="maintenance_action.decision",
        actor_id=reviewer.identifier,
        actor_assurance=reviewer.assurance,
        before_state={"sequence": sequence - 1},
        after_state={"decision": decision, "sequence": sequence},
        reason=reason or None,
        context={
            "kind": action.kind,
            "event_id": action.event_id,
            "target_record_id": action.target_record_id,
            "applied_revision_id": applied_revision_id,
            "applied_field_revision_id": applied_field_revision_id,
        },
    )
    return row


def _apply(
    session: Session, action: MaintenanceAction, reviewer: Reviewer, reason: str
) -> tuple[str | None, str | None, str | None]:
    """Aplica al catálogo lo que la acción aceptada pide. Devuelve (revisión, campo, cola)."""
    if action.kind == "revisar_archivo":
        return _archive(session, action, reviewer, reason), None, None
    if action.kind == "proponer_activo_n":
        return None, _write_activo(session, action, reviewer, reason), None
    if action.kind == "proponer_alta":
        revision_id, target_id = _create_draft(session, action, reviewer, reason)
        return revision_id, None, target_id
    return None, None, None  # revisado conforme: no escribe catálogo


def _archive(
    session: Session, action: MaintenanceAction, reviewer: Reviewer, reason: str
) -> str | None:
    identity = session.get(MedicationCatalogIdentity, action.identity_id or "")
    if identity is None:
        raise ActionError("La identidad del catálogo ya no existe.")
    if not identity.active:
        return None
    try:
        revised = revise_identity(
            session, identity.id,
            expected_version=identity.version,
            display_name=identity.display_name,
            code=identity.code,
            active=False,
            actor_id=reviewer.identifier,
            actor_assurance=reviewer.assurance,
            reason=f"Baja CIMA (acción {action.id}). {reason}".strip(),
        )
    except CatalogStoreError as error:
        raise ActionConflict(str(error)) from error
    session.flush()
    return session.scalar(
        select(MedicationCatalogRevision.id).where(
            MedicationCatalogRevision.identity_id == revised.id,
            MedicationCatalogRevision.sequence == revised.version,
        )
    )


def _write_activo(
    session: Session, action: MaintenanceAction, reviewer: Reviewer, reason: str
) -> str | None:
    if (
        action.rule_id != RULE_BAJA_ACTIVO
        or action.proposed_value != "N"
        or not action.master_field_value_id
        or not action.target_record_id
    ):
        raise ActionError("La acción no tiene un campo ACTIVO sobre el que proponer.")
    current = master_activo(session, action.target_record_id).value
    if current == "N":
        return None  # el maestro ya dice N: no hay nada que revisar
    last = session.scalar(
        select(FieldMaintenanceRevision.sequence)
        .where(FieldMaintenanceRevision.field_value_id == action.master_field_value_id)
        .order_by(FieldMaintenanceRevision.sequence.desc())
        .limit(1)
    )
    revision = FieldMaintenanceRevision(
        field_value_id=action.master_field_value_id,
        sequence=(last or 0) + 1,
        before_value=current,
        after_value="N",
        actor_id=reviewer.identifier,
        actor_assurance=reviewer.assurance,
        reason=f"{RULE_BAJA_ACTIVO} (acción {action.id}). {reason}".strip(),
        recorded_at=datetime.now(UTC),
    )
    session.add(revision)
    session.flush()
    return revision.id


def _create_draft(
    session: Session, action: MaintenanceAction, reviewer: Reviewer, reason: str
) -> tuple[str, str]:
    """Identidad borrador pendiente de validar; el resto de columnas queda vacío."""
    if action.data_origin != DataOrigin.REAL.value:
        raise ActionConflict("En DEMO no se crean borradores de alta.")
    if not action.proposal_json or not action.cima_version_id or action.rule_id != RULE_ALTA_NOMBRE:
        raise ActionConflict("La propuesta de alta no está completa.")
    try:
        proposal = json.loads(action.proposal_json)
        columns = {item["name"]: item for item in proposal["columns"]}
        cn = columns.get("CODIGO_NACIONAL", {}).get("value")
        name = columns.get("DESCRIPCION_PRESCRIPCION", {}).get("value")
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ActionError("La propuesta de alta guardada no es válida.") from error
    if not cn or not name:
        raise ActionConflict("La propuesta no trae código nacional y nombre de CIMA.")
    try:
        code = parse_national_code(cn).canonical_six
    except NationalCodeError:
        code = cn
    if session.scalar(
        select(MedicationCatalogIdentity.id).where(
            MedicationCatalogIdentity.source_system == DRAFT_SOURCE_SYSTEM,
            MedicationCatalogIdentity.code == code,
        )
    ):
        raise ActionConflict("Ya existe un borrador de alta para este código nacional.")
    target = TargetRecord(entity_type="specialty")
    session.add(target)
    session.flush()
    fragments: dict[str, SourceFragment] = {}
    for item in proposal["columns"]:
        provenance = item.get("provenance")
        if item["value"] is None or not provenance:
            continue
        fragment = SourceFragment(
            document_version_id=provenance["cima_version_id"],
            locator_type="json_pointer",
            locator=provenance["pointer"],
            literal_text=item["value"],
        )
        session.add(fragment)
        fragments[item["name"]] = fragment
    session.flush()
    block = BlockInstance(
        target_record_id=target.id, block_type=SPECIALTY_BLOCK, ordinal=1,
        source_fragment_id=fragments["CODIGO_NACIONAL"].id,
    )
    session.add(block)
    session.flush()
    for title, fragment in fragments.items():
        item = columns[title]
        value = FieldValue(
            block_instance_id=block.id, field_name=title, source_column_index=item["column"],
            literal_value=item["value"], observed_type="cima_literal", logical_state="valued",
        )
        session.add(value)
        session.flush()
        session.add(
            ValueProvenance(
                field_value_id=value.id, source_fragment_id=fragment.id,
                provenance_role="cima_alta_borrador",
            )
        )
    try:
        identity = create_identity(
            session,
            CatalogIdentity(
                id=str(uuid5(NAMESPACE_URL, f"maintenance-alta-draft:v1:{action.id}")),
                identity_type="presentation", display_name=name, code=code,
                target_record_id=target.id,
            ),
            source_system=DRAFT_SOURCE_SYSTEM,
            source_version="novedades-v1",
            source_literal=cn,
            source_fragment_id=fragments["CODIGO_NACIONAL"].id,
            actor_id=reviewer.identifier,
            actor_assurance=reviewer.assurance,
            reason=f"Borrador de alta por novedad CIMA (acción {action.id}). {reason}".strip(),
        )
    except (CatalogStoreError, CatalogDomainError) as error:
        raise ActionError(str(error)) from error
    session.flush()
    revision_id = session.scalar(
        select(MedicationCatalogRevision.id).where(
            MedicationCatalogRevision.identity_id == identity.id,
            MedicationCatalogRevision.sequence == 1,
        )
    )
    assert revision_id is not None
    return revision_id, target.id


@dataclass
class SendResult:
    enqueued: list[str] = field(default_factory=list)
    already_queued: list[str] = field(default_factory=list)
    decided: list[str] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)


def send_to_review(
    session: Session, *, action_ids: list[str], reviewer: Reviewer
) -> SendResult:
    """Encola en el conjunto general los registros de varias acciones, sin duplicar."""
    result = SendResult()
    targets: dict[str, None] = {}
    for action_id in dict.fromkeys(action_ids):
        action = session.get(MaintenanceAction, action_id)
        reason = None
        if action is None:
            reason = "No existe."
        elif action.target_record_id is None:
            reason = "No tiene registro en el catálogo."
        elif action.diagnostic_code == DIAG_CIMA_NO_DISPONIBLE:
            reason = "Pendiente de consultar CIMA."
        if action is not None and reason is None:
            state = current_state(session, [action_id])[action_id]
            if state.state in CLOSED:
                reason = "Ya está decidida."
            elif state.state == "enviada_revision":
                reason = "Ya se envió a Revisión."
        if reason is not None or action is None or action.target_record_id is None:
            result.rejected.append({"action_id": action_id, "reason": reason or "No válida."})
            continue
        _append(session, action, "enviada_revision", "", state.sequence + 1, reviewer)
        result.decided.append(action_id)
        targets[action.target_record_id] = None
    session.flush()
    for target_id in targets:
        exists = session.scalar(
            select(ReviewQueueEntry.id).where(ReviewQueueEntry.target_record_id == target_id)
        )
        (result.already_queued if exists else result.enqueued).append(target_id)
        review_queue_store.enqueue(session, target_id, review_set="corpus")
    session.commit()
    return result
