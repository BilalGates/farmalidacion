from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.cima_changes import CimaChange
from pharma_validator_api.cima_client import CimaResponse
from pharma_validator_api.document_versions import ArtifactInput, persist_cima_document_version
from pharma_validator_api.models import (
    DocumentRecordLink,
    FieldValue,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
    ValidationDecisionRecord,
    ValueProvenance,
)
from pharma_validator_api.review import current_decision
from pharma_validator_api.version_diff import VersionDiff, create_version_diff


class MaintenanceRefreshError(RuntimeError):
    pass


class MaintenanceClient(Protocol):
    def changes(
        self, *, date: str, nregistros: Sequence[str] = ()
    ) -> CimaResponse: ...

    def medication(
        self,
        *,
        nregistro: str | None = None,
        cn: str | None = None,
        use_cache: bool = True,
    ) -> CimaResponse: ...

    def sections(
        self, *, nregistro: str, document_type: int = 1, use_cache: bool = True
    ) -> CimaResponse: ...

    def content(
        self,
        *,
        nregistro: str,
        section: str | None = None,
        document_type: int = 1,
        accept: str = "application/json",
        use_cache: bool = True,
    ) -> CimaResponse: ...


@dataclass(frozen=True)
class RefreshResult:
    nregistro: str
    old_version_id: str | None
    new_version_id: str
    created: bool
    diff: VersionDiff | None
    changed_sections: tuple[str, ...]
    marked_field_value_ids: tuple[str, ...]


def _section_codes(response: CimaResponse) -> tuple[str, ...]:
    try:
        payload = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MaintenanceRefreshError("El índice de secciones CIMA no es JSON válido.") from exc
    if not isinstance(payload, list):
        raise MaintenanceRefreshError("El índice de secciones CIMA debe ser una lista.")
    result: list[str] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise MaintenanceRefreshError(f"Sección {index}: se esperaba un objeto.")
        raw = item.get("seccion")
        if not isinstance(raw, (str, int)) or isinstance(raw, bool) or not str(raw).strip():
            raise MaintenanceRefreshError(f"Sección {index}: identificador incompatible.")
        value = str(raw)
        if value in result:
            raise MaintenanceRefreshError(f"Sección repetida en CIMA: {value}")
        result.append(value)
    if not result:
        raise MaintenanceRefreshError("La ficha técnica CIMA no declara secciones.")
    return tuple(result)


def _download(
    client: MaintenanceClient, *, nregistro: str, document_type: int
) -> tuple[ArtifactInput, ...]:
    metadata = client.medication(nregistro=nregistro, use_cache=False)
    index = client.sections(nregistro=nregistro, document_type=document_type, use_cache=False)
    codes = _section_codes(index)
    artifacts = [
        ArtifactInput("metadata", 1, "medicamento", metadata),
        ArtifactInput("section_index", 1, "secciones", index),
    ]
    artifacts.extend(
        ArtifactInput(
            "section",
            ordinal,
            code,
            client.content(
                nregistro=nregistro,
                section=code,
                document_type=document_type,
                accept="application/json",
                use_cache=False,
            ),
        )
        for ordinal, code in enumerate(codes, start=1)
    )
    return tuple(artifacts)


def _current_version(
    session: Session, *, nregistro: str, document_type: int
) -> SourceDocumentVersion | None:
    source_type = f"cima_document_type_{document_type}"
    documents = session.scalars(
        select(SourceDocument).where(
            SourceDocument.source_type == source_type,
            SourceDocument.name == nregistro,
        )
    ).all()
    if len(documents) > 1:
        raise MaintenanceRefreshError(f"Documento CIMA duplicado: {source_type}/{nregistro}")
    if not documents:
        return None
    return session.scalars(
        select(SourceDocumentVersion)
        .where(SourceDocumentVersion.document_id == documents[0].id)
        .order_by(SourceDocumentVersion.acquired_at.desc(), SourceDocumentVersion.id.desc())
        .limit(1)
    ).first()


def _copy_links(
    session: Session, *, old_version_id: str, new_version_id: str
) -> None:
    links = session.scalars(
        select(DocumentRecordLink).where(DocumentRecordLink.document_version_id == old_version_id)
    ).all()
    for link in links:
        identity = f"maintenance-link:{new_version_id}:{link.target_record_id}:{link.link_type}"
        session.add(
            DocumentRecordLink(
                id=str(uuid5(NAMESPACE_URL, identity)),
                document_version_id=new_version_id,
                target_record_id=link.target_record_id,
                link_type=link.link_type,
            )
        )


