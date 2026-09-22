from conftest import seed_reviewable_record
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.catalog_projection import project_target_records
from pharma_validator_api.models import (
    MedicationCatalogIdentity,
    MedicationCatalogRelation,
    MedicationCatalogRevision,
    TargetRecordLink,
)


def _seed_projection_graph(session: Session) -> None:
    seed_reviewable_record(
        session,
        record_id="pa-1",
        entity_type="active_ingredient",
        fields=(("PA_DESCRIPCION", "amoxicilina"), ("PA_IDEXTERNO", "PA-10")),
    )
    seed_reviewable_record(
        session,
        record_id="med-1",
        entity_type="medication",
        fields=(("ME_DESCRIPCION", "amoxicilina + ácido clavulánico"), ("ME_IDEXTERNO", "M-2")),
    )
    seed_reviewable_record(
        session,
        record_id="esp-1",
        entity_type="specialty",
        fields=(("ES_DESCRIPCION", "Producto, 20 comprimidos"), ("CODIGO_NACIONAL", "0654789")),
    )
    session.add_all(
        [
            TargetRecordLink(
                id="composition",
                source_record_id="med-1",
                target_record_id="pa-1",
                link_type="composition_active_ingredient",
                source_fragment_id="frag-med-1-1",
            ),
            TargetRecordLink(
                id="specialty",
                source_record_id="esp-1",
                target_record_id="med-1",
                link_type="specialty_medication",
                source_fragment_id="frag-esp-1-1",
            ),
        ]
    )
    session.commit()


def test_dry_run_reports_without_writing(scratch_db_url: str) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        _seed_projection_graph(session)
        report = project_target_records(session)

        assert report.projectable_identities == 3
        assert report.projectable_relations == 1
        assert report.created_identities == 0
        assert {item.code for item in report.diagnostics} == {"MISSING_DCPF_BRIDGE"}
        assert session.scalar(select(func.count()).select_from(MedicationCatalogIdentity)) == 0


def test_apply_is_idempotent_and_preserves_source_literal(scratch_db_url: str) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        _seed_projection_graph(session)
        first = project_target_records(session, apply=True)
        session.commit()
        second = project_target_records(session, apply=True)
        session.commit()

        assert first.created_identities == 3
        assert first.created_relations == 1
        assert second.created_identities == 0
        assert second.existing_identities == 3
        assert second.existing_relations == 1
        presentation = session.scalar(
            select(MedicationCatalogIdentity).where(
                MedicationCatalogIdentity.identity_type == "presentation"
            )
        )
        assert presentation is not None
        assert presentation.code == "065478"
        assert presentation.source_literal == "0654789"
        assert session.scalar(select(func.count()).select_from(MedicationCatalogRevision)) == 3
        assert session.scalar(select(func.count()).select_from(MedicationCatalogRelation)) == 1


def test_invalid_cn_and_missing_name_are_diagnostics(scratch_db_url: str) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(
            session,
            record_id="bad-cn",
            entity_type="specialty",
            fields=(("ES_DESCRIPCION", "Presentación"), ("CODIGO_NACIONAL", "12-3456")),
        )
        seed_reviewable_record(
            session,
            record_id="no-name",
            entity_type="medication",
            fields=(("ME_IDEXTERNO", "M-3"),),
        )
        report = project_target_records(session, apply=True)
        session.commit()

        assert {item.code for item in report.diagnostics} == {
            "INVALID_NATIONAL_CODE",
            "MISSING_DISPLAY_NAME",
        }
        assert session.scalar(select(func.count()).select_from(MedicationCatalogIdentity)) == 0
