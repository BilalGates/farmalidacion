'''Exact, read-only audit of master CN values against local CIMA metadata.'''

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


def _master_cn(database: Path) -> dict[str, set[str]]:
    connection = sqlite3.connect(f'file:{database.as_posix()}?mode=ro', uri=True)
    try:
        rows = connection.execute(
            '''
            SELECT fv.literal_value, bi.target_record_id
            FROM field_value AS fv
            JOIN block_instance AS bi ON bi.id = fv.block_instance_id
            WHERE fv.field_name = 'CODIGO_NACIONAL'
              AND fv.literal_value IS NOT NULL
              AND fv.literal_value != ''
            '''
        )
        result: dict[str, set[str]] = defaultdict(set)
        for cn, record_id in rows:
            result[str(cn)].add(str(record_id))
        return dict(result)
    finally:
        connection.close()


def _cima_cn(corpus: Path) -> tuple[dict[str, set[str]], dict[str, set[str]], list[str]]:
    by_cn: dict[str, set[str]] = defaultdict(set)
    by_registration: dict[str, set[str]] = defaultdict(set)
    incidents: list[str] = []
    for path in sorted((corpus / 'artifacts').glob('*-metadata.json')):
        payload = json.loads(path.read_text(encoding='utf-8'))
        nregistro = payload.get('nregistro')
        presentations = payload.get('presentaciones')
        if not isinstance(nregistro, str) or not nregistro:
            incidents.append(f'{path.name}: nregistro ausente o inválido')
            continue
        if not isinstance(presentations, list):
            incidents.append(f'{nregistro}: presentaciones ausentes o inválidas')
            continue
        for ordinal, presentation in enumerate(presentations, start=1):
            cn = presentation.get('cn') if isinstance(presentation, dict) else None
            if not isinstance(cn, str) or not cn:
                incidents.append(f'{nregistro}: presentación {ordinal} sin CN válido')
                continue
            by_cn[cn].add(nregistro)
            by_registration[nregistro].add(cn)
    return dict(by_cn), dict(by_registration), incidents


def analyze(database: Path, corpus: Path) -> dict[str, Any]:
    master = _master_cn(database)
    cima, registrations, incidents = _cima_cn(corpus)
    common = set(master) & set(cima)
    unique = sorted(cn for cn in common if len(master[cn]) == 1 and len(cima[cn]) == 1)
    ambiguous = sorted(cn for cn in common if len(master[cn]) > 1 or len(cima[cn]) > 1)
    missing = sorted(set(master) - set(cima))
    cima_only = sorted(set(cima) - set(master))
    multiple_cn = sorted(nreg for nreg, cns in registrations.items() if len(cns) > 1)
    return {
        'scope': 'exact literals; local 500-document CIMA sample versus complete master database',
        'master_cn_distinct': len(master),
        'cima_documents': len(registrations),
        'cima_cn_distinct': len(cima),
        'master_cn_exact_unique_match': len(unique),
        'master_cn_without_match_in_sample': len(missing),
        'master_cn_with_multiple_candidates': len(ambiguous),
        'cima_cn_without_master_match': len(cima_only),
        'nregistro_with_multiple_cn': len(multiple_cn),
        'coverage_master_percent': round(100 * len(common) / len(master), 4) if master else 0.0,
        'coverage_cima_sample_percent': round(100 * len(common) / len(cima), 4) if cima else 0.0,
        'incidents': incidents,
        'examples': {
            'exact_unique': [
                {'cn': cn, 'master_record': next(iter(master[cn])), 'nregistro': next(iter(cima[cn]))}
                for cn in unique[:10]
            ],
            'without_match_in_sample': missing[:10],
            'multiple_candidates': [
                {'cn': cn, 'master_records': sorted(master[cn]), 'nregistros': sorted(cima[cn])}
                for cn in ambiguous[:10]
            ],
            'nregistro_with_multiple_cn': [
                {'nregistro': item, 'cn': sorted(registrations[item])}
                for item in multiple_cn[:10]
            ],
            'cima_only': cima_only[:10],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=Path('data/local/real.db'))
    parser.add_argument('--corpus', type=Path, default=Path('data/local/cima-corpus-random-203'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = analyze(args.database, args.corpus)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
    else:
        print(rendered, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
