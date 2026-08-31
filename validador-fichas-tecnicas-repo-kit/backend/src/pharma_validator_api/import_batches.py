from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.models import ImportBatch, ImportDiagnostic, QuarantinedSourceRow


@dataclass(frozen=True)
class ImportBatchRequest:
    source_system: str
    source_locator: str
    source_bytes: bytes
    importer_name: str
    importer_version: str
    source_version: str | None = None
    source_document_version_id: str | None = None


def _stable_key(*parts: str) -> str:
    framed = "".join(f"{len(part)}:{part}" for part in parts)
    return sha256(framed.encode("utf-8")).hexdigest()


def get_or_create_import_batch(
    session: Session,
    request: ImportBatchRequest,
    *,
    now: datetime | None = None,
) -> tuple[ImportBatch, bool]:
    content_hash = sha256(request.source_bytes).hexdigest()
    batch_id = _stable_key(
        request.source_system,
        request.source_locator,
        request.source_version or "",
        content_hash,
        request.importer_name,
        request.importer_version,
    )
    existing = session.get(ImportBatch, batch_id)
    if existing is not None:
        return existing, False
    batch = ImportBatch(
        id=batch_id,
        source_system=request.source_system,
        source_locator=request.source_locator,
        source_version=request.source_version,
        content_hash=content_hash,
        importer_name=request.importer_name,
        importer_version=request.importer_version,
        status="pending",
        created_at=now or datetime.now(UTC),
        completed_at=None,
        source_document_version_id=request.source_document_version_id,
    )
    session.add(batch)
    session.flush()
    return batch, True


def complete_import_batch(batch: ImportBatch, *, now: datetime | None = None) -> None:
    batch.status = "completed"
    batch.completed_at = now or datetime.now(UTC)


def fail_import_batch(batch: ImportBatch, *, now: datetime | None = None) -> None:
    batch.status = "failed"
    batch.completed_at = now or datetime.now(UTC)


def record_diagnostic(
    session: Session,
    *,
    batch: ImportBatch,
    severity: str,
    code: str,
    message: str,
    source_locator: str | None = None,
    details_literal: str | None = None,
    occurrence_count: int = 1,
    now: datetime | None = None,
) -> tuple[ImportDiagnostic, bool]:
    key = _stable_key(severity, code, source_locator or "", message, details_literal or "")
    existing = session.scalar(
        select(ImportDiagnostic).where(
            ImportDiagnostic.import_batch_id == batch.id,
            ImportDiagnostic.diagnostic_key == key,
        )
    )
    if existing is not None:
        return existing, False
    diagnostic = ImportDiagnostic(
        id=_stable_key(batch.id, key),
        import_batch_id=batch.id,
        diagnostic_key=key,
        severity=severity,
        code=code,
        source_locator=source_locator,
        message=message,
        details_literal=details_literal,
        occurrence_count=occurrence_count,
        created_at=now or datetime.now(UTC),
    )
    session.add(diagnostic)
    session.flush()
    return diagnostic, True


def quarantine_source_row(
    session: Session,
    *,
    batch: ImportBatch,
    source_locator: str,
    reason_code: str,
    reason: str,
    raw_payload: str,
    now: datetime | None = None,
) -> tuple[QuarantinedSourceRow, bool]:
    payload_hash = sha256(raw_payload.encode("utf-8")).hexdigest()
    key = _stable_key(source_locator, reason_code, payload_hash)
    existing = session.scalar(
        select(QuarantinedSourceRow).where(
            QuarantinedSourceRow.import_batch_id == batch.id,
            QuarantinedSourceRow.quarantine_key == key,
        )
    )
    if existing is not None:
        return existing, False
    quarantined = QuarantinedSourceRow(
        id=_stable_key(batch.id, key),
        import_batch_id=batch.id,
        quarantine_key=key,
        source_locator=source_locator,
        reason_code=reason_code,
        reason=reason,
        raw_payload=raw_payload,
        payload_hash=payload_hash,
        created_at=now or datetime.now(UTC),
    )
    session.add(quarantined)
    session.flush()
    return quarantined, True
