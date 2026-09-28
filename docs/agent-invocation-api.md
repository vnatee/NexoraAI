# Agent Invocation API

The Agent Invocation API lets an approved external application invoke a
NexoraAI Agent without using an interactive Portal session. Access is
Team-scoped and is configured in **Team workspace > Team governance > Agent API
access**.

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
for request correlation. Phase 1 invocations are stateless.

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

The Phase 1 API is synchronous. Streaming, asynchronous jobs, idempotency keys,
OpenAPI publication and client SDKs remain planned follow-up work.
