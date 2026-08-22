# Codex handoff — NexoraAI

Last updated: 2026-08-22 UTC

This document replaces a raw chat transcript as the engineering handoff. It
captures the decisions and evidence needed to continue without storing copied
logs, credentials, attachments, or repetitive conversational text.

## Repository state

- Workspace: `/workspaces/NexoraAI`
- Branch: `feature/document-extraction-recovery`
- Base checkpoint: `09eef3e feat: add private chat document workflows`.
- The current working tree adds private Chat document extraction recovery and
  managed OCR routing, plus graceful restart recovery for persistent Knowledge
  ingestion jobs; it is not yet committed.
- Azure baseline: `8ee1e8a` / `origin/Release-2.2.0`
- This checkpoint includes private Chat/Ask document upload, native extraction,
  temporary retrieval, prompt-intent evidence scope, ACL-checked citations,
  per-Agent image/document policy, request-local Vision routing, local/Azure
  attachment storage, retention cleanup, and the memory-safe local build path.
- Milestone 2 now has a provider-neutral `AttachmentStore` contract, private
  local/container and Azure Blob adapters, stable Chat/Ask conversation UUIDs,
  an ACL-scoped Mongo-compatible metadata repository, coordinated object/
  metadata retention cleanup, and authenticated private document upload/list/
  delete APIs. Bounded native extraction and a conversation-private temporary
  index are also implemented. Ready document IDs can now be retrieved by Legacy
  and LangGraph Chat/Ask with bounded, untrusted excerpts and file/page source
  names. The shared composer now uploads supported documents on Send, shows
  processing state, and sends only ready attachment IDs.

## Product background and fixed decisions

NexoraAI began as an Azure-hosted Agentic Platform and Knowledge Management/RAG
application using Azure AI Search, Azure Blob/Data Lake, Azure OpenAI,
embeddings, Azure Document Intelligence, Entra ID, MongoDB/Cosmos-compatible
storage, and Bicep IaC.

The target is one product architecture that can gradually support Azure and a
fully self-hosted/local deployment. The local direction should minimize Azure
PaaS dependency, start with Docker/Compose, and keep a clean path to Helm and
Kubernetes.

Decisions already made with the product owner:

- LLM selection is per Agent.
- Internet access is allowed for explicitly selected cloud LLM, embedding, or
  document-processing providers; “local” does not mean air-gapped by default.
- Internal authentication will eventually use application-managed
  username/password and an internal User Management page, not Keycloak.
- Existing Azure AI Search/Blob/Mongo data does not need migration; a new local
  deployment may start empty, but Azure behavior should have minimal impact.
- Agent tools may execute automatically. Server-side tool policy and audit are
  the safety boundary; there is no mandatory confirmation for every tool call.
- Docker is the first deployment target. Kubernetes follows after interfaces
  and persistent storage are stable.
- Migration should proceed in small slices with smoke tests and rollback/fallback
  behavior, not as a full rewrite.

## Implemented work

### Runtime and LLM providers

- Admin-managed LLM Provider CRUD and encrypted API keys.
- Provider/model selection per Agent and a small model label in Chat Agent
  selection.
- Known vendor choices include Azure OpenAI, OpenAI, Gemini, Anthropic/Claude,
  Ollama, Groq, OpenRouter, Mistral, DeepSeek, Together, vLLM/LocalAI, and generic
  OpenAI-compatible endpoints.
- Vendor-specific request normalization prevents unsupported parameters such as
  Gemini `seed` from being sent.
- Tool/function-calling support is configured per model because capability
  differs even within one vendor.
- The LLM Provider **Test** action now tests every configured model and performs
  live tool-call and image-input probes. Results for each capability are stored
  as `supported`, `unsupported`, or `unknown`. Confirmed unsupported models are
  forced off and the corresponding frontend switch is disabled; inconclusive
  network/quota/provider errors remain editable.
- `Supports image / vision input` is managed per model in the Portal and exposed
  through the Agent LLM profile. A Legacy Agent using a capable managed model
  can process request-local Chat/Ask image attachments without `USE_GPT4V` or
  `AZURE_VISION_ENDPOINT`. Those environment settings remain the separate
  compatibility path for the system profile and Azure Knowledge image vectors.
- Azure Knowledge image-vector retrieval is now enabled only when
  `USE_GPT4V=true` **and** `AZURE_VISION_ENDPOINT` is a valid absolute HTTP(S)
  URL. If the flag is present without the endpoint, startup logs a warning and
  safely falls back to text embeddings/Knowledge text sources while managed
  request-local image input remains available. This prevents the malformed
  `computervision/retrieval:vectorizeText` request previously seen at runtime.
- Provider cards show per-model capability tags after Test (`Tools`, `Vision`,
  `No tools`, or `No vision`). Saving, testing, or deleting a provider refreshes
  Chat/Ask model capabilities immediately without a browser reload.
- OpenAI, Gemini, and Ollama were manually smoke-tested by the product owner.
- Azure smoke testing passed earlier in the migration.

