from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.database import create_database_engine, create_session_factory
from pharma_validator_api.document_versions import (
    DocumentVersionConflictError,
    DocumentVersionError,
)
from pharma_validator_api.models import SourceDocumentArtifact, SourceDocumentVersion
from pharma_validator_api.sampling import SamplingPersistenceError

DIFF_VERSION = 'cima-version-diff-v1'
ChangeType = Literal['added', 'removed', 'modified', 'unchanged']


@dataclass(frozen=True)
class Snapshot:
    role: str
    ordinal: int
    locator: str
    source_url: str
    status_code: int
    media_type: str | None
    response_headers: str
    content_hash: str
    body: bytes
    fetched_at: str


@dataclass(frozen=True)
class ArtifactChange:
    role: str
    ordinal: int
    change_type: ChangeType
    old_locator: str | None
    new_locator: str | None
    old_hash: str | None
    new_hash: str | None
    old_media_type: str | None
    new_media_type: str | None
    changed_metadata: tuple[str, ...]
    diff_kind: str
    text_diff: str | None


@dataclass(frozen=True)
class VersionDiff:
    report_id: str
    old_version_id: str
    new_version_id: str
    document_id: str
    old_source_version: str | None
    new_source_version: str | None
    changes: tuple[ArtifactChange, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            'schema_version': '1.0.0',
            'diff_version': DIFF_VERSION,
            'report_id': self.report_id,
            'old_version_id': self.old_version_id,
            'new_version_id': self.new_version_id,
            'document_id': self.document_id,
            'old_source_version': self.old_source_version,
            'new_source_version': self.new_source_version,
            'direction_policy': 'orden explícito old/new; no implica vigencia regulatoria',
            'changes': [asdict(change) for change in self.changes],
        }


def _snapshot(row: SourceDocumentArtifact) -> Snapshot:
    if hashlib.sha256(row.body).hexdigest() != row.content_hash:
        raise DocumentVersionConflictError(f'Hash de artefacto incompatible: {row.id}')
    return Snapshot(
        row.artifact_role,
        row.ordinal,
        row.locator,
        row.source_url,
        row.status_code,
        row.media_type,
        row.response_headers,
        row.content_hash,
        row.body,
        row.fetched_at,
    )


def _load(session: Session, version_id: str) -> dict[tuple[str, int], Snapshot]:
    rows = session.scalars(
        select(SourceDocumentArtifact)
        .where(SourceDocumentArtifact.document_version_id == version_id)
        .order_by(SourceDocumentArtifact.artifact_role, SourceDocumentArtifact.ordinal)
    ).all()
    if not rows:
        raise DocumentVersionError(f'Versión sin artefactos: {version_id}')
    result: dict[tuple[str, int], Snapshot] = {}
    for row in rows:
        item = _snapshot(row)
        key = (item.role, item.ordinal)
        if key in result:
            raise DocumentVersionConflictError(f'Ocurrencia documental ambigua: {key}')
        result[key] = item
    return result


def _decode(item: Snapshot) -> str | None:
    if item.media_type is None:
        return None
    parts = [part.strip() for part in item.media_type.split(';')]
    base = parts[0].lower()
    textual = (
        base.startswith('text/')
        or base in {'application/json', 'application/xml', 'application/xhtml+xml'}
        or base.endswith(('+json', '+xml'))
    )
    if not textual:
        return None
    charset = 'utf-8'
    for part in parts[1:]:
        name, separator, value = part.partition('=')
        if separator and name.strip().lower() == 'charset':
            charset = value.strip().strip(chr(34))
    try:
        return item.body.decode(charset, errors='strict')
    except (LookupError, UnicodeDecodeError):
        return None


def _metadata(old: Snapshot, new: Snapshot) -> tuple[str, ...]:
    fields = (
        'locator',
        'source_url',
        'status_code',
        'media_type',
        'response_headers',
        'fetched_at',
    )
    return tuple(field for field in fields if getattr(old, field) != getattr(new, field))


def _one_side(item: Snapshot, change_type: Literal['added', 'removed']) -> ArtifactChange:
    added = change_type == 'added'
    return ArtifactChange(
        item.role,
        item.ordinal,
        change_type,
        None if added else item.locator,
        item.locator if added else None,
        None if added else item.content_hash,
        item.content_hash if added else None,
        None if added else item.media_type,
        item.media_type if added else None,
        (),
        'not_applicable',
        None,
    )


