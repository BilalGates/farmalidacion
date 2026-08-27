from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.fixtures import FixtureConflictError, load_demo_fixture
from pharma_validator_api.main import create_app
from pharma_validator_api.models import Base, BlockInstance, FieldValue

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'data' / 'examples' / 'omeprazole-demo.json'
RECORD_ID = '00000000-0000-4000-8000-000000000101'


def create_database(path: Path) -> str:
    url = f'sqlite:///{path.as_posix()}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


def test_fixture_is_idempotent_and_preserves_duplicate_occurrences(tmp_path: Path) -> None:
    url = create_database(tmp_path / 'fixture.db')
    engine = create_engine(url)
    with Session(engine) as session:
        assert load_demo_fixture(session, FIXTURE) is True
        assert load_demo_fixture(session, FIXTURE) is False
        assert session.scalar(select(func.count()).select_from(BlockInstance)) == 2
        values = session.scalars(select(FieldValue).order_by(FieldValue.id)).all()
        assert [value.literal_value for value in values] == ['omeprazol', 'omeprazol']
        assert values[0].block_instance_id != values[1].block_instance_id
    engine.dispose()


def test_fixture_rejects_collision_without_overwriting(tmp_path: Path) -> None:
    url = create_database(tmp_path / 'collision.db')
    engine = create_engine(url)
    with Session(engine) as session:
        load_demo_fixture(session, FIXTURE)
        value = session.get(FieldValue, '00000000-0000-4000-8000-000000000301')
        assert value is not None
        value.literal_value = 'contenido distinto'
        session.commit()
        with pytest.raises(FixtureConflictError, match='contenido distinto'):
            load_demo_fixture(session, FIXTURE)
        assert value.literal_value == 'contenido distinto'
    engine.dispose()


def test_record_api_returns_ordered_occurrences_with_separate_provenance(
    tmp_path: Path,
) -> None:
    url = create_database(tmp_path / 'api.db')
    settings = Settings(
        env='test',
        database_url=url,
        load_demo_fixture=True,
        demo_fixture_path=FIXTURE,
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get(f'/records/{RECORD_ID}')
        missing = client.get('/records/does-not-exist')

    assert response.status_code == 200
    payload = response.json()
    assert payload['id'] == RECORD_ID
    assert [block['ordinal'] for block in payload['blocks']] == [1, 2]
    assert len({block['id'] for block in payload['blocks']}) == 2
    assert [
        block['values'][0]['literal_value'] for block in payload['blocks']
    ] == ['omeprazol', 'omeprazol']
    assert [
        block['values'][0]['provenance'][0]['locator'] for block in payload['blocks']
    ] == ['composition/1', 'composition/2']
    assert all(
        block['values'][0]['provenance'][0]['document_version_id']
        == '00000000-0000-4000-8000-000000000002'
        for block in payload['blocks']
    )
    assert missing.status_code == 404
    assert missing.json() == {'detail': 'Registro no encontrado.'}