See `docs/model_provider_configuration.md`.

### LangGraph Agent Runtime

- Opt-in/per-Agent LangGraph runtime with the Legacy runtime retained for
  rollback.
- LangChain-compatible tool registry.
- Permission-aware RAG exposed as `search_knowledge`, with Auto, Always, and
  Disabled behavior.
- REST, external database, MCP, chart, mail, messaging, and sub-agent adapters.
- MCP invocation Auto/Required behavior.
- Same-team sub-agent delegation, recursion/cycle protection, and bounded depth.
- Server-enforced tool execution policy: total/per-tool calls, size, timeout,
  blocked tool/source prefixes, and structured policy-denied results.
- Structured run/tool/model audit events with trace IDs. Raw prompts, arguments,
  outputs, and credentials are intentionally not persisted.
- Admin Agent Audit page and audit query endpoint.

See `docs/langgraph-agent-runtime.md`.

### MCP

- Managed MCP Server catalog grouped by category.
- Streamable HTTP discovery/invocation and per-Agent selection.
- Encrypted headers, tool allowlists, test/discovery action, timeout isolation.
- Datadog preset supporting official sites and Bearer PAT/SAT or Datadog
  API/Application keys.
- After a successful MCP connection test, the connected/tool-count badge opens
  a searchable dialog containing the discovered tool names and descriptions.
  This discovery result is held only in the current frontend session and is not
  persisted; running Test again refreshes it without exposing stored headers.
- Datadog live behavior was iterated to force tool use when appropriate and to
  handle monitor/log query issues. Treat broader Datadog tool coverage as a
  continuing integration smoke-test area.

### Database and charts

- Managed PostgreSQL, MySQL/MariaDB, SQL Server, MongoDB, and SQLite
  connections with encrypted credentials and read-only controls.
- Per-Agent Database Query Profiles: business context, allowed objects,
  glossary, rules, and verified examples.
- Schema-first database tool contract and enforced table/collection allowlists.
- General chart generation plus specialized heatmap, radar, gauge, funnel,
  treemap, boxplot, and Sankey schemas.
- Adaptive x-axis label rotation.
- SQL/server-side chart aggregation so heatmaps and boxplots do not silently use
  only the ordinary row window.
- PO-risk query-profile work was used as the primary manual use case, while the
  chart schemas remain industry-neutral.

See `docs/database-integrations.md`.

### Integration management

- Integration Management was reorganized into grouped catalogs while retaining
  the existing visual style.
- Agent Integration tabs were aligned with the management catalogs.
- Mail connections: Microsoft 365 Graph, Gmail API, and generic IMAP/POP3 +
  SMTP, with Agent read/send permissions, recipient constraints, templates, and
  encrypted credentials.
- Messaging & Chat connections: LINE, Slack, and Discord outbound messaging,
  with Agent bindings and templates.
- Mail and messaging adapters exist and have unit coverage. Continue real-server
  E2E tests for SMTP/network timeouts, OAuth permissions, mailbox restrictions,
  channel membership, and write-action policy before production use.

See `docs/mail-integrations.md` and `docs/messaging-integrations.md`.

### Document processing and OCR

- Management page: **Admin Management → Integrations → Document Processing &
  OCR**, with Provider and Profile tabs.
- Existing Azure Document Intelligence and local pypdf behavior remain as
  system providers/fallbacks.
- Docling Serve and optional embedded Docling adapter.
- PaddleOCR/PaddleX self-hosted API adapter for `/ocr` and
  `/layout-parsing`.
- Google Document AI REST adapter using encrypted Service Account JSON and a
  short-lived OAuth service-account assertion; no large Google SDK dependency.
- Generic OCR REST adapter supporting multipart or Base64 JSON, API key/Bearer
  auth, and dot-path response mapping.
- Normalized parser pages can carry text, table, confidence, and provider
  metadata. RAG persists page number and text plus the safe provider/profile/
  confidence allowlist described below.
- Docling Serve and embedded Docling normalize structured provenance into real
  document pages before chunking. Tables remain on their source page, and the
  existing `SplitPage.page_num` contract produces page-aware PDF citations
  without binding the parser to Azure AI Search. Serve requests JSON first and
  sends a separate Markdown request when that format is rejected or does not
  contain recognized pages; Markdown still ingests as one logical page.
- Normalized chunks now allowlist provider name, profile name, and finite
  numeric confidence. Azure AI Search maps these to optional filterable
  `processingProvider`, `processingProfile`, and `processingConfidence` fields.
  Raw provider responses, tables, config, credentials, and arbitrary metadata
  are not indexed. Existing indexes receive the fields lazily and safely before
  the first upload; old documents need re-indexing to populate them.
- Optional Compose services and a PaddleOCR CPU Dockerfile are present.
- Docling URL normalization accepts a base URL or a URL ending in `/health`,
  `/ready`, `/docs`, or `/ui`. Runtime always derives the service base before
  health and conversion calls.
