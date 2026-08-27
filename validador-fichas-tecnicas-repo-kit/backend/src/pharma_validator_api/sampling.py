from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.database import create_database_engine, create_session_factory
from pharma_validator_api.models import SamplingItem, SamplingRun

ALGORITHM_VERSION = 'cima-sampling-v1'
SamplingMode = Literal['aleatorio', 'estratificado']


class SamplingError(RuntimeError):
    pass


class SamplingInputError(SamplingError):
    pass


class SamplingPersistenceError(SamplingError):
    pass


@dataclass(frozen=True)
class Candidate:
    nregistro: str
    authorized: bool
    commercialized: bool
    atc_codes: tuple[str, ...]
    source_response_hash: str

    @property
    def eligible(self) -> bool:
        return self.authorized and self.commercialized


@dataclass(frozen=True)
class SelectedItem:
    ordinal: int
    nregistro: str
    atc_stratum: str | None
    source_response_hash: str


@dataclass(frozen=True)
class SampleResult:
    run_id: str
    mode: SamplingMode
    seed: int
    requested_size: int
    eligible_count: int
    excluded_count: int
    source_snapshot_hash: str
    algorithm_version: str
    items: tuple[SelectedItem, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            'schema_version': '1.0.0',
            'run_id': self.run_id,
            'mode': self.mode,
            'seed': self.seed,
            'requested_size': self.requested_size,
            'eligible_count': self.eligible_count,
            'excluded_count': self.excluded_count,
            'source_snapshot_hash': self.source_snapshot_hash,
            'algorithm_version': self.algorithm_version,
            'items': [
                {
                    'ordinal': item.ordinal,
                    'nregistro': item.nregistro,
                    'atc_stratum': item.atc_stratum,
                    'source_response_hash': item.source_response_hash,
                }
                for item in self.items
            ],
        }


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def candidates_from_pages(page_bodies: list[bytes]) -> tuple[list[Candidate], str]:
    candidates: list[Candidate] = []
    seen_pages: set[int] = set()
    seen_records: set[str] = set()
    page_evidence: list[tuple[int, str]] = []
    declared_totals: set[int] = set()
    observed_rows = 0

    for body in page_bodies:
        body_hash = _sha256(body)
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SamplingInputError(f'Respuesta CIMA no es JSON UTF-8: {body_hash}') from exc
        if not isinstance(payload, dict):
            raise SamplingInputError(f'Página CIMA no es un objeto: {body_hash}')
        page = payload.get('pagina')
        total_rows = payload.get('totalFilas')
        results = payload.get('resultados')
        if (
            not isinstance(page, int)
            or not isinstance(total_rows, int)
            or total_rows < 0
            or not isinstance(results, list)
        ):
            raise SamplingInputError(f'Paginación CIMA incompatible: {body_hash}')
        if page in seen_pages:
            raise SamplingInputError(f'Página CIMA repetida: {page}')
        seen_pages.add(page)
        page_evidence.append((page, body_hash))
        declared_totals.add(total_rows)
        observed_rows += len(results)

        for raw in results:
            if not isinstance(raw, dict):
                raise SamplingInputError(f'Fila CIMA incompatible en página {page}')
            nregistro = raw.get('nregistro')
            if not isinstance(nregistro, str) or not nregistro.strip():
                raise SamplingInputError(f'nregistro ausente o inválido en página {page}')
            if nregistro in seen_records:
                raise SamplingInputError(f'nregistro repetido entre páginas: {nregistro}')
            seen_records.add(nregistro)

            state = raw.get('estado')
            authorized = isinstance(state, dict) and state.get('aut') is not None
            commercialized = raw.get('comerc') is True
            raw_atcs = raw.get('atcs', [])
            if not isinstance(raw_atcs, list):
                raise SamplingInputError(f'atcs incompatible para nregistro {nregistro}')
            atc_codes: list[str] = []
            for raw_atc in raw_atcs:
                if not isinstance(raw_atc, dict) or not isinstance(raw_atc.get('codigo'), str):
                    raise SamplingInputError(f'ATC incompatible para nregistro {nregistro}')
                code = raw_atc['codigo'].strip()
                if code:
                    atc_codes.append(code)
            candidates.append(
                Candidate(
                    nregistro=nregistro,
                    authorized=authorized,
                    commercialized=commercialized,
                    atc_codes=tuple(atc_codes),
                    source_response_hash=body_hash,
                )
            )

    if len(declared_totals) != 1 or observed_rows != next(iter(declared_totals), -1):
        raise SamplingInputError(
            f'Inventario CIMA incompleto o inconsistente: {observed_rows} filas observadas, '
            f'totales declarados {sorted(declared_totals)}.'
        )

    snapshot = json.dumps(sorted(page_evidence), separators=(',', ':')).encode()
    return candidates, _sha256(snapshot)


def _atc_stratum(candidate: Candidate) -> str:
    levels = {code[0].upper() for code in candidate.atc_codes if code}
    if len(levels) != 1:
        raise SamplingInputError(
            f'El estrato ATC de {candidate.nregistro} es ambiguo: {sorted(levels)}'
        )
    return next(iter(levels))


