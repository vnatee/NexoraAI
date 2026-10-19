from __future__ import annotations

import json
import logging

import pytest

from core.observability import JsonLogFormatter, load_observability_settings


def test_observability_defaults_to_none_without_azure_connection():
    settings = load_observability_settings({})

    assert settings.provider == "none"
    assert settings.service_name == "nexoraai"
    assert settings.environment == "local"
    assert settings.json_logs is False


def test_observability_auto_preserves_azure_monitor_behavior():
    settings = load_observability_settings(
        {"APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=test"}
    )

    assert settings.provider == "azure_monitor"


def test_explicit_otlp_requires_absolute_http_endpoint():
    with pytest.raises(ValueError, match="absolute HTTP"):
        load_observability_settings({"OBSERVABILITY_PROVIDER": "otlp"})

    settings = load_observability_settings(
        {
            "OBSERVABILITY_PROVIDER": "otlp",
            "OBSERVABILITY_OTLP_ENDPOINT": "http://collector:4318/v1/traces",
            "OBSERVABILITY_JSON_LOGS": "true",
        }
    )

    assert settings.provider == "otlp"
    assert settings.otlp_endpoint == "http://collector:4318/v1/traces"
    assert settings.json_logs is True


def test_explicit_azure_monitor_requires_connection_string():
    with pytest.raises(ValueError, match="APPLICATIONINSIGHTS_CONNECTION_STRING"):
        load_observability_settings({"OBSERVABILITY_PROVIDER": "azure_monitor"})


def test_json_formatter_uses_stable_envelope_and_ignores_arbitrary_extras():
    settings = load_observability_settings(
        {
            "OBSERVABILITY_PROVIDER": "none",
            "OBSERVABILITY_SERVICE_NAME": "nexoraai",
            "OBSERVABILITY_ENVIRONMENT": "test",
            "OBSERVABILITY_SERVICE_VERSION": "2.3.0",
            "OBSERVABILITY_JSON_LOGS": "true",
        }
    )
    record = logging.LogRecord(
        name="nexora.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="ready",
        args=(),
        exc_info=None,
    )
    record.secret = "must-not-leak"

    payload = json.loads(JsonLogFormatter(settings).format(record))

    assert payload["message"] == "ready"
    assert payload["service"] == "nexoraai"
    assert payload["environment"] == "test"
    assert payload["version"] == "2.3.0"
    assert "secret" not in payload
    assert "must-not-leak" not in str(payload)