- Manual connectivity evidence: from the backend environment,
  `http://host.docker.internal:5001/health` returned HTTP 200; the Docling root
  returned 404, which is normal for that image.

Important validation boundary:

- Docling health/connectivity and page-aware citation against a real multi-page
  document were manually verified by the product owner.
- Provider/profile/confidence metadata on a newly indexed document was manually
  verified in Azure AI Search by the product owner.
- PaddleOCR Compose schema and adapter response parsing were tested, but the
  large Paddle image/model was not fully built and inference-smoke-tested in
  this session.
- Google Document AI was not called against a real Google project/processor in
  this session.

See `docs/document-processing.md`, `docs/ocr-provider-contract.md`,
`docker-compose.ocr.yml`, and `services/paddleocr/Dockerfile`.

## OCR routing behavior

OCR Routing Rules are implemented for Personal, Team, and Global uploads. Rules
store scope (`all`, `personal`, `team`, `global`), optional team ID, file types,
processing profile, priority, enabled state, and unavailable-profile behavior.

Resolution is deterministic:

```text
authorized explicit override
→ exact team
→ exact upload scope
→ all scopes
→ legacy Default profile
→ startup Azure/local parser
```

Within a scope, an exact extension outranks `*`, then priority breaks ties.
Enabled rules at the same scope/file specificity/priority cannot conflict.
Unavailable profiles may continue to the next rule, use the legacy/system
fallback chain, or fail the upload.

The management page includes a Routing Rules tab and an **Explain Route** test.
The rule list is presented with enabled rules first, then higher priority and
name, while actual resolution still follows the scope/file-specific precedence
above. Explain Route disables duplicate submissions and shows a spinner,
`Checking…` button label, and live status message while the request is running.
Personal, Team, and Global upload pages default to `Auto — use routing rules`.
Manual profile selection is currently system-admin-only and is enforced by the
backend, not only hidden in the UI. Provider/profile/rule management is also
system-admin-only. Routing context is passed separately from the file stream;
existing Personal/Team/Global ACL construction was not changed.
The shared upload selector explicitly renders `Auto — use routing rules` for
its empty/default value; it no longer appears as an unselected blank field.

The legacy single Default profile remains as a compatibility fallback so an
existing deployment does not change behavior merely by receiving this update.

Processing Profile creation is idempotent in the current frontend. Each opened
create dialog sends one stable client request UUID, the backend atomically
upserts on that ID, and the Save button is disabled with a `Saving…` state until
the request and list refresh complete. Replayed requests return the existing
profile. New requests with a case-insensitive duplicate profile name are
rejected. Duplicates created before this protection are not deleted
automatically; remove the unwanted entry through the UI after confirming that
no routing rule uses it.

## Persistent ingestion jobs

Personal, Team, and Global uploads now create one MongoDB-backed job per file
and return HTTP 202 after the source object is stored. OCR extraction, chunking,
embedding/indexing, and completion/failure are timestamped. The upload UI shows
the current stage, selected provider/profile/rule, elapsed time, safe error
message, and Retry for failed work. Job list and Retry queries are restricted to
the authenticated submitter; existing Personal and data-group ACLs are reused.
Active and failed jobs remain in the Recent panel. Indexed jobs stay there for
60 seconds as completion feedback, then their durable Indexed Time is shown in
the corresponding Personal, Team, or Global file list instead. The Mongo job
record is retained; only its Recent-panel visibility is shortened.

The processing profile resolved at submission is pinned into the private job
context so rule edits cannot make the displayed provider differ from the parser
actually used. Mongo worker leases and a recovery sweep resume unclaimed work
and work whose process lease expired after restart. Claiming now changes the
visible status from `uploaded` to `extracting` immediately. Graceful application
shutdown cancels tracked ingestion tasks and atomically returns their owned jobs
to `uploaded` without a worker lease, so the next process recovers them on its
first sweep. A hard kill still waits for the existing one-hour lease to expire
to prevent another live replica from stealing the job. This remains an
in-process worker rather than an external durable queue; see
`docs/ingestion-jobs.md` for the contract and scaling limitation.

Example target rules:

| Scope | File types | Profile/provider | Priority |
| --- | --- | --- | ---: |
| all | `.pdf,.docx,.pptx` | Docling | 100 |
| all | `.png,.jpg,.tiff` | PaddleOCR | 90 |
| global | `.pdf` | Google Layout | 80 |
| team:finance | `.pdf,.png` | Google Invoice | 70 |
| all | `*` | Azure/system fallback | 10 |

## Chat image attachments — first slice

The shared Chat/Ask composer now accepts ordinary pasted text unchanged and
accepts PNG, JPEG, WebP, or GIF images through paste, file selection, or drag
and drop. It displays previews with per-image removal. Limits are four images,
10 MB per image, and 20 MB combined. The browser checks these limits for fast
feedback; the backend independently validates the declared kind/MIME/size,
base64 data URL, decoded size, filename normalization, and file signature.

