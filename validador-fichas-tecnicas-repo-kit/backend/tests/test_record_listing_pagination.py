"""Paginación del listado de registros.

El resumen de un registro recorre sus ocurrencias, valores, decisiones y
conflictos. Mientras el listado sólo servía el conjunto DEMO (cinco registros)
resumirlos todos era gratis; con los maestros reales importados son 7.189, y
devolver una página tardaba horas. Estas pruebas fijan el contrato de la
paginación y que los filtros siguen significando lo mismo.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.models import Base, BlockInstance, FieldValue, TargetRecord

REVIEWERS = ('ana:Ana Ruiz',)
RECORD_COUNT = 12


def seeded_client(tmp_path: Path) -> TestClient:
    """Base con registros suficientes para que la página no los abarque todos."""
    url = f'sqlite:///{(tmp_path / "listing.db").as_posix()}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for index in range(RECORD_COUNT):
            record = TargetRecord(id=f'rec-{index:03d}', entity_type='medication')
            session.add(record)
            session.add(
                BlockInstance(
                    id=f'blk-{index:03d}',
                    target_record_id=record.id,
                    block_type='medication_general',
                    ordinal=1,
                )
            )
        session.commit()
    engine.dispose()
    settings = Settings(env='test', database_url=url, reviewers=REVIEWERS, _env_file=None)
    return TestClient(create_app(settings))


def test_listing_is_paginated_and_reports_the_full_total(tmp_path: Path) -> None:
    with seeded_client(tmp_path) as client:
        body = client.get('/records', params={'limit': 5}).json()

    assert len(body['items']) == 5
    # `total` es el maestro completo, no el tamaño de la página: el cliente lo
    # necesita para saber cuántas páginas quedan.
    assert body['total'] == RECORD_COUNT


def test_offset_walks_the_listing_without_repeating_or_skipping(tmp_path: Path) -> None:
    with seeded_client(tmp_path) as client:
        first = client.get('/records', params={'limit': 5, 'offset': 0}).json()['items']
        second = client.get('/records', params={'limit': 5, 'offset': 5}).json()['items']
        third = client.get('/records', params={'limit': 5, 'offset': 10}).json()['items']

    seen = [item['id'] for item in first + second + third]
    assert len(third) == 2, 'la última página se queda corta, no se rellena'
    assert seen == sorted(seen), 'el orden es estable entre páginas'
    assert len(set(seen)) == RECORD_COUNT, 'ninguna fila se repite ni se pierde'


def test_default_limit_bounds_an_unparameterised_request(tmp_path: Path) -> None:
    """Un cliente que no pagina no puede provocar un recorrido completo."""
    with seeded_client(tmp_path) as client:
        body = client.get('/records').json()

    assert len(body['items']) <= 50
    assert body['total'] == RECORD_COUNT


@pytest.mark.parametrize(
    'params',
    [{'limit': 0}, {'limit': 201}, {'offset': -1}],
)
def test_out_of_range_pagination_is_rejected(tmp_path: Path, params: dict[str, int]) -> None:
    """El techo evita que `limit` reintroduzca el recorrido completo."""
    with seeded_client(tmp_path) as client:
        assert client.get('/records', params=params).status_code == 422


def test_search_counts_only_matches(tmp_path: Path) -> None:
    """Con filtro, `total` cuenta coincidencias: no el maestro entero."""
    with seeded_client(tmp_path) as client:
        body = client.get('/records', params={'q': 'rec-003'}).json()

    assert [item['id'] for item in body['items']] == ['rec-003']
    assert body['total'] == 1


def test_search_without_matches_is_empty(tmp_path: Path) -> None:
    with seeded_client(tmp_path) as client:
        body = client.get('/records', params={'q': 'inexistente'}).json()

    assert body['items'] == []
    assert body['total'] == 0


def accented_client(tmp_path: Path) -> TestClient:
    """Un registro cuyo nombre lleva acento, como los principios activos reales."""
    url = f'sqlite:///{(tmp_path / "accents.db").as_posix()}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(TargetRecord(id='rec-acc', entity_type='active_ingredient'))
        session.add(
            BlockInstance(
                id='blk-acc',
                target_record_id='rec-acc',
                block_type='active_ingredient_general',
                ordinal=1,
            )
        )
        session.add(
            FieldValue(
                id='val-acc',
                block_instance_id='blk-acc',
                field_name='DESCRIPCION',
                literal_value='omeprazol magnésico',
                observed_type='text',
                logical_state='present',
            )
        )
        session.commit()
    engine.dispose()
    settings = Settings(env='test', database_url=url, reviewers=REVIEWERS, _env_file=None)
    return TestClient(create_app(settings))


@pytest.mark.parametrize('needle', ['magnésico', 'MAGNÉSICO', 'Magnésico'])
def test_search_ignores_case_on_accented_letters(tmp_path: Path, needle: str) -> None:
    """`LIKE` sólo ignora mayúsculas en ASCII: `É` no casa con `é`.

    La preselección en SQL llegó a descartar filas que el filtro en Python sí
    aceptaba, y con acentos —que abundan en los nombres de principio activo— la
    búsqueda se vaciaba entera.
    """
    with accented_client(tmp_path) as client:
        body = client.get('/records', params={'q': needle}).json()

    assert [item['display_name'] for item in body['items']] == ['omeprazol magnésico']


def test_search_does_not_normalise_accents(tmp_path: Path) -> None:
    """Sin acento no encuentra con acento: buscar es literal, y así era antes."""
    with accented_client(tmp_path) as client:
        body = client.get('/records', params={'q': 'magnesico'}).json()

    assert body['items'] == []
