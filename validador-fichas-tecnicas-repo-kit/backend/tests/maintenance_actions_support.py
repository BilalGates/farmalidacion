"""Siembra y cliente CIMA falso para las pruebas de acciones de novedades."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from pharma_validator_api.cima_client import CimaClientError, CimaResponse
from pharma_validator_api.maintenance_actions import SPECIALTY_WORKBOOK
from pharma_validator_api.models import (
    BlockInstance,
    DocumentRecordLink,
    FieldValue,
    ImportBatch,
    ImportedSourceSheet,
    MaintenanceChangeEvent,
    MaintenanceChangeEventTarget,
    MedicationCatalogIdentity,
    SourceDocument,
    SourceDocumentVersion,
    TargetRecord,
)

HEADER = ["BN_IDEXTERNO", "ID_ESPECIALIDAD", "CODIGO_NACIONAL", "DESCRIPCION_PRESCRIPCION",
          "ME_DESCRIPCION", "DESCRIPCION_GESTION", "ACTIVO"]


def response(url: str, payload: object) -> CimaResponse:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return CimaResponse(
        url=url, status_code=200, headers=(("Content-Type", "application/json"),),
        body=body, content_sha256=hashlib.sha256(body).hexdigest(),
        fetched_at="2026-10-30T09:00:00+00:00", from_cache=False,
    )


class FakeCima:
    """Cliente falso: `presentacion` por CN y `presentaciones` por nregistro."""

    def __init__(self, *, states: dict[str, Any] | None = None,
                 lists: dict[str, Any] | None = None, down: bool = False) -> None:
        self.states = states or {}
        self.lists = lists or {}
        self.down = down
        self.calls: list[str] = []

    def __enter__(self) -> FakeCima:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def presentation(self, *, cn: str, use_cache: bool = True) -> CimaResponse:
        self.calls.append(f"presentacion:{cn}")
        if self.down or cn not in self.states:
            raise CimaClientError("CIMA no responde")
        return response(f"https://cima.aemps.es/cima/rest/presentacion/{cn}", self.states[cn])

    def presentations(self, *, nregistro: str, pagina: int = 1) -> CimaResponse:
        self.calls.append(f"presentaciones:{nregistro}:{pagina}")
        if self.down or nregistro not in self.lists:
            raise CimaClientError("CIMA no responde")
        return response(
            f"https://cima.aemps.es/cima/rest/presentaciones?nregistro={nregistro}",
            self.lists[nregistro],
        )


def listing(*rows: tuple[str, str]) -> dict[str, Any]:
    return {
        "totalFilas": len(rows), "pagina": 1, "tamanioPagina": 25,
        "resultados": [{"cn": cn, "nombre": name, "nregistro": "9001"} for cn, name in rows],
    }


def seed_catalog_record(
    session: Session, *, record_id: str = "rec-1", cn: str = "600000", activo: str = "S",
    demo: bool = False,
) -> tuple[TargetRecord, MedicationCatalogIdentity, FieldValue]:
    record = TargetRecord(id=record_id, entity_type="specialty")
    session.add(record)
    block = BlockInstance(
        id=f"blk-{record_id}", target_record_id=record_id, block_type="specialty_general",
        ordinal=1,
    )
    session.add_all([block])
    session.flush()
    values = {}
    for index, (name, value) in enumerate(
        (("CODIGO_NACIONAL", cn), ("ACTIVO", activo)), start=1
    ):
        values[name] = FieldValue(
            id=f"fv-{record_id}-{name}", block_instance_id=block.id, field_name=name,
            source_column_index=index, literal_value=value, observed_type="texto",
            logical_state="valued",
        )
        session.add(values[name])
    identity = MedicationCatalogIdentity(
        id=f"ident-{record_id}", identity_type="presentation", code=cn,
        display_name=f"Medicamento {record_id}", target_record_id=record_id,
        source_system="master_excel", source_version="v1", active=True, version=1,
    )
    session.add(identity)
    if demo:
        document = SourceDocument(id=f"demo-doc-{record_id}", source_type="demo_showcase", name="x")
        version = SourceDocumentVersion(
            id=f"demo-ver-{record_id}", document_id=document.id, content_hash="0" * 64,
            source_locator="demo", acquired_at=datetime.now(UTC),
        )
        session.add_all([document, version])
        session.flush()
        session.add(DocumentRecordLink(
            document_version_id=version.id, target_record_id=record_id, link_type="demo"
        ))
    session.commit()
    return record, identity, values["ACTIVO"]


def seed_event(
    session: Session, *, areas: list[str], change_type: int = 3, nregistro: str = "9001",
    epoch: int = 1000, targets: tuple[tuple[str, str], ...] = (("rec-1", "600000"),),
    suffix: str = "a",
) -> MaintenanceChangeEvent:
    event = MaintenanceChangeEvent(
        id=(suffix * 64)[:64], nregistro=nregistro, occurred_at_epoch=epoch,
        change_type=change_type, areas_json=json.dumps(sorted(areas)),
        source_sha256="b" * 64, fetched_at="2026-10-30T08:00:00+00:00",
        old_version_id=None, new_version_id=None, diff_json=None, affected_field_count=0,
        recorded_at=datetime.now(UTC),
    )
    session.add(event)
    session.flush()
    for record_id, cn in targets:
        session.add(MaintenanceChangeEventTarget(
            id=f"{event.id[:8]}-{record_id}", event_id=event.id, target_record_id=record_id,
            national_code=cn,
        ))
    session.commit()
    return event


def seed_master_header(session: Session, header: list[str] | None = None) -> None:
    batch = ImportBatch(
        id="batch-esp", source_system="master", source_locator=SPECIALTY_WORKBOOK,
        source_version="v1", content_hash="1" * 64, importer_name="specialty_master",
        importer_version="1.0.0", status="completed", created_at=datetime.now(UTC),
    )
    session.add(batch)
    session.flush()
    names = header or HEADER
    session.add(ImportedSourceSheet(
        id="sheet-esp-general", import_batch_id=batch.id, sheet_name="General",
        sheet_ordinal=1, header_row_number=1, data_row_count=1, material_value_count=1,
        header_payload=json.dumps([
            {"column": index, "formula": None, "header": name, "literal_value": name,
             "observed_type": "shared_string"}
            for index, name in enumerate(names, start=1)
        ]),
    ))
    session.commit()