def _affected_values(
    session: Session, *, old_version_id: str, changed_sections: tuple[str, ...]
) -> tuple[FieldValue, ...]:
    fragments = session.scalars(
        select(SourceFragment).where(SourceFragment.document_version_id == old_version_id)
    ).all()
    if not fragments:
        return ()
    exact = [item.id for item in fragments if item.locator in changed_sections]
    broad_locators = {"all-sections", "documento-completo"}
    broad = [item.id for item in fragments if item.locator in broad_locators]
    fragment_ids = exact or broad
    if not fragment_ids:
        return ()
    return tuple(
        session.scalars(
            select(FieldValue)
            .join(ValueProvenance, ValueProvenance.field_value_id == FieldValue.id)
            .where(ValueProvenance.source_fragment_id.in_(fragment_ids))
            .order_by(FieldValue.id)
        ).unique().all()
    )


def _mark_pending(
    session: Session,
    *,
    values: Sequence[FieldValue],
    old_version_id: str,
    new_version_id: str,
    report_id: str,
) -> tuple[str, ...]:
    marked: list[str] = []
    for value in values:
        previous = current_decision(session, value.id)
        if previous is None or previous.state in {"pendiente", "revision_pendiente"}:
            continue
        session.add(
            ValidationDecisionRecord(
                field_value_id=value.id,
                sequence=previous.sequence + 1,
                field_name=value.field_name,
                state="revision_pendiente",
                final_value=None,
                comment=(
                    "Cambio de ficha técnica CIMA; revisar contra la nueva versión. "
                    f"diff={report_id}; anterior={old_version_id}; nueva={new_version_id}"
                ),
                reviewer_id="system:cima-maintenance",
                reviewer_role="otro",
                reviewer_assurance="system",
                seconds_spent=None,
                decided_at=datetime.now(UTC),
            )
        )
        marked.append(value.id)
    return tuple(marked)


def refresh_technical_sheet(
    session: Session,
    *,
    client: MaintenanceClient,
    nregistro: str,
    document_type: int = 1,
) -> RefreshResult:
    if not nregistro or document_type <= 0:
        raise MaintenanceRefreshError("Identidad documental CIMA incompatible.")
    old = _current_version(session, nregistro=nregistro, document_type=document_type)
    artifacts = _download(client, nregistro=nregistro, document_type=document_type)
    try:
        persisted = persist_cima_document_version(
            session,
            nregistro=nregistro,
            document_type=document_type,
            artifacts=artifacts,
            commit=False,
        )
        if not persisted.created:
            session.rollback()
            return RefreshResult(
                nregistro, old.id if old else None, persisted.version_id, False, None, (), ()
            )
        if old is None:
            session.commit()
            return RefreshResult(nregistro, None, persisted.version_id, True, None, (), ())

        report = create_version_diff(
            session, old_version_id=old.id, new_version_id=persisted.version_id
        )
        changed_sections = tuple(
            item.old_locator or item.new_locator or ""
            for item in report.changes
            if item.role == "section"
            and (
                item.change_type in {"added", "removed"}
                or item.old_hash != item.new_hash
                or item.old_locator != item.new_locator
            )
        )
        _copy_links(session, old_version_id=old.id, new_version_id=persisted.version_id)
        values = _affected_values(
            session, old_version_id=old.id, changed_sections=changed_sections
        )
        marked = _mark_pending(
            session,
            values=values,
            old_version_id=old.id,
            new_version_id=persisted.version_id,
            report_id=report.report_id,
        )
        session.commit()
        return RefreshResult(
            nregistro,
            old.id,
            persisted.version_id,
            True,
            report,
            changed_sections,
            marked,
        )
    except Exception:
        session.rollback()
        raise


def refresh_changed_technical_sheets(
    session: Session,
    *,
    client: MaintenanceClient,
    changes: Sequence[CimaChange],
    document_type: int = 1,
) -> tuple[RefreshResult, ...]:
    """Conecta DEV-701 con DEV-702 sin convertir otros cambios en cambios de FT."""
    nregistros = tuple(
        dict.fromkeys(item.nregistro for item in changes if item.affects_technical_sheet)
    )
    return tuple(
        refresh_technical_sheet(
            session,
            client=client,
            nregistro=nregistro,
            document_type=document_type,
        )
        for nregistro in nregistros
    )
