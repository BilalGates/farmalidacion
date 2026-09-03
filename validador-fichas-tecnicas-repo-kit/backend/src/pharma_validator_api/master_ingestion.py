"""Orquestación de la ingesta de los maestros Excel existentes.

Fase 3 ya implementa los importadores por fichero. Lo que faltaba era un punto
de entrada ejecutable que los aplique sobre una misma base de datos en el orden
correcto: el importador de medicamentos resuelve sus enlaces de composición
buscando principios activos ya presentes, y el de especialidades resuelve los
suyos buscando medicamentos ya presentes. Invertir el orden no falla de forma
ruidosa: produce enlaces vacíos y filas en cuarentena, así que el orden se fija
aquí en lugar de dejarlo a quien llame.

Este módulo no reimplementa ninguna ingesta: sólo compone las existentes y
resume su resultado de forma uniforme.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from sqlalchemy.orm import Session

from pharma_validator_api.active_ingredient_importer import (
    SOURCE_FILENAME as ACTIVE_INGREDIENT_FILENAME,
)
from pharma_validator_api.active_ingredient_importer import import_active_ingredients
from pharma_validator_api.catalog_importer import CATALOG_FILENAME, import_catalog
from pharma_validator_api.medication_importer import (
    SOURCE_FILENAME as MEDICATION_FILENAME,
)
from pharma_validator_api.medication_importer import import_medications
from pharma_validator_api.specialty_importer import (
    SOURCE_FILENAME as SPECIALTY_FILENAME,
)
from pharma_validator_api.specialty_importer import import_specialties


class MasterIngestionError(RuntimeError):
    """La ingesta no puede continuar de forma segura."""


@dataclass(frozen=True)
class MasterSource:
    """Un maestro Excel y el importador que lo consume."""

    key: str
    filename: str
    importer: Callable[..., object]


# El orden es una dependencia real de datos, no una preferencia de estilo:
#   catálogo            -> define los campos declarados
#   principios activos  -> destinos que el maestro de medicamentos enlaza
#   medicamentos        -> destinos que el maestro de especialidades enlaza
#   especialidades      -> hoja dependiente final
MASTER_SOURCES: tuple[MasterSource, ...] = (
    MasterSource("catalog", CATALOG_FILENAME, import_catalog),
    MasterSource("active_ingredients", ACTIVE_INGREDIENT_FILENAME, import_active_ingredients),
    MasterSource("medications", MEDICATION_FILENAME, import_medications),
    MasterSource("specialties", SPECIALTY_FILENAME, import_specialties),
)


@dataclass(frozen=True)
class SourceIngestionReport:
    """Resultado uniforme de un maestro, derivado del resultado del importador."""

    key: str
    filename: str
    content_hash: str
    batch_id: str
    status: str
    created: bool
    metrics: dict[str, int]

    @property
    def skipped_as_duplicate(self) -> bool:
        """El lote ya existía: la reejecución no vuelve a insertar nada."""
        return not self.created


@dataclass(frozen=True)
class MasterIngestionReport:
    sources: tuple[SourceIngestionReport, ...] = field(default_factory=tuple)

    @property
    def failed(self) -> tuple[SourceIngestionReport, ...]:
        return tuple(item for item in self.sources if item.status == "failed")

    @property
    def ok(self) -> bool:
        return not self.failed


_METRIC_FIELDS: tuple[str, ...] = (
    "sheets",
    "source_rows",
    "occurrences",
    "values",
    "imported_fields",
    "quarantined_rows",
    "orphan_parent_identifiers",
    "diagnostics",
    "composition_links",
    "medication_links",
)


def _metrics(result: object) -> dict[str, int]:
    """Extrae las métricas presentes; cada importador expone un subconjunto."""
    collected: dict[str, int] = {}
    for name in _METRIC_FIELDS:
        value = getattr(result, name, None)
        if isinstance(value, int):
            collected[name] = value
    return collected


def resolve_sources(
    raw_directory: Path,
    *,
    only: Sequence[str] | None = None,
) -> tuple[MasterSource, ...]:
    """Selecciona los maestros a importar conservando el orden de dependencia."""
    selected = MASTER_SOURCES
    if only:
        requested = tuple(dict.fromkeys(only))
        known = {source.key for source in MASTER_SOURCES}
        unknown = [key for key in requested if key not in known]
        if unknown:
            raise MasterIngestionError(
                f"Maestros desconocidos: {', '.join(sorted(unknown))}. "
                f"Disponibles: {', '.join(source.key for source in MASTER_SOURCES)}."
            )
        selected = tuple(source for source in MASTER_SOURCES if source.key in set(requested))
    missing = [
        source.filename
        for source in selected
        if not (raw_directory / source.filename).is_file()
    ]
    if missing:
        raise MasterIngestionError(
            "Faltan ficheros maestros en "
            f"{raw_directory}: {', '.join(sorted(missing))}."
        )
    return selected


def ingest_masters(
    session: Session,
    raw_directory: Path,
    *,
    only: Sequence[str] | None = None,
    source_version: str | None = None,
) -> MasterIngestionReport:
    """Importa los maestros en orden de dependencia sobre una misma sesión.

    Es idempotente por delegación: cada importador reutiliza su lote si el
    contenido del fichero no ha cambiado, de modo que una segunda ejecución no
    duplica datos. Un maestro que falle no interrumpe a los demás, pero queda
    registrado como `failed` en el informe.
    """
    sources = resolve_sources(raw_directory, only=only)
    reports: list[SourceIngestionReport] = []
    for source in sources:
        path = raw_directory / source.filename
        content_hash = sha256(path.read_bytes()).hexdigest()
        result = source.importer(session, path, source_version=source_version)
        session.commit()
        reports.append(
            SourceIngestionReport(
                key=source.key,
                filename=source.filename,
                content_hash=content_hash,
                batch_id=str(getattr(result, "batch_id", "")),
                status=str(getattr(result, "status", "unknown")),
                created=bool(getattr(result, "created", False)),
                metrics=_metrics(result),
            )
        )
    return MasterIngestionReport(tuple(reports))
