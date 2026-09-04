"""Separación entre datos REALES y datos DEMO.

La distinción no se inventa aquí: se lee del origen documental de cada
registro. El conjunto de demostración se carga con documentos cuyo
`source_type` es `demo_showcase` (ver `fixtures.load_showcase_fixture`),
mientras que los importadores de maestros crean documentos `master_excel`.

Mezclarlos silenciosamente sería el peor fallo posible de esta vertical: un
revisor no puede distinguir un valor de demostración de uno importado si la
interfaz no se lo dice, así que el origen se propaga hasta la respuesta.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from pharma_validator_api.models import (
    DocumentRecordLink,
    SourceDocument,
    SourceDocumentVersion,
    TargetRecord,
)

#: `source_type` de los documentos que produce el conjunto de demostración.
DEMO_SOURCE_TYPE = "demo_showcase"


class DataOrigin(StrEnum):
    """Origen de un registro, tal y como se expone en la API."""

    REAL = "real"
    DEMO = "demo"


def _demo_record_ids() -> Select[tuple[str]]:
    """Identificadores de los registros enlazados a un documento de demostración.

    Se expresa como conjunto (`IN`) y no como `EXISTS` correlacionado: con los
    maestros reales cargados, la variante correlacionada recorría la tabla de
    enlaces una vez por registro y la consulta no terminaba. Aquí los enlaces se
    recorren una sola vez.
    """
    return (
        select(DocumentRecordLink.target_record_id)
        .join(
            SourceDocumentVersion,
            DocumentRecordLink.document_version_id == SourceDocumentVersion.id,
        )
        .join(SourceDocument, SourceDocumentVersion.document_id == SourceDocument.id)
        .where(SourceDocument.source_type == DEMO_SOURCE_TYPE)
    )


def apply_origin_filter(
    statement: Select[tuple[str]], origin: DataOrigin | None
) -> Select[tuple[str]]:
    """Restringe una consulta de registros al origen indicado.

    Un registro sin ningún enlace documental se considera REAL: no procede del
    fixture de demostración, y ocultarlo lo haría invisible sin explicación.
    """
    if origin is None:
        return statement
    demo_ids = _demo_record_ids()
    if origin is DataOrigin.DEMO:
        return statement.where(TargetRecord.id.in_(demo_ids))
    return statement.where(TargetRecord.id.not_in(demo_ids))


def origins_for_records(session: Session, record_ids: list[str]) -> dict[str, DataOrigin]:
    """Origen de cada registro en una sola consulta."""
    if not record_ids:
        return {}
    demo_ids = set(
        session.scalars(
            select(TargetRecord.id)
            .where(TargetRecord.id.in_(record_ids))
            .where(TargetRecord.id.in_(_demo_record_ids()))
        ).all()
    )
    return {
        record_id: DataOrigin.DEMO if record_id in demo_ids else DataOrigin.REAL
        for record_id in record_ids
    }


def origin_for_record(session: Session, record_id: str) -> DataOrigin:
    return origins_for_records(session, [record_id]).get(record_id, DataOrigin.REAL)
