from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.catalog_demo_fixture import load_catalog_demo_fixture
from pharma_validator_api.models import (
    MedicationCatalogClassification,
    MedicationCatalogIdentity,
    MedicationCatalogRelation,
)

FIXTURE = Path(__file__).parents[2] / "data/examples/medication-domain-acceptance.json"


def test_demo_catalog_loads_full_multicomponent_hierarchy_idempotently(
    scratch_db_url: str,
) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        load_catalog_demo_fixture(session, FIXTURE)
        load_catalog_demo_fixture(session, FIXTURE)

        assert session.scalar(select(func.count()).select_from(MedicationCatalogIdentity)) == 11
        assert session.scalar(select(func.count()).select_from(MedicationCatalogRelation)) == 11
        assert (
            session.scalar(select(func.count()).select_from(MedicationCatalogClassification)) == 6
        )
        dcp_id = session.scalar(
            select(MedicationCatalogIdentity.id).where(
                MedicationCatalogIdentity.identity_type == "dcp"
            )
        )
        assert dcp_id is not None
        composition = list(
            session.scalars(
                select(MedicationCatalogRelation)
                .where(MedicationCatalogRelation.source_identity_id == dcp_id)
                .where(MedicationCatalogRelation.relation_type == "dcp_active_ingredient")
                .order_by(MedicationCatalogRelation.ordinal)
            )
        )
        assert [item.ordinal for item in composition] == [1, 2]