The composer also exposes a visible **Vision On/Off** button. The attachment
button is enabled only while Vision is on. `/config` exposes the normalized
global Agent runtime mode so the UI can combine deployment availability with
the selected Agent's runtime and model capability. Vision is disabled with an
explanatory tooltip when the Agent model is not marked vision-capable, the
selected/global runtime is LangGraph, or the capability is unavailable.
Vision and Agentic Retrieval are mutually exclusive modes: enabling either
turns the other off, rather than leaving the Vision button permanently disabled.
Changing to an incompatible Agent turns Vision off instead of leaving a
misleading active state. Ask now sends the selected Agent ID, matching Chat, so
the backend applies the same managed model capability instead of the system
profile. Chat and Ask use the stored active Agent only as an ID bookmark and
always replace its prompt/config with the latest backend Agent record. This
prevents an old local-storage `llm_profile_id` from hiding a newly assigned
Vision-capable profile. Disabled-state guidance names the active Agent/profile
or identifies an unavailable profile instead of showing a generic provider
message.

Validated images are request-local and are passed only to the existing Legacy
vision approaches. They are not stored, indexed, added to browser chat history,
or returned as Knowledge citations. Inline attachment bytes are redacted from
the prompt diagnostics returned to the UI. Chat keeps an in-memory copy for the
current page session and renders sent-image thumbnails with filenames on the
corresponding user turn, including loading, streaming, error, and Retry states.
The pending user turn remains visible through metadata-only stream events and
is replaced only after the first streamed answer turn is rendered, avoiding a
blank/flicker interval before the first answer token.
The thumbnails are cleared for New Chat/history restore and are not available
after a reload. A non-vision Agent, unavailable
vision configuration, or LangGraph runtime receives a controlled HTTP 400 with
a clear reason rather than silently ignoring the image.

Current boundaries are deliberate: LangGraph multimodal image messages are not
implemented in this working tree.
The approved staged design and security acceptance criteria are in
`docs/product-backlog.md`.

### Math and special-symbol rendering

Chat/Ask answers use `remark-math` and `rehype-katex` with bundled KaTeX CSS and
fonts. Standard `$...$`/`$$...$$` Markdown math and LaTeX `\\(...\\)`/`\\[...\\]`
delimiters render as mathematical notation. A conservative preprocessor also
normalizes common model output that omits delimiters, including standalone/list
formulas and balanced commands such as `\\sqrt{...}` or `\\frac{...}{...}`
embedded in prose. Fenced code blocks are excluded so programming examples keep
their literal backslashes. Raw HTML still passes through the existing DOMPurify
step before Markdown/KaTeX rendering.

### Private document attachments and temporary retrieval — current working tree

`core/attachment_store.py` defines an async provider-neutral contract plus
`LocalAttachmentStore` and `AzureBlobAttachmentStore` adapters. Both use opaque
UUID storage keys, basename-only normalized filenames, exact owner and
conversation authorization, configurable byte/TTL limits, SHA-256 verification,
read-time expiry, explicit deletion, and fail-closed cleanup for expired,
corrupt, or old orphaned payloads. Local storage additionally uses private
`0700` directories, `0600` files, and atomic writes. Azure payload and metadata
sidecars remain inside a dedicated private container and no public URL is
generated or returned.

The factory is opt-in through `CHAT_ATTACHMENT_STORE=local|azure`; its default
is `disabled`, so existing deployments retain their behavior. Local mode also
requires `CHAT_ATTACHMENT_LOCAL_PATH`. Azure mode requires the existing
`AZURE_STORAGE_ACCOUNT` plus a dedicated `AZURE_CHAT_ATTACHMENTS_CONTAINER`.
`CHAT_ATTACHMENT_TTL_HOURS` (default 24), `CHAT_ATTACHMENT_MAX_MB` (default 25),
and `CHAT_ATTACHMENT_CLEANUP_INTERVAL_SECONDS` (default 3600, minimum 60)
control retention. The Azure container must be provisioned with public access
disabled; application startup does not create or change its access policy.

For local development only, `app/start.sh`, `app/start.ps1`, and the VS Code
Backend launch configuration default to `CHAT_ATTACHMENT_STORE=local` with
`.data/chat-attachments` when the caller has not explicitly configured a
backend. `.data` is Git-ignored. Restart the backend after receiving these
settings because `/config` derives `chatDocumentAttachmentsEnabled` at startup.
Production/deployment environments remain opt-in and do not inherit this local
default.

When enabled, startup creates the metadata indexes where supported and starts a
bounded-lifecycle cleanup task. It deletes expired/corrupt/orphaned objects,
then temporary chunks, then expired Mongo metadata; it logs counts, survives
transient cleanup failures, and is cancelled before the Azure container client
closes at shutdown.
Mongo TTL remains optional because Cosmos compatibility is not assumed.

