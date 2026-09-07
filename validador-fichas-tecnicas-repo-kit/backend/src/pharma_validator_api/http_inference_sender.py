'''HTTP sender for an explicitly configured OpenAI-compatible local server.'''

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from pharma_validator_api.inference_backend import InferenceBackendError


class OpenAIChatSender:
    '''Reusable HTTP sender; it never selects a model or endpoint implicitly.'''

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError('El sender requiere base_url explícita.')
        headers = {'Authorization': f'Bearer {api_key}'} if api_key else None
        self._client = httpx.Client(
            base_url=base_url.rstrip('/') + '/', headers=headers, transport=transport
        )

    def __call__(
        self, payload: Mapping[str, Any], timeout_seconds: float
    ) -> Mapping[str, Any]:
        try:
            response = self._client.post(
                'chat/completions', json=dict(payload), timeout=timeout_seconds
            )
        except httpx.TimeoutException as error:
            raise InferenceBackendError('timeout', 'Timeout del servidor de inferencia.') from error
        except httpx.TransportError as error:
            raise InferenceBackendError(
                'transport', 'No se pudo contactar con el servidor de inferencia.'
            ) from error
        if response.status_code in {408, 429} or response.status_code >= 500:
            raise InferenceBackendError(
                'server_error', f'El servidor de inferencia respondió {response.status_code}.'
            )
        if response.status_code >= 400:
            raise InferenceBackendError(
                'schema_violation',
                f'El servidor rechazó la petición con estado {response.status_code}.',
            )
        try:
            payload_out = response.json()
        except ValueError as error:
            raise InferenceBackendError(
                'invalid_json', 'El servidor devolvió un cuerpo que no es JSON.'
            ) from error
        if not isinstance(payload_out, dict):
            raise InferenceBackendError(
                'schema_violation', 'La respuesta HTTP debe ser un objeto JSON.'
            )
        return payload_out

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpenAIChatSender:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
