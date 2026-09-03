"""Pruebas de la selección reproducible del conjunto oro (DEV-407).

Cubren el criterio 1 de aceptación del contrato —selección reproducible desde el
universo de 500 con huella estable— y los criterios 8 y 9 en lo que atañe a la
selección: salidas idénticas entre ejecuciones y ninguna descarga ni
modificación del corpus.

Los criterios 2 a 7 corresponden a la anotación, que no se implementa aquí
porque GOLD-002 sigue pendiente de decisión humana.
"""

import json
from pathlib import Path

import pytest

from pharma_validator_api.gold_selection import (
    ALGORITHM_VERSION,
    GOLD_SEED,
    GOLD_SIZE,
    GoldCandidate,
    GoldSelectionError,
    compute_universe_hash,
    select_gold_set,
)

ROOT = Path(__file__).resolve().parents[2]
CORPUS_MANIFEST = ROOT / 'data' / 'local' / 'cima-corpus-random-203' / 'manifest.json'


def synthetic_universe(size: int = 500) -> tuple[GoldCandidate, ...]:
    return tuple(
        GoldCandidate(nregistro=f'{index:06d}', document_version_hash=f'{index:064x}')
        for index in range(1, size + 1)
    )


def test_selection_is_deterministic_for_the_same_universe_and_seed() -> None:
    universe = synthetic_universe()
    first = select_gold_set(universe)
    second = select_gold_set(universe)
    assert first.run_id == second.run_id
    assert first.items == second.items
    assert first.as_dict() == second.as_dict()


def test_selection_uses_the_approved_seed_and_size_by_default() -> None:
    """GOLD-001 fija la semilla 407 y la especificación 1.1 el tamaño 20."""
    selection = select_gold_set(synthetic_universe())
    assert selection.seed == GOLD_SEED == 407
    assert selection.requested_size == GOLD_SIZE == 20
    assert len(selection.items) == 20
    assert selection.algorithm_version == ALGORITHM_VERSION


def test_selection_does_not_depend_on_the_input_order() -> None:
    """El orden de lectura del corpus no puede cambiar el conjunto oro.

    `random.sample` depende del orden de la secuencia: sin la ordenación previa
    por `nregistro` que exige el contrato, leer el mismo corpus en otro orden
    daría un conjunto distinto con la misma semilla.
    """
    universe = synthetic_universe()
    shuffled = tuple(reversed(universe))
    assert select_gold_set(universe).items == select_gold_set(shuffled).items


def test_a_different_seed_selects_a_different_set() -> None:
    universe = synthetic_universe()
    default = {item.nregistro for item in select_gold_set(universe).items}
    other = {item.nregistro for item in select_gold_set(universe, seed=203).items}
    assert default != other


def test_selected_items_are_numbered_and_unique() -> None:
    selection = select_gold_set(synthetic_universe())
    assert [item.ordinal for item in selection.items] == list(range(1, 21))
    assert len({item.nregistro for item in selection.items}) == 20


def test_every_selected_item_is_anchored_to_a_document_version() -> None:
    """Una anotación pertenece a una versión, nunca «a la ficha»."""
    universe = synthetic_universe()
    versions = {item.nregistro: item.document_version_hash for item in universe}
    for item in select_gold_set(universe).items:
        assert item.document_version_hash == versions[item.nregistro]


def test_universe_hash_covers_the_document_version() -> None:
    """Mismos registros con versiones distintas no son el mismo universo."""
    universe = synthetic_universe(30)
    changed = (
        GoldCandidate(universe[0].nregistro, 'f' * 64),
        *universe[1:],
    )
    assert compute_universe_hash(universe) != compute_universe_hash(changed)


def test_universe_hash_does_not_depend_on_order() -> None:
    universe = synthetic_universe(30)
    assert compute_universe_hash(universe) == compute_universe_hash(tuple(reversed(universe)))


def test_a_changed_universe_changes_the_run_identity() -> None:
    """Una selección no puede parecer la misma sobre otro corpus."""
    universe = synthetic_universe(30)
    changed = (GoldCandidate(universe[0].nregistro, 'f' * 64), *universe[1:])
    assert select_gold_set(universe).run_id != select_gold_set(changed).run_id


def test_duplicate_nregistro_is_rejected() -> None:
    universe = (
        GoldCandidate('000001', 'a' * 64),
        GoldCandidate('000001', 'b' * 64),
    )
    with pytest.raises(GoldSelectionError, match='duplicado'):
        select_gold_set(universe, size=1)


def test_a_universe_smaller_than_the_gold_set_is_rejected() -> None:
    with pytest.raises(GoldSelectionError, match='superior al universo'):
        select_gold_set(synthetic_universe(5))


def test_stratified_mode_is_not_supported() -> None:
    """GOLD-003: no se estratifica; el inventario carece de ATC."""
    with pytest.raises(GoldSelectionError, match='no soportado'):
        select_gold_set(synthetic_universe(), mode='estratificado')  # type: ignore[arg-type]


@pytest.mark.skipif(
    not CORPUS_MANIFEST.exists(),
    reason='El corpus real de DEV-208 no está disponible en este entorno.',
)
def test_selection_over_the_real_corpus_is_stable_and_reads_only() -> None:
    """Selección sobre el corpus real de 500, sin red y sin modificarlo."""
    before = CORPUS_MANIFEST.stat().st_mtime_ns
    manifest = json.loads(CORPUS_MANIFEST.read_text(encoding='utf-8'))
    documents = manifest['documents']
    assert len(documents) == 500

    universe = tuple(
        GoldCandidate(
            nregistro=document['nregistro'],
            document_version_hash=next(
                artifact['content_sha256']
                for artifact in document['artifacts']
                if artifact['artifact_role'] == 'metadata'
            ),
        )
        for document in documents
    )
    first = select_gold_set(universe)
    second = select_gold_set(universe)

    assert len(first.items) == 20
    assert first.universe_size == 500
    assert first.run_id == second.run_id
    assert first.as_dict() == second.as_dict()
    # Los 20 elegidos pertenecen realmente al universo de 500.
    assert {item.nregistro for item in first.items} <= {
        document['nregistro'] for document in documents
    }
    # El corpus no se ha tocado.
    assert CORPUS_MANIFEST.stat().st_mtime_ns == before
