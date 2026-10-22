# Observability readiness

NexoraAI is observable without requiring Datadog, Azure Monitor, or another
collector on the first production day. The application writes logs to standard
output, exposes small infrastructure probes, and creates provider-neutral
OpenTelemetry spans. Export is disabled by default in the portable runtime.

## Runtime contract

| Surface | Contract |
| --- | --- |
| `GET /health/live` | Process liveness only. Returns HTTP 200 and `{"status":"alive"}`. |
| `GET /health/ready` | Minimal MongoDB readiness. Returns HTTP 200 when ready and HTTP 503 otherwise. It never returns connection details. |
| `GET /admin/system-health` | Authenticated System Administrator snapshot with resource, dependency, integration and queue detail. Do not expose it as a public probe. |
| Standard output | Optional one-line JSON logs for container collection. |
| OpenTelemetry | HTTP, outbound HTTP, OpenAI-compatible calls, `agent.run`, and `tool.execute` traces. |

The Compose liveness check uses `/health/live`. A load balancer or monitoring
system should use `/health/ready` when it needs to stop sending new traffic to
a replica whose metadata database is unavailable.

## Configuration

```dotenv
# none (default), otlp, azure_monitor, or auto
OBSERVABILITY_PROVIDER=none
OBSERVABILITY_SERVICE_NAME=nexoraai
OBSERVABILITY_ENVIRONMENT=production
OBSERVABILITY_SERVICE_VERSION=
OBSERVABILITY_JSON_LOGS=true

# Required only for provider=otlp. Use the complete HTTP trace endpoint.
OBSERVABILITY_OTLP_ENDPOINT=http://collector:4318/v1/traces

# Optional Datadog Prompt Tracking metadata. Prompt content remains redacted.
DATADOG_LLMOBS_PROMPT_TRACKING_ENABLED=false
```

`auto` preserves the existing Azure behavior: it selects Azure Monitor only
when `APPLICATIONINSIGHTS_CONNECTION_STRING` exists; otherwise it selects
`none`. An explicit `azure_monitor` requires that connection string. An
explicit `otlp` requires an absolute HTTP(S) endpoint. Invalid explicit
configuration fails startup instead of silently losing telemetry.

Changing `OBSERVABILITY_PROVIDER` requires an application restart.

## JSON log fields

When `OBSERVABILITY_JSON_LOGS=true`, application handlers use this stable
envelope:

- `timestamp`, `severity`, `logger`, and `message`
- `service`, `environment`, and optional `version`
- `trace_id` and `span_id` when a valid OpenTelemetry context is active
- `exception_type` for exception records

Logs remain on standard output even when trace export is disabled. Existing log
messages are caller-owned, so production review must still prevent application
code from logging secrets or customer content.

## Agent and LLM telemetry

The runtime creates these content-free custom spans:

- `agent.run`: Agent, Team, run linkage, message count, iteration count and
  tool-call count
- `tool.execute`: normalized tool name, source, result status and output size
- OpenAI-compatible model calls: emitted by the existing OpenTelemetry OpenAI
  instrumentation

Agent audit records gain `trace_id` and `span_id` when tracing is active.
The observability layer does not add prompts, responses, tool arguments, tool
outputs, credentials, retrieved Knowledge, attachment content, or actor
identifiers to spans. The runtime forces OpenTelemetry GenAI message-content
capture off before instrumentation starts.

For a controlled Datadog Prompt Tracking trial, set
`DATADOG_LLMOBS_PROMPT_TRACKING_ENABLED=true` and restart the application. The
`llm.invoke` span then includes `_dd.ml_obs.prompt_tracking` with a stable
prompt name, a SHA-256-derived version, a fixed structural template, and
redacted variables. The hash is only a change identifier: raw system prompts,
user messages, model responses, and real variable values are not exported.

This baseline is sufficient for service maps, latency/error investigation and
correlation from an Agent audit run into infrastructure traces. A vendor's
specialized LLM product view may require a later vendor adapter; that adapter
must keep this no-content policy and must not replace the provider-neutral
spans.

## Operations without a collector

With `OBSERVABILITY_PROVIDER=none`:

1. NexoraAI starts and serves traffic normally.
2. Health probes and JSON logs remain available.
3. Agent audit and System Health remain available in the product.
4. No trace exporter makes an outbound connection.
5. Installing a collector later does not require recreating Agents or Knowledge.

See [Datadog monitoring installation](datadog-monitoring.md) for the deferred
collector procedure.