Chat and Ask now create a stable UUID `conversation_id` independently from
history/session state, retain it for the active conversation, reset it for New
Chat, and restore a UUID history session when available. The backend validates
it on `/ask`, `/chat`, and `/chat/stream`, while generating a UUID fallback for
older clients. Invalid IDs receive a controlled HTTP 400.

`mongo_table_connecters/chat_attachment_metadata.py` stores only bounded
attachment metadata and enforces attachment ID + owner + conversation + active
expiry in every read/update/delete query. Its client serializer excludes owner,
conversation, storage key, and checksum. It supports explicit expiry cleanup;
the Mongo TTL index is optional because Cosmos compatibility is not assumed.

Authenticated `GET/POST /chat/attachments` and
`DELETE /chat/attachments/<id>` routes now provide the first private document
boundary. Upload requires UUID `conversation_id` and `upload_id`, and the
owner/conversation/upload tuple is idempotent so a repeated submission returns
the existing record. Supported types are PDF, DOCX, PPTX, XLSX, TXT, CSV, and
Markdown. Validation enforces basename-only filenames, declared MIME matching,
magic/structure checks, UTF-8 text, PDF page limits, and Office archive entry,
path, encryption, uncompressed-size, compression-ratio, slide, and worksheet
limits. The fixed API ceiling is 25 MB even if the underlying store is configured
higher.

The upload passes through a provider-neutral malware scanner interface before
storage. The current configured implementation is an explicit no-op and records
`scan_status=not_configured`; a real scanner adapter remains mandatory before a
production rollout that accepts untrusted documents. Object creation is rolled
back if Mongo metadata creation fails, duplicate-key races discard the second
object, and delete revokes metadata access before object deletion. The JSON
sidecars are adapter implementation details, not the client or final query
contract.

Successful upload now schedules background native extraction without delaying
the API response. Metadata transitions from `stored` to `extracting`, then
`ready` with bounded chunk/character counts or `failed` with a controlled error
code. PDF retains one-based page provenance; PowerPoint retains slide numbers;
Excel retains worksheet order and cell coordinates; DOCX is labeled `document`
because reliable rendered page numbers are unavailable without a layout engine.
TXT/CSV/Markdown are treated as page 1. Native extraction enforces a 2,000,000
character, 2,000 chunk, 2,000 character-per-chunk, and 10 MB XML-part ceiling.
Image-only/scanned PDFs fail with `ocr_required` instead of silently producing
an empty index.

`core/attachment_index.py` defines the provider-neutral temporary index
contract. `MongoAttachmentIndex` is the first implementation and works with
local MongoDB as well as the current Cosmos-compatible connector. Chunks carry
attachment/file/page provenance and TTL; retry uses fail-closed replacement and
removes partial inserts if the connector fails. Search uses bounded local
lexical ranking without Azure AI Search or an embedding provider. Every
write/search/delete requires
exact owner and conversation scope. Delete revokes metadata first and removes
chunks plus the object; retention cleanup runs object → chunks → metadata.
Extraction tasks are cancelled before storage clients close, and a delete/
extraction race removes newly created chunks if metadata was already revoked.

`/ask`, `/chat`, and `/chat/stream` now accept a bounded list of
`document_attachment_ids`. Client-supplied internal source overrides are removed;
every selected ID must be a valid UUID and resolve to an active `ready` record
under the exact authenticated owner and conversation. Processing, failed,
cross-owner, and cross-conversation selections fail with controlled errors.
Retrieval is also scoped by owner, conversation, and selected IDs at the index
layer. A query without lexical overlap falls back to the first bounded chunks so
requests such as “summarize this document” still work.

Requests with selected temporary documents use a deterministic Thai/English
prompt-intent classifier with three evidence scopes. Ordinary summary/analysis
requests and ambiguous prompts default to `uploaded_only`; explicit comparison,
cross-check, RAG, or Knowledge-base language selects `both`; explicit requests
to ignore the attachment and use only RAG select `knowledge_only`. This adds no
extra model call or latency. Legacy skips or combines ordinary/agentic Azure
Knowledge retrieval according to that scope. LangGraph registers
`search_knowledge` against the temporary index only or against both authorized
indexes, while the Agent's disabled Knowledge policy still prevents enterprise
search. The default prevents unrelated permanent citations from leaking into a
simple attachment summary. A future explicit UI source-scope selector may
override Auto for the requirement-to-evidence workflow. Both runtimes label
extracted text as untrusted reference data and instruct the model never to execute commands found in it.
Source text is capped at 12,000 characters and uses a sanitized private namespace such as
`chat-attachment-<uuid>--requirements.pdf#page=12`; storage paths and owner IDs
are not exposed. Temporary citation clicks are recognized by their private
namespace and routed to authenticated
`GET /chat/attachments/<attachment_id>/content?conversation_id=<uuid>` rather
than permanent Knowledge `/content`. The endpoint rechecks active `ready`
metadata, authenticated owner, conversation, TTL, and store integrity before
streaming the original file with `private, no-store`; mismatched scope returns
404. Chat/Ask preserve PDF `#page=` fragments after authenticated blob fetch.
The analysis panel now rejects non-2xx responses instead of rendering an HTML
Forbidden page as citation content.

