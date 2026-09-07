'''Live smoke of the critical REAL API path; never writes application data.'''

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from typing import Any


def get(base_url: str, path: str) -> dict[str, Any]:
    with urllib.request.urlopen(base_url.rstrip('/') + path, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f'{path} respondió {response.status}')
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise TypeError(f'{path} no devolvió un objeto JSON')
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--query', default='omeprazol')
    parser.add_argument('--expected-field', default='CODIGO_NACIONAL')
    parser.add_argument('--expected-value', default='707703')
    args = parser.parse_args()

    info = get(args.base_url, '/database-info')
    if info.get('mode') != 'real' or not info.get('consistent'):
        raise RuntimeError('El backend no sirve una base REAL consistente.')
    page = get(args.base_url, '/insights/records?origin=real&limit=50&offset=0')
    if not page.get('items'):
        raise RuntimeError('La primera página REAL está vacía.')

    offset = 0
    found: tuple[dict[str, Any], dict[str, Any]] | None = None
    while True:
        query = urllib.parse.urlencode(
            {'origin': 'real', 'q': args.query, 'limit': 50, 'offset': offset}
        )
        matches = get(args.base_url, '/insights/records?' + query)
        for item in matches.get('items', []):
            detail = get(args.base_url, '/insights/records/' + urllib.parse.quote(item['id']))
            for block in detail.get('blocks', []):
                for value in block.get('values', []):
                    if (
                        value.get('field_name') == args.expected_field
                        and value.get('literal_value') == args.expected_value
                    ):
                        found = (item, value)
                        break
                if found:
                    break
            if found:
                break
        offset += 50
        if found or offset >= int(matches.get('total', 0)):
            break
    if not found:
        raise RuntimeError('La búsqueda no contiene el valor real esperado.')
    item, value = found
    provenance = value.get('provenance') or []
    if not provenance or provenance[0].get('source_system') != 'master_excel':
        raise RuntimeError('El valor esperado no conserva procedencia master_excel.')
    print(
        json.dumps(
            {
                'status': 'PASS',
                'records_total': info['records_real'],
                'search_total': matches['total'],
                'record_id': item['id'],
                'field': args.expected_field,
                'value': args.expected_value,
                'provenance': provenance[0],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