def _allocate_strata(groups: dict[str, list[Candidate]], size: int) -> dict[str, int]:
    total = sum(len(group) for group in groups.values())
    exact = {name: size * len(group) / total for name, group in groups.items()}
    allocation = {name: int(value) for name, value in exact.items()}
    remaining = size - sum(allocation.values())
    order = sorted(groups, key=lambda name: (-(exact[name] - allocation[name]), name))
    for name in order[:remaining]:
        allocation[name] += 1
    return allocation


def create_sample(
    candidates: list[Candidate],
    *,
    source_snapshot_hash: str,
    mode: SamplingMode,
    seed: int,
    size: int,
) -> SampleResult:
    if mode not in ('aleatorio', 'estratificado'):
        raise ValueError(f'Modo de muestreo no soportado: {mode}')
    if size <= 0:
        raise ValueError('El tamaño de muestra debe ser mayor que cero.')
    eligible = sorted(
        (item for item in candidates if item.eligible),
        key=lambda item: item.nregistro,
    )
    if size > len(eligible):
        raise SamplingInputError(
            f'Muestra solicitada {size} superior a candidatos elegibles {len(eligible)}.'
        )

    rng = random.Random(seed)
    selected: list[tuple[Candidate, str | None]] = []
    if mode == 'aleatorio':
        selected = [(item, None) for item in rng.sample(eligible, size)]
    else:
        groups: dict[str, list[Candidate]] = defaultdict(list)
        for item in eligible:
            groups[_atc_stratum(item)].append(item)
        for stratum, count in sorted(_allocate_strata(groups, size).items()):
            selected.extend((item, stratum) for item in rng.sample(groups[stratum], count))

    run_payload = {
        'algorithm_version': ALGORITHM_VERSION,
        'mode': mode,
        'seed': seed,
        'size': size,
        'source_snapshot_hash': source_snapshot_hash,
    }
    run_id = _sha256(json.dumps(run_payload, sort_keys=True, separators=(',', ':')).encode())
    items = tuple(
        SelectedItem(
            ordinal=ordinal,
            nregistro=item.nregistro,
            atc_stratum=stratum,
            source_response_hash=item.source_response_hash,
        )
        for ordinal, (item, stratum) in enumerate(selected, start=1)
    )
    return SampleResult(
        run_id=run_id,
        mode=mode,
        seed=seed,
        requested_size=size,
        eligible_count=len(eligible),
        excluded_count=len(candidates) - len(eligible),
        source_snapshot_hash=source_snapshot_hash,
        algorithm_version=ALGORITHM_VERSION,
        items=items,
    )


def persist_sample(
    session: Session,
    result: SampleResult,
    *,
    created_at: datetime | None = None,
) -> bool:
    current = session.get(SamplingRun, result.run_id)
    if current is not None:
        current_metadata = (
            current.mode,
            current.seed,
            current.requested_size,
            current.eligible_count,
            current.excluded_count,
            current.source_snapshot_hash,
            current.algorithm_version,
        )
        expected_metadata = (
            result.mode,
            result.seed,
            result.requested_size,
            result.eligible_count,
            result.excluded_count,
            result.source_snapshot_hash,
            result.algorithm_version,
        )
        stored = session.scalars(
            select(SamplingItem)
            .where(SamplingItem.sampling_run_id == result.run_id)
            .order_by(SamplingItem.ordinal)
        ).all()
        observed = [
            (item.ordinal, item.nregistro, item.atc_stratum, item.source_response_hash)
            for item in stored
        ]
        expected = [
            (item.ordinal, item.nregistro, item.atc_stratum, item.source_response_hash)
            for item in result.items
        ]
        if current_metadata != expected_metadata or observed != expected:
            raise SamplingPersistenceError(f'Ejecución persistida incompatible: {result.run_id}')
        return False

    session.add(
        SamplingRun(
            id=result.run_id,
            mode=result.mode,
            seed=result.seed,
            requested_size=result.requested_size,
            eligible_count=result.eligible_count,
            excluded_count=result.excluded_count,
            source_snapshot_hash=result.source_snapshot_hash,
            algorithm_version=result.algorithm_version,
            created_at=created_at or datetime.now(UTC),
        )
    )
    session.add_all(
        [
            SamplingItem(
                id=_sha256(f'{result.run_id}:{item.ordinal}:{item.nregistro}'.encode()),
                sampling_run_id=result.run_id,
                ordinal=item.ordinal,
                nregistro=item.nregistro,
                atc_stratum=item.atc_stratum,
                source_response_hash=item.source_response_hash,
            )
            for item in result.items
        ]
    )
    session.commit()
    return True


def write_manifest(path: Path, result: SampleResult) -> bool:
    content = (
        json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as output:
            output.write(content)
        return True
    except FileExistsError:
        if path.read_bytes() != content:
            raise SamplingPersistenceError(
                f'Manifiesto existente incompatible: {path}'
            ) from None
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Muestreo CIMA reproducible desde caché local')
    parser.add_argument('--input', type=Path, action='append', required=True)
    parser.add_argument('--modo', choices=('aleatorio', 'estratificado'), required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--size', type=int, default=500)
    parser.add_argument('--output', type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidates, snapshot_hash = candidates_from_pages(
        [path.read_bytes() for path in args.input]
    )
    result = create_sample(
        candidates,
        source_snapshot_hash=snapshot_hash,
        mode=args.modo,
        seed=args.seed,
        size=args.size,
    )
    write_manifest(args.output, result)
    settings = Settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        persist_sample(session, result)
    print(result.run_id)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
