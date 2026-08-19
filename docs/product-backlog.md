# Product backlog

Items in this document are proposals only. Their architecture, scope, priority, and acceptance criteria must be discussed before implementation.

## Proposed — AI guardrails

Add configurable safeguards around agent input, model output, retrieved content, and tool execution.

Initial discussion scope:

- Guardrail levels: system, team, agent, and individual tool.
- Input controls: prompt-injection detection, sensitive-data detection, topic/policy rules, and request-size limits.
- Output controls: sensitive-data redaction, groundedness/citation checks, unsafe-content handling, and structured-output validation.
- Tool controls: argument validation, allow/deny policies, risk classification, execution limits, and audit events.
- Provider strategy: provider-native guardrails versus a provider-independent local implementation.
- Policy outcomes: allow, block, redact, warn, retry, or route for human review.
- Evaluation: policy test sets, false-positive/false-negative targets, and bypass testing.

## Proposed — Agent invocation API

Expose selected agents for programmatic invocation by approved external systems.

Initial discussion scope:

- API styles: synchronous response, streaming response, and asynchronous job/webhook.
- Authentication: internal API keys, OAuth2 client credentials, or service accounts.
- Authorization: team/agent scopes and whether callers inherit a user identity or use a service identity.
- Agent behavior: conversation/session handling, attachments, RAG access, and tool/MCP execution.
- Operations: versioning, idempotency, rate limits, quotas, timeouts, retries, and cancellation.
- Security: secret rotation, network restrictions, request signing, audit logs, and abuse controls.
- Developer experience: OpenAPI specification, examples, API-key management, and usage/error responses.

## Proposed — System usage dashboard and reporting

Expand reporting to cover system adoption, agent usage, and model-provider consumption across Azure and local modes.

Initial discussion scope:

- Dimensions: time, user, team, agent, provider, model, runtime, tool, and deployment mode.
- Metrics: active users, request count, successful/failed runs, input/output tokens, latency, tool calls, and estimated cost.
- Provider reporting: token usage and errors per configured provider/model, including local models where token counts may be estimated.
- Agent reporting: usage, success/error rate, runtime duration, RAG/tool utilization, and user feedback.
- Access control: system administrators, team administrators, and personal views.
- Data pipeline: event schema, collection point, retention, aggregation, timezone, and export.
- Presentation: summary KPIs, trends, drill-down filters, CSV export, and configurable date ranges.
- Privacy: user identifiers, prompt/content exclusion, aggregation thresholds, and retention/deletion policies.

## Discussion order

Recommended order when these items are scheduled:

1. Define the usage-event and audit-event schemas shared by all three features.
2. Design AI guardrails and tool-execution policies before exposing agents externally.
3. Implement the Agent Invocation API with guardrails, authorization, quotas, and audit events enabled from the beginning.
4. Build dashboard aggregation and reporting from the collected events.

