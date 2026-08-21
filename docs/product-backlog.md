# Product backlog

Items in this document are proposals only. Their architecture, scope, priority, and acceptance criteria must be discussed before implementation.

## Approved — Chat multimodal, attachments, and evidence workflows

Build a ChatGPT-style composer shared by Chat and Ask. The product owner
approved this direction on 2026-08-21.

### Input experience

- Paste ordinary clipboard text into the composer without changing its text.
- Paste clipboard images, select files, or drag and drop them with previews,
  accessible status, per-item removal, and clear validation errors.
- Accept images and approved document formats with server-enforced type, count,
  and byte limits; do not trust browser MIME declarations alone.
- Keep browser speech-to-text input and improve its recording/progress/error
  feedback. Add provider-neutral server speech-to-text later for browsers or
  deployments where Web Speech is unavailable.
- Future inputs may include camera/screenshot capture, audio-file transcription,
  CSV/Excel analysis, and exported result files.

### Attachment lifecycle and storage

- Draft attachments remain in browser memory until Send and are released from
  component state on removal/send; they are not uploaded merely by selecting
  or pasting them.
- Sent Chat attachments belong only to the authenticated user and conversation.
  Store them behind a provider-neutral `AttachmentStore`, initially backed by a
  private Azure container and later by local filesystem/S3-compatible storage.
- Apply configurable TTL cleanup (target default: 24 hours). Do not add Chat
  documents to permanent Knowledge RAG automatically.
- Process documents into a conversation-private temporary attachment index via
  a provider-neutral `AttachmentIndex`. A separate ACL-checked **Save to
  Knowledge** action may promote an attachment to Personal/Team/Global RAG.
- Keep metadata and audit records in MongoDB-compatible storage. Never persist
  raw prompts, clipboard content, provider responses, or credentials in audit
  events.

### Model and processing behavior

- Record image/multimodal capability per Agent model. Unsupported models must
  use OCR-only text extraction or reject the attachment with a clear reason;
  supported models may receive normalized image parts.
- Keep the attachment request contract provider-neutral and adapt it separately
  for Legacy and LangGraph/OpenAI-compatible runtimes.
- Compose prompts from validated attachment references and extracted text; do
  not interpolate storage paths, untrusted filenames, or raw provider payloads
  into system instructions.

### Requirement-to-evidence workflow

- Parse a requirements/specification attachment into numbered requirements.
- Treat the requirements file as the question/checklist and existing Knowledge
  RAG as evidence; do not cite the uploaded requirement itself as proof.
- Evaluate every requirement and return a structured matrix containing status,
  explanation, Knowledge RAG file, page, and supporting quote.
- Distinguish supported, partially supported/conflicting, missing, and
  insufficient-evidence outcomes. Allow export to Excel/CSV in a later phase.

### Delivery milestones

1. Shared composer: paste text/image, file picker, drag/drop, previews/removal,
   client/server limits, and a canonical attachment request model.
2. Private session `AttachmentStore`, TTL cleanup, document extraction, and
   temporary conversation RAG.
3. Requirement-to-evidence matrix with page-aware Knowledge RAG citations.
4. Per-Agent vision capability and OCR-only versus multimodal execution in both
   Legacy and LangGraph runtimes.
5. Speech improvements, provider-neutral server transcription, camera capture,
   **Save to Knowledge**, retention controls, and result export.

Security acceptance includes owner/conversation authorization, filename/path
normalization, MIME signature validation, decompression/page limits, malware
scanning integration point, prompt-injection boundaries for extracted content,
TTL deletion, and no public attachment URLs.

Current delivery state (2026-08-21): the initial request-local image portion of
milestone 1 is checkpointed for the Legacy vision
runtime, including previews/removal, client/server limits, signature checks,
an explicit composer Vision On/Off control with runtime-aware disabled states,
per-model Portal configuration and live image-input capability probes,
controlled capability errors, citation separation, and diagnostic redaction.
Managed Legacy models no longer require the Azure Knowledge Vision environment
feature merely to process a user attachment. Milestone 2 has started with a
provider-neutral async `AttachmentStore` contract and a private local/container
reference adapter covering owner/conversation ACLs, filename normalization,
atomic writes, integrity checks, TTL, and fail-closed cleanup. Chat/Ask now send
a stable conversation UUID independently from history, and an ACL/expiry-scoped
Mongo-compatible repository stores bounded metadata without exposing storage
keys or owner IDs. Document bytes are not route-integrated yet. The private
Azure adapter/factory, coordinated cleanup, documents, temporary RAG, LangGraph
images, and OCR-only fallback remain pending as described above.

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
