from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class CimaClientError(RuntimeError):
    pass


class CimaCacheIntegrityError(CimaClientError):
    pass


class CimaTransportError(CimaClientError):
    pass


class CimaRetryDelayError(CimaClientError):
    pass


class CimaHTTPError(CimaClientError):
    def __init__(self, response: CimaResponse) -> None:
        super().__init__(f'CIMA respondió HTTP {response.status_code}: {response.url}')
        self.response = response


@dataclass(frozen=True)
class CimaResponse:
    url: str
    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
    content_sha256: str
    fetched_at: str
    from_cache: bool

    @property
    def content_type(self) -> str | None:
        return next(
            (value for name, value in self.headers if name.lower() == 'content-type'),
            None,
        )

    def json(self) -> Any:
        return json.loads(self.body)


class RateLimiter:
    def __init__(
        self,
        requests_per_second: float,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if requests_per_second <= 0:
            raise ValueError('requests_per_second debe ser mayor que cero.')
        self._interval = 1.0 / requests_per_second
        self._monotonic = monotonic
        self._sleep = sleep
        self._last_request: float | None = None
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._monotonic()
            if self._last_request is not None:
                delay = self._interval - (now - self._last_request)
                if delay > 0:
                    self._sleep(delay)
                    now = self._monotonic()
            self._last_request = now


class ImmutableCimaCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def key(url: str, accept: str) -> str:
        payload = json.dumps(
            {'method': 'GET', 'url': url, 'accept': accept},
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    def load(self, key: str) -> CimaResponse | None:
        entry = self.root / key
        if not entry.exists():
            return None
        body_path = entry / 'response.body'
        manifest_path = entry / 'manifest.json'
        if not body_path.is_file() or not manifest_path.is_file():
            raise CimaCacheIntegrityError(f'Entrada de caché incompleta: {key}')
        body = body_path.read_bytes()
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CimaCacheIntegrityError(f'Manifiesto de caché inválido: {key}') from exc
        digest = hashlib.sha256(body).hexdigest()
        if digest != manifest.get('content_sha256'):
            raise CimaCacheIntegrityError(f'Hash de caché no coincide: {key}')
        try:
            return CimaResponse(
                url=manifest['url'],
                status_code=manifest['status_code'],
                headers=tuple((name, value) for name, value in manifest['headers']),
                body=body,
                content_sha256=digest,
                fetched_at=manifest['fetched_at'],
                from_cache=True,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CimaCacheIntegrityError(f'Contrato de caché inválido: {key}') from exc

    def store(self, key: str, response: CimaResponse) -> CimaResponse:
        self.root.mkdir(parents=True, exist_ok=True)
        current = self.load(key)
        if current is not None:
            return current
        temporary = Path(tempfile.mkdtemp(prefix=f'.{key}-', dir=self.root))
        try:
            (temporary / 'response.body').write_bytes(response.body)
            manifest = {
                'schema_version': '1.0.0',
                'url': response.url,
                'status_code': response.status_code,
                'headers': response.headers,
                'content_sha256': response.content_sha256,
                'fetched_at': response.fetched_at,
            }
            (temporary / 'manifest.json').write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
                encoding='utf-8',
            )
            try:
                temporary.rename(self.root / key)
            except FileExistsError:
                return self.load(key) or response
            return response
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)


class CimaClient:
    def __init__(
        self,
        *,
        base_url: str,
        cache_dir: Path,
        timeout_seconds: float = 15.0,
        requests_per_second: float = 5.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
        max_retry_delay_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        parsed_base = httpx.URL(base_url)
        if parsed_base.scheme != 'https' or not parsed_base.host:
            raise ValueError('CIMA base_url debe ser una URL HTTPS absoluta.')
        if timeout_seconds <= 0 or max_retries < 0 or backoff_seconds < 0:
            raise ValueError('Configuración temporal de CIMA inválida.')
        if max_retry_delay_seconds < 0:
            raise ValueError('max_retry_delay_seconds no puede ser negativo.')
        self._base_url = str(parsed_base).rstrip('/')
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._max_retry_delay_seconds = max_retry_delay_seconds
        self._sleep = sleep
        self._rate_limiter = RateLimiter(
            requests_per_second,
            monotonic=monotonic,
            sleep=sleep,
        )
        self._cache = ImmutableCimaCache(cache_dir)
        self._http = httpx.Client(
            timeout=timeout_seconds,
            transport=transport,
            headers={'User-Agent': 'farmalidacion-cima-client/0.1'},
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> CimaClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _validate_path(self, path: str) -> None:
        if not path.startswith('/') or '://' in path or '..' in path.split('/'):
            raise ValueError('La ruta CIMA debe ser relativa y no contener segmentos ascendentes.')

    def _delay_for(self, response: httpx.Response, retry_number: int) -> float:
        retry_after = response.headers.get('Retry-After')
        try:
            delay = float(retry_after) if retry_after is not None else None
        except ValueError:
            delay = None
        if delay is None or delay < 0:
            delay = self._backoff_seconds * (2**retry_number)
        if delay > self._max_retry_delay_seconds:
            raise CimaRetryDelayError(
                f'CIMA solicita una espera de {delay:g}s, superior al máximo configurado.'
            )
        return delay

    @staticmethod
    def _capture(response: httpx.Response) -> CimaResponse:
        body = response.content
        return CimaResponse(
            url=str(response.url),
            status_code=response.status_code,
            headers=tuple(response.headers.multi_items()),
            body=body,
            content_sha256=hashlib.sha256(body).hexdigest(),
            fetched_at=datetime.now(UTC).isoformat(),
            from_cache=False,
        )

    def get(
        self,
        path: str,
        *,
        params: Sequence[tuple[str, str]] = (),
        accept: str = 'application/json',
    ) -> CimaResponse:
        self._validate_path(path)
        query_params: list[tuple[str, str | int | float | bool | None]] = list(params)
        request = self._http.build_request(
            'GET',
            f'{self._base_url}{path}',
            params=query_params,
            headers={'Accept': accept},
        )
        key = self._cache.key(str(request.url), accept)
        cached = self._cache.load(key)
        if cached is not None:
            return cached

        for attempt in range(self._max_retries + 1):
            self._rate_limiter.wait()
            request = self._http.build_request(
                'GET',
                f'{self._base_url}{path}',
                params=query_params,
                headers={'Accept': accept},
            )
            try:
                raw_response = self._http.send(request)
            except httpx.TransportError as exc:
                if attempt >= self._max_retries:
                    raise CimaTransportError(f'Fallo de transporte CIMA: {request.url}') from exc
                self._sleep(self._backoff_seconds * (2**attempt))
                continue

            captured = self._capture(raw_response)
            if raw_response.status_code in RETRYABLE_STATUS_CODES:
                if attempt >= self._max_retries:
                    raise CimaHTTPError(captured)
                self._sleep(self._delay_for(raw_response, attempt))
                continue
            if not raw_response.is_success:
                raise CimaHTTPError(captured)
            return self._cache.store(key, captured)
        raise AssertionError('Bucle de reintentos CIMA inalcanzable.')

    def medication(self, *, nregistro: str | None = None, cn: str | None = None) -> CimaResponse:
        if (nregistro is None) == (cn is None):
            raise ValueError('Debe indicarse exactamente uno de nregistro o cn.')
        name, value = ('nregistro', nregistro) if nregistro is not None else ('cn', cn)
        return self.get('/medicamento', params=[(name, value or '')])

    def medications(self, *, pagina: int = 1) -> CimaResponse:
        return self.get(
            '/medicamentos',
            params=[('pagina', str(pagina)), ('autorizados', '1'), ('comerc', '1')],
        )

    def presentations(self, *, nregistro: str, pagina: int = 1) -> CimaResponse:
        return self.get(
            '/presentaciones',
            params=[('nregistro', nregistro), ('pagina', str(pagina))],
        )

    def sections(self, *, nregistro: str, document_type: int = 1) -> CimaResponse:
        return self.get(
            f'/docSegmentado/secciones/{document_type}',
            params=[('nregistro', nregistro)],
        )

    def content(
        self,
        *,
        nregistro: str,
        section: str | None = None,
        document_type: int = 1,
        accept: str = 'application/json',
    ) -> CimaResponse:
        params = [('nregistro', nregistro)]
        if section is not None:
            params.append(('seccion', section))
        return self.get(
            f'/docSegmentado/contenido/{document_type}',
            params=params,
            accept=accept,
        )

    def changes(self, *, date: str, nregistros: Sequence[str] = ()) -> CimaResponse:
        params = [('fecha', date)]
        params.extend(('nregistro', item) for item in nregistros)
        return self.get('/registroCambios', params=params)
