"""Carga controlada de nuevas versiones de los tres libros maestros."""

from __future__ import annotations

import hashlib
import secrets
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import unquote
from xml.etree import ElementTree

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from pharma_validator_api.active_ingredient_importer import (
    ActiveIngredientImportError,
    import_active_ingredients,
)
from pharma_validator_api.active_ingredient_importer import (
    _parse_workbook as parse_active_ingredient_workbook,
)
from pharma_validator_api.medication_importer import (
    MedicationImportError,
    import_medications,
)
from pharma_validator_api.medication_importer import (
    _parse_workbook as parse_medication_workbook,
)
from pharma_validator_api.models import ImportBatch
from pharma_validator_api.specialty_importer import (
    SpecialtyImportError,
    import_specialties,
)
from pharma_validator_api.specialty_importer import (
    _parse_workbook as parse_specialty_workbook,
)

router = APIRouter(prefix="/imports/master", tags=["importaciones"])
MAX_WORKBOOK_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True)
class WorkbookSpec:
    filename: str
    importer_name: str
    parser: Callable[[Path], list[Any]]
    importer: Callable[..., Any]
    errors: tuple[type[Exception], ...]


WORKBOOKS: dict[str, WorkbookSpec] = {
    "especialidades": WorkbookSpec(
        "Especialidades-CargaMaster190626.xlsx",
        "specialty_master",
        parse_specialty_workbook,
        import_specialties,
        (SpecialtyImportError,),
    ),
    "medicamentos": WorkbookSpec(
        "Medicamento-cargaMaster25062026.xlsx",
        "medication_master",
        parse_medication_workbook,
        import_medications,
        (MedicationImportError,),
    ),
    "principios_activos": WorkbookSpec(
        "PrincipioActivoCargaMaster-22062026.xlsx",
        "active_ingredient_master",
        parse_active_ingredient_workbook,
        import_active_ingredients,
        (ActiveIngredientImportError,),
    ),
}


class WorkbookSheetPreview(BaseModel):
    name: str
    columns: int
    data_rows: int


class WorkbookPreview(BaseModel):
    workbook: str
    sha256: str
    size_bytes: int
    sheets: list[WorkbookSheetPreview]
    data_rows: int
    can_import: bool
    blocked_reason: str | None


class WorkbookImportResult(BaseModel):
    batch_id: str
    created: bool
    status: str
    sha256: str


def _spec(kind: str) -> WorkbookSpec:
    spec = WORKBOOKS.get(kind)
    if spec is None:
        raise HTTPException(status_code=404, detail="Tipo de maestro no admitido.")
    return spec


async def _save_request_body(request: Request, path: Path) -> tuple[str, int]:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_WORKBOOK_BYTES:
        raise HTTPException(status_code=413, detail="El Excel supera el límite de 256 MiB.")
    digest = hashlib.sha256()
    size = 0
    with path.open("wb") as target:
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_WORKBOOK_BYTES:
                raise HTTPException(status_code=413, detail="El Excel supera el límite de 256 MiB.")
            digest.update(chunk)
            target.write(chunk)
    if not size:
        raise HTTPException(status_code=400, detail="El fichero está vacío.")
    return digest.hexdigest(), size


async def _validated_upload(
    request: Request, spec: WorkbookSpec
) -> tuple[tempfile.TemporaryDirectory[str], Path, str, int]:
    temporary = tempfile.TemporaryDirectory(prefix="farmalidacion-import-")
    path = Path(temporary.name) / spec.filename
    try:
        content_hash, size = await _save_request_body(request, path)
    except Exception:
        temporary.cleanup()
        raise
    return temporary, path, content_hash, size


def _preview(path: Path, spec: WorkbookSpec) -> list[WorkbookSheetPreview]:
    try:
        parsed = spec.parser(path)
    except Exception as error:
        expected_errors = spec.errors + (
            ElementTree.ParseError,
            zipfile.BadZipFile,
            KeyError,
            OSError,
        )
        if not isinstance(error, expected_errors):
            raise
        raise HTTPException(
            status_code=422, detail=f"El libro no supera la validación: {error}"
        ) from error
    result: list[WorkbookSheetPreview] = []
    for sheet in parsed:
        sheet_name = sheet[1]
        headers = sheet[4]
        rows = sheet[6]
        result.append(
            WorkbookSheetPreview(name=sheet_name, columns=len(headers), data_rows=len(rows))
        )
    return result


