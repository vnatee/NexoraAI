# Agent Invocation API

The Agent Invocation API lets an approved external application invoke a
NexoraAI Agent without using an interactive Portal session. Access is
Team-scoped and is configured in **Team workspace > Team governance > Agent API
access**.

For application code, Postman setup, and an acceptance checklist, start with
the [Agent API Developer Guide](agent-api-developer-guide.md). A deployment
publishes its machine-readable OpenAPI 3.0 contract at
`/api/v1/openapi.yaml`.

## Security model

Each key is restricted to:

- one Team;
- one or more active LangGraph Agents in that Team;
- selected Team-wide Data Groups;
- optional Global Knowledge;
- an expiry date (90 days by default, maximum 365 days); and
- a per-minute request limit (60 by default, maximum 1,000).

Personal Knowledge and Data Groups restricted to selected users cannot be
assigned to an API key. Agent guardrails, server-side tool policy, licensing and
LLM usage quotas are still enforced for every invocation.

The complete key is displayed only after creation or rotation. NexoraAI stores
a SHA-256 digest, not the plaintext secret. Treat the displayed value as a
password: copy it into the calling application's secret store and never commit
it to source control.

## Create a key

A Team administrator with **Manage agents** permission can:

1. Open the Team workspace.
2. Open **Team governance > Agent API access**.
3. Select **Create API key**.
4. Enter a descriptive name, such as `HR portal - production`.
5. Select the Agents the application may invoke.
6. Select only the Team-wide Knowledge required by the application.
7. Optionally allow Global Knowledge.
8. Set expiry and requests per minute.
9. Select **Create key**, then copy the secret immediately.

If the secret is lost, rotate the key. It cannot be displayed again.

## Invoke an Agent

```bash
curl -X POST "https://YOUR-NEXORA-HOST/api/v1/agents/AGENT_ID/invoke" \
  -H "Authorization: Bearer nxai_REDACTED" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Summarize the current employee leave policy.",
    "conversation_id": "71d143ae-ad2f-45f3-915e-a7d465141486"
  }'
```

`conversation_id` is optional. If omitted, NexoraAI creates one and returns it
for request correlation. Synchronous invocations are stateless.

Successful response:

```json
{
  "id": "request-id",
  "object": "agent.invocation",
  "agent_id": "agent-id",
  "conversation_id": "conversation-id",
  "output": "The Agent response.",
  "citations": [],
  "chart": null,
  "diagram": null
}
```

Internal reasoning and tool traces are never returned. Citations, a validated
chart, or a diagram are returned only when the Agent runtime produced them.

## Stream an invocation

Use Server-Sent Events (SSE) when the caller needs an open connection and
lifecycle updates while the Agent works:

```bash
curl -N -X POST \
  "https://YOUR-NEXORA-HOST/api/v1/agents/AGENT_ID/invoke/stream" \
  -H "Authorization: Bearer nxai_REDACTED" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"input":"Investigate the current service alerts."}'
```

The stream emits `started`, periodic `heartbeat`, and either `completed` or
`error` events. The completed event uses the same public response schema as
the synchronous endpoint. This stream reports execution lifecycle and the final
answer; it deliberately does not expose internal tool events, chain-of-thought,
or unvalidated token fragments.

## Run an asynchronous job

Use an asynchronous job for long-running integrations or callers that should
not keep an HTTP connection open:

```bash
curl -X POST \
  "https://YOUR-NEXORA-HOST/api/v1/agents/AGENT_ID/jobs" \
  -H "Authorization: Bearer nxai_REDACTED" \
  -H "Idempotency-Key: customer-operation-123" \
  -H "Content-Type: application/json" \
  -d '{"input":"Analyze the incident and compare it with our runbooks."}'
```

The API returns `202 Accepted`, a job object, and a `Location` header. Poll
that URL with the same API key:

```bash
curl "https://YOUR-NEXORA-HOST/api/v1/agent-jobs/JOB_ID" \
  -H "Authorization: Bearer nxai_REDACTED"
```

Job status is one of `queued`, `running`, `succeeded`, or `failed`. A
successful job includes `result` in the synchronous invocation response
format. Only the key that created the job may read or retry it.

If a failed job remains within its retention period, retry it with:

```bash
curl -X POST \
  "https://YOUR-NEXORA-HOST/api/v1/agent-jobs/JOB_ID/retry" \
  -H "Authorization: Bearer nxai_REDACTED"
```

`Idempotency-Key` is optional but strongly recommended. Repeating the same
request with the same key returns the original job and does not run it twice.
Reusing that key with a different Agent, input, or conversation returns `409`.
Only keyed HMAC digests of the idempotency key and request fingerprint are stored.

Queued and running jobs use leases so another application replica can resume
work after a restart. Recovery is at-least-once: an external action may have
completed immediately before a worker failed, so action tools should also use
their own idempotency controls. Inputs and successful results are encrypted with
`APP_DATA_ENCRYPTION_KEY` while stored. They expire automatically after
`AGENT_INVOCATION_JOB_RETENTION_HOURS` (168 hours by default). Keep the
encryption key stable across replicas and restarts.


## Key lifecycle

- **Rotate** creates a new secret with the same Agent and Knowledge scope and
  revokes the old key immediately.
- **Revoke** disables the key immediately.
- Expired and revoked keys remain visible as metadata for administration but
  cannot authenticate.
- **Last used** is updated after a successful invocation.
- Audit events contain identifiers, outcome, duration and an error class only;
  prompt and response content are not stored in this API-key audit collection.

Recommended practice is one key per calling application and environment. Rotate
before expiry, revoke unused keys, and use the smallest Agent and Knowledge
scope required.

## Error responses

Common status codes are:

- `400`: invalid input or key configuration;
- `401`: missing, invalid, revoked or expired key;
- `403`: the key does not allow that Agent or Knowledge scope;
- `404`: Agent unavailable in the key's Team;
- `409`: inactive/non-LangGraph Agent or stale configuration;
- `413`: input exceeds the configured character limit;
- `429`: API-key rate limit or Team usage quota exceeded.

The Phase 3A API publishes an OpenAPI contract and includes a Postman collection
plus Python, TypeScript, C#, and curl integration examples. Generated client SDK
packages, webhooks, cancellation, and true token-delta streaming remain planned
follow-up work.
