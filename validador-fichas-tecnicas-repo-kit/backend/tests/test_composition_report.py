import hashlib
import json
from pathlib import Path

import pytest

from pharma_validator_api.composition_report import (
    MISSING_IDENTIFIER,
    create_composition_report,
    sample_reference,
    write_report,
)
from pharma_validator_api.sampling import SamplingInputError, SamplingPersistenceError


def medication(
    nregistro: str,
    *,
    atcs: list[str],
    form: tuple[int, str] | None,
    routes: list[tuple[int, str]],
) -> bytes:
    return json.dumps(
        {
            'nregistro': nregistro,
            'atcs': [{'codigo': code} for code in atcs],
            'formaFarmaceutica': (
                {'id': form[0], 'nombre': form[1]} if form is not None else None
            ),
            'viasAdministracion': [
                {'id': identifier, 'nombre': name} for identifier, name in routes
            ],
            'nombre': f'Medicamento {nregistro}',
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode()


def bodies() -> list[bytes]:
    return [
        medication(
            'M1',
            atcs=['A01', 'A02'],
            form=(1, 'Comprimido | recubierto'),
            routes=[(10, 'Vía oral'), (10, 'Vía oral')],
        ),
        medication(
            'M2',
            atcs=['B01'],
            form=(1, 'Comprimido | recubierto'),
            routes=[(20, 'Vía intravenosa')],
        ),
        medication('M3', atcs=[], form=None, routes=[]),
    ]


def test_report_is_multilabel_reproducible_and_preserves_occurrences() -> None:
    first = create_composition_report(
        sample_run_id='sample-1',
        sample_nregistros=('M1', 'M2', 'M3'),
        medication_bodies=bodies(),
    )
    second = create_composition_report(
        sample_run_id='sample-1',
        sample_nregistros=('M1', 'M2', 'M3'),
        medication_bodies=list(reversed(bodies())),
    )

    assert first == second
    assert first.sample_size == 3
    rows = {(row.dimension, row.identifier): row for row in first.rows}
    assert rows[('atc_first_level', 'A')].document_count == 1
    assert rows[('atc_first_level', 'A')].occurrence_count == 2
    assert rows[('pharmaceutical_form', '1')].document_count == 2
    assert rows[('administration_route', '10')].document_count == 1
    assert rows[('administration_route', '10')].occurrence_count == 2
    assert rows[('administration_route', '10')].label == 'Vía oral'
    assert rows[('atc_first_level', MISSING_IDENTIFIER)].document_count == 1
    assert rows[('pharmaceutical_form', MISSING_IDENTIFIER)].document_count == 1
    assert rows[('administration_route', MISSING_IDENTIFIER)].document_count == 1


def test_json_csv_and_markdown_are_byte_reproducible_and_immutable(tmp_path: Path) -> None:
    report = create_composition_report(
        sample_run_id='sample-1',
        sample_nregistros=('M1', 'M2', 'M3'),
        medication_bodies=bodies(),
    )
    output = tmp_path / 'report'
    paths = write_report(output, report)
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}

    assert write_report(output, report) == paths
    assert hashes == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert b'Comprimido \\| recubierto' in (output / 'composition.md').read_bytes()

    different = create_composition_report(
        sample_run_id='sample-2',
        sample_nregistros=('M1', 'M2', 'M3'),
        medication_bodies=bodies(),
    )
    with pytest.raises(SamplingPersistenceError, match='Informe existente incompatible'):
        write_report(output, different)
    assert hashes == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_report_requires_exactly_one_response_per_sample_document() -> None:
    with pytest.raises(SamplingInputError, match='Faltan respuestas'):
        create_composition_report(
            sample_run_id='sample',
            sample_nregistros=('M1', 'M2'),
            medication_bodies=bodies()[:1],
        )
    with pytest.raises(SamplingInputError, match='repetida'):
        create_composition_report(
            sample_run_id='sample',
            sample_nregistros=('M1',),
            medication_bodies=[bodies()[0], bodies()[0]],
        )
    with pytest.raises(SamplingInputError, match='fuera de muestra'):
        create_composition_report(
            sample_run_id='sample',
            sample_nregistros=('M1',),
            medication_bodies=[bodies()[1]],
        )


def test_incompatible_atc_is_not_normalized() -> None:
    invalid = medication('M1', atcs=['a01'], form=(1, 'Comprimido'), routes=[])
    with pytest.raises(SamplingInputError, match='Primer nivel ATC incompatible'):
        create_composition_report(
            sample_run_id='sample',
            sample_nregistros=('M1',),
            medication_bodies=[invalid],
        )


def test_sample_manifest_reference_rejects_duplicates() -> None:
    manifest = json.dumps(
        {
            'run_id': 'sample',
            'requested_size': 2,
            'items': [
                {'ordinal': 1, 'nregistro': 'M1'},
                {'ordinal': 2, 'nregistro': 'M2'},
            ],
        }
    ).encode()
    assert sample_reference(manifest) == ('sample', ('M1', 'M2'))

    duplicate = json.dumps(
        {
            'run_id': 'sample',
            'requested_size': 2,
            'items': [
                {'ordinal': 1, 'nregistro': 'M1'},
                {'ordinal': 2, 'nregistro': 'M1'},
            ],
        }
    ).encode()
    with pytest.raises(SamplingInputError, match='repetido'):
        sample_reference(duplicate)

    invalid_ordinal = json.dumps(
        {
            'run_id': 'sample',
            'requested_size': 1,
            'items': [{'ordinal': 2, 'nregistro': 'M1'}],
        }
    ).encode()
    with pytest.raises(SamplingInputError, match='Ítem de muestra incompatible'):
        sample_reference(invalid_ordinal)