@router.post("/{kind}/preview", response_model=WorkbookPreview)
async def preview_workbook(kind: str, request: Request) -> WorkbookPreview:
    """Analiza hojas y filas sin escribir datos de catálogo ni crear un lote."""
    spec = _spec(kind)
    temporary, path, content_hash, size = await _validated_upload(request, spec)
    try:
        sheets = await run_in_threadpool(_preview, path, spec)
        factory = request.app.state.session_factory

        def check_update_safety() -> bool:
            with factory() as session:
                return session.scalar(
                    select(ImportBatch.id).where(
                        ImportBatch.source_locator == spec.filename,
                        ImportBatch.importer_name == spec.importer_name,
                        ImportBatch.status == "completed",
                        ImportBatch.content_hash != content_hash,
                    ).limit(1)
                ) is None

        can_import = await run_in_threadpool(check_update_safety)
        return WorkbookPreview(
            workbook=spec.filename,
            sha256=content_hash,
            size_bytes=size,
            sheets=sheets,
            data_rows=sum(sheet.data_rows for sheet in sheets),
            can_import=can_import,
            blocked_reason=(
                None
                if can_import
                else (
                    "Este maestro ya está cargado. La sustitución queda bloqueada hasta "
                    "comparar y enlazar sus cambios sin duplicar registros."
                )
            ),
        )
    finally:
        temporary.cleanup()


@router.post("/{kind}", response_model=WorkbookImportResult)
async def import_workbook(
    kind: str,
    request: Request,
    expected_sha256: Annotated[str, Header(alias="X-Expected-SHA256")],
    actor_id: Annotated[str, Header(alias="X-Import-Actor")],
    reason: Annotated[str, Header(alias="X-Import-Reason")],
) -> WorkbookImportResult:
    """Importa sólo el mismo archivo validado previamente en la vista previa."""
    if request.app.state.settings.data_mode != "real":
        raise HTTPException(
            status_code=403,
            detail="La carga de maestros reales sólo está disponible en el entorno REAL.",
        )
    spec = _spec(kind)
    actor_id = unquote(actor_id).strip()
    reason = unquote(reason).strip()
    if not actor_id or len(actor_id) > 80 or not reason or len(reason) > 1000:
        raise HTTPException(status_code=422, detail="Indique responsable y motivo válidos.")
    temporary, path, content_hash, _size = await _validated_upload(request, spec)
    try:
        if not secrets.compare_digest(content_hash, expected_sha256.lower()):
            raise HTTPException(
                status_code=409, detail="El fichero ha cambiado desde la vista previa."
            )

        factory = request.app.state.session_factory

        def execute() -> WorkbookImportResult:
            with factory.begin() as session:
                prior_success = session.scalar(
                    select(ImportBatch.id).where(
                        ImportBatch.source_locator == spec.filename,
                        ImportBatch.importer_name == spec.importer_name,
                        ImportBatch.status == "completed",
                        ImportBatch.content_hash != content_hash,
                    ).limit(1)
                )
                if prior_success is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "La sustitución de un maestro cargado requiere comparar y enlazar "
                            "sus cambios. No se ha modificado el catálogo."
                        ),
                    )
                result = spec.importer(session, path)
                batch = session.get(ImportBatch, result.batch_id)
                if batch is None:
                    raise RuntimeError("El importador no devolvió un lote persistido.")
                if result.created:
                    batch.started_by = actor_id
                    batch.reason = reason
                return WorkbookImportResult(
                    batch_id=batch.id,
                    created=result.created,
                    status=batch.status,
                    sha256=content_hash,
                )

        return await run_in_threadpool(execute)
    finally:
        temporary.cleanup()