The shared Chat/Ask composer now accepts PDF, DOCX, PPTX, XLSX, TXT, CSV, and
Markdown alongside the existing image types. Document selection remains local
until Send. Each draft receives a stable UUID `upload_id`; Send uploads through
the private API, displays Uploading/Processing/Ready/Failed state, polls for up
to two minutes, and calls Chat/Ask only after every selected document is
`ready`. The request contains only `document_attachment_ids`, never document
bytes or storage paths. A transient upload/poll failure leaves the draft and its
stable upload ID available for another Send. A server-side extraction failure
requires remove/re-attach. Removing an already uploaded draft revokes it through
the private delete API. Chat stores ready document metadata with the in-memory
user turn so request Retry reuses the same IDs without uploading again; New Chat
and history restore clear that session-only display. `/config` exposes a safe
feature flag, so document selection is unavailable when the private store is
disabled.

Image and document input are now separate Agent policies under **Agent Info →
Configuration → Message attachments**. `image_input_enabled` is opt-in and can
only be saved with a Vision-capable LLM profile on the Legacy runtime.
`document_attachments_enabled` is independent of Vision and defaults to enabled
for existing Agents to preserve the attachment behavior introduced in this
milestone. New and edited Agent configs persist both booleans. Chat and Ask no
longer expose a per-message Vision toggle; they show the paperclip only when at
least one attachment type is enabled by the selected Agent, and explain a
missing model/runtime/store capability when an enabled type is unavailable.

The backend is the authority for these policies. Agent resolution replaces a
client-supplied `use_gpt4v` value and internal policy overrides before image
validation. The Agent image flag is permission, not a permanent routing mode:
text-only and document-only requests use the ordinary text approach; a request
with validated inline images uses the Vision approach; and a mixed image plus
document request uses Vision for the images while merging temporary document
sources. Image requests suppress Agentic Retrieval for that request only.
Ready-document retrieval rejects Agents that disable documents, and the normal
upload flow sends `agent_id` so disabled Agents are rejected before storage.
Existing clients without an Agent retain the system-profile compatibility path;
an unknown Agent fails both policies. Document selection still additionally
requires the deployment-level private attachment store.

Uploaded Chat documents are not promoted into permanent Knowledge automatically.
Private attachment extraction now uses an atomic, owner/conversation-scoped
worker lease. A background recovery scan requeues active `stored` records and
legacy or lease-expired `extracting` records, while graceful shutdown releases
its own in-flight claims back to `stored`. The default recovery interval is 30
seconds and can be changed with
`CHAT_ATTACHMENT_RECOVERY_INTERVAL_SECONDS` (minimum 5 seconds). Native parsing
still runs first; documents with no machine-readable text are then sent through
the existing Personal-scope document-processing rules and managed OCR provider
adapters. OCR output is normalized into the same bounded private chunks and
retains page provenance. Failed or revoked work remains fail-closed, and a worker
that loses its lease cannot overwrite status or delete another worker's chunks.
A production malware scanner remains pending.

## Other next work

### Near-term document work

1. Add a production malware-scanner adapter and make its deployment policy
   explicit before accepting untrusted documents outside development.
2. Add the requirement-to-Knowledge-evidence matrix, per-model vision/OCR
   routing in both runtimes, and speech improvements in that order. See
   `docs/product-backlog.md`.

### Platform roadmap

- Internal username/password authentication and User Management, without
  requiring Entra ID.
- Provider interfaces and local implementations for object storage, vector
  search/RAG, and embeddings. `APP_RUNTIME_MODE=local` is still partial; search
  and storage remain Azure-dependent.
- Docker Compose for the complete application, persistent volumes, health/readiness,
  secret injection, backup/restore, and then Helm/Kubernetes.
- AI guardrails.
- Agent Invocation API.
- Usage dashboard/reporting by user, team, Agent, model/provider, tokens, tools,
  errors, latency, and estimated cost.
- Shared time/token budgets across a delegation tree, persisted LangGraph
  checkpoints, and audit retention/index policies.

The guardrail/API/dashboard discussion order is documented in
`docs/product-backlog.md`.

## Critical known limitations and risks

- **Admin authorization:** OCR provider/profile/rule management now enforces
  system-admin authorization server-side. Continue auditing mail, messaging and
  other newer management routes that still use only the generic authenticated
  decorator or UI visibility.
- **OCR routing:** automated tests cover precedence, conflicts, fallback and
  override authorization, but live Personal/Team/Global uploads with multiple
  providers still require manual smoke testing before checkpointing.
- **Ingestion worker:** jobs and leases are persistent, but execution still runs
  inside the web application. Use a dedicated queue/worker before high-volume
  horizontal scaling or extraction calls that can exceed the one-hour lease.
  Graceful shutdown returns owned jobs to the queue immediately; a hard kill
  waits for lease expiry. No automatic ingestion-job retention/TTL policy is
  configured yet.
