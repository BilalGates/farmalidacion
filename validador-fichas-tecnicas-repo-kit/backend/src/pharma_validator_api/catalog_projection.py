"""Proyección conservadora del modelo importado al catálogo farmacéutico.

La proyección sólo materializa equivalencias aprobadas. En particular, no
convierte el vínculo histórico especialidad→medicamento en presentación→DCP:
esa arista saltaría el DCPF, que todavía no puede obtenerse de forma fiable.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.catalog_domain import CatalogIdentity
from pharma_validator_api.catalog_store import create_identity
from pharma_validator_api.models import (
    BlockInstance,
    ExternalIdentifier,
    FieldValue,
    MedicationCatalogIdentity,
    MedicationCatalogRelation,
    TargetRecord,
    TargetRecordLink,
)
from pharma_validator_api.national_code import NationalCodeError, parse_national_code

PROJECTION_VERSION = "target-record-v1"
PROJECTION_ACTOR = "sistema:proyeccion_catalogo_v1"
_NAMESPACE = UUID("0be44c5e-55ac-4b09-a00e-386ec62c444c")

_TYPE_MAP = {
    "specialty": "presentation",
    "medication": "dcp",
    "active_ingredient": "active_ingredient",
}
_NAME_FIELDS = {
    "specialty": ("ES_DESCRIPCION", "ME_DESCRIPCION", "DESCRIPCION", "NOMBRE"),
    "medication": ("ME_DESCRIPCION", "DESCRIPCION", "NOMBRE"),
    "active_ingredient": ("PA_DESCRIPCION", "DESCRIPCION", "NOMBRE"),
}
_CODE_FIELDS = {
    "specialty": ("CODIGO_NACIONAL",),
    "medication": ("ME_IDEXTERNO", "MED_IDEXTERNO", "IDEXTERNO"),
    "active_ingredient": ("PA_IDEXTERNO", "IDEXTERNO"),
}


@dataclass(frozen=True)
class ProjectionDiagnostic:
    record_id: str
    code: str
    detail: str


@dataclass(frozen=True)
class CatalogProjectionReport:
    apply: bool
    inspected_records: int
    projectable_identities: int
    created_identities: int
    existing_identities: int
    projectable_relations: int
    created_relations: int
    existing_relations: int
    diagnostics: tuple[ProjectionDiagnostic, ...]


@dataclass(frozen=True)
class _Candidate:
    identity: CatalogIdentity
    source_literal: str | None
    source_fragment_id: str | None


def _identity_id(record_id: str, identity_type: str) -> str:
    return str(uuid5(_NAMESPACE, f"identity:{identity_type}:{record_id}"))


def _relation_id(relation_type: str, source_id: str, target_id: str) -> str:
    return str(uuid5(_NAMESPACE, f"relation:{relation_type}:{source_id}:{target_id}"))


def _field_values(session: Session, record_id: str) -> list[tuple[FieldValue, BlockInstance]]:
    return [
        (value, block)
        for value, block in session.execute(
            select(FieldValue, BlockInstance)
            .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
            .where(BlockInstance.target_record_id == record_id)
            .order_by(BlockInstance.ordinal, FieldValue.id)
        ).all()
    ]


def _first_field(
    values: list[tuple[FieldValue, BlockInstance]], names: tuple[str, ...]
) -> tuple[str | None, str | None]:
    for name in names:
        for value, block in values:
            if value.field_name == name and value.literal_value not in (None, ""):
                return value.literal_value, block.source_fragment_id
    return None, None


def _external_code(session: Session, record_id: str) -> str | None:
    return session.scalars(
        select(ExternalIdentifier.source_identifier)
        .where(ExternalIdentifier.target_record_id == record_id)
        .order_by(ExternalIdentifier.source_system, ExternalIdentifier.source_identifier)
        .limit(1)
    ).first()


def _candidate(
    session: Session, record: TargetRecord
) -> tuple[_Candidate | None, ProjectionDiagnostic | None]:
    identity_type = _TYPE_MAP.get(record.entity_type)
    if identity_type is None:
        return None, ProjectionDiagnostic(
            record.id, "UNSUPPORTED_ENTITY_TYPE", f"Tipo no proyectable: {record.entity_type}."
        )
    values = _field_values(session, record.id)
    name, name_fragment_id = _first_field(values, _NAME_FIELDS[record.entity_type])
    if name is None:
        return None, ProjectionDiagnostic(
            record.id, "MISSING_DISPLAY_NAME", "No existe un nombre literal autorizado."
        )
    raw_code, code_fragment_id = _first_field(values, _CODE_FIELDS[record.entity_type])
    if raw_code is None:
        raw_code = _external_code(session, record.id)
    code = raw_code
    if record.entity_type == "specialty":
        if raw_code is None:
            return None, ProjectionDiagnostic(
                record.id, "MISSING_NATIONAL_CODE", "La presentación no tiene Código Nacional."
            )
        try:
            code = parse_national_code(raw_code).canonical_six
        except NationalCodeError as error:
            return None, ProjectionDiagnostic(record.id, "INVALID_NATIONAL_CODE", str(error))
    identity = CatalogIdentity(
        id=_identity_id(record.id, identity_type),
        identity_type=identity_type,  # type: ignore[arg-type]
        display_name=name,
        code=code,
        target_record_id=record.id,
    )
    return _Candidate(identity, raw_code, code_fragment_id or name_fragment_id), None


def project_target_records(session: Session, *, apply: bool = False) -> CatalogProjectionReport:
    """Analiza o aplica una proyección determinista e idempotente.

    ``apply=False`` es el valor deliberado por defecto: permite auditar los
    diagnósticos y recuentos antes de escribir el estado canónico.
    """

    records = list(session.scalars(select(TargetRecord).order_by(TargetRecord.id)))
    existing_ids = set(session.scalars(select(MedicationCatalogIdentity.id)))
    candidates: dict[str, _Candidate] = {}
    diagnostics: list[ProjectionDiagnostic] = []
    created_identities = existing_identities = 0
    for record in records:
        candidate, diagnostic = _candidate(session, record)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
            continue
        assert candidate is not None
        candidates[record.id] = candidate
        if candidate.identity.id in existing_ids:
            existing_identities += 1
        elif apply:
            create_identity(
                session,
                candidate.identity,
                source_system="canonical_target_record",
                source_version=PROJECTION_VERSION,
                source_literal=candidate.source_literal,
                source_fragment_id=candidate.source_fragment_id,
                actor_id=PROJECTION_ACTOR,
                actor_assurance="tecnica",
                reason="Proyección conservadora desde el registro importado.",
            )
            existing_ids.add(candidate.identity.id)
            created_identities += 1

    relation_candidates: list[tuple[str, str, str, str | None]] = []
    for link in session.scalars(select(TargetRecordLink).order_by(TargetRecordLink.id)):
        if link.link_type == "specialty_medication":
            diagnostics.append(
                ProjectionDiagnostic(
                    link.source_record_id,
                    "MISSING_DCPF_BRIDGE",
                    "El vínculo especialidad→medicamento se conserva sin proyectar "
                    "hasta identificar DCPF.",
                )
            )
            continue
        if link.link_type != "composition_active_ingredient":
            continue
        source = candidates.get(link.source_record_id)
        target = candidates.get(link.target_record_id)
        if source is None or target is None:
            diagnostics.append(
                ProjectionDiagnostic(
                    link.source_record_id,
                    "UNPROJECTABLE_COMPOSITION_LINK",
                    "La composición no se proyecta porque uno de sus extremos no es proyectable.",
                )
            )
            continue
        relation_candidates.append(
            (
                "dcp_active_ingredient",
                source.identity.id,
                target.identity.id,
                link.source_fragment_id,
            )
        )

    existing_relation_keys = {
        (relation_type, source_id, target_id)
        for relation_type, source_id, target_id in session.execute(
            select(
                MedicationCatalogRelation.relation_type,
                MedicationCatalogRelation.source_identity_id,
                MedicationCatalogRelation.target_identity_id,
            )
        ).all()
    }
    created_relations = existing_relations = 0
    for relation_type, source_id, target_id, fragment_id in relation_candidates:
        key = (relation_type, source_id, target_id)
        if key in existing_relation_keys:
            existing_relations += 1
        elif apply:
            session.add(
                MedicationCatalogRelation(
                    id=_relation_id(*key),
                    relation_type=relation_type,
                    source_identity_id=source_id,
                    target_identity_id=target_id,
                    ordinal=None,
                    source_fragment_id=fragment_id,
                )
            )
            existing_relation_keys.add(key)
            created_relations += 1

    return CatalogProjectionReport(
        apply=apply,
        inspected_records=len(records),
        projectable_identities=len(candidates),
        created_identities=created_identities,
        existing_identities=existing_identities,
        projectable_relations=len(relation_candidates),
        created_relations=created_relations,
        existing_relations=existing_relations,
        diagnostics=tuple(diagnostics),
    )
