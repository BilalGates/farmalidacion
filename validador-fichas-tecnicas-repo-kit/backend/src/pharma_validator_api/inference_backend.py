"""Contrato de transporte hacia un servidor de inferencia local (DEV-402).

Este módulo define **cómo se habla** con un servidor compatible con la API de
chat de OpenAI, no **con qué modelo** se habla. D-014 sigue pendiente de
aceptación humana, así que aquí no aparece ningún nombre de modelo, ningún
endpoint por defecto y ninguna cuantización: todo eso es configuración que
entra por parámetro.

La separación importa porque el resto de la Fase 4 —agrupación por sección,
esquema guiado, verificación literal, lotes reanudables— ya está construida y
sólo necesita un transporte. Fijar el modelo aquí obligaría a reescribir el
transporte cuando se acepte D-014, y convertiría en decisión de código una
decisión que el registro reserva a una persona.

Lo que sí es responsabilidad de este módulo:

- normalizar parámetros de generación reproducibles;
- clasificar los fallos en categorías accionables;
- decidir qué se reintenta y qué no;
- exigir que toda respuesta viaje con la identidad del modelo que la produjo.

Módulo puro: no abre sockets. El envío real se inyecta como función.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

BACKEND_CONTRACT_VERSION = "inference-backend-v1"

#: Categorías de fallo. Se distinguen porque exigen respuestas distintas: un
#: timeout se reintenta, un esquema incumplido no (repetir la misma petición
#: daría el mismo resultado y sólo gastaría tiempo de GPU).
FailureKind = Literal[
    "timeout",
    "transport",
    "server_error",
    "invalid_json",
    "schema_violation",
    "empty_response",
]

RETRYABLE: frozenset[FailureKind] = frozenset({"timeout", "transport", "server_error"})


class InferenceBackendError(RuntimeError):
    """Fallo de transporte o de contrato con el servidor de inferencia."""

    def __init__(self, kind: FailureKind, message: str) -> None:
        super().__init__(message)
        self.kind: FailureKind = kind

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE


@dataclass(frozen=True)
class GenerationParameters:
    """Parámetros de generación con reproducibilidad como valor por defecto.

    `temperature` 0.0 y `seed` fijo no son una preferencia estética: una
    evaluación de Fase 4 que no se puede repetir no es evidencia. Quien quiera
    muestreo creativo debe pedirlo explícitamente.
    """

    temperature: float = 0.0
    top_p: float = 1.0
    max_output_tokens: int = 1024
    seed: int | None = 0
    stop: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature debe estar en [0.0, 2.0].")
        if not 0.0 < self.top_p <= 1.0:
            raise ValueError("top_p debe estar en (0.0, 1.0].")
        if self.max_output_tokens < 1:
            raise ValueError("max_output_tokens debe ser positivo.")

    @property
    def is_reproducible(self) -> bool:
        """Sólo una configuración determinista sostiene una métrica publicable."""
        return self.temperature == 0.0 and self.seed is not None


@dataclass(frozen=True)
class BackendConfig:
    """Configuración del servidor. Todo se inyecta; nada se asume.

    `model` es obligatorio y no tiene valor por defecto **a propósito**:
    mientras D-014 esté pendiente, ningún camino de código debe poder elegir un
    modelo por omisión.
    """

    base_url: str
    model: str
    timeout_seconds: float = 120.0
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    parameters: GenerationParameters = field(default_factory=GenerationParameters)
    quantization: str | None = None
    runtime: str | None = None

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("El backend requiere base_url.")
        if not self.model.strip():
            raise ValueError(
                "El backend requiere un modelo explícito; D-014 no está aceptada."
            )
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds debe ser positivo.")
        if self.max_retries < 0:
            raise ValueError("max_retries no puede ser negativo.")


@dataclass(frozen=True)
class InferenceRequest:
    """Petición de una sección al servidor, con su esquema de salida guiada."""

    prompt: str
    json_schema: Mapping[str, Any]
    schema_name: str

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("La petición requiere prompt.")
        if not self.json_schema:
            raise ValueError("La salida guiada requiere un esquema JSON cerrado.")


@dataclass(frozen=True)
class InferenceResponse:
    """Respuesta ya parseada y atribuida a un modelo concreto."""

    payload: Mapping[str, Any]
    model: str
    attempts: int
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    duration_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.model.strip():
            # Una respuesta sin modelo no es atribuible, y una métrica no
            # atribuible no puede compararse en DEV-408.
            raise ValueError("Toda respuesta debe declarar el modelo que la produjo.")


def build_chat_payload(
    config: BackendConfig, request: InferenceRequest
) -> dict[str, Any]:
    """Construye el cuerpo de la llamada compatible con OpenAI chat.

    Se usa `response_format` de tipo `json_schema` con `strict`: la salida
    guiada es la barrera que evita tener que "reparar" JSON. Reparar una
    respuesta malformada es inventar contenido, y el contrato de evidencia lo
    prohíbe.
    """
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [{"role": "user", "content": request.prompt}],
        "temperature": config.parameters.temperature,
        "top_p": config.parameters.top_p,
        "max_tokens": config.parameters.max_output_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": request.schema_name,
                "schema": dict(request.json_schema),
                "strict": True,
            },
        },
    }
    if config.parameters.seed is not None:
        payload["seed"] = config.parameters.seed
    if config.parameters.stop:
        payload["stop"] = list(config.parameters.stop)
    return payload


def parse_chat_response(raw: Mapping[str, Any], config: BackendConfig) -> Mapping[str, Any]:
    """Extrae y parsea el JSON de una respuesta de chat.

    No repara, no recorta y no rellena huecos: si la respuesta no es el JSON
    que se pidió, es un fallo declarado, no un resultado degradado.
    """
    choices = raw.get("choices")
    if not choices:
        raise InferenceBackendError(
            "empty_response", "El servidor no devolvió ninguna alternativa."
        )
    content = choices[0].get("message", {}).get("content")
    if not content:
        raise InferenceBackendError(
            "empty_response", "La alternativa no contiene contenido."
        )
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        raise InferenceBackendError(
            "invalid_json", f"La respuesta no es JSON válido: {error}"
        ) from error
    if not isinstance(parsed, dict):
        raise InferenceBackendError(
            "schema_violation", "La respuesta debe ser un objeto JSON."
        )
    returned = raw.get("model")
    if returned and config.model and returned != config.model:
        # Un servidor que sirve otro modelo del solicitado invalida la
        # atribución de toda la ejecución. Es preferible fallar que publicar
        # métricas de un modelo bajo el nombre de otro.
        raise InferenceBackendError(
            "schema_violation",
            f"El servidor respondió con el modelo {returned!r}, no {config.model!r}.",
        )
    return parsed


def call_with_retries(
    config: BackendConfig,
    request: InferenceRequest,
    send: Callable[[Mapping[str, Any], float], Mapping[str, Any]],
    *,
    sleep: Callable[[float], None] | None = None,
) -> InferenceResponse:
    """Ejecuta la llamada aplicando la política de reintentos del contrato.

    `send` recibe el cuerpo y el timeout y devuelve la respuesta cruda. Inyectar
    el envío mantiene este módulo puro y comprobable sin levantar un servidor.

    Sólo se reintentan los fallos transitorios. Un JSON inválido o un esquema
    incumplido se propagan al primer intento: con `temperature` 0 y semilla
    fija, repetir produce exactamente el mismo error.
    """
    sleeper = sleep or (lambda _seconds: None)
    payload = build_chat_payload(config, request)
    last: InferenceBackendError | None = None

    for attempt in range(1, config.max_retries + 2):
        try:
            raw = send(payload, config.timeout_seconds)
        except InferenceBackendError as error:
            if not error.retryable or attempt == config.max_retries + 1:
                raise
            last = error
            sleeper(config.retry_backoff_seconds * attempt)
            continue

        parsed = parse_chat_response(raw, config)
        usage = raw.get("usage") or {}
        choice = (raw.get("choices") or [{}])[0]
        return InferenceResponse(
            payload=parsed,
            model=str(raw.get("model") or config.model),
            attempts=attempt,
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )

    assert last is not None  # pragma: no cover - el bucle siempre sale antes
    raise last