- **Local mode:** LLM/provider work is ahead of search, storage, authentication,
  and deployment migration; this is not yet a fully local product.
- **Tool-capability probes:** detection is a live request and can consume a small
  number of tokens per model. Rate limits or ambiguous provider errors produce
  `unknown` rather than incorrectly disabling tools. Re-test after changing a
  model name, deployment, provider version, or compatibility gateway.
- **Write tools:** mail and messaging execute automatically when allowed. Keep
  narrow bindings, recipient/target constraints, tool policies, and audit.
- **MCP/REST SSRF:** private REST targets are blocked unless
  `ALLOW_PRIVATE_INTEGRATION_ENDPOINTS=true`. Enable this only for trusted
  container-network integrations.
- **Secrets:** changing or losing `APP_DATA_ENCRYPTION_KEY` makes stored provider,
  database, MCP, mail, messaging, and OCR credentials unreadable.
- **Paddle resource usage:** the CPU image and first model download are large;
  pin versions/digests and bake/cache models for production.
- **Frontend bundle:** the existing vendor chunk is large and requires a larger
  Node heap for reliable production builds.
- **Chat attachments:** request-local images still support only the Legacy
  vision runtime. Private document storage, native extraction, TTL cleanup, and
  Legacy/LangGraph temporary text retrieval and composer upload/progress/remove
  behavior, private ACL-checked temporary citation opening, scanned-document OCR
  routing, and restart recovery exist. LangGraph image messages and a production
  malware scanner remain pending.
- **Cosmos/Mongo compatibility:** PyMongo may warn when connected to Cosmos DB;
  avoid assuming every MongoDB feature is supported.
- **Dirty diff size:** some frontend files contain large formatting/line-ending
  changes from earlier work. Avoid broad formatting and review functional hunks
  carefully before checkpointing.

## Configuration and secrets

Required for every feature storing application-managed secrets:

```bash
APP_DATA_ENCRYPTION_KEY=<stable Fernet key shared by every replica>
```

Generate once, store in Dev Container/Docker/Kubernetes secret management, and
do not commit the value:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Useful development settings include:

```bash
# Per-Agent runtime selection unless explicitly overridden.
AGENT_RUNTIME_MODE=per_agent

# Required only when trusted Docker-network REST integrations use private IPs.
ALLOW_PRIVATE_INTEGRATION_ENDPOINTS=true

# Optional embedded Docling; service mode is preferred.
INSTALL_LOCAL_OCR=true
```

Do not put real credentials in this file or examples.

## Validation status

The product owner manually verified graceful-stop recovery of an in-progress
Knowledge ingestion job on 2026-08-22. A legacy job left with the former
one-hour lease was reset only after confirming no backend worker was running;
the restarted service then resumed processing successfully.

Latest service-free backend regression on 2026-08-22:

```text
614 passed, 1 deselected
```

Command:

```bash
.venv/bin/pytest -q -m 'not data_integration'
```

Latest focused provider capability, Chat attachment, configuration, and mocked
route/vision regression:

```text
66 passed
```

Latest focused private attachment storage, retention, extraction, index,
retrieval, prompt-boundary, route, and LangGraph RAG validation:

```text
99 passed, 8 deselected
```

Command:

```bash
.venv/bin/pytest -q tests/test_attachment_cleanup.py tests/test_attachment_extraction.py tests/test_attachment_retrieval.py tests/test_attachment_store.py tests/test_chat_attachment_extraction_lifecycle.py tests/test_chat_attachment_index.py tests/test_chat_attachment_metadata.py tests/test_chat_attachments.py tests/test_chat_document_attachment_routes.py tests/test_document_attachments.py tests/test_agent_runtime.py -k 'attachment or rag'
```

Latest focused attachment extraction recovery, OCR routing, and document
processing validation:

```text
62 passed
```

Latest focused private attachment and persistent ingestion lifecycle validation:

```text
26 passed
```

Latest focused ingestion/document-processing, splitter, and search-metadata validation:

```text
79 passed, 1 deselected
```

Latest focused LLM provider/model-capability validation:

```text
18 passed
```

Frontend typecheck and the memory-safe production bundle passed. Use:

```bash
cd app/frontend
npx tsc --noEmit
NODE_OPTIONS=--max-old-space-size=3072 npm run build:memory-safe
```

For memory-constrained local startup, `npm run build:memory-safe` omits source
maps while producing the same runtime bundle. This completed with a 3 GB Node
heap after the source-map build was killed twice during chunk rendering.

The full source-map build remains available as `npm run build`, but the latest
4 GB attempts were killed by container memory pressure during Vite chunk
rendering. Local start scripts therefore use the validated memory-safe command.

Compose schemas passed:

```bash
docker compose -f docker-compose.ocr.yml config
docker compose -f docker-compose.ocr.yml --profile paddleocr config
```

Known non-blocking warnings:

