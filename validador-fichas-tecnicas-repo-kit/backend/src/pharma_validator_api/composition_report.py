from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from pharma_validator_api.sampling import SamplingInputError, SamplingPersistenceError

REPORT_VERSION = 'cima-composition-v1'
MISSING_IDENTIFIER = '__MISSING__'
MISSING_LABEL = 'Sin dato en respuesta CIMA'


@dataclass(frozen=True, order=True)
class Category:
    dimension: str
    identifier: str
    label: str


@dataclass(frozen=True)
class CompositionRow:
    dimension: str
    identifier: str
    label: str
    document_count: int
    occurrence_count: int
    percentage_of_sample: str


@dataclass(frozen=True)
class CompositionReport:
    report_id: str
    sample_run_id: str
    sample_size: int
    report_version: str
    medication_sources: tuple[tuple[str, str], ...]
    rows: tuple[CompositionRow, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            'schema_version': '1.0.0',
            'report_id': self.report_id,
            'sample_run_id': self.sample_run_id,
            'sample_size': self.sample_size,
            'report_version': self.report_version,
            'counting_policy': {
                'document_count': 'un documento por categoría distinta',
                'occurrence_count': 'todas las ocurrencias recibidas, incluidos duplicados',
                'percentage_denominator': 'sample_size',
            },
            'medication_sources': [
                {'nregistro': nregistro, 'content_sha256': digest}
                for nregistro, digest in self.medication_sources
            ],
            'rows': [
                {
                    'dimension': row.dimension,
                    'identifier': row.identifier,
                    'label': row.label,
                    'document_count': row.document_count,
                    'occurrence_count': row.occurrence_count,
                    'percentage_of_sample': row.percentage_of_sample,
                }
                for row in self.rows
            ],
        }


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _read_json(body: bytes, *, context: str) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SamplingInputError(f'JSON CIMA incompatible en {context}') from exc
    if not isinstance(payload, dict):
        raise SamplingInputError(f'Objeto JSON esperado en {context}')
    return payload


def sample_reference(body: bytes) -> tuple[str, tuple[str, ...]]:
    payload = _read_json(body, context='manifiesto de muestra')
    run_id = payload.get('run_id')
    requested_size = payload.get('requested_size')
    items = payload.get('items')
    if (
        not isinstance(run_id, str)
        or not run_id
        or not isinstance(requested_size, int)
        or not isinstance(items, list)
        or not items
        or requested_size != len(items)
    ):
        raise SamplingInputError('Manifiesto de muestra incompatible.')
    nregistros: list[str] = []
    for expected_ordinal, item in enumerate(items, start=1):
        if (
            not isinstance(item, dict)
            or item.get('ordinal') != expected_ordinal
            or not isinstance(item.get('nregistro'), str)
            or not item['nregistro']
        ):
            raise SamplingInputError('Ítem de muestra incompatible.')
        nregistro = item['nregistro']
        if nregistro in nregistros:
            raise SamplingInputError(f'nregistro repetido en muestra: {nregistro}')
        nregistros.append(nregistro)
    return run_id, tuple(nregistros)


def _named_category(raw: object, *, dimension: str, context: str) -> Category:
    if not isinstance(raw, dict):
        raise SamplingInputError(f'{dimension} incompatible para {context}')
    identifier = raw.get('id')
    label = raw.get('nombre')
    if not isinstance(identifier, (str, int)) or isinstance(identifier, bool):
        raise SamplingInputError(f'Identificador de {dimension} incompatible para {context}')
    if not isinstance(label, str) or not label:
        raise SamplingInputError(f'Nombre de {dimension} incompatible para {context}')
    return Category(dimension, str(identifier), label)


def _categories(payload: dict[str, Any], nregistro: str) -> list[Category]:
    categories: list[Category] = []
    raw_atcs = payload.get('atcs', [])
    if not isinstance(raw_atcs, list):
        raise SamplingInputError(f'atcs incompatible para {nregistro}')
    for raw_atc in raw_atcs:
        if not isinstance(raw_atc, dict) or not isinstance(raw_atc.get('codigo'), str):
            raise SamplingInputError(f'ATC incompatible para {nregistro}')
        code = raw_atc['codigo']
        if not code or code[0] not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            raise SamplingInputError(f'Primer nivel ATC incompatible para {nregistro}: {code!r}')
        categories.append(Category('atc_first_level', code[0], code[0]))
    if not raw_atcs:
        categories.append(Category('atc_first_level', MISSING_IDENTIFIER, MISSING_LABEL))

    raw_form = payload.get('formaFarmaceutica')
    if raw_form is None:
        categories.append(Category('pharmaceutical_form', MISSING_IDENTIFIER, MISSING_LABEL))
    else:
        categories.append(
            _named_category(raw_form, dimension='pharmaceutical_form', context=nregistro)
        )

    raw_routes = payload.get('viasAdministracion', [])
    if not isinstance(raw_routes, list):
        raise SamplingInputError(f'viasAdministracion incompatible para {nregistro}')
    if raw_routes:
        categories.extend(
            _named_category(raw, dimension='administration_route', context=nregistro)
            for raw in raw_routes
        )
    else:
        categories.append(Category('administration_route', MISSING_IDENTIFIER, MISSING_LABEL))
    return categories


