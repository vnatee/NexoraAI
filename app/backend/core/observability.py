from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.trace import Span, Status, StatusCode


@dataclass(frozen=True)
class ObservabilitySettings:
    provider: str
    service_name: str
    environment: str
    service_version: str
    json_logs: bool
    otlp_endpoint: str | None = None


_instrumentation_started = False

_SAFE_AGENT_PROMPT_TEMPLATE = """Role: {{role}}
Task: {{task}}
Context: {{detail_context}}
Output format: {{output_format}}
Constraints: {{constraints}}"""
_SAFE_AGENT_PROMPT_VARIABLES = {
    "role": "<redacted>",
    "task": "<redacted>",
    "detail_context": "<redacted>",
    "output_format": "<redacted>",
    "constraints": "<redacted>",
}


def _is_true(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_observability_settings(
    environ: Mapping[str, str] | None = None,
) -> ObservabilitySettings:
    settings = os.environ if environ is None else environ
    requested = str(settings.get("OBSERVABILITY_PROVIDER", "auto")).strip().lower()
    if requested == "auto":
        provider = (
            "azure_monitor"
            if str(settings.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")).strip()
            else "none"
        )
    else:
        provider = requested
    if provider not in {"none", "azure_monitor", "otlp"}:
        raise ValueError(
            "OBSERVABILITY_PROVIDER must be auto, none, azure_monitor, or otlp"
        )

    endpoint = str(
        settings.get("OBSERVABILITY_OTLP_ENDPOINT")
        or settings.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or ""
    ).strip()
    if provider == "azure_monitor" and not str(
        settings.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    ).strip():
        raise ValueError(
            "APPLICATIONINSIGHTS_CONNECTION_STRING is required for azure_monitor"
        )
    if provider == "otlp":
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                "OBSERVABILITY_OTLP_ENDPOINT must be an absolute HTTP(S) URL for otlp"
            )

    return ObservabilitySettings(
        provider=provider,
        service_name=str(
            settings.get("OBSERVABILITY_SERVICE_NAME", "nexoraai")
        ).strip()
        or "nexoraai",
        environment=str(
            settings.get("OBSERVABILITY_ENVIRONMENT", "local")
        ).strip()
        or "local",
        service_version=str(settings.get("OBSERVABILITY_SERVICE_VERSION", "")).strip(),
        json_logs=_is_true(settings.get("OBSERVABILITY_JSON_LOGS")),
        otlp_endpoint=endpoint or None,
    )


class JsonLogFormatter(logging.Formatter):
    """Small stable JSON envelope; application messages remain caller-owned."""

    def __init__(self, settings: ObservabilitySettings):
        super().__init__()
        self.settings = settings

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, timezone.utc
            ).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.settings.service_name,
            "environment": self.settings.environment,
        }
        if self.settings.service_version:
            payload["version"] = self.settings.service_version
        trace_ids = current_trace_identifiers()
        if trace_ids:
            payload.update(trace_ids)
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_application_logging(settings: ObservabilitySettings) -> None:
    if not settings.json_logs:
        return
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.addHandler(logging.StreamHandler())
    formatter = JsonLogFormatter(settings)
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)


def _instrument_clients() -> None:
    global _instrumentation_started
    if _instrumentation_started:
        return
    # Prompt, response, tool arguments and tool output are never enabled here.
    os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "false"
    AioHttpClientInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    OpenAIInstrumentor().instrument()
    _instrumentation_started = True


def configure_application_observability(app: Any) -> ObservabilitySettings:
    settings = load_observability_settings()
    configure_application_logging(settings)
    app.config["observability_settings"] = settings
    if settings.provider == "none":
        app.logger.info("Observability export is disabled")
        return settings

    if settings.provider == "azure_monitor":
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor()
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource_attributes = {
            "service.name": settings.service_name,
            "deployment.environment.name": settings.environment,
        }
        if settings.service_version:
            resource_attributes["service.version"] = settings.service_version
        provider = TracerProvider(resource=Resource.create(resource_attributes))
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otlp_endpoint))
        )
        trace.set_tracer_provider(provider)

    _instrument_clients()
    app.asgi_app = OpenTelemetryMiddleware(app.asgi_app)
    app.logger.info(
        "Observability export enabled through %s for service %s",
        settings.provider,
        settings.service_name,
    )
    return settings


def current_trace_identifiers() -> dict[str, str]:
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return {}
    return {
        "trace_id": format(context.trace_id, "032x"),
        "span_id": format(context.span_id, "016x"),
    }


def _set_if_present(span: Span, key: str, value: Any) -> None:
    if value is not None and value != "":
        span.set_attribute(key, value)


def datadog_prompt_tracking_attribute(
    system_prompt: str,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Return opt-in Datadog Prompt Tracking metadata without prompt content."""

    settings = os.environ if environ is None else environ
    if not _is_true(settings.get("DATADOG_LLMOBS_PROMPT_TRACKING_ENABLED")):
        return None
    prompt_fingerprint = hashlib.sha256(
        str(system_prompt or "").encode("utf-8")
    ).hexdigest()[:12]
    return json.dumps(
        {
            "name": "nexora-agent-system-prompt",
            "version": f"sha256-{prompt_fingerprint}",
            "template": _SAFE_AGENT_PROMPT_TEMPLATE,
            "variables": _SAFE_AGENT_PROMPT_VARIABLES,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


@contextmanager
def agent_run_span(audit: Any, message_count: int) -> Iterator[Span]:
    tracer = trace.get_tracer("nexoraai.agent_runtime")
    with tracer.start_as_current_span("agent.run") as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        span.set_attribute("gen_ai.input.messages.count", int(message_count))
        if audit is not None:
            _set_if_present(span, "nexora.agent.id", audit.agent_id)
            _set_if_present(span, "nexora.team.id", audit.team_id)
            _set_if_present(span, "nexora.run.id", audit.run_id)
            _set_if_present(span, "nexora.parent_run.id", audit.parent_run_id)
        yield span


@contextmanager
def model_completion_span(system_prompt: str) -> Iterator[Span]:
    tracer = trace.get_tracer("nexoraai.agent_runtime")
    with tracer.start_as_current_span("llm.invoke") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        prompt_tracking = datadog_prompt_tracking_attribute(system_prompt)
        if prompt_tracking is not None:
            span.set_attribute("_dd.ml_obs.prompt_tracking", prompt_tracking)
        yield span


@contextmanager
def tool_execution_span(name: str, source: str | None) -> Iterator[Span]:
    tracer = trace.get_tracer("nexoraai.agent_runtime")
    with tracer.start_as_current_span("tool.execute") as span:
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        _set_if_present(span, "gen_ai.tool.name", name)
        _set_if_present(span, "nexora.tool.source", source)
        yield span


def mark_span_success(span: Span, **attributes: Any) -> None:
    for key, value in attributes.items():
        _set_if_present(span, key, value)
    span.set_status(Status(StatusCode.OK))


def mark_span_failed(span: Span, error_type: str) -> None:
    span.set_attribute("error.type", str(error_type))
    span.set_status(Status(StatusCode.ERROR))


def mark_span_error(span: Span, error: BaseException) -> None:
    mark_span_failed(span, type(error).__name__)
