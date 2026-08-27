import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session
from test_database_migrations import alembic_config

from pharma_validator_api.models import SamplingItem, SamplingRun
from pharma_validator_api.sampling import (
    SamplingInputError,
    SamplingPersistenceError,
    candidates_from_pages,
    create_sample,
    persist_sample,
    write_manifest,
)


def page(
    number: int,
    rows: list[dict[str, object]],
    *,
    total: int | None = None,
) -> bytes:
    return json.dumps(
        {
            'totalFilas': len(rows) if total is None else total,
            'pagina': number,
            'tamanioPagina': len(rows),
            'resultados': rows,
        },
        sort_keys=True,
        separators=(',', ':'),
    ).encode()


def row(
    nregistro: str,
    atc: str,
    *,
    authorized: bool = True,
    commercialized: bool = True,
) -> dict[str, object]:
    return {
        'nregistro': nregistro,
        'estado': {'aut': 1700000000000} if authorized else {'rev': 1700000000000},
        'comerc': commercialized,
        'atcs': [{'codigo': atc}],
        'campoAdicional': 'se conserva en la respuesta original',
    }


def inventory() -> tuple[list[bytes], list[str]]:
    rows = [
        row('A1', 'A01'),
        row('A2', 'A02'),
        row('A3', 'A03'),
        row('B1', 'B01'),
        row('B2', 'B02'),
        row('C1', 'C01'),
        row('X1', 'A01', authorized=False),
        row('X2', 'A01', commercialized=False),
    ]
    return [
        page(1, rows[:4], total=len(rows)),
        page(2, rows[4:], total=len(rows)),
    ], ['A1', 'A2', 'A3', 'B1', 'B2', 'C1']


@pytest.mark.parametrize('mode', ['aleatorio', 'estratificado'])
def test_same_snapshot_seed_and_mode_produce_same_sample(mode: str) -> None:
    pages, eligible_ids = inventory()
    candidates, snapshot_hash = candidates_from_pages(pages)

    first = create_sample(
        candidates,
        source_snapshot_hash=snapshot_hash,
        mode=mode,  # type: ignore[arg-type]
        seed=20260827,
        size=4,
    )
    second = create_sample(
        list(reversed(candidates)),
        source_snapshot_hash=snapshot_hash,
        mode=mode,  # type: ignore[arg-type]
        seed=20260827,
        size=4,
    )

    assert first == second
    assert first.eligible_count == 6
    assert first.excluded_count == 2
    assert len(first.items) == 4
    assert {item.nregistro for item in first.items} <= set(eligible_ids)
    assert first.as_dict() == second.as_dict()


def test_stratified_sampling_uses_proportional_first_level_atc() -> None:
    pages, _ = inventory()
    candidates, snapshot_hash = candidates_from_pages(pages)

    result = create_sample(
        candidates,
        source_snapshot_hash=snapshot_hash,
        mode='estratificado',
        seed=7,
        size=4,
    )

    strata = [item.atc_stratum for item in result.items]
    assert strata.count('A') == 2
    assert strata.count('B') == 1
    assert strata.count('C') == 1


def test_fixed_seed_reproduces_exactly_500_documents() -> None:
    rows = [row(f'R{index:04d}', f'{chr(65 + index % 10)}01') for index in range(600)]
    candidates, snapshot_hash = candidates_from_pages([page(1, rows)])

    first = create_sample(
        candidates,
        source_snapshot_hash=snapshot_hash,
        mode='aleatorio',
        seed=203,
        size=500,
    )
    second = create_sample(
        candidates,
        source_snapshot_hash=snapshot_hash,
        mode='aleatorio',
        seed=203,
        size=500,
    )

    assert len(first.items) == 500
    assert first.run_id == second.run_id
    assert first.as_dict() == second.as_dict()


def test_ambiguous_atc_and_repeated_pages_or_records_fail_visibly() -> None:
    ambiguous = page(1, [{**row('M1', 'A01'), 'atcs': [{'codigo': 'A01'}, {'codigo': 'B01'}]}])
    candidates, snapshot_hash = candidates_from_pages([ambiguous])
    with pytest.raises(SamplingInputError, match='ambiguo'):
        create_sample(
            candidates,
            source_snapshot_hash=snapshot_hash,
            mode='estratificado',
            seed=1,
            size=1,
        )

    one = page(1, [row('A1', 'A01')])
    with pytest.raises(SamplingInputError, match='Página CIMA repetida'):
        candidates_from_pages([one, one])
    with pytest.raises(SamplingInputError, match='nregistro repetido'):
        candidates_from_pages(
            [page(1, [row('A1', 'A01')], total=2), page(2, [row('A1', 'A01')], total=2)]
        )

    with pytest.raises(SamplingInputError, match='incompleto o inconsistente'):
        candidates_from_pages([page(1, [row('A1', 'A01')], total=2)])


def test_sample_persistence_is_idempotent_and_migration_reversible(tmp_path: Path) -> None:
    pages, _ = inventory()
    candidates, snapshot_hash = candidates_from_pages(pages)
    result = create_sample(
        candidates,
        source_snapshot_hash=snapshot_hash,
        mode='aleatorio',
        seed=11,
        size=5,
    )
    database_path = tmp_path / 'sampling.db'
    config = alembic_config(database_path)
    command.upgrade(config, 'head')
    engine = create_engine(f'sqlite:///{database_path.as_posix()}')

    with Session(engine) as session:
        assert persist_sample(session, result, created_at=datetime(2026, 8, 27, tzinfo=UTC))
        assert not persist_sample(session, result)
        assert session.scalar(select(func.count()).select_from(SamplingRun)) == 1
        assert session.scalar(select(func.count()).select_from(SamplingItem)) == 5
        stored = session.scalars(select(SamplingItem).order_by(SamplingItem.ordinal)).all()
        assert [item.nregistro for item in stored] == [item.nregistro for item in result.items]
        assert {item.source_response_hash for item in stored} == {
            item.source_response_hash for item in result.items
        }

    command.downgrade(config, '9b01a03d5247')
    assert {'sampling_run', 'sampling_item'}.isdisjoint(inspect(engine).get_table_names())


def test_manifest_is_reproducible_and_never_overwritten(tmp_path: Path) -> None:
    pages, _ = inventory()
    candidates, snapshot_hash = candidates_from_pages(pages)
    first = create_sample(
        candidates,
        source_snapshot_hash=snapshot_hash,
        mode='aleatorio',
        seed=1,
        size=4,
    )
    different = create_sample(
        candidates,
        source_snapshot_hash=snapshot_hash,
        mode='aleatorio',
        seed=2,
        size=4,
    )
    output = tmp_path / 'sample.json'

    assert write_manifest(output, first)
    original = output.read_bytes()
    assert not write_manifest(output, first)
    with pytest.raises(SamplingPersistenceError, match='Manifiesto existente incompatible'):
        write_manifest(output, different)
    assert output.read_bytes() == original