def create_composition_report(
    *,
    sample_run_id: str,
    sample_nregistros: tuple[str, ...],
    medication_bodies: list[bytes],
) -> CompositionReport:
    if not sample_nregistros:
        raise SamplingInputError('La muestra está vacía.')
    expected = set(sample_nregistros)
    source_hashes: dict[str, str] = {}
    document_categories: dict[Category, set[str]] = defaultdict(set)
    occurrences: Counter[Category] = Counter()

    for body in medication_bodies:
        digest = _sha256(body)
        payload = _read_json(body, context=digest)
        nregistro = payload.get('nregistro')
        if not isinstance(nregistro, str) or nregistro not in expected:
            raise SamplingInputError(f'Respuesta de medicamento fuera de muestra: {nregistro!r}')
        if nregistro in source_hashes:
            raise SamplingInputError(f'Respuesta de medicamento repetida: {nregistro}')
        source_hashes[nregistro] = digest
        categories = _categories(payload, nregistro)
        occurrences.update(categories)
        for category in set(categories):
            document_categories[category].add(nregistro)

    missing = sorted(expected - source_hashes.keys())
    if missing:
        raise SamplingInputError(f'Faltan respuestas de medicamento: {missing}')

    sample_size = len(sample_nregistros)
    rows = tuple(
        CompositionRow(
            dimension=category.dimension,
            identifier=category.identifier,
            label=category.label,
            document_count=len(document_categories[category]),
            occurrence_count=occurrences[category],
            percentage_of_sample=str(
                (Decimal(len(document_categories[category])) * 100 / Decimal(sample_size)).quantize(
                    Decimal('0.0001'), rounding=ROUND_HALF_UP
                )
            ),
        )
        for category in sorted(occurrences)
    )
    medication_sources = tuple(sorted(source_hashes.items()))
    identity = json.dumps(
        {
            'report_version': REPORT_VERSION,
            'sample_run_id': sample_run_id,
            'medication_sources': medication_sources,
        },
        sort_keys=True,
        separators=(',', ':'),
    ).encode()
    return CompositionReport(
        report_id=_sha256(identity),
        sample_run_id=sample_run_id,
        sample_size=sample_size,
        report_version=REPORT_VERSION,
        medication_sources=medication_sources,
        rows=rows,
    )


def _csv_content(report: CompositionReport) -> bytes:
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(
        ['dimension', 'identifier', 'label', 'document_count', 'occurrence_count', 'percentage']
    )
    for row in report.rows:
        writer.writerow(
            [
                row.dimension,
                row.identifier,
                row.label,
                row.document_count,
                row.occurrence_count,
                row.percentage_of_sample,
            ]
        )
    return output.getvalue().encode()


def _markdown_cell(value: str) -> str:
    return value.replace('|', '\\|').replace('\r\n', '<br>').replace('\n', '<br>')


def _markdown_content(report: CompositionReport) -> bytes:
    lines = [
        '# Informe de composición CIMA',
        '',
        f'- Ejecución de muestra: `{report.sample_run_id}`',
        f'- Identificador del informe: `{report.report_id}`',
        f'- Documentos: {report.sample_size}',
        f'- Versión: `{report.report_version}`',
        '',
        '| Dimensión | Identificador | Etiqueta literal | Documentos | Ocurrencias | % muestra |',
        '|---|---|---|---:|---:|---:|',
    ]
    lines.extend(
        '| '
        + ' | '.join(
            [
                row.dimension,
                _markdown_cell(row.identifier),
                _markdown_cell(row.label),
                str(row.document_count),
                str(row.occurrence_count),
                row.percentage_of_sample,
            ]
        )
        + ' |'
        for row in report.rows
    )
    lines.extend(
        [
            '',
            '> Un documento cuenta una vez por categoría distinta. Ocurrencias conserva',
            '> todas las apariciones recibidas, incluso duplicadas.',
            '',
        ]
    )
    return '\n'.join(lines).encode()


def write_report(directory: Path, report: CompositionReport) -> tuple[Path, ...]:
    contents = {
        directory / 'composition.json': (
            json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
        ).encode(),
        directory / 'composition.csv': _csv_content(report),
        directory / 'composition.md': _markdown_content(report),
    }
    for path, content in contents.items():
        if path.exists() and path.read_bytes() != content:
            raise SamplingPersistenceError(f'Informe existente incompatible: {path}')
    directory.mkdir(parents=True, exist_ok=True)
    for path, content in contents.items():
        if not path.exists():
            with path.open('xb') as output:
                output.write(content)
    return tuple(contents)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Informe de composición CIMA offline')
    parser.add_argument('--sample', type=Path, required=True)
    parser.add_argument('--medication', type=Path, action='append', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id, nregistros = sample_reference(args.sample.read_bytes())
    report = create_composition_report(
        sample_run_id=run_id,
        sample_nregistros=nregistros,
        medication_bodies=[path.read_bytes() for path in args.medication],
    )
    write_report(args.output_dir, report)
    print(report.report_id)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
