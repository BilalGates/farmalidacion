from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.analyze_master_cima_links import analyze


def test_exact_analysis_keeps_cardinalities_and_does_not_normalize(tmp_path: Path) -> None:
    database = tmp_path / 'real.db'
    connection = sqlite3.connect(database)
    connection.executescript(
        '''
        CREATE TABLE block_instance (id TEXT PRIMARY KEY, target_record_id TEXT NOT NULL);
        CREATE TABLE field_value (
          id TEXT PRIMARY KEY,
          block_instance_id TEXT NOT NULL,
          field_name TEXT NOT NULL,
          literal_value TEXT
        );
        INSERT INTO block_instance VALUES ('b1', 'r1'), ('b2', 'r2'), ('b3', 'r3');
        INSERT INTO field_value VALUES
          ('v1', 'b1', 'CODIGO_NACIONAL', '111111'),
          ('v2', 'b2', 'CODIGO_NACIONAL', '222222'),
          ('v3', 'b3', 'CODIGO_NACIONAL', '012345');
        '''
    )
    connection.commit()
    connection.close()

    artifacts = tmp_path / 'corpus' / 'artifacts'
    artifacts.mkdir(parents=True)
    payloads = {
        'n1-metadata.json': {'nregistro': 'n1', 'presentaciones': [{'cn': '111111'}]},
        'n2-metadata.json': {
            'nregistro': 'n2',
            'presentaciones': [{'cn': '222222'}, {'cn': '333333'}],
        },
        'n3-metadata.json': {'nregistro': 'n3', 'presentaciones': [{'cn': '222222'}]},
        'n4-metadata.json': {'nregistro': 'n4', 'presentaciones': [{'cn': '12345'}]},
    }
    for name, payload in payloads.items():
        (artifacts / name).write_text(json.dumps(payload), encoding='utf-8')

    report = analyze(database, tmp_path / 'corpus')

    assert report['master_cn_exact_unique_match'] == 1
    assert report['master_cn_with_multiple_candidates'] == 1
    assert report['nregistro_with_multiple_cn'] == 1
    assert report['master_cn_without_match_in_sample'] == 1
    assert report['cima_cn_without_master_match'] == 2
    assert '012345' in report['examples']['without_match_in_sample']