- Azure Monitor imports deprecated `pkg_resources` through an upstream package.
- Vite reports an existing large vendor chunk.
- `npm install` currently reports 18 dependency audit findings (1 low, 9
  moderate, 8 high). No broad or breaking `npm audit fix` was applied as part
  of the focused math-rendering slice.
- PyMongo can emit a Cosmos DB feature-compatibility warning.

## Manual smoke-test checklist before the next checkpoint

- Chat/Ask normal text paste remains unchanged. In **Agent Management → Agent
  Info → Message attachments**, verify image input cannot be enabled for a
  non-Vision model or LangGraph runtime. With both Agent policies off, confirm
  the paperclip is hidden. Enable image input, then paste, select, and drag/drop
  a supported image and verify preview/removal, image-only send, and limits. In
  Chat, confirm sent thumbnails and filenames remain on the correct user turn
  during loading and after the answer, and that Retry resends the same image.
  Confirm a reload/history restore does not persist the inline image bytes.
- With Legacy vision enabled, verify the real model uses the attached image and
  that the attachment is not shown as a Knowledge citation or raw data URL in
  prompt diagnostics. Verify both streamed Chat and non-streamed Ask.
- In **Admin Management → LLM Providers**, run Test for at least one real
  vision-capable managed model. Confirm the Provider card displays the Vision
  tag and the composer updates without a browser refresh. Select the profile on
  a Legacy Agent, enable image input in Agent Management (including while
  Agentic Retrieval was previously on), and verify it works without setting `USE_GPT4V` or
  `AZURE_VISION_ENDPOINT`. Reload Chat after changing the Agent profile and
  confirm it uses the backend profile rather than a stale locally cached Agent.
- Disable image input on the Agent and verify pasted/dropped images are not
  accepted. With a LangGraph Agent, verify the management switch is disabled
  rather than silently sending or ignoring an image.
- Verify Answer rendering with `$x^2$`, `$$\\frac{1}{2}$$`, `\\(x+y\\)`, a raw
  `\\sqrt{147}` embedded in Thai prose, and the nested raw expression
  `3\\sqrt{147} - 7\\sqrt{\\frac{1}{27}}`. Confirm the same commands remain
  literal inside a fenced code block.
- Enable `CHAT_ATTACHMENT_STORE=local|azure` and its required settings, then use
  the shared Chat and Ask attachment button with a native-text PDF plus TXT,
  DOCX, PPTX, XLSX, CSV, or Markdown samples. Confirm files are not uploaded at
  selection time; after Send, verify Uploading → Processing → Ready feedback,
  the user turn keeps the filenames, and the answer/data points cite the
  sanitized filename and page/section. Test remove before Send, Retry after a
  transient request error, New Chat during processing, 25 MB/10-document limits,
  an unsupported extension, and an image-only PDF (`ocr_required`). Repeat with
  a LangGraph Agent whose Knowledge Search is Disabled and verify only the
  selected temporary documents are searched. Click a temporary PDF citation and
  verify the private viewer opens the cited page; a different conversation or
  expired attachment must return 404. Disable document attachments on the Agent
  and verify the picker no longer accepts documents while image input can remain
  independently enabled.

- Azure startup, Personal/Team/Global upload, search, deletion, and citations.
- OCR routing precedence for Personal/Team/Global, Auto selection, authorized
  manual override, conflict rejection, Explain Route, and legacy/system fallback.
- Persistent job stages for Personal/Team/Global, selected provider/profile/rule,
  controlled failure and Retry, page refresh persistence, immediate recovery
  after a graceful restart, and lease-expiry recovery after a hard kill. Confirm
  Indexed leaves Recent after about one minute while Indexed Time remains visible
  in the relevant file list.
- At least one Agent per OpenAI/Gemini/Ollama provider and a tool-capable model.
- Run LLM Provider Test for every configured model and verify supported models
  stay enabled, unsupported switches become disabled, and ambiguous failures
  remain `unknown` rather than being forced off.
- LangGraph RAG Auto/Always/Disabled and Legacy rollback.
- Database schema-first query and full-dataset chart aggregation.
- Managed MCP discovery, Datadog invocation, allowlist, timeout, and audit.
- Sub-agent delegation, cycle/depth denial, and trace linkage.
- Mail read/send and messaging send against approved test accounts/channels.
- Docling scanned Thai PDF/image ingestion and unique-token RAG retrieval.
- PaddleOCR General OCR and Layout Parsing after the first model download.
- Google Document AI test and one document against a least-privilege test
  processor.
- Restart containers and verify managed configurations survive.

## Suggested Codex CLI continuation prompt

```text
Read AGENTS.md and docs/CODEX_HANDOFF.md completely. Preserve the working tree
and do not discard unrelated changes. Continue milestone 2 by adding a
production malware-scanner adapter and explicit deployment policy for private
Chat document uploads, preserving owner/conversation ACLs, TTL, idempotency,
and fail-closed behavior.
```
