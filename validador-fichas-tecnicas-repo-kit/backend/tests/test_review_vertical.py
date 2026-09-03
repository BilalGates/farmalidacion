"""Pruebas de la vertical de revisión: listado, ficha, decisión y persistencia.

Lo que estas pruebas protegen no es la pantalla, sino que la capa HTTP **no
puede saltarse** las barreras que ya viven en los módulos puros. Una vertical de
demostración es exactamente donde es tentador relajarlas.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.fixtures import FixtureConflictError, load_showcase_fixture
from pharma_validator_api.main import create_app
from pharma_validator_api.models import (
    Base,
    BlockInstance,
    ImmutableHistoryError,
    TargetRecord,
    ValidationDecisionRecord,
)

ROOT = Path(__file__).resolve().parents[2]
SHOWCASE = ROOT / 'data' / 'examples' / 'showcase-demo.json'
REVIEWERS = ('ana:Ana Ruiz', 'luis:Luis Marín')


def create_database(path: Path) -> str:
    url = f'sqlite:///{path.as_posix()}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    url = create_database(tmp_path / 'vertical.db')
    settings = Settings(
        env='test',
        database_url=url,
        load_showcase_fixture=True,
        showcase_fixture_path=SHOWCASE,
        reviewers=REVIEWERS,
        _env_file=None,
    )
    return TestClient(create_app(settings))


def count_decisions(client: TestClient, value_id: str) -> int:
    """Número de decisiones registradas sobre un campo."""
    for item in client.get('/records').json()['items']:
        detail = client.get(f'/records/{item["id"]}').json()
        for block in detail['blocks']:
            for value in block['values']:
                if value['id'] == value_id:
                    return len(value['history'])
    raise AssertionError(f'Campo no encontrado: {value_id}')


def field_id(client: TestClient, external_id: str, field_name: str) -> str:
    record = next(
        item
        for item in client.get('/records').json()['items']
        if item['primary_identifier'] == external_id
    )
    detail = client.get(f'/records/{record["id"]}').json()
    return next(
        value['id']
        for block in detail['blocks']
        for value in block['values']
        if value['field_name'] == field_name
    )


def test_showcase_fixture_is_idempotent_and_marked_as_demo(tmp_path: Path) -> None:
    """El conjunto DEMO se carga dos veces sin duplicar y se declara como DEMO."""
    url = create_database(tmp_path / 'demo.db')
    engine = create_engine(url)
    with Session(engine) as session:
        assert load_showcase_fixture(session, SHOWCASE) is True
        assert load_showcase_fixture(session, SHOWCASE) is False
        assert session.scalar(select(func.count()).select_from(TargetRecord)) == 5
        # Los bloques repetibles conservan ocurrencias separadas.
        blocks = session.scalars(
            select(BlockInstance).where(BlockInstance.block_type == 'Composición')
        ).all()
        assert len(blocks) == 10
        assert {block.ordinal for block in blocks} == {1, 2}
    engine.dispose()


def test_showcase_fixture_refuses_to_overwrite_divergent_content(tmp_path: Path) -> None:
    url = create_database(tmp_path / 'collision.db')
    engine = create_engine(url)
    with Session(engine) as session:
        load_showcase_fixture(session, SHOWCASE)
        record = session.scalars(select(TargetRecord).limit(1)).one()
        record.entity_type = 'otro'
        session.commit()
        with pytest.raises(FixtureConflictError):
            load_showcase_fixture(session, SHOWCASE)
        assert record.entity_type == 'otro'
    engine.dispose()


def test_demo_records_declare_a_demo_source_system(client: TestClient) -> None:
    """Un dato DEMO debe ser distinguible de uno importado, no parecerse a él."""
    with client:
        items = client.get('/records').json()['items']
        for item in items:
            detail = client.get(f'/records/{item["id"]}').json()
            assert all(
                identifier['source_system'] == 'demo_showcase'
                for identifier in detail['external_identifiers']
            )


def test_list_supports_search_and_state_filter(client: TestClient) -> None:
    with client:
        assert client.get('/records').json()['total'] == 5
        assert client.get('/records', params={'q': 'metotrexato'}).json()['total'] == 1
        assert client.get('/records', params={'q': 'DEMO-0001'}).json()['total'] == 1
        assert client.get('/records', params={'q': 'no-existe'}).json()['total'] == 0
        conflicted = client.get('/records', params={'estado': 'requiere_revision'}).json()
        assert conflicted['total'] == 1
        assert conflicted['items'][0]['primary_identifier'] == 'DEMO-0002'


def test_conflicting_sources_are_reported_without_being_resolved(client: TestClient) -> None:
    """La discrepancia se detecta entre fuentes y ninguna prevalece sola."""
    with client:
        record = next(
            item
            for item in client.get('/records').json()['items']
            if item['primary_identifier'] == 'DEMO-0002'
        )
        assert record['conflict_count'] == 1
        detail = client.get(f'/records/{record["id"]}').json()
        cantidades = [
            value
            for block in detail['blocks']
            for value in block['values']
            if value['field_name'] == 'CANTIDAD'
        ]
        # Ambas afirmaciones se conservan, cada una con su procedencia.
        assert len(cantidades) == 2
        assert {value['literal_value'] for value in cantidades} == {
            '2,5 mg',
            '2,5 mg/comprimido',
        }
        assert all(
            value['conflict_status'] == 'unresolved_pending_priority'
            for value in cantidades
        )
        roles = {
            item['provenance_role'] for value in cantidades for item in value['provenance']
        }
        assert roles == {'master_baseline', 'cima_structured'}


def test_repeated_occurrences_are_not_collapsed(client: TestClient) -> None:
    with client:
        record = client.get('/records').json()['items'][0]
        detail = client.get(f'/records/{record["id"]}').json()
        compositions = [
            block for block in detail['blocks'] if block['block_type'] == 'Composición'
        ]
        assert [block['ordinal'] for block in compositions] == [1, 2]
        assert len({block['id'] for block in compositions}) == 2


def test_decision_is_persisted_and_changes_the_list_state(client: TestClient) -> None:
    """Recorrido de la demo: guardar una decisión y verla en el listado."""
    with client:
        value_id = field_id(client, 'DEMO-0001', 'ME_DESCRIPCION')
        response = client.post(
            f'/records/values/{value_id}/decisions',
            json={
                'state': 'confirmado',
                'reviewer_id': 'ana',
                'final_value': 'Omeprazol 20 mg cápsulas duras',
            },
        )
        assert response.status_code == 201
        assert response.json()['reviewer_assurance'] == 'declarada'

        record = next(
            item
            for item in client.get('/records').json()['items']
            if item['primary_identifier'] == 'DEMO-0001'
        )
        assert record['resolved_count'] == 1
        assert record['review_state'] == 'en_revision'
        assert record['last_reviewed_at'] is not None


def test_decision_survives_a_restart(tmp_path: Path) -> None:
    """Cerrar la aplicación no pierde el trabajo confirmado."""
    url = create_database(tmp_path / 'persist.db')
    settings = Settings(
        env='test',
        database_url=url,
        load_showcase_fixture=True,
        showcase_fixture_path=SHOWCASE,
        reviewers=REVIEWERS,
        _env_file=None,
    )
    with TestClient(create_app(settings)) as first:
        value_id = field_id(first, 'DEMO-0003', 'ATC')
        first.post(
            f'/records/values/{value_id}/decisions',
            json={'state': 'confirmado', 'reviewer_id': 'luis', 'final_value': 'L04AB04'},
        )

    with TestClient(create_app(settings)) as second:
        record = next(
            item
            for item in second.get('/records').json()['items']
            if item['primary_identifier'] == 'DEMO-0003'
        )
        assert record['resolved_count'] == 1
        detail = second.get(f'/records/{record["id"]}').json()
        atc = next(
            value
            for block in detail['blocks']
            for value in block['values']
            if value['field_name'] == 'ATC'
        )
        assert atc['validation_state'] == 'confirmado'
        assert atc['history'][0]['reviewer_id'] == 'luis'


def test_history_is_append_only_and_keeps_the_previous_decision(client: TestClient) -> None:
    """Una decisión posterior no borra la anterior: se apila."""
    with client:
        value_id = field_id(client, 'DEMO-0004', 'ATC')
        client.post(
            f'/records/values/{value_id}/decisions',
            json={'state': 'confirmado', 'reviewer_id': 'ana', 'final_value': 'J01CA04'},
        )
        client.post(
            f'/records/values/{value_id}/decisions',
            json={
                'state': 'corregido',
                'reviewer_id': 'luis',
                'final_value': 'J01CA04 corregido',
                'comment': 'Corrección tras revisar la ficha.',
            },
        )
        record = next(
            item
            for item in client.get('/records').json()['items']
            if item['primary_identifier'] == 'DEMO-0004'
        )
        detail = client.get(f'/records/{record["id"]}').json()
        atc = next(
            value
            for block in detail['blocks']
            for value in block['values']
            if value['field_name'] == 'ATC'
        )
        assert [item['sequence'] for item in atc['history']] == [1, 2]
        assert [item['state'] for item in atc['history']] == ['confirmado', 'corregido']
        assert atc['validation_state'] == 'corregido'


def test_stored_decision_cannot_be_mutated(tmp_path: Path) -> None:
    """Sobrescribir una decisión borraría la autoría; el modelo lo impide."""
    url = create_database(tmp_path / 'immutable.db')
    settings = Settings(
        env='test',
        database_url=url,
        load_showcase_fixture=True,
        showcase_fixture_path=SHOWCASE,
        reviewers=REVIEWERS,
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        value_id = field_id(client, 'DEMO-0005', 'ATC')
        client.post(
            f'/records/values/{value_id}/decisions',
            json={'state': 'confirmado', 'reviewer_id': 'ana', 'final_value': 'C09AA02'},
        )
    engine = create_engine(url)
    with Session(engine) as session:
        stored = session.scalars(select(ValidationDecisionRecord)).one()
        stored.state = 'descartado'
        with pytest.raises(ImmutableHistoryError):
            session.commit()
    engine.dispose()


# --- Barreras clínicas: la capa HTTP no puede saltárselas -------------------


def test_decision_without_reviewer_is_rejected(client: TestClient) -> None:
    """Sin revisor no se guarda nada.

    El rechazo lo produce la construcción de la decisión, antes incluso de
    resolver la identidad. Que haya dos barreras para lo mismo es deliberado: la
    firma es lo que convierte un dato en una decisión atribuible.
    """
    with client:
        value_id = field_id(client, 'DEMO-0001', 'ATC')
        response = client.post(
            f'/records/values/{value_id}/decisions',
            json={'state': 'confirmado', 'reviewer_id': '', 'final_value': 'A02BC01'},
        )
        assert response.status_code == 400
        assert 'revisor' in response.json()['detail'].lower()
        assert count_decisions(client, value_id) == 0


def test_unknown_reviewer_cannot_sign(client: TestClient) -> None:
    with client:
        value_id = field_id(client, 'DEMO-0001', 'ATC')
        response = client.post(
            f'/records/values/{value_id}/decisions',
            json={'state': 'confirmado', 'reviewer_id': 'intruso', 'final_value': 'A02BC01'},
        )
        assert response.status_code == 400
        assert 'no pertenece a la lista configurada' in response.json()['detail']


def test_no_aplica_requires_a_pharmacist_comment(client: TestClient) -> None:
    with client:
        value_id = field_id(client, 'DEMO-0001', 'RECOMENPRESCRIP')
        rejected = client.post(
            f'/records/values/{value_id}/decisions',
            json={'state': 'no_aplica', 'reviewer_id': 'ana'},
        )
        assert rejected.status_code == 400
        assert 'exige comentario' in rejected.json()['detail']

        accepted = client.post(
            f'/records/values/{value_id}/decisions',
            json={
                'state': 'no_aplica',
                'reviewer_id': 'ana',
                'comment': 'El campo no tiene sentido para este medicamento.',
            },
        )
        assert accepted.status_code == 201


def test_no_aplica_cannot_be_decided_by_a_non_pharmacist(client: TestClient) -> None:
    with client:
        value_id = field_id(client, 'DEMO-0001', 'RECOMENPRESCRIP')
        response = client.post(
            f'/records/values/{value_id}/decisions',
            json={
                'state': 'no_aplica',
                'reviewer_id': 'ana',
                'reviewer_role': 'otro',
                'comment': 'Intento indebido.',
            },
        )
        assert response.status_code == 400
        assert 'solo puede decidirlo un farmacéutico' in response.json()['detail']


def test_no_consta_requires_reviewing_the_mandatory_sources(client: TestClient) -> None:
    with client:
        value_id = field_id(client, 'DEMO-0001', 'RECOMENPRESCRIP')
        response = client.post(
            f'/records/values/{value_id}/decisions',
            json={
                'state': 'no_consta',
                'reviewer_id': 'ana',
                'applicable_sources': ['maestro', 'cima'],
                'required_sources': ['maestro', 'cima'],
                'reviewed_sources': ['maestro'],
            },
        )
        assert response.status_code == 400
        assert 'fuentes obligatorias' in response.json()['detail']


def test_confirmed_state_requires_a_final_value(client: TestClient) -> None:
    with client:
        value_id = field_id(client, 'DEMO-0001', 'ATC')
        response = client.post(
            f'/records/values/{value_id}/decisions',
            json={'state': 'confirmado', 'reviewer_id': 'ana'},
        )
        assert response.status_code == 400
        assert 'valor final' in response.json()['detail']


def test_a_resolved_decision_cannot_go_back_to_pending(client: TestClient) -> None:
    """Volver a pendiente borraría la autoría sin dejar rastro."""
    with client:
        value_id = field_id(client, 'DEMO-0001', 'ATC')
        client.post(
            f'/records/values/{value_id}/decisions',
            json={'state': 'confirmado', 'reviewer_id': 'ana', 'final_value': 'A02BC01'},
        )
        response = client.post(
            f'/records/values/{value_id}/decisions',
            json={'state': 'pendiente', 'reviewer_id': 'ana'},
        )
        assert response.status_code == 400
        assert 'no vuelve a pendiente' in response.json()['detail']


def test_reverting_no_aplica_requires_a_comment(client: TestClient) -> None:
    with client:
        value_id = field_id(client, 'DEMO-0002', 'FORMAFARMA')
        client.post(
            f'/records/values/{value_id}/decisions',
            json={
                'state': 'no_aplica',
                'reviewer_id': 'ana',
                'comment': 'No aplicable a esta forma.',
            },
        )
        response = client.post(
            f'/records/values/{value_id}/decisions',
            json={'state': 'confirmado', 'reviewer_id': 'ana', 'final_value': 'Comprimido'},
        )
        assert response.status_code == 400
        assert 'exige comentario' in response.json()['detail']


def test_reviewers_endpoint_reflects_the_configured_list(client: TestClient) -> None:
    with client:
        reviewers = client.get('/records/reviewers').json()
        assert [item['identifier'] for item in reviewers] == ['ana', 'luis']
        assert all(item['assurance'] == 'declarada' for item in reviewers)


def test_decision_on_unknown_field_is_not_found(client: TestClient) -> None:
    with client:
        response = client.post(
            '/records/values/no-existe/decisions',
            json={'state': 'confirmado', 'reviewer_id': 'ana', 'final_value': 'x'},
        )
        assert response.status_code == 404
