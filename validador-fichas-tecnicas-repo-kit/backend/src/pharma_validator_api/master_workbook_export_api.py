"""Controlled download of the three source workbooks with maintained cells."""

from __future__ import annotations

import shutil
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from pharma_validator_api.master_workbook_export import (
    MasterWorkbookExportError,
    export_master_workbooks,
)
from pharma_validator_api.queue_api import SettingsDependency
from pharma_validator_api.records import SessionDependency

router = APIRouter(prefix="/master-workbooks", tags=["exportación de maestros"])


def _remove_run_directory(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


@router.post("/export")
def download_maintained_masters(
    background_tasks: BackgroundTasks,
    session: SessionDependency,
    settings: SettingsDependency,
) -> FileResponse:
    """Return all three preserved workbooks as one ZIP, only when explicitly enabled."""
    if not settings.enable_master_workbook_export:
        raise HTTPException(404, "La exportación de los maestros está desactivada.")
    if settings.master_data_directory is None:
        raise HTTPException(503, "No se ha configurado la carpeta de los tres maestros.")
    source_directory = Path(settings.master_data_directory)
    if not source_directory.is_dir():
        raise HTTPException(503, "La carpeta configurada de maestros no está disponible.")

    run_directory = Path(settings.export_artifact_dir).resolve() / str(uuid.uuid4())
    books_directory = run_directory / "libros"
    archive_path = run_directory / "maestros_farmalidacion.zip"
    try:
        run_directory.mkdir(parents=True, exist_ok=False)
        results = export_master_workbooks(session, source_directory, books_directory)
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for result in results:
                archive.write(result.output, arcname=result.filename)
    except MasterWorkbookExportError as error:
        _remove_run_directory(run_directory)
        raise HTTPException(409, str(error)) from error
    except (OSError, zipfile.BadZipFile) as error:
        _remove_run_directory(run_directory)
        raise HTTPException(503, "No se pudo preparar el paquete de los maestros.") from error

    background_tasks.add_task(_remove_run_directory, run_directory)
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename="maestros_farmalidacion.zip",
    )
