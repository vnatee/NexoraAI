# Datadog monitoring installation (deferred)

This guide is for a later production change window. Datadog is not a NexoraAI
startup dependency and is not included in the base Compose runtime. The same
procedure applies to a private Linux VM whether the VM is on-premises or hosted
as Azure IaaS.

## What is ready before Datadog is installed

- container logs on standard output, optionally formatted as JSON
- unauthenticated, detail-free liveness and readiness endpoints
- provider-neutral OpenTelemetry HTTP, model, Agent and tool spans
- authenticated System Health and metadata-only Agent Audit
- no Datadog API key, Agent image, host socket mount or outbound Datadog traffic

The Datadog MCP integration is separate. It lets an authorized NexoraAI Agent
read Datadog data; it does not monitor NexoraAI.

## Deployment decision

Use a Datadog Agent on the same Docker host for the first deployment. It can
collect host/container metrics and logs and receive OTLP traces over the private
Compose network. Do not publish ports 4318, 8126, or the Docker socket to the
public network.

Keep the Datadog API key in the deployment secret store or ignored environment
file. Never put it in Git, an Agent prompt, a Knowledge document, or the Portal.

## Example Compose overlay

Create an operator-owned overlay outside the repository, for example
`/opt/nexora/docker-compose.datadog.yml`:

```yaml
services:
  datadog-agent:
    image: gcr.io/datadoghq/agent:7
    restart: unless-stopped
    environment:
      DD_API_KEY: ${DD_API_KEY:?Set DD_API_KEY}
      DD_SITE: ${DD_SITE:-datadoghq.com}
      DD_ENV: ${OBSERVABILITY_ENVIRONMENT:-production}
      DD_SERVICE: ${OBSERVABILITY_SERVICE_NAME:-nexoraai}
      DD_VERSION: ${OBSERVABILITY_SERVICE_VERSION:-}
      DD_APM_ENABLED: "true"
      DD_LOGS_ENABLED: "true"
      DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL: "true"
      DD_CONTAINER_EXCLUDE_LOGS: "name:datadog-agent"
      DD_OTLP_CONFIG_RECEIVER_PROTOCOLS_HTTP_ENDPOINT: 0.0.0.0:4318
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /proc:/host/proc:ro
      - /sys/fs/cgroup:/host/sys/fs/cgroup:ro

  app:
    environment:
      OBSERVABILITY_PROVIDER: otlp
      OBSERVABILITY_SERVICE_NAME: ${OBSERVABILITY_SERVICE_NAME:-nexoraai}
      OBSERVABILITY_ENVIRONMENT: ${OBSERVABILITY_ENVIRONMENT:-production}
      OBSERVABILITY_SERVICE_VERSION: ${OBSERVABILITY_SERVICE_VERSION:-}
      OBSERVABILITY_JSON_LOGS: "true"
      OBSERVABILITY_OTLP_ENDPOINT: http://datadog-agent:4318/v1/traces
```

Pin the Agent image or digest according to the customer's patch policy before
production. Validate the exact environment variable names against the Datadog
Agent version selected for that change window.

Start the existing runtime plus the operator overlay:

```bash
docker compose \
  --env-file /opt/nexora/.env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f /opt/nexora/docker-compose.datadog.yml \
  up -d
```

## Verification

Before enabling trace export:

```bash
curl -fsS http://127.0.0.1:50505/health/live
curl -fsS http://127.0.0.1:50505/health/ready
docker compose logs app --tail=20
```

After adding the overlay:

1. Confirm the Datadog Agent is healthy and can reach the selected Datadog site.
2. Confirm host and Docker container metrics appear.
3. Confirm NexoraAI JSON logs parse `service`, `environment`, `trace_id`
   and `span_id`.
4. Invoke one ordinary API route and confirm service `nexoraai` appears in APM.
5. Invoke one LangGraph Agent that calls a read-only tool. Confirm an
   `agent.run` span contains a child `tool.execute` span and the model call.
6. Copy the run ID from Agent Audit and confirm its trace ID correlates to APM.
7. Inspect span and log samples and verify no prompt, response, tool payload,
   credential, retrieved Knowledge, or attachment content is present.
8. Configure alerts for readiness failure, HTTP 5xx/error rate, p95 latency,
   container restart, CPU/memory/disk pressure and failed background jobs.

For a private deployment, run endpoint checks from the local Datadog Agent or
another private monitoring node. Do not expose `/admin/system-health`.

## LLM Observability boundary

The first connection provides OpenTelemetry APM traces for model calls plus
NexoraAI Agent/tool spans. Do not promise that every field automatically appears
in Datadog's specialized LLM Observability UI: that mapping depends on the
Datadog Agent and backend version in use. If the native LLM view is required,
validate it in a staging change window and add a small vendor adapter only for
the missing mapping. The adapter must remain optional, metadata-only by default,
and must preserve the provider-neutral runtime and Azure Monitor compatibility.

## Rollback

Set `OBSERVABILITY_PROVIDER=none`, remove the Datadog overlay from the Compose
command, and recreate only the application and Agent services. Health endpoints,
JSON logs, System Health, Agent Audit and all business functions continue to
work. Removing Datadog must never block Chat, RAG, ingestion, integrations or
Agent Invocation API traffic.
