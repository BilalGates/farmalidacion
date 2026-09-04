"""Adaptador entre el servidor local y `ExtractorLLM` (DEV-402).

Estas pruebas fijan lo que el adaptador **no** puede hacer: elegir modelo,
admitir sus propias propuestas, reparar una respuesta malformada o alterar el
texto sobre el que se citará la evidencia.
"""

from collections.abc import Mapping
from typing import Any

import pytest

from pharma_validator_api.evidence_verification import DocumentSection
from pharma_validator_api.extractor import (
    ExtractorError,
    FieldRequest,
    SectionRequest,
    run_extraction,
)
from pharma_validator_api.inference_backend import (
    BackendConfig,
    InferenceBackendError,
)
from pharma_validator_api.llm_extractor import (
    LocalServerExtractor,
    build_prompt,
)

# HTML literal con entidades, como el corpus real.
SECTION_TEXT = "<p>La dosis recomendada es de 20 mg cada 24&#160;horas</p>"
SECTION = DocumentSection("ver-1", "4.2", SECTION_TEXT)
POSOLOGIA = FieldRequest("POSOLOGIA", "Dosis", "CHAR(100)", "proponer_valor")
REQUEST = SectionRequest("ver-1", "Ejemplo 20 mg", SECTION, (POSOLOGIA,))

EVIDENCE = "La dosis recomendada es de 20 mg"
START = SECTION_TEXT.index(EVIDENCE)


def config(model: str = "modelo-pendiente-de-d014") -> BackendConfig:
    return BackendConfig(base_url="http://localhost:8000/v1", model=model)


def chat(content: str, model: str = "modelo-pendiente-de-d014") -> dict[str, Any]:
    return {
        "model": model,
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def result(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "campo": "POSOLOGIA",
        "estado": "encontrado",
        "valor": "20 mg",
        "opciones": None,
        "evidencia_texto": EVIDENCE,
        "evidencia_ini": START,
        "evidencia_fin": START + len(EVIDENCE),
        "confianza": 0.9,
    }
    base.update(overrides)
    return base


def sender_returning(payload: str):
    def send(body: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        return chat(payload)

    return send


def test_the_adapter_cannot_be_built_without_a_model() -> None:
    """D-014 sigue pendiente: ningún camino elige modelo por omisión."""
    with pytest.raises(ValueError, match="D-014"):
        BackendConfig(base_url="http://localhost:8000/v1", model="")


def test_identity_carries_the_configured_model() -> None:
    """Sin atribución, los resultados de DEV-408 no serían comparables."""
    extractor = LocalServerExtractor(config("modelo-x"), sender_returning("{}"))

    assert extractor.identity.model == "modelo-x"
    assert extractor.identity.extractor_version == "llm-extractor-v1"


def test_prompt_carries_the_section_text_verbatim() -> None:
    """El texto no se limpia: la evidencia se citará sobre esta misma cadena."""
    prompt = build_prompt(REQUEST)

    assert SECTION_TEXT in prompt
    assert "&#160;" in prompt
    assert "POSOLOGIA" in prompt


def test_a_well_formed_response_becomes_an_admitted_proposal() -> None:
    """Camino feliz completo: transporte, esquema y verificación literal."""
    import json

    extractor = LocalServerExtractor(
        config(), sender_returning(json.dumps({"resultados": [result()]}))
    )
    outcome = run_extraction(extractor, REQUEST)

    assert len(outcome.admitted) == 1
    assert outcome.admitted[0].proposal is not None
    assert outcome.admitted[0].proposal.proposed_value == "20 mg"
    assert not outcome.incidents


def test_an_invented_citation_is_rejected_by_the_literal_verifier() -> None:
    """El adaptador no puede admitir sus propias propuestas."""
    import json

    extractor = LocalServerExtractor(
        config(),
        sender_returning(
            json.dumps(
                {"resultados": [result(evidencia_texto="Texto que no aparece jamas")]}
            )
        ),
    )
    outcome = run_extraction(extractor, REQUEST)

    assert not outcome.admitted
    assert outcome.rejected


def test_a_server_failure_becomes_an_incident_not_a_crash() -> None:
    """Un servidor caído degrada la extracción; no bloquea la revisión manual."""

    def send(body: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        raise InferenceBackendError("server_error", "500")

    outcome = run_extraction(LocalServerExtractor(config(), send), REQUEST)

    assert not outcome.admitted
    assert outcome.incidents
    assert "inferencia" in outcome.incidents[0]


def test_a_malformed_response_is_not_repaired() -> None:
    """Reparar introduciría un valor que el modelo no emitió."""
    extractor = LocalServerExtractor(config(), sender_returning("no soy json"))

    with pytest.raises(ExtractorError):
        extractor.extract_section(REQUEST)


def test_a_schema_violation_surfaces_as_an_extractor_error() -> None:
    import json

    extractor = LocalServerExtractor(
        config(), sender_returning(json.dumps({"resultados": []}))
    )

    with pytest.raises(ExtractorError):
        extractor.extract_section(REQUEST)


def test_the_request_asks_for_strict_guided_output() -> None:
    """La salida guiada es lo que evita tener que reparar JSON."""
    captured: dict[str, Any] = {}

    def send(body: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        captured.update(body)
        import json

        return chat(json.dumps({"resultados": [result()]}))

    LocalServerExtractor(config(), send).extract_section(REQUEST)

    fmt = captured["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True
    assert captured["temperature"] == 0.0
