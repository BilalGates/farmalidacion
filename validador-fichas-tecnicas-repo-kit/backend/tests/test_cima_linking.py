import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pharma_validator_api.cima_client import CimaResponse
from pharma_validator_api.cima_linking import link_cima_to_master
from pharma_validator_api.document_versions import ArtifactInput, persist_cima_document_version
from pharma_validator_api.models import BlockInstance, DocumentRecordLink, FieldValue, TargetRecord


def response(payload: object) -> CimaResponse:
    body = json.dumps(payload).encode()
    return CimaResponse(
        "https://cima.test",
        200,
        (),
        body,
        __import__("hashlib").sha256(body).hexdigest(),
        "2026-09-09T00:00:00Z",
        True,
    )


def test_only_exact_unambiguous_cn_is_linked_and_rerun_is_idempotent(scratch_db_url: str) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        for suffix, cn in (("one", "600001"), ("two", "600002")):
            session.add(TargetRecord(id=f"record-{suffix}", entity_type="specialty"))
            session.add(
                BlockInstance(
                    id=f"block-{suffix}",
                    target_record_id=f"record-{suffix}",
                    block_type="GENERAL",
                    ordinal=1,
                )
            )
            session.add(
                FieldValue(
                    id=f"field-{suffix}",
                    block_instance_id=f"block-{suffix}",
                    field_name="CODIGO_NACIONAL",
                    literal_value=cn,
                    observed_type="text",
                    logical_state="valued",
                )
            )
        session.commit()
        for nregistro, cn in (("R1", "600001"), ("R2", "600002"), ("R3", "600002")):
            persist_cima_document_version(
                session,
                nregistro=nregistro,
                document_type=1,
                artifacts=(
                    ArtifactInput(
                        "metadata", 1, "medicamento", response({"presentaciones": [{"cn": cn}]})
                    ),
                ),
            )
        first = link_cima_to_master(session)
        second = link_cima_to_master(session)
        assert first.created_links == 1
        assert first.ambiguous_cn == ("600002",)
        assert second.created_links == 0
        assert second.existing_links == 1
        links = session.scalars(select(DocumentRecordLink)).all()
        assert [(item.target_record_id, item.link_type) for item in links] == [
            ("record-one", "exact_national_code_v1")
        ]
    engine.dispose()
