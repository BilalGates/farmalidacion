import hashlib
import zipfile
from pathlib import Path

import httpx
import pytest

from pharma_validator_api.cima_client import (
    CimaCacheIntegrityError,
    CimaClient,
    CimaHTTPError,
    CimaRetryDelayError,
    RateLimiter,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


def client(
    tmp_path: Path,
    handler: httpx.MockTransport,
    *,
    clock: FakeClock | None = None,
    max_retries: int = 2,
    max_retry_delay_seconds: float = 30,
) -> CimaClient:
    active_clock = clock or FakeClock()
    return CimaClient(
        base_url='https://cima.example.test/rest',
        cache_dir=tmp_path / 'cache',
        timeout_seconds=1,
        requests_per_second=5,
        max_retries=max_retries,
        backoff_seconds=0.25,
        max_retry_delay_seconds=max_retry_delay_seconds,
        transport=handler,
        sleep=active_clock.sleep,
        monotonic=active_clock.monotonic,
    )


def test_success_is_cached_byte_for_byte_without_second_request(tmp_path: Path) -> None:
    calls = 0
    body = b'\xff<html>literal</html>'

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers['Accept'] == 'text/html'
        return httpx.Response(
            200,
            content=body,
            headers={'Content-Type': 'text/html; charset=iso-8859-1'},
            request=request,
        )

    with client(tmp_path, httpx.MockTransport(handler)) as cima:
        first = cima.content(nregistro='51347', section='4.2', accept='text/html')
        second = cima.content(nregistro='51347', section='4.2', accept='text/html')

    assert calls == 1
    assert first.body == second.body == body
    assert first.content_sha256 == hashlib.sha256(body).hexdigest()
    assert first.from_cache is False
    assert second.from_cache is True
    assert second.content_type == 'text/html; charset=iso-8859-1'


def test_relative_cache_path_uses_one_absolute_atomic_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b'cuerpo', request=request)

    transport = httpx.MockTransport(handler)
    with CimaClient(
        base_url='https://cima.example.test/rest',
        cache_dir=Path('cache-relativa'),
        transport=transport,
    ) as cima:
        assert cima.medication(nregistro='51347').body == b'cuerpo'
        assert cima.medication(nregistro='51347').from_cache is True

    assert calls == 1
    assert len(list((tmp_path / 'cache-relativa').glob('*.zip'))) == 1


def test_cache_corruption_fails_instead_of_refetching_or_overwriting(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={'nregistro': '51347'}, request=request)

    with client(tmp_path, httpx.MockTransport(handler)) as cima:
        cima.medication(nregistro='51347')
        archive_path = next((tmp_path / 'cache').glob('*.zip'))
        with zipfile.ZipFile(archive_path) as archive:
            manifest = archive.read('manifest.json')
        with zipfile.ZipFile(archive_path, 'w') as archive:
            archive.writestr('response.body', b'alterado')
            archive.writestr('manifest.json', manifest)
        with pytest.raises(CimaCacheIntegrityError, match='Hash'):
            cima.medication(nregistro='51347')

    assert calls == 1


def test_atomic_permission_failure_is_never_reported_as_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, request=request))
    original_rename = Path.rename

    def denied_rename(source: Path, target: Path) -> Path:
        if source.suffix == '.zip':
            raise PermissionError('denegado')
        return original_rename(source, target)

    monkeypatch.setattr(Path, 'rename', denied_rename)
    with client(tmp_path, transport) as cima, pytest.raises(PermissionError, match='denegado'):
        cima.medication(nregistro='51347')

    assert not list((tmp_path / 'cache').glob('*.zip'))


def test_transport_and_429_are_retried_then_cached(tmp_path: Path) -> None:
    calls = 0
    clock = FakeClock()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout('timeout', request=request)
        if calls == 2:
            return httpx.Response(429, headers={'Retry-After': '0'}, request=request)
        return httpx.Response(200, content=b'[]', request=request)

    with client(tmp_path, httpx.MockTransport(handler), clock=clock) as cima:
        response = cima.sections(nregistro='51347')

    assert calls == 3
    assert response.status_code == 200
    assert response.body == b'[]'
    assert 0.25 in clock.sleeps


def test_non_retryable_error_is_captured_and_not_cached(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            404,
            content=b'{error:missing}',
            headers={'Content-Type': 'application/json'},
            request=request,
        )

    with client(tmp_path, httpx.MockTransport(handler)) as cima:
        with pytest.raises(CimaHTTPError) as raised:
            cima.medication(nregistro='missing')
        with pytest.raises(CimaHTTPError):
            cima.medication(nregistro='missing')

    assert calls == 2
    assert raised.value.response.status_code == 404
    assert raised.value.response.body == b'{error:missing}'
    assert not (tmp_path / 'cache').exists()


def test_retry_after_above_safe_window_fails_without_early_retry(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={'Retry-After': '120'}, request=request)

    with client(
        tmp_path,
        httpx.MockTransport(handler),
        max_retry_delay_seconds=30,
    ) as cima, pytest.raises(CimaRetryDelayError, match='120s'):
        cima.medication(nregistro='51347')

    assert calls == 1


def test_repeated_change_parameters_and_content_accept_are_preserved(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=b'contenido literal', request=request)

    with client(tmp_path, httpx.MockTransport(handler)) as cima:
        response = cima.changes(date='26/08/2026', nregistros=['1', '2'])

    assert requests[0].url.params.multi_items() == [
        ('fecha', '26/08/2026'),
        ('nregistro', '1'),
        ('nregistro', '2'),
    ]
    assert requests[0].headers['Accept'] == 'application/json'
    assert response.body == b'contenido literal'


def test_input_scope_and_rate_limiter_are_explicit(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, request=request))
    with client(tmp_path, transport) as cima:
        with pytest.raises(ValueError, match='exactamente uno'):
            cima.medication()
        with pytest.raises(ValueError, match='relativa'):
            cima.get('https://example.test/escape')
        with pytest.raises(ValueError, match='ascendentes'):
            cima.get('/../escape')

    clock = FakeClock()
    limiter = RateLimiter(5, monotonic=clock.monotonic, sleep=clock.sleep)
    limiter.wait()
    limiter.wait()
    assert clock.sleeps == [0.2]


def test_medication_inventory_requests_only_authorized_commercialized_page(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={'resultados': []}, request=request)

    with client(tmp_path, httpx.MockTransport(handler)) as cima:
        cima.medications(pagina=3)

    assert requests[0].url.params.multi_items() == [
        ('pagina', '3'),
        ('autorizados', '1'),
        ('comerc', '1'),
    ]
