"""Contrato de transporte hacia el servidor de inferencia local (DEV-402).

Las pruebas fijan dos ideas: el transporte no elige modelo (D-014 pendiente) y
una respuesta que no es la pedida es un fallo declarado, nunca un resultado
reparado.
"""

from collections.abc import Mapping
from typing import Any

import pytest

from pharma_validator_api.inference_backend import (
    BackendConfig,
    GenerationParameters,
    InferenceBackendError,
    InferenceRequest,
    InferenceResponse,
    build_chat_payload,
    call_with_retries,
    parse_chat_response,
)

SCHEMA = {"type": "object", "properties": {"resultados": {"type": "array"}}}
REQUEST = InferenceRequest(
    prompt="Extrae los campos del apartado 4.2.",
    json_schema=SCHEMA,
    schema_name="extraccion_seccion",
)


def config(**overrides: Any) -> BackendConfig:
    base: dict[str, Any] = {
        "base_url": "http://localhost:8000/v1",
        "model": "modelo-pendiente-de-d014",
    }
    base.update(overrides)
    return BackendConfig(**base)


def chat_response(content: str, model: str = "modelo-pendiente-de-d014") -> dict[str, Any]:
    return {
        "model": model,
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def test_a_backend_cannot_be_built_without_an_explicit_model() -> None:
    """Mientras D-014 esté pendiente, ningún camino elige modelo por omisión."""
    with pytest.raises(ValueError, match="D-014"):
        BackendConfig(base_url="http://localhost:8000/v1", model="  ")


def test_default_parameters_are_reproducible() -> None:
    """Una evaluación que no se puede repetir no es evidencia."""
    assert GenerationParameters().is_reproducible
    assert not GenerationParameters(temperature=0.7).is_reproducible
    assert not GenerationParameters(seed=None).is_reproducible


def test_payload_requests_strict_guided_output() -> None:
    payload = build_chat_payload(config(), REQUEST)

    assert payload["model"] == "modelo-pendiente-de-d014"
    assert payload["temperature"] == 0.0
    assert payload["seed"] == 0
    response_format = payload["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] == SCHEMA


def test_a_valid_response_is_parsed_and_attributed() -> None:
    parsed = parse_chat_response(chat_response('{"resultados": []}'), config())

    assert parsed == {"resultados": []}


def test_malformed_json_is_a_declared_failure_and_is_never_repaired() -> None:
    with pytest.raises(InferenceBackendError) as error:
        parse_chat_response(chat_response('{"resultados": ['), config())

    assert error.value.kind == "invalid_json"
    assert not error.value.retryable


def test_a_server_serving_another_model_invalidates_attribution() -> None:
    """Publicar métricas de un modelo bajo el nombre de otro es inaceptable."""
    with pytest.raises(InferenceBackendError) as error:
        parse_chat_response(
            chat_response('{"resultados": []}', model="otro-modelo"), config()
        )

    assert error.value.kind == "schema_violation"


def test_an_empty_response_is_not_an_empty_result() -> None:
    with pytest.raises(InferenceBackendError) as error:
        parse_chat_response({"model": "modelo-pendiente-de-d014", "choices": []}, config())

    assert error.value.kind == "empty_response"


def test_transient_failures_are_retried_until_success() -> None:
    attempts: list[int] = []

    def send(payload: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        attempts.append(1)
        if len(attempts) < 3:
            raise InferenceBackendError("timeout", "El servidor tardó demasiado.")
        return chat_response('{"resultados": []}')

    response = call_with_retries(config(max_retries=2), REQUEST, send, sleep=lambda _: None)

    assert isinstance(response, InferenceResponse)
    assert response.attempts == 3
    assert response.payload == {"resultados": []}


def test_retries_are_bounded_and_the_last_failure_surfaces() -> None:
    def send(payload: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        raise InferenceBackendError("server_error", "500")

    with pytest.raises(InferenceBackendError) as error:
        call_with_retries(config(max_retries=1), REQUEST, send, sleep=lambda _: None)

    assert error.value.kind == "server_error"


def test_a_schema_violation_is_not_retried() -> None:
    """Con temperatura 0 y semilla fija, repetir da exactamente el mismo error."""
    calls: list[int] = []

    def send(payload: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        calls.append(1)
        return chat_response("[]")

    with pytest.raises(InferenceBackendError) as error:
        call_with_retries(config(max_retries=3), REQUEST, send, sleep=lambda _: None)

    assert error.value.kind == "schema_violation"
    assert len(calls) == 1


def test_a_response_without_model_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="modelo"):
        InferenceResponse(payload={}, model="", attempts=1)
