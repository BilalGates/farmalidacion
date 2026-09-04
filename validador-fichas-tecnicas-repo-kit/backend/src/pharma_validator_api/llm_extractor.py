"""Adaptador que conecta el servidor local con la interfaz `ExtractorLLM` (DEV-402).

Este módulo **no añade una capa nueva**: une piezas que ya existen y que hasta
ahora no se hablaban entre sí.

    build_schema (DEV-403) → inference_backend (transporte) → parse_response (DEV-403)
                           → run_extraction → verify_extraction (DEV-405)

Todo lo que decide algo ya estaba escrito. Aquí sólo se ordena la secuencia.

Dos cosas que este adaptador deliberadamente **no** hace:

- **No elige modelo.** `BackendConfig` lo exige explícito, y quien construye el
  adaptador debe aportarlo. Mientras D-014 siga pendiente, no existe ningún
  camino que seleccione uno por omisión.
- **No admite propuestas.** Devuelve candidatas. La admisión la decide
  `run_extraction` con el verificador literal, y ese orden no se invierte:
  un adaptador que pudiera admitir sus propias propuestas puentearía la barrera
  de evidencia.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pharma_validator_api.evidence_verification import ProposedExtraction
from pharma_validator_api.extractor import (
    ExtractorError,
    ExtractorIdentity,
    ExtractorLLM,
    SectionRequest,
)
from pharma_validator_api.guided_schema import (
    GuidedSchemaError,
    build_schema,
    parse_response,
)
from pharma_validator_api.inference_backend import (
    BackendConfig,
    InferenceBackendError,
    InferenceRequest,
    call_with_retries,
)

ADAPTER_VERSION = "llm-extractor-v1"

#: Versión del prompt. Forma parte de la identidad del trabajo en
#: `extraction_batches`: cambiarlo supera las ejecuciones anteriores en lugar de
#: mezclarse con ellas.
PROMPT_VERSION = "seccion-v1"

Sender = Callable[[Mapping[str, Any], float], Mapping[str, Any]]


def build_prompt(request: SectionRequest) -> str:
    """Redacta la petición de una sección.

    El texto de la sección se entrega **tal cual se almacenó**. No se limpia el
    HTML ni se normalizan los espacios: la evidencia se citará por
    desplazamientos sobre esta misma cadena, y cualquier transformación aquí
    haría que los desplazamientos del modelo no correspondiesen al documento
    inmutable.
    """
    campos = "\n".join(
        f"- {item.field_name} ({item.data_type}): {item.description}"
        for item in request.fields
    )
    return (
        "Eres un asistente que localiza datos en una ficha técnica de medicamento.\n"
        "Transcribe literalmente lo que dice el texto. No interpretes, no calcules, "
        "no conviertas unidades y no completes lo que el texto no diga.\n"
        "Para cada campo devuelve el valor y la cita literal exacta que lo respalda, "
        "copiada carácter a carácter del texto.\n"
        "Si un campo no aparece en el texto, devuélvelo con estado 'no_encontrado' "
        "y sin valor.\n\n"
        f"Medicamento: {request.medication_name}\n"
        f"Apartado: {request.section.section}\n\n"
        f"Campos solicitados:\n{campos}\n\n"
        f"Texto del apartado:\n{request.section.canonical_text}"
    )


class LocalServerExtractor(ExtractorLLM):
    """Extractor contra un servidor local compatible con OpenAI-chat.

    El envío HTTP se inyecta (`sender`), de modo que el adaptador se prueba sin
    levantar un servidor y sin GPU. La implementación real de `sender` es un
    detalle de despliegue que depende del runtime que se acepte en D-014.
    """

    def __init__(
        self,
        config: BackendConfig,
        sender: Sender,
        *,
        adapter_version: str = ADAPTER_VERSION,
    ) -> None:
        self._config = config
        self._sender = sender
        # La identidad incluye el modelo declarado en la configuración: sin
        # atribución, los resultados de DEV-408 no serían comparables.
        self._identity = ExtractorIdentity(adapter_version, config.model)

    @property
    def identity(self) -> ExtractorIdentity:
        return self._identity

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION

    def extract_section(self, request: SectionRequest) -> tuple[ProposedExtraction, ...]:
        """Pide una sección y devuelve candidatas sin admitir ninguna.

        Todo fallo se traduce a `ExtractorError`, que `run_extraction` convierte
        en incidencia sin interrumpir el lote. Un servidor caído degrada la
        extracción, no bloquea la revisión manual.
        """
        schema = build_schema(request.fields)
        inference = InferenceRequest(
            prompt=build_prompt(request),
            json_schema=schema,
            schema_name="extraccion_seccion",
        )
        try:
            response = call_with_retries(self._config, inference, self._sender)
        except InferenceBackendError as error:
            raise ExtractorError(
                f"El servidor de inferencia falló ({error.kind}): {error}"
            ) from error

        try:
            return parse_response(
                dict(response.payload), request.fields, request.section.section
            )
        except (GuidedSchemaError, ValueError) as error:
            # Una respuesta que no cumple el esquema no se repara: reparar
            # introduciría un valor que el modelo no emitió.
            raise ExtractorError(
                f"La respuesta no cumple el esquema guiado: {error}"
            ) from error
