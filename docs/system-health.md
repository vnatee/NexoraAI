# System Health

System Health is a System-Admin-only operational view inside **System
administration**. It is intended for first-line diagnosis; it does not replace
external monitoring because the in-product page is unavailable whenever the
application itself is down.

## Current checks

- application API availability;
- active MongoDB ping;
- active MinIO, Qdrant, Ollama, and Integration Controller health probes when
  those local services are configured;
- initialized status for Azure storage/search and non-local model clients;
- secret-free counts of configured, enabled, disabled, and attention-required
  integrations;
- ingestion and temporary attachment queue, processing, failure, recovery
  worker, and cleanup worker status.

The browser loads one snapshot when the page opens and refreshes only when a
System Administrator selects **Refresh**; there is no continuous browser
polling. The snapshot also includes CPU, memory, root-disk, logical-core/load,
and application resident-memory values from the runtime environment visible to
the application process. In a container deployment these values may describe
the container namespace/runtime rather than the physical host's capacity.

HTTP probes have a short timeout. The response contains provider names and controlled status messages,
but never configured URLs, exception text, credentials, prompts, tool output,
or document content.

## API

`GET /admin/system-health` requires an active System Administrator. The route
returns HTTP 200 when the monitoring surface itself is available, with an
overall `healthy` or `degraded` status in the body. This lets the page display
partial results when a dependency is unavailable.

## Follow-up

Add explicit host/container metrics, restart count, request latency/error-rate
time series, alert rules, and external Prometheus/Grafana or Datadog monitoring.
External alerts remain mandatory for production because they can detect a full
NexoraAI outage.
