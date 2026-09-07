from __future__ import annotations

import httpx
import pytest

from pharma_validator_api.http_inference_sender import OpenAIChatSender
from pharma_validator_api.inference_backend import InferenceBackendError


def test_sender_posts_to_explicit_openai_chat_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == 'http://127.0.0.1:9000/v1/chat/completions'
        assert request.headers['authorization'] == 'Bearer local-token'
        return httpx.Response(200, json={'model': 'explicit-model', 'choices': []})

    with OpenAIChatSender(
        'http://127.0.0.1:9000/v1',
        api_key='local-token',
        transport=httpx.MockTransport(handler),
    ) as sender:
        result = sender({'model': 'explicit-model'}, 5.0)
    assert result['model'] == 'explicit-model'


@pytest.mark.parametrize('status', [408, 429, 500, 503])
def test_sender_classifies_transient_statuses_as_retryable(status: int) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(status))
    with (
        OpenAIChatSender('http://127.0.0.1:9000/v1', transport=transport) as sender,
        pytest.raises(InferenceBackendError) as captured,
    ):
        sender({}, 5.0)
    assert captured.value.kind == 'server_error'
    assert captured.value.retryable is True


def test_sender_does_not_retry_a_rejected_schema_request() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(400))
    with (
        OpenAIChatSender('http://127.0.0.1:9000/v1', transport=transport) as sender,
        pytest.raises(InferenceBackendError) as captured,
    ):
        sender({}, 5.0)
    assert captured.value.kind == 'schema_violation'
    assert captured.value.retryable is False
