"""Utilidades compartidas para las pruebas de la experiencia de revisión.

Regla de datos del proyecto: el corpus real (`data/local/real.db`) **nunca** es
entorno de escritura. Toda prueba que decida, edite bloques, mida tiempos o
mute estado construye su propia base a partir del esquema declarado en
`models.Base`, que es el mismo esquema que tiene el corpus real. Así la prueba
se ejecuta sobre la estructura real sin poner en riesgo el dato real.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_validator_api.models import (
    Base,
    BlockInstance,
    FieldValue,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
)


@pytest.fixture
def master_data_directory() -> Path:
    """Directorio de maestros reales, configurable sin copiar los Excel."""
    configured = os.environ.get("FARMALIDACION_MASTER_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    root = Path(__file__).resolve().parents[2]
    checked_in = root / "data" / "reference" / "raw"
    external_base = root.parent / "Catalogo_campos_clinicos_medicamentos" / "base"
    return (
        checked_in
        if (checked_in / "PrincipioActivoCargaMaster-22062026.xlsx").is_file()
        else external_base
    )


@pytest.fixture
def scratch_db_url(tmp_path: Path) -> str:
    """Base vacía con el esquema real. Desechable y aislada por prueba."""
    url = f"sqlite:///{(tmp_path / 'scratch.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


def seed_reviewable_record(
    session: Session,
    *,
    record_id: str = "rec-1",
    entity_type: str = "active_ingredient",
    block_type: str = "active_ingredient_general",
    occurrences: int = 1,
    fields: tuple[tuple[str, str | None], ...] = (
        ("DESCRIPCION", "ácido nicotínico"),
        ("ACTIVO", "N"),
    ),
    literal_text: str | None = "Fragmento literal de la fuente.",
) -> TargetRecord:
    """Siembra un registro revisable con procedencia completa.

    Reproduce la forma que tiene un registro del corpus real: un `TargetRecord`
    con ocurrencias explícitas, valores con `logical_state` y cada valor atado a
    un `SourceFragment` a través de `ValueProvenance`. Sin ese encadenamiento la
    evaluación de conflicto falla, que es exactamente lo que ocurre en real.
    """
    document = SourceDocument(id=f"doc-{record_id}", source_type="master_excel", name="Maestro")
    version = SourceDocumentVersion(
        id=f"ver-{record_id}",
        document_id=document.id,
        content_hash="0" * 64,
        source_version="v1",
        source_locator="Maestro.xlsx",
        acquired_at=datetime.now(UTC),
    )
    session.add_all([document, version])

    record = TargetRecord(id=record_id, entity_type=entity_type)
    session.add(record)

    for ordinal in range(1, occurrences + 1):
        fragment = SourceFragment(
            id=f"frag-{record_id}-{ordinal}",
            document_version_id=version.id,
            locator_type="excel_row",
            locator=f'{{"sheet": "Hoja1", "row": {ordinal}}}',
            literal_text=literal_text,
        )
        block = BlockInstance(
            id=f"blk-{record_id}-{ordinal}",
            target_record_id=record.id,
            block_type=block_type,
            ordinal=ordinal,
            source_fragment_id=fragment.id,
        )
        session.add_all([fragment, block])
        for index, (name, value) in enumerate(fields):
            field = FieldValue(
                id=f"fv-{record_id}-{ordinal}-{index}",
                block_instance_id=block.id,
                field_name=name,
                literal_value=value,
                observed_type="texto",
                logical_state="valued" if value is not None else "empty",
            )
            session.add(field)
            session.add(
                ValueProvenance(
                    id=f"vp-{record_id}-{ordinal}-{index}",
                    field_value_id=field.id,
                    source_fragment_id=fragment.id,
                    provenance_role="master_baseline",
                )
            )
    session.commit()
    return record
