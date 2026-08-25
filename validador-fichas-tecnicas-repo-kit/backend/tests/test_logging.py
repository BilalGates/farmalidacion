import json
import logging

from pharma_validator_api.logging import JsonFormatter


def test_json_formatter_emits_structured_record() -> None:
    record = logging.LogRecord(
        name="backend.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Servicio disponible",
        args=(),
        exc_info=None,
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "backend.test"
    assert payload["message"] == "Servicio disponible"
    assert payload["timestamp"].endswith("+00:00")