def _both(old: Snapshot, new: Snapshot) -> ArtifactChange:
    metadata = _metadata(old, new)
    if old.content_hash == new.content_hash and not metadata:
        return ArtifactChange(
            old.role,
            old.ordinal,
            'unchanged',
            old.locator,
            new.locator,
            old.content_hash,
            new.content_hash,
            old.media_type,
            new.media_type,
            (),
            'identical',
            None,
        )
    text_diff = None
    if old.content_hash == new.content_hash:
        kind = 'metadata_only'
    else:
        old_text, new_text = _decode(old), _decode(new)
        if old_text is None or new_text is None:
            kind = 'binary_or_undecodable'
        else:
            kind = 'text'
            text_diff = ''.join(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=f'{old.role}:{old.ordinal}:{old.locator}',
                    tofile=f'{new.role}:{new.ordinal}:{new.locator}',
                    lineterm='\n',
                )
            )
    return ArtifactChange(
        old.role,
        old.ordinal,
        'modified',
        old.locator,
        new.locator,
        old.content_hash,
        new.content_hash,
        old.media_type,
        new.media_type,
        metadata,
        kind,
        text_diff,
    )


def create_version_diff(
    session: Session, *, old_version_id: str, new_version_id: str
) -> VersionDiff:
    old_version = session.get(SourceDocumentVersion, old_version_id)
    new_version = session.get(SourceDocumentVersion, new_version_id)
    if old_version is None or new_version is None:
        raise DocumentVersionError('Una o ambas versiones documentales no existen.')
    if old_version.document_id != new_version.document_id:
        raise DocumentVersionError('No se pueden comparar versiones de documentos distintos.')
    old_items, new_items = _load(session, old_version_id), _load(session, new_version_id)
    changes: list[ArtifactChange] = []
    for key in sorted(old_items.keys() | new_items.keys()):
        old, new = old_items.get(key), new_items.get(key)
        if old is None and new is not None:
            changes.append(_one_side(new, 'added'))
        elif new is None and old is not None:
            changes.append(_one_side(old, 'removed'))
        elif old is not None and new is not None:
            changes.append(_both(old, new))
    identity = json.dumps(
        {'version': DIFF_VERSION, 'old': old_version_id, 'new': new_version_id},
        sort_keys=True,
        separators=(',', ':'),
    ).encode()
    return VersionDiff(
        hashlib.sha256(identity).hexdigest(),
        old_version_id,
        new_version_id,
        old_version.document_id,
        old_version.source_version,
        new_version.source_version,
        tuple(changes),
    )


def _cell(value: str | None) -> str:
    if value is None:
        return ''
    return value.replace('|', '\\|').replace('\r\n', '<br>').replace('\n', '<br>')


def _markdown(report: VersionDiff) -> bytes:
    lines = [
        '# Diff de versiones CIMA',
        '',
        f'- Versión anterior explícita: `{report.old_version_id}`',
        f'- Versión nueva explícita: `{report.new_version_id}`',
        f'- Informe: `{report.report_id}`',
        '',
        '> La dirección anterior/nueva es explícita; no declara vigencia regulatoria.',
        '',
        '| Rol | Ordinal | Cambio | Localizador anterior | Localizador nuevo | Diff |',
        '|---|---:|---|---|---|---|',
    ]
    for change in report.changes:
        lines.append(
            '| '
            + ' | '.join(
                [
                    _cell(change.role),
                    str(change.ordinal),
                    change.change_type,
                    _cell(change.old_locator),
                    _cell(change.new_locator),
                    change.diff_kind,
                ]
            )
            + ' |'
        )
        if change.text_diff is not None:
            lines.extend(['', '```diff', change.text_diff, '```', ''])
    lines.append('')
    return '\n'.join(lines).encode()


def write_version_diff(directory: Path, report: VersionDiff) -> tuple[Path, ...]:
    contents = {
        directory / 'version-diff.json': (
            json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
        ).encode(),
        directory / 'version-diff.md': _markdown(report),
    }
    for path, content in contents.items():
        if path.exists() and path.read_bytes() != content:
            raise SamplingPersistenceError(f'Diff existente incompatible: {path}')
    directory.mkdir(parents=True, exist_ok=True)
    for path, content in contents.items():
        if not path.exists():
            with path.open('xb') as output:
                output.write(content)
    return tuple(contents)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Diff offline de versiones documentales CIMA')
    parser.add_argument('--old-version-id', required=True)
    parser.add_argument('--new-version-id', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    engine = create_database_engine(Settings())
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        report = create_version_diff(
            session,
            old_version_id=args.old_version_id,
            new_version_id=args.new_version_id,
        )
    write_version_diff(args.output_dir, report)
    print(report.report_id)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
