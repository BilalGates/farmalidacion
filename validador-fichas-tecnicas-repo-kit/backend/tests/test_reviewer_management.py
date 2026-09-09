"""Gestión de la lista de revisores (10.1, D-018)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.models import Base


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    path = tmp_path / 'revisores.db'
    url = f'sqlite:///{path.as_posix()}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    settings = Settings(
        env='test',
        database_url=url,
        reviewers=('ana:Ana Ruiz',),
        _env_file=None,
    )
    return TestClient(create_app(settings))


def add(client: TestClient, identifier: str, name: str, role: str):
    return client.post(
        '/reviewers', json={'identifier': identifier, 'display_name': name, 'role': role}
    )


def test_roles_are_published_for_the_interface(client: TestClient) -> None:
    """La pantalla pide los roles en lugar de llevarlos escritos."""
    with client:
        roles = client.get('/reviewers/roles').json()
        valores = {item['value']: item['label'] for item in roles}
        assert valores['farmaceutico'] == 'Farmacéutico'
        assert valores['tecnico'] == 'Técnico'
        assert valores['cientifico_datos'] == 'Científico de datos'


def test_reviewers_can_be_added_without_restarting(client: TestClient) -> None:
    """El alta es un dato, no un cambio de despliegue."""
    with client:
        created = add(client, 'bea', 'Bea Gil', 'cientifico_datos')
        assert created.status_code == 201
        assert created.json()['role_label'] == 'Científico de datos'
        assert created.json()['active'] is True

        # Y queda disponible para firmar de inmediato.
        firmantes = client.get('/records/reviewers').json()
        assert 'bea' in [item['identifier'] for item in firmantes]


def test_identifier_is_never_reused(client: TestClient) -> None:
    """Reasignar un identificador reescribiría en silencio firmas antiguas."""
    with client:
        add(client, 'bea', 'Bea Gil', 'tecnico')
        repetido = add(client, 'bea', 'Otra Persona', 'tecnico')
        assert repetido.status_code == 400
        assert 'ya está en uso' in repetido.json()['detail']


def test_deactivated_reviewer_leaves_the_signing_list_but_stays_listed(
    client: TestClient,
) -> None:
    """Desactivar retira del selector sin borrar a nadie.

    Sigue apareciendo en la pantalla de gestión: si desapareciera, no habría
    forma de reactivarlo.
    """
    with client:
        add(client, 'ana', 'Ana Ruiz', 'farmaceutico')
        add(client, 'bea', 'Bea Gil', 'tecnico')

        apagado = client.put('/reviewers/bea/active', json={'active': False})
        assert apagado.status_code == 200
        assert apagado.json()['active'] is False

        firmantes = [item['identifier'] for item in client.get('/records/reviewers').json()]
        assert 'bea' not in firmantes

        gestion = [item['identifier'] for item in client.get('/reviewers').json()]
        assert 'bea' in gestion

        # Y puede volver.
        client.put('/reviewers/bea/active', json={'active': True})
        firmantes = [item['identifier'] for item in client.get('/records/reviewers').json()]
        assert 'bea' in firmantes


def test_last_active_pharmacist_cannot_be_retired(client: TestClient) -> None:
    """Sin farmacéutico nadie podría declarar «no consta» ni «no aplica»."""
    with client:
        add(client, 'ana', 'Ana Ruiz', 'farmaceutico')
        add(client, 'bea', 'Bea Gil', 'tecnico')

        apagado = client.put('/reviewers/ana/active', json={'active': False})
        assert apagado.status_code == 400
        assert 'último farmacéutico' in apagado.json()['detail']

        cambio = client.put('/reviewers/ana/role', json={'role': 'tecnico'})
        assert cambio.status_code == 400

        # Con un segundo farmacéutico, deja de ser el último.
        add(client, 'carlos', 'Carlos Vera', 'farmaceutico')
        assert client.put('/reviewers/ana/active', json={'active': False}).status_code == 200


def test_unknown_role_is_rejected(client: TestClient) -> None:
    """El vocabulario de roles es cerrado: un rol inventado no se acepta."""
    with client:
        assert add(client, 'bea', 'Bea Gil', 'jefe').status_code == 400
