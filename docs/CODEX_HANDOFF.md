# Codex handoff — NexoraAI

Last updated: 2026-09-06 UTC

This document replaces a raw chat transcript as the engineering handoff. It
captures the decisions and evidence needed to continue without storing copied
logs, credentials, attachments, or repetitive conversational text.

## Repository state

- Workspace: `/workspaces/NexoraAI`
- Branch: `feature/mcp-catalog-navigation`
- Base checkpoint: `09eef3e feat: add private chat document workflows`.
- Implementation checkpoint: `eff68fb feat: recover interrupted document
  processing`. It adds private Chat document extraction recovery and managed OCR
  routing, plus graceful restart recovery for persistent Knowledge ingestion
  jobs.
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
- Checkpoint `33a6b40 feat: add selectable knowledge object storage` adds the
  provider-neutral Knowledge object-store boundary and optional MinIO adapter.
  The product owner manually confirmed normal application behavior with MinIO.
- Checkpoints `4b53e75 feat: add local vector search and refine chat workspace`
  and `57b6e72 feat: add local BGE-M3 embedding stack` contain the accepted
  Qdrant and Ollama/BGE-M3 slices. The current uncommitted slice packages the
  application, MongoDB, MinIO, Qdrant, Ollama, local authentication, and local
  attachments as one portable Compose runtime while preserving Azure provider
  selection.

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
- Internal authentication uses application-managed username/password and the
  internal User Management page, not Keycloak. Microsoft Entra remains
  available and may be enabled alongside local login.
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
- Assistant tool-call messages use an empty string instead of JSON `null` for
  content. This preserves the tool-call protocol while remaining compatible
  with Azure OpenAI deployments that reject null message content.
- Admin Agent Audit page and audit query endpoint.

See `docs/langgraph-agent-runtime.md`.

### AI guardrails — current working tree

- Branch `feature/ai-guardrails` starts from checkpoint `bf08076 feat: add
  unassigned integration catalog`, which the product owner manually accepted.
- A provider-independent Guardrail policy is normalized into every Agent
  configuration and is enforced for both Legacy and LangGraph Chat routes.
  Safe defaults block high-confidence prompt injection, excessive latest-user
  input, and credentials/secrets in input; model secrets are redacted before
  response text is released.
- Agent configuration exposes enablement, input limit, input/output actions,
  and organization-specific literal blocked phrases. Output redact/block mode
  intentionally buffers response text until validation is complete.
- Knowledge/temporary attachment text and LangGraph tool output are treated as
  untrusted data. Detected embedded instruction patterns are neutralized before
  being consumed as instructions, and tool output also passes secret controls.
- Guardrail audit events persist only detector/category/count/outcome metadata,
  never raw prompts, matched values, retrieved content, tool output, or model
  output.
- Agent create/edit/delete now requires the Team `Manage agents` permission
  server-side and edit/delete verifies that the Agent belongs to the supplied
  Team. This prevents an authenticated caller from disabling another Team's
  guardrail policy through a direct API request.
- The first slice is not complete DLP/moderation. Multilingual semantic
  classifiers, groundedness, human review, and production malware scanning
  remain pending.
- The current uncommitted second slice adds separate PII/DLP and content-safety
  actions for input and output. Deterministic PII coverage includes email,
  Thai telephone numbers, US SSNs, checksum-valid Thai national IDs, and
  checksum-valid payment cards. High-confidence requests to disclose protected
  identifiers are also detected. Output PII is redacted by default and input
  PII is blocked by default; deployments with legitimate contact-data workflows
  may explicitly select Audit only.
- Narrow high-confidence English/Thai harmful-instruction detectors now support
  block/audit/allow actions. This is deliberately not presented as complete
  semantic multilingual moderation.
- Optional System and Team policies are persisted in the existing
  `application_settings` collection. Runtime enforcement merges
  **System → Team → Agent** using the smallest input limit, strictest action,
  and union of blocked phrases. An enabled parent cannot be disabled or
  weakened below it. System Admins configure the System minimum in
  **Administration → Guardrail Policy**; Team administrators with `Manage
  agents` configure their Team minimum in **Team settings → Guardrail Policy**.
- The product owner manually accepted this Guardrails scope on 2026-09-02,
  including protected-identifier request blocking. Further Guardrails work is
  intentionally deferred to the product backlog; do not expand this slice
  before checkpointing unless a concrete defect is found.

See `docs/ai-guardrails.md`.

### MCP

- Managed MCP Server catalog grouped by category.
- The current MCP management navigation separates **Configured Servers** from
  **Browse Catalog**, replacing the expanding horizontal category tabs with a
  searchable catalog and responsive Category, Status, and Agent Usage filters.
  Supported templates open the existing encrypted configuration workflow;
  unavailable templates remain visibly marked as coming soon. The catalog is
  now part of Team Integrations: a connection created for a Team is visible and
  assignable only within that Team, while a System Admin can create an
  Unassigned connection and assign it once through the shared integration
  catalog workflow. Agent save and runtime both reject cross-Team connection
  IDs. Legacy connections without ownership remain usable only by Agents that
  already referenced them and cannot receive new bindings until reassigned.
  Stored headers remain encrypted and are never returned to the browser.
  Personal/user-owned MCP credentials are not part of this slice.
- Microsoft Azure and Draw.io are available catalog templates. Draw.io uses the
  official hosted Streamable HTTP endpoint. Because the Chat client does not
  yet host MCP Apps, successful Draw.io calls expose the submitted XML as a
  downloadable `.drawio` response artifact (or Mermaid source as `.mmd`). Azure
  architecture prompts prefer XML and distinguish evidenced solid connectors
  from conventional, explicitly labelled dashed `inferred` connectors. Azure
  supports both an externally
  operated endpoint and a System-Admin-only managed mode. In managed mode the
  Portal encrypts the Azure workload client secret, then an internal integration
  controller starts one pinned official
  `mcr.microsoft.com/azure-sdk/azure-mcp` container per enabled connection.
  The controller is not published on a host port, authenticates Nexora with a
  separate bearer secret, accepts no arbitrary image/command/mount/port input,
  applies resource and capability limits, and removes a container when its
  connection is deleted. Managed local mode disables the upstream server's
  incoming HTTP authentication only inside the unpublished private Compose
  network, so its Portal form needs only tenant ID, workload client ID/secret,
  and subscription IDs. External Azure MCP endpoints retain Entra OAuth.
  Enabled instances are reconciled after restart. Deleting while the controller
  is unavailable returns an accepted cleanup-pending result, hides the record,
  erases its stored credentials, and retries container removal later rather
  than trapping an undeletable failed record in the Portal.
  Controller-returned URLs must match the connection-specific internal host and
  managed HTTP redirects are disabled. The controller remains idle when Azure
  is not configured, so Azure is not a first-deployment prerequisite.
- Azure is locked to `read_only`; the official server starts with a small
  inventory tool set and discovery/runtime suppress write-oriented or ambiguous
  tools. Draw.io remains `read_write` so it can create/update diagrams. Tool
  descriptions guide a LangGraph Agent to preserve Azure resource IDs and
  relationships when producing a diagram. Provisioning Azure resources from
  diagrams remains outside this slice. See `docs/azure-drawio-mcp.md`.
- Streamable HTTP discovery/invocation and per-Agent selection.
- Encrypted headers, tool allowlists, test/discovery action, timeout isolation.
- Datadog preset supporting official sites and Bearer PAT/SAT or Datadog
  API/Application keys.
- Atlassian Jira/Confluence and ServiceNow are available as external remote MCP
  catalog presets; NexoraAI does not provision containers for them. Atlassian
  is pinned to the official hosted Rovo MCP endpoint, while ServiceNow accepts
  the MCP endpoint exposed by the customer's `service-now.com` instance. Both
  currently accept an encrypted OAuth bearer access token. Browser-driven
  OAuth authorization and refresh-token rotation remain follow-up work; see
  `docs/jira-servicenow-mcp.md`.
- The Administration integration landing page now consumes a provider-neutral,
  secret-free connection projection across native and MCP collections. It
  separates **Configured connections** from **Browse catalog**, and displays
  all configured connections together with `Native` or `MCP`, status, provider,
  and Agent usage, while provider-specific editors and storage remain intact.
  The page repeats its Team or System/Unassigned scope so catalog actions cannot
  be mistaken for another workspace. Agent Management places MCP assignments inside the shared
  **Integrations** tab. A compatibility binding projection reads all existing
  binding collections plus legacy `mcp_server_ids`; no credential or binding
  data migration has been performed. See `docs/integration-control-plane.md`.
- After a successful MCP connection test, the connected/tool-count badge opens
  a searchable dialog containing the discovered tool names and descriptions.
  This discovery result is held only in the current frontend session and is not
  persisted; running Test again refreshes it without exposing stored headers.
- Datadog live behavior was iterated to force tool use when appropriate and to
  handle monitor/log query issues. Treat broader Datadog tool coverage as a
  continuing integration smoke-test area.
- The catalog-navigation, Team-ownership, managed-Azure, and Azure-to-Draw.io
  slices passed 92 focused MCP, controller, authentication,
  integration-catalog, Agent authorization, and runtime tests. The complete
  service-free backend suite passed (`827 passed, 1 deselected`), as did
  frontend TypeScript validation, the memory-safe production build, and local
  Compose schema validation. The controller and application images built
  successfully with a command-scoped empty `DOCKER_CONFIG`; the host VS Code
  Dev Containers credential helper is unavailable and otherwise exits with
  status 255. A live pinned Azure MCP container was provisioned successfully on
  the private runtime network and reached its HTTP-ready state. A real Azure
  resource/tool call still remains to validate the configured service
  principal and Reader RBAC. The existing large-vendor-chunk warning remains.

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
- System administrators can now open **Administration → Integrations** without
  an active Team, create and test REST API, database, mail, or messaging
  connections in an `Unassigned` catalog, and explicitly assign each connection
  to one Team. Unassigned connections are excluded from Team lists and cannot
  be bound to Agents. Assignment is a one-way ownership transition in this
  slice; moving an assigned connection or sharing one credential across Teams
  requires an explicit future workflow rather than changing `team_id` through
  an edit request.
- Team Settings now uses its explicit target Team for the Agents and
  Integrations tabs instead of rereading potentially stale Active Team browser
  state. When there is no active Team, the dialog is titled **Administration**,
  hides Team-scoped tabs, and exposes the unassigned catalog only to System
  Admins. Integration catalog CRUD is authorized against `Manage integrations`
  for a Team or System Admin for unassigned records. Agent binding creation and
  update reject unassigned and cross-Team connections server-side.
- Mail connections: Microsoft 365 Graph, Gmail API, and generic IMAP/POP3 +
  SMTP, with Agent read/send permissions, recipient constraints, templates, and
  encrypted credentials.
- Messaging & Chat connections: LINE, Slack, and Discord outbound messaging,
  with Agent bindings and templates.
- Mail and messaging adapters exist and have unit coverage. Continue real-server
  E2E tests for SMTP/network timeouts, OAuth permissions, mailbox restrictions,
  channel membership, and write-action policy before production use.
- Business Documents now provides Team-scoped Microsoft 365 and Google
  Workspace connections. The LangGraph adapter can search/read Word, Excel,
  PowerPoint, Google Docs, Sheets, Slides, PDF, and text documents, and can
  create native cloud documents when both the connection and Agent binding
  explicitly allow Create. Connections use encrypted OAuth credentials,
  default to read-only, support the unassigned-to-Team catalog workflow, and
  reject cross-Team Agent bindings. See
  `docs/business-document-integrations.md`.

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

### Chat history owner isolation

- Browser/IndexedDB Chat history records now carry the stable application User
  ID. List, open, search, update, and delete operations require an exact owner
  match. Legacy browser records without owner metadata remain in IndexedDB but
  are hidden from every account because ownership cannot be inferred safely.
- Changing the signed-in application User remounts the history list and clears
  the active conversation, attachments, search results, selected Agent, and
  citation state before browser paint, preventing the previous User's state
  from flashing or being submitted under the new session.
- Cosmos Chat History already uses the authenticated `oid` and hierarchical
  partition key. Individual read/delete queries now also include an explicit
  `entra_oid` predicate as defense in depth.
- TypeScript validation and the memory-safe production build passed. The 25
  focused Cosmos Chat History tests passed, including owner-predicate checks.
- The current local-runtime slice adds MongoDB-backed server history behind
  `USE_CHAT_HISTORY_DATABASE=true`; Compose enables it and disables browser and
  Cosmos history. Conversations are keyed by UUID, scoped by exact stable owner
  ID on every list/read/write/delete operation, limited to 8 MiB, and carry an
  absolute expiry. A bounded application cleanup worker is authoritative and
  deletes attachment objects, extracted chunks, metadata, then the conversation;
  conversation TTL is intentionally not delegated to MongoDB.
- Retention defaults to 90 days and can be configured in **Administration →
  System chat history**. Teams with `Manage agents` may choose a shorter period
  in **Team settings → Team chat history**, never a value longer than the
  System policy. Supported choices are 30, 90, 180, 365 days and no expiry
  where the parent permits it. Policy changes recalculate expiry from each
  conversation's latest update. Manual deletion uses the same immediate
  dependency cascade. Metadata-only deletion audit stores actor, time, reason,
  and counts for 365 days without deleted messages, citations, diagram XML,
  credentials, or tool output. Settings are stored in `application_settings`.
- Focused Chat history and management authorization validation passed (`53
  passed`). The complete service-free backend suite passed (`852 passed, 1
  deselected`), as did frontend TypeScript validation, the memory-safe
  production build, and local Compose schema validation.

### Agent and data-scope selector summary

- The Agent selector shared by Chat and Ask now presents the selected Agent and
  model on its first row and the active Global/Personal scopes and named Data
  Groups as compact chips on its second row. Scope chips and Data Group chips
  use distinct styles, long selections collapse to `+N`, and the full selection
  remains available through the tooltip and accessible label.
- The summary is presentation-only and continues to use the existing selection
  dialog, persisted scope choices, Data Group authorization, and backend ACL
  enforcement. TypeScript validation and the memory-safe production build
  passed after this change.
- The surrounding Chat/Ask shell was also tightened into a 64-pixel application
  header, bounded conversation canvas, in-flow context bar, smaller responsive
  empty state, and bottom composer with clearer focus treatment. The Chat
  sidebar now aligns with the shorter header. This is a presentation-only
  change; request, history, attachment, Agent, and authorization behavior is
  unchanged. Reduced-motion preferences disable the decorative animations.

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

The first built-in requirement-to-evidence slice is now wired through both the
Chat and Ask composers. With one or more document drafts selected, users can
enable **Evidence matrix** and choose `knowledge_only` (the recommended
default), `uploaded_only`, or `both`. These are top-level validated request
fields; client-supplied internal overrides are still removed. The first
selected attachment is the requirements checklist. Backend-owned instructions
require a fixed Markdown matrix (Requirement, Status, Explanation, Evidence,
Source file, Page, Confidence, Gap), restrict status values, require page-aware
citations for supported/partial rows, and prohibit the checklist itself from
being used as proof. Evidence metadata now separates a basename-only display
filename from the full citation locator: the Source file column must show only
`report.pdf`, while the inline citation retains its authorized storage locator
so citation opening continues to work. The Evidence column contains only the
supporting quote; filenames, page numbers, and citations belong in the separate
Source file/Page columns. Team-scoped permanent citation authorization now
resolves the Team UUID path prefix through the same application-user/Data Group
policy as Chat retrieval instead of comparing application Data Group IDs only
with Entra groups. Non-Team and access-control-disabled paths retain the legacy
behavior. Legacy retrieval uses a bounded server-derived checklist
query and at least ten ACL-filtered Knowledge results; LangGraph receives the
same workflow contract and retains its permission-aware `search_knowledge`
tool. Attached-only requests still suppress enterprise retrieval.

This is intentionally the synchronous first slice: checklist input is bounded
to 20 temporary chunks / 24,000 characters, the returned table is model-rendered
Markdown rather than server-validated row JSON, and CSV/Excel export is not yet
implemented. A later batch/job slice should extract stable requirement IDs,
search/evaluate each row independently, persist progress, and expose validated
JSON plus export without weakening document or Knowledge ACLs.

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

### Team access and Data Group authorization

- Team settings now use the selected Team passed by the parent dialog instead
  of independently reading a potentially stale Active Team from browser
  storage. Tabs are ordered by the administration flow: Members, Data access,
  Roles & permissions, Agents, and Integrations, followed by system-only tools.
- Data Groups have an explicit access mode: `team` means every current and
  future Team member; `selected_users` requires at least one selected Team
  member. Legacy records retain their previous meaning (`user_id=[]` is
  inferred as Team-wide). The management UI labels these modes, shows distinct
  email/employee identity details, and no longer describes Team-wide access as
  “No users”.
- `core/effective_access.py` is the provider-neutral authorization boundary for
  Chat/Ask data selection. `POST /effective-access` returns only the groups the
  signed-in application user may use. Chat and Ask use this endpoint for the
  selector; `/ask`, `/chat`, and `/chat/stream` independently rebuild trusted
  Team/Data Group/scope claims server-side and reject cross-Team groups, agents,
  non-members, and unsupported scopes. Client-selected IDs are never trusted as
  RAG filters directly.
- Data Group create/edit/delete requires `Manage team data groups` on the
  server. Selected users are verified against Team membership. Team member
  listing requires Team membership.
- Member approval/rejection/removal/addition requires `Manage team users` on
  the server. Removing a Team member now deletes the applicable permission
  record rather than incorrectly calling the user deletion connector with a
  permission-record ID.
- Team role create/edit/delete and user permission assignment require `Manage
  team permissions`. Role permissions are restricted to Team permission IDs.
  Team-level permission changes cannot modify `is_sys_admin`; only the existing
  system-admin path may modify system roles/permissions.
- System Team CRUD requires `Manage teams`; User directory CRUD requires
  `Manage users`. A delegated system-permission manager cannot promote or
  demote a system administrator. User profile editing no longer silently resets
  the target user's `is_sys_admin` field.
- This authorization core uses application user/team IDs and is intentionally
  independent of Azure Search and Entra token shape after identity resolution.
  The remaining Entra-specific username-to-application-user lookup should be
  moved behind an identity-provider interface in the next local-runtime slice.
- Chat/Ask usage persistence now consumes the server-validated request claims.
  Requests without a Team store `group: null` instead of failing after the
  response stream with `KeyError: team_id`; Team-scoped requests retain the
  validated Team ID and name.

### Local and Microsoft Entra authentication

- `LOCAL_AUTH_ENABLED=true` enables a provider-neutral local login alongside
  the existing Entra adapter. Both providers resolve to the existing
  application User ID before Team, Data Group, permission, document ACL, and
  audit checks; authorization rules were not forked by provider.
- A new deployment bootstraps exactly one local system administrator from the
  Login page using `LOCAL_AUTH_BOOTSTRAP_TOKEN`. A persistent singleton guard
  and the unique local username index prevent duplicate bootstrap accounts.
  Remove the bootstrap token from the runtime environment after setup.
- Passwords use salted scrypt hashes. Opaque 12-hour session tokens are kept in
  browser `sessionStorage`, while MongoDB stores only their SHA-256 digests and
  a TTL expiry. Five failed logins lock the account for 15 minutes; a shared
  Mongo-backed source limit allows 30 login attempts per 15-minute bucket.
- User Management can create Entra-only or local users. Local password reset
  revokes all existing sessions for that user. Disabled/deleted application
  users cannot resolve a valid local session.
- The account menu now displays the application user's full name and exposes a
  self-service **My profile** dialog. Users may edit only first name, last name,
  contact email, and telephone; identity, employee ID, status, administrator,
  Team, role, and permission fields are read-only. Local users can change their
  password only after supplying the current password. The password policy is
  reused, the replacement must differ, and every Local session is revoked;
  Entra-only users are directed to Microsoft password management. The local
  logout route also now revokes its server-side token instead of leaving it
  valid until TTL expiry.
- User Management and User Permission now list system administrators instead of
  silently filtering them out, so the currently signed-in administrator is
  visible in the directory. System-admin badges are explicit. Delegated
  `Manage users` holders may view but cannot edit, delete, reset, promote, or
  demote a system administrator. A system administrator cannot remove their own
  account or the final active administrator.
- System administrators have an Authentication tab for managed Entra tenant,
  server-app, SPA-app and client-secret settings. The secret uses the existing
  Fernet helper and is never returned to the browser. Managed settings override
  environment Entra settings and can be removed to restore the environment
  configuration. Browser reload is required after changing MSAL settings.
- Azure-only startup behavior is unchanged: managed authentication storage is
  read only when Local Auth is enabled, preventing an unnecessary MongoDB call
  in existing Azure startup/test paths.

See `docs/local-authentication.md`.

### Local MongoDB deployment

- `docker-compose.local-mongodb.yml` runs the metadata/control-plane database
  on MongoDB 8 by default without changing the existing PyMongo connector.
  `MONGO_URI`/`MONGO_DB_NAME` select local MongoDB; the legacy
  username/password/SRV environment path remains available for Azure Cosmos DB
  Mongo-compatible deployments.
- MongoDB is published only on host loopback, has a health check, restarts
  unless stopped, and stores `/data/db` in the `nexora_mongodb_data` named
  volume. The checked-in Compose file contains no credentials and requires root
  and application credentials from an ignored environment file.
- First-volume initialization creates a database-scoped `readWrite`
  application user. NexoraAI does not connect as the root user. Initialization
  scripts do not rerun for an existing volume, so changing the environment file
  alone does not rotate database credentials.
- `docs/local-mongodb.env.example` and `docs/local-mongodb.md` document startup,
  host-backend configuration, persistence checks, safe shutdown, credential
  rotation boundaries, and the fact that Cosmos-to-local migration is not
  automatic.
- The first local smoke test exposed a new-Team state gap: Team creation
  succeeded, but Data access still received a null previous Current Team and
  disabled **New Data Group**. Team creation now returns the created Team,
  includes the creator as a member, selects/persists it as Current Team, updates
  the account menu, and opens Data access immediately for a system
  administrator. Backend Data Group permission enforcement is unchanged.
- Switching from Cosmos-compatible metadata to local MongoDB can leave an old
  Team ID in browser `Active_Teams` storage. Chat and Ask now validate that
  saved ID against the authenticated user's current Team list before loading
  Agents, effective access, or Data Groups. A missing Team is replaced with the
  first currently accessible Team (or cleared when none is available), and the
  repaired selection is persisted. This prevents Data Group creation from
  submitting a stale Team ID and returning `Team not found` without requiring a
  manual browser-storage reset.
- Quart's implicit 16 MiB request ceiling caused otherwise valid Team uploads
  to return HTTP 413 while the Portal button remained busy. The application now
  applies a configurable `MAX_UPLOAD_SIZE_BYTES` hard request limit (100 MiB by
  default), returns a JSON 413 explanation, exposes the limit to the Portal,
  blocks oversized Team selections before upload, displays the actual server
  error, and always clears the upload spinner immediately. Deployment ingress
  limits must be configured to the same or a larger value.
- Team and Global Knowledge upload drop zones now support keyboard/click file
  browsing as well as drag-and-drop. Each has explicit **Browse files** and
  **Select folder** actions; folder selection preserves browser-provided
  relative paths, and duplicate file/path selections are ignored. Directory
  browsing uses the Chromium-supported `webkitdirectory` input capability.

This slice moves application metadata, identities, authorization configuration,
jobs, and managed integration settings to an optional local database. Azure AI
Search and the separate optional Cosmos-native Chat History feature are not
replaced by it. Knowledge object storage is now independently selectable as
described below.

### Local Knowledge object storage

- `core/knowledge_store.py` defines the provider-neutral object contract used
  by Personal, Team, Global, and web-ingested Knowledge source files. Existing
  upload, listing, ingestion-job, deletion, Data Group tag, and authenticated
  citation routes now use this boundary instead of Azure clients directly.
- `KNOWLEDGE_STORAGE_PROVIDER=azure|minio` selects the deployment-wide
  provider. `azure` remains the default and keeps the existing Blob/Data Lake
  clients and ACL behavior. `minio` stores all scopes in one private bucket
  under isolated prefixes while the application remains the authorization
  boundary.
- `docker-compose.local-storage.yml` provides a loopback-bound, persistent
  MinIO service. `docs/local-storage.env.example` contains placeholders only;
  `docs/local-knowledge-storage.md` documents generated credentials, startup,
  persistence, security, verification, and migration boundaries.
- MinIO operations run through worker threads so its synchronous SDK does not
  block Quart's event loop. Object tags preserve processing status and Team
  Data Group associations. Missing objects map to the same controlled
  not-found behavior as Azure.
- This slice does not migrate existing Azure objects automatically. One backend
  uses one Knowledge object provider at a time, while separate deployments may
  independently choose Azure or MinIO. Azure AI Search remains the Knowledge
  index/retrieval backend for both choices in this slice.
- Azure Knowledge image-vector retrieval remains Azure-only and is disabled
  when MinIO is selected. Agent message image input and OCR routing are
  independent and remain available when their selected model/provider supports
  them.

### Local Knowledge vector search

- `core/knowledge_search.py` defines the small client contract shared by
  retrieval, citation authorization, ingestion, and deletion. Azure AI Search
  remains the default; `KNOWLEDGE_SEARCH_PROVIDER=qdrant` selects the local
  adapter.
- The Qdrant adapter creates a persistent collection with the configured
  embedding dimension, adds keyword payload indexes for source and ACL fields,
  upserts stable point IDs, and preserves existing citation/processing/ACL
  payload names.
- Existing application-generated OData filters are translated into Qdrant
  filters for category, source path, Personal `oids`, Team/Data Group `groups`,
  and Global empty ACLs. Unknown expressions fail closed instead of issuing an
  unfiltered query.
- Qdrant uses vector retrieval and provides a bounded lexical fallback when a
  text-only query is requested. Azure-only semantic ranker, query rewriting,
  agentic retrieval, and Knowledge image vectors are disabled in Qdrant mode.
  Agent message vision and OCR routing remain independent.
- `docker-compose.local-vector.yml`, `docs/local-vector.env.example`, and
  `docs/local-vector-search.md` document a loopback-bound persistent Qdrant
  service and the opt-in configuration. No Azure-to-Qdrant migration is
  automatic; content must be re-indexed into the selected collection.
- A disposable real Qdrant container smoke passed collection creation, payload
  index creation, deterministic upsert, Personal/Team/Global ACL-filtered
  vector search, exact count, and deletion. The temporary container, network,
  and volume were removed afterward.

### Local text embeddings

- `docker-compose.local-embedding.yml` provides a loopback-bound persistent
  Ollama service plus a one-shot model installer. The recommended baseline is
  `bge-m3`, which produces fixed 1024-dimensional vectors and supports mixed
  Thai/English Knowledge content.
- `docs/local-embedding.env.example` selects the existing
  `openai_compatible` embedding provider and a distinct
  `nexora-knowledge-bge-m3` Qdrant collection. Azure OpenAI and OpenAI remain
  supported and remain independent from the Agent's chat-completion provider.
- `docs/local-embeddings.md` covers startup, model installation, host versus
  Compose URLs, re-indexing, ACL validation, persistence, and operational
  constraints. Vectors are never migrated or mixed automatically.
- A real CPU Ollama container passed its health check, downloaded BGE-M3 into a
  persistent volume, and returned a 1024-dimensional vector for Thai synthetic
  text through `/v1/embeddings`. The product owner subsequently confirmed that
  Portal ingestion and retrieval with the local embedding configuration works
  end to end, including the requested cross-user/Team ACL, service restart, and
  document-deletion checks. Azure search/embedding fallback remains available
  by configuration and must continue to be covered when that deployment mode
  changes.

### Portable local runtime

- `Dockerfile.local` is a multi-stage image: Node 20 builds the frontend with
  the memory-safe production command, a disposable Python builder compiles any
  ARM64-only source dependencies, and the final Python 3.11 image runs
  Hypercorn as an unprivileged `nexora` user. Build tools and frontend source
  dependencies are not retained in the runtime image.
- `docker-compose.local-runtime.yml` combines the application, MongoDB, MinIO,
  Qdrant, and Ollama. It installs BGE-M3 and the configured local chat model
  through a one-shot service, waits for healthy dependencies, uses named
  volumes, keeps stateful APIs on the private Compose network, and binds the
  application and MinIO console to loopback by default.
- Docling is available through the optional `ocr` profile and must be selected
  by a managed document-processing profile at `http://docling:5001`.
- `docs/local-runtime.env.example` contains placeholders only;
  `docs/local-runtime.md` documents secret generation, first-admin bootstrap,
  safe stop/restart, persistence, smoke testing, and Azure VM constraints.
- MinIO startup no longer requires placeholder Azure Blob variables. Azure
  storage remains the default and now reports all missing Azure storage
  settings in one startup error when selected.
- The production entry point skips `azd env list` when
  `APP_RUNTIME_MODE=local`, so the Compose application consumes its injected
  environment without requiring Azure Developer CLI inside the image. The
  existing Azure-compatible local development path still loads the default
  `azd` environment. The direct local entry-point import and 38 focused
  runtime/configuration tests passed. A subsequent full service-free run was
  interrupted after it stopped making progress around 20%; the prior complete
  685-test result below remains the latest completed full regression.
- The local Compose profile disables the optional Azure Cosmos-native Chat
  History provider and enables the owner-isolated MongoDB history adapter. This
  prevents a clean local deployment from requiring `AZURE_COSMOSDB_ACCOUNT` at
  startup and synchronizes history across browsers for the same application
  user. Azure deployments may continue to enable the existing Cosmos history
  provider.
- The focused local-runtime/entry-point regression after this correction passed
  (`6 passed`), and `docker compose config` confirmed both history flags in the
  rendered application environment.
- The Compose schema, focused 48-test provider/runtime suite, 685-test
  service-free regression suite, multi-stage ARM64 image build, packaged
  frontend artifact, and Hypercorn import all passed. A destructive full-stack
  startup was intentionally not run against the developer's existing service
  volumes; the product owner still needs to run the documented clean-deployment
  smoke test.

### Local backup and restore — current working tree

- Branch `feature/local-backup-restore` starts from accepted checkpoint
  `c617141 feat: refine chat workspace and usage analytics`.
- `scripts/local_runtime_backup.py` provides `backup`, `validate`, and
  destructive `restore --confirm-restore` commands for the portable Compose
  runtime. It stops only the application writer when necessary and returns it
  to its previous running state.
- One versioned archive contains a logical gzip MongoDB dump, MinIO Knowledge
  objects with metadata/tags, and native snapshots for every Qdrant collection.
  The manifest allowlists components and records sizes, SHA-256 checksums,
  non-secret runtime compatibility values, and only a fingerprint of the
  Fernet key.
- Credentials, the environment file, `APP_DATA_ENCRYPTION_KEY`, bootstrap/API
  tokens, Ollama's reproducible model cache, browser history, and temporary Chat
  attachments are excluded. The deployment operator must protect the stable
  Fernet key separately.
- Restore requires matching database, bucket, configured Qdrant collection,
  embedding model/dimensions, and Fernet fingerprint. MinIO and Qdrant are
  restored before MongoDB metadata is restored with `mongorestore --drop`.
  Only Qdrant collections present in the backup are replaced; unrelated
  collections remain. The cross-product operation is not atomic; failure
  leaves the app stopped and requires rerunning the same validated archive.
- `app/backend/core/local_backup_io.py` performs bounded-memory MinIO archive
  streaming and Qdrant snapshot streaming. Qdrant multipart restore does not
  load the full snapshot into process memory.
- Unit coverage validates archive checksums/allowlists, rejects unexpected
  members, preserves MinIO metadata/tags while removing stale objects, replaces
  Qdrant collections from snapshots, and verifies bounded streaming upload.
  Focused validation passes (`7 passed`), the complete service-free backend
  suite passes (`777 passed, 1 deselected`), frontend TypeScript/build passes,
  and the local Compose schema renders successfully. A real backup/restore
  drill remains required on a disposable local runtime.
- See `docs/local-backup-restore.md` for operator commands, exclusions,
  compatibility requirements, and post-restore ACL/citation verification.

### Usage analytics dashboard — current working tree

- Branch `feature/usage-analytics-dashboard` starts from checkpoint `af326ba
  feat: add configurable AI guardrails`.
- Chat and Ask usage now records safe provider-neutral dimensions for Agent,
  provider, model/deployment, LLM profile, runtime, request mode, reasoning
  tokens, and per-stage model calls. Raw prompts and responses are not stored.
- Successful Knowledge ingestion records document-processing telemetry for all
  configured providers (including local parsers), with scope, provider/profile,
  file type, page count, and duration. This replaces the Azure Document
  Intelligence-only assumption for new records while retaining safe legacy
  totals.
- `GET /usage-analytics` performs aggregation on the backend and enforces three
  scopes: System requires `View system dashboard`, Team requires membership plus
  the new `View team dashboard` Team permission, and Personal is forcibly bound
  to the signed-in application user. Reporting periods are capped at 366 days.
- The Chat navigation now opens **Usage Analytics**, with System/Team/Personal,
  date, daily/weekly/monthly, Team, user, Agent, provider, and model filters.
  It separates LLM token and document-processing views and shows timelines and
  top breakdowns without returning raw usage records to the browser.
- Existing records remain visible; historically absent dimensions appear as
  `Unknown`. Legacy OCR rows are excluded from Personal summaries because they
  did not store an immutable application user ID.
- Focused analytics validation passed (`11 passed`). The complete service-free
  suite passed (`740 passed, 1 deselected`), and the memory-safe frontend
  production build passed. An unfiltered run also reached `740 passed` with one
  unrelated `data_integration` failure caused by a local PDF fixture that
  yielded no text sections.

See `docs/usage-analytics.md`.

### Usage quotas — current working tree

- Hierarchical quotas were checkpointed as `89ddc72 feat: add hierarchical
  usage quotas`; the product owner manually accepted that slice. The current
  durable metering and Team member quota checkpoint is `fa3fe65 feat: add
  durable scoped usage quotas`.
- Provider-independent quota policies can be stored at System, Team, and User
  levels. Enabled limits merge System → Team → User using the smallest non-zero
  value; zero means unlimited at that level.
- The first enforceable limits are monthly LLM tokens, monthly processed
  document pages, and LLM requests per minute. Each hierarchy level is compared
  against usage in its own scope. Requests-per-minute uses atomic MongoDB
  fixed-window counters.
- Optional monthly token rules can target a configured provider or exact model
  profile and can apply to all requests, Chat, or Ask. Stable provider/profile
  IDs are used for enforcement; labels are snapshots only. All matching rules
  must pass, while the Overall limit automatically covers newly added models.
  Deleted provider/model targets remain visible as unavailable rules until an
  administrator removes them.
- Quotas are checked before Chat/Ask provider calls and before document
  extraction. A reached LLM quota returns 429; a reached document quota fails
  the persistent ingestion job before invoking its parser.
- System Admins configure System and per-User overrides under **Usage Quotas**.
  Team administrators with `Manage team permissions` configure their Team
  policy. To avoid a hidden Administration-only route, System Admins can switch
  **Entire system / Current team / Specific user** from the same page even when
  Team settings is open. Current monthly usage is shown beside each configured
  limit.
- Team policies also support a default monthly LLM-token allowance per member.
  A Team administrator can select a current member and set a `(team_id,
  user_id)` override that replaces that Team default without bypassing
  Team/System totals. The same user can therefore have different allowances in
  different Teams. Existing global User ceilings remain available to System
  Admins and continue to act as an additional ceiling.
- Monthly LLM enforcement now counts completed persisted events plus active
  request reservations. Document pages are still checked from completed jobs,
  because their authoritative page count may only be known after parsing.
  Document-page reservations, approval workflows, notifications, pricing/cost
  budgets, and immutable billing-period rollups remain follow-up work.
- Token totals include input, output, and reasoning tokens. Provider/model
  attribution applies to newly metered selected request profiles; old events
  remain in Overall totals, and exact per-call attribution for multi-model
  sub-agent runs and embeddings remains follow-up work.
- Subscription licensing is intentionally designed as a separate entitlement
  layer rather than being embedded in quota records. The approved direction for
  signed offline licenses, one-year terms, feature/capacity claims, grace and
  renewal behavior is recorded in `docs/product-backlog.md`.
- The current uncommitted metering slice assigns each Chat/Ask call a UUID,
  creates an expiring token reservation before provider execution, persists the
  final LLM usage synchronously and idempotently with that UUID, and finalizes
  the reservation. Duplicate active/completed request IDs are rejected. A
  failed usage write leaves a conservative 15-minute reservation instead of
  failing an otherwise successful response. Persistent ingestion-job IDs now
  make document-processing usage idempotent across recovery/retry.
- Quota status includes used/reserved amounts and 80/90/100 percent severity.
  Safe metadata-only threshold, block, and metering-failure events are retained
  for 90 days and displayed in the quota Portal. Raw prompts and responses are
  not written to these records.
- Remaining metering work before contractual billing includes exact
  per-model-call/sub-agent and embedding attribution, page reservations,
  provider reconciliation, notifications, and immutable period rollups.
- Focused quota/config/analytics/ingestion validation passed (`186 passed`), the
  complete service-free suite passed (`767 passed, 1 deselected`), frontend
  TypeScript validation passed, and the memory-safe production build passed.
  The known repository PDF fixture that yields no local text sections remains
  outside this service-free run under the `data_integration` marker.

See `docs/usage-quotas.md`.

### Settings navigation

- Checkpoint `66d0595 feat: organize settings navigation` starts from the
  accepted durable quota checkpoint `fa3fe65`, so the previous horizontal-tab
  interface remains easy to recover or compare.
- The settings dialog now uses stable page identifiers and a categorized,
  collapsible desktop sidebar instead of one overflowing horizontal tab row.
  Team pages are grouped under **People & access**, **AI workspace**, and
  **Governance**; authorized platform pages are visually separated under
  **System administration**.
- With no active Team, the same shell presents Administration-oriented groups
  and labels the unassigned integration page **Integration catalog**. With a
  Team it is labeled **Team integrations**.
- Small screens use one grouped Settings-section selector rather than the
  sidebar. Existing page components, permission checks, backend routes, and
  creation flows are unchanged. Creating a Team still moves directly to Data
  access, now by a stable page key rather than a fragile tab index.
- The navigation shell restores the content gutter previously supplied by
  `TabPanel` for pages that rely on it, while avoiding double padding for
  Integrations, Guardrail Policy, and Usage Quotas, which own their content
  spacing. This keeps page headings and primary actions away from dialog edges
  across every current menu.
- Frontend TypeScript validation and the memory-safe production build passed.
  The product owner manually accepted the Settings Navigation layout and page
  gutters before checkpointing.
- The current working tree removes the nested horizontal tabs from the former
  **User directory** page. **Teams**, **Users**, and **User permissions** are
  grouped under one collapsible **Organization** menu, while **Sign-in &
  authentication** remains a separate final entry under **System
  administration**. Team-scoped settings are grouped first under the actual
  Team name (with ellipsis and a full-name tooltip), followed by AI Workspace,
  Governance, Organization, and System Administration; all groups start
  collapsed whenever Administration opens. The Teams list has
  one primary **Manage** action that opens the existing Team Settings workspace;
  member management remains in **Members**, while rename moves to the Team
  Settings title and delete stays in the row overflow menu. This removes the
  duplicate View/Edit/Manage Members workflows without changing their backend
  authorization contracts. TypeScript validation, the memory-safe production
  build, and the complete service-free backend suite (`860 passed, 1
  deselected`) passed; the rebuilt local application container is healthy.
- The settings header now makes the active context explicit with distinct
  **TEAM WORKSPACE** and **SYSTEM ADMINISTRATION** treatments, a scope chip, and
  destination-oriented switch actions such as **Switch to system
  administration** and **Return to Presale team**. This is presentation-only;
  the existing Team and System authorization boundaries remain unchanged.

### System Health

- System Administrators have a **System administration → System health** page
  backed by `GET /admin/system-health`. It loads on entry and refreshes only on
  explicit request; there is no continuous browser polling. It shows a
  secret-free snapshot of CPU, memory, disk, application RSS, core services,
  aggregate integration health, and ingestion/attachment queues and workers.
- MongoDB and configured local MinIO, Qdrant, Ollama, and Integration Controller
  endpoints receive short read-only liveness probes. Azure and other remote
  clients are reported as initialized/configured rather than making potentially
  costly provider calls on every refresh. Full host metrics, time-series,
  alerting, and externally hosted outage detection remain follow-up work; see
  `docs/system-health.md`.
- Focused System Health tests pass (`5 passed`), the complete service-free suite
  passes (`874 passed, 1 deselected`), and the frontend TypeScript/production
  build passes.

### Production TLS ingress

- `docker-compose.local-tls.yml` is an opt-in overlay for the portable local
  runtime. It adds an Nginx gateway on ports 80/443, redirects HTTP to HTTPS,
  proxies streaming/API traffic to the private application service, and mounts
  operator-supplied `fullchain.pem` and `privkey.pem` files read-only from a
  directory outside the repository.
- The gateway accepts TLS 1.2/1.3, adds baseline HSTS, MIME-sniffing,
  same-origin framing, referrer and browser-permission headers, disables
  response buffering for Chat streams, and retains the base application's
  loopback-only port for host maintenance. Stateful services remain private.
- Enabling the TLS overlay also registers its internal Nginx liveness endpoint
  with System Health, where it appears as **HTTPS gateway · Nginx**. The base
  runtime omits this component when the overlay is not enabled. Certificate
  expiry inspection and warning thresholds remain follow-up work. The combined
  System Health/TLS regression suite passes (`8 passed`) and the merged Compose
  schema exposes the probe only on the private runtime network.
- Certificate issuance/ACME automation, physical firewall/DNS configuration,
  an HttpOnly Local Auth cookie/BFF flow, and product entitlement licensing are
  deliberately separate follow-up slices. See `docs/production-tls.md`.
- The focused TLS/Compose tests pass (`2 passed`), the complete service-free
  backend suite passes (`876 passed, 1 deselected`), the frontend production
  build passes, the merged Compose schema renders, and a temporary real Nginx
  container passed HTTPS proxy, security-header, and HTTP-redirect smoke tests.

### Product licensing foundation

- `core/licensing.py` defines version 1 entitlement claims and a deterministic,
  side-effect-free evaluator for unlicensed, active, grace, expired, revoked,
  and invalid states. Claims cover stable license/customer/product/issuer/key
  identifiers, edition, timezone-aware validity, bounded grace, feature flags,
  capacity ceilings, and optional stable installation binding.
- This slice performs schema validation only after a future caller has verified
  a license document. It deliberately provides no signature verifier,
  persistence, Portal import/status API, feature gates, or enforcement, so an
  unsigned document cannot accidentally become an authorization boundary and
  existing installations do not change behavior.
- The focused deterministic licensing suite passes (`20 passed`), the complete
  service-free backend suite passes (`896 passed, 1 deselected`), Ruff passes
  for the initial Python files, and the frontend production build passes.

The next licensing slice is now implemented in audit mode. System Admins have a
**System administration → License** page showing a stable MongoDB-backed
Installation ID and safe status. They can start one 14-day Trial or import an
`NX1` offline license. Imports verify an Ed25519 signature against a bounded,
rotatable read-only public-key directory before validating product, period,
features, capacities, and installation binding. The raw license is Fernet
encrypted, never returned to the Portal, and excluded from metadata-only
365-day Trial/import audit events. `scripts/license_key_tool.py` generates
vendor keypairs and signed license files but is excluded from the application
image; the private signing key must remain outside this repository and customer
deployments. Feature and capacity enforcement remains disabled pending an
explicit audit-mode comparison slice. See `docs/licensing.md`.
- Focused license schema, signature, persistence, route, and issuer-tool tests
  pass (`33 passed`); the complete service-free backend suite passes (`909
  passed, 1 deselected`), Ruff passes for the focused licensing modules and
  tests, the frontend production build passes, and the local Compose schema
  renders with the read-only public-key mount.
- Post-checkpoint validation against the real local MongoDB runtime found that
  PyMongo returns stored UTC Trial timestamps without `tzinfo`. The status path
  now normalizes only persisted naive timestamps as UTC, while explicit caller
  timestamps remain strict. The Portal also reports a controlled HTTP error
  instead of exposing a JSON parse error when an upstream response is HTML.
  Focused regression tests pass (`34 passed`), the frontend production build
  passes, and the live stored Trial evaluates as active. The full suite reached
  `910 passed` with one unrelated data-integration failure where a repository
  PDF fixture produced no text-splitter sections.

### Chat workspace polish

- Checkpoint `c617141 feat: refine chat workspace and usage analytics` starts
  from the accepted Settings Navigation checkpoint `66d0595`.
- The shared Chat/Ask context selector now presents Agent, model, active Team,
  and selected data scope together, with a visible Change affordance. Selection
  state, authorization, and request payload behavior are unchanged.
- The Chat sidebar retains all existing permission checks and actions while
  grouping them into **Workspace**, **Management**, and **Insights**. Empty
  Management sections are not rendered, and chat history has an explicit
  **Recent chats** heading.
- Users without Team/System analytics permission see the dashboard entry and
  dialog as **My Usage**. Personal scope continues to be enforced by the
  backend and no longer renders the redundant Users breakdown; Models, Agents,
  and the current user's own Team attribution remain available. Authorized
  Team/System analytics retain the broader Usage Analytics views.
- Document Processing analytics now has domain-specific Provider, Profile,
  File type, and Document scope filters and breakdowns. Authorized Team/System
  views add By User, and System view adds By Team. Personal scope omits both
  identity breakdowns. Legacy records without an immutable application user
  remain excluded from Personal scope and are labeled `Unknown / legacy` in
  authorized aggregate views rather than being matched from historical email.
- The empty Chat state is more compact and the composer/context spacing is
  tightened without changing Chat, attachment, Vision, history, or RAG logic.
- Frontend TypeScript validation and the memory-safe production build pass.
  Focused usage analytics, route authorization, document usage, and quota tests
  pass (`29 passed`).
  The product owner manually accepted the expanded/collapsed sidebar, scoped
  My Usage/Usage Analytics behavior, and document-processing breakdowns before
  checkpointing.

## Other next work

### Near-term document work

1. Add a production malware-scanner adapter and make its deployment policy
   explicit before accepting untrusted documents outside development.
2. Continue the requirement-to-Knowledge-evidence matrix with long-document
   batch evaluation, validated row JSON, progress/retry, and CSV/Excel export.
   Then add per-model vision/OCR routing in both runtimes and speech
   improvements. See `docs/product-backlog.md`.

### Platform roadmap

- **Immediate next slice:** complete a disposable backup/restore drill for the
  portable Compose runtime, then add production ingress/TLS. Design verified-channel
  forgotten-password recovery and decide
  whether production deployments should move the local bearer from
  `sessionStorage` to an HttpOnly cookie/BFF flow before production hardening.
- Docker Compose for the complete application, persistent volumes,
  health/readiness, secret injection, tested backup/restore, and then
  Helm/Kubernetes.
- AI guardrails.
- Agent Invocation API.
- Extend usage analytics with a versioned pricing catalog, estimated cost,
  budgets/alerts, CSV/Excel export, scheduled reports, tool/error/latency
  telemetry, retention rollups, and high-volume database indexes.
- Shared time/token budgets across a delegation tree, persisted LangGraph
  checkpoints, and audit retention/index policies.

The guardrail/API/dashboard discussion order is documented in
`docs/product-backlog.md`.

## Critical known limitations and risks

- **Admin authorization:** OCR and the Team member/Data Group/role-permission
  routes described above enforce authorization server-side. Continue auditing
  Agent, mail, messaging, external database, and other newer management routes
  that still use only the generic authenticated decorator or UI visibility.
- **OCR routing:** automated tests cover precedence, conflicts, fallback and
  override authorization, but live Personal/Team/Global uploads with multiple
  providers still require manual smoke testing before checkpointing.
- **Ingestion worker:** jobs and leases are persistent, but execution still runs
  inside the web application. Use a dedicated queue/worker before high-volume
  horizontal scaling or extraction calls that can exceed the one-hour lease.
  Graceful shutdown returns owned jobs to the queue immediately; a hard kill
  waits for lease expiry. No automatic ingestion-job retention/TTL policy is
  configured yet.
- **Local mode:** local authentication, MongoDB metadata, and MinIO Knowledge
  object storage now have provider-backed first slices, but vector search/RAG
  and complete deployment packaging remain Azure-dependent. This is not yet a
  fully local product.
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
  database, MCP, mail, messaging, OCR, and managed Entra credentials unreadable.
- **Local-auth hardening:** local bearer tokens are opaque, persisted only as
  hashes server-side, and stored in browser `sessionStorage`, but they remain
  sensitive to a successful same-origin XSS attack. Production deployment must
  enforce HTTPS and should evaluate an HttpOnly-cookie/BFF flow. MFA and
  self-service password recovery are not implemented yet.
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

Latest Guardrails regression on 2026-09-02:

```text
36 passed
```

This focused suite covers deterministic secret/PII/content checks, policy
inheritance, cross-chunk redaction, untrusted tool output, and Team policy
authorization. The complete service-free backend regression also passed:

```text
731 passed, 1 deselected
```

Frontend TypeScript checking and the memory-safe production build passed. The
build retains the existing large-vendor-chunk warning.

The product owner manually verified graceful-stop recovery of an in-progress
Knowledge ingestion job on 2026-08-22. A legacy job left with the former
one-hour lease was reset only after confirming no backend worker was running;
the restarted service then resumed processing successfully.

The product owner manually verified the account-menu full-name display,
self-service profile editing, and Local current-password change flow on
2026-08-23.

The product owner also confirmed the Local-only and hybrid Local+Entra
authentication acceptance flow, including the relevant access-control behavior,
on 2026-08-23.

Latest service-free backend regression on 2026-09-01 after the unassigned
integration catalog and target-Team consistency slice:

```text
695 passed, 1 deselected
```

Command:

```bash
.venv/bin/pytest -q -m 'not azure and not external and not data_integration'
```

The broader service-free run reached `680 passed` but one data-integration test
failed because it iterates every local `data/*.pdf` file and one current PDF is
image-only or otherwise yields no text through `pypdf`. This is unrelated to
the embedding configuration and the local data file was not modified.

The focused Knowledge storage provider, startup configuration, content,
ingestion-job, and legacy upload regression passed:

```text
55 passed
```

The MinIO Compose schema passed with placeholder credentials. A disposable
MinIO container also passed bucket creation, Team-scope upload/read/list,
processing-tag read/update, and delete through the real SDK; its temporary
container, network, and volume were removed afterward. Full browser-level
Personal/Team/Global ACL and citation smoke testing remains pending. The
product owner additionally confirmed on 2026-08-24 that the application starts
with MinIO enabled and the exercised Knowledge workflow operates normally.

The focused Qdrant/search/configuration/ACL/ingestion regression passed:

```text
93 passed
```

Ruff passed for the changed Python files. Targeted mypy remains blocked by the
existing optional Docling import stubs and by the repository's Python 3.9 mypy
target parsing Python 3.10 syntax in the installed AnyIO dependency. Frontend
typecheck and the memory-safe production build passed after the Qdrant config
surface was added.

Latest focused evidence-matrix, attachment retrieval, Agent RAG, and document
validation regression:

```text
63 passed
```

Latest focused effective-access and authentication-filter regression:

```text
45 passed
```

Latest focused local/Entra authentication, password/session, effective-access,
profile-boundary, and usage validation:

```text
54 passed
```

The current profile, Team-state, upload-limit, and local MongoDB slices also
passed the memory-safe TypeScript/production build. Focused application config,
effective-access, local MongoDB connector/Compose contract, and
local-authentication validation passed:

```text
54 passed
```

An unfiltered `.venv/bin/pytest -q` run reached `617 passed` but the single
`data_integration` splitter test failed on a repository `data/` PDF whose local
parser returned no text sections. The supported service-free command above
passes; no user data file was modified or removed to mask that dataset-specific
failure.

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
NEXORA_MONGO_ROOT_USERNAME=test-root \
NEXORA_MONGO_ROOT_PASSWORD=test-root-password \
NEXORA_MONGO_APP_USERNAME=test-app \
NEXORA_MONGO_APP_PASSWORD=test-app-password \
docker compose -f docker-compose.local-mongodb.yml config
MINIO_ACCESS_KEY=test-access \
MINIO_SECRET_KEY=test-secret \
docker compose -f docker-compose.local-storage.yml config
docker compose --env-file docs/local-vector.env.example -f docker-compose.local-vector.yml config
docker compose --env-file docs/local-embedding.env.example -f docker-compose.local-embedding.yml config
```

Known non-blocking warnings:

- Azure Monitor imports deprecated `pkg_resources` through an upstream package.
- Vite reports an existing large vendor chunk.
- `npm install` currently reports 18 dependency audit findings (1 low, 9
  moderate, 8 high). No broad or breaking `npm audit fix` was applied as part
  of the focused math-rendering slice.
- PyMongo can emit a Cosmos DB feature-compatibility warning.

## Manual smoke-test checklist before the next checkpoint

- As System Admin, send Chat/Ask requests through two Agents/models and index
  documents with two processing profiles. Open **Usage Analytics**, verify
  System/Team/Personal totals, change date bucket and all dimension filters,
  and confirm old rows show `Unknown` rather than disappearing. Assign `View
  team dashboard` to one Team role and verify that user sees only that Team;
  verify a user without it receives 403 and My usage cannot be broadened with a
  different user ID. Confirm the analytics records contain no prompt, response,
  extracted text, credentials, or tool output.
- As a System Admin, open **Administration → Guardrail Policy**, save a System
  policy with PII output `Redact`, then open a Team's **Guardrail Policy** and
  save a stricter PII input `Block` policy. Configure an Agent with weaker
  `Allow` values and verify the effective runtime still blocks a valid PII test
  value in input and redacts an email/telephone number in output. Confirm a
  Team user without `Manage agents` receives 403 from the Team guardrail API.
  Repeat one blocked English and Thai high-confidence unsafe instruction and
  one ordinary safety-policy question to check the intended precision. Finally,
  confirm **Agent Audit** contains only detector/category/count/outcome metadata
  and no submitted PII, prompt, or model response.

- Follow `docs/local-knowledge-storage.md`, start MinIO with newly generated
  credentials, and run the backend with `KNOWLEDGE_STORAGE_PROVIDER=minio`.
  Confirm `/config` reports `minio`; upload, index, list, cite, and delete one
  Personal, Team, and Global document; restart both services without deleting
  the named volume; then verify persistence and that an unauthorized user
  cannot retrieve a Team source. Azure mode must still pass the corresponding
  upload/citation smoke test. No Azure-to-MinIO copy is automatic.
- Follow `docs/local-vector-search.md`, start Qdrant, and run the backend with
  `KNOWLEDGE_SEARCH_PROVIDER=qdrant`. Re-index unique Personal, Team, and Global
  documents; verify retrieval, citations, restart persistence, deletion, and a
  denied cross-Team/Data Group query. Switching back to `azure` must retain the
  existing Azure AI Search behavior.
- Follow `docs/local-embeddings.md`, start Ollama, install BGE-M3, then load the
  local vector settings followed by the local embedding settings. Re-index into
  `nexora-knowledge-bge-m3`; confirm `/v1/embeddings` returns 1024 dimensions
  and repeat the Personal/Team/Global, citation, restart, deletion, and denied
  cross-Team/Data Group checks. Do not reuse a collection created by another
  embedding model.

- Follow `docs/local-mongodb.md` with two newly generated passwords. Confirm the
  Compose service becomes healthy and the database-scoped application user can
  ping `nexora`. Start the backend with that `MONGO_URI`, create a test Team and
  Data Group, restart the backend and MongoDB container without deleting the
  named volume, and confirm the records remain. Then change a Local password
  and exercise one document-processing restart to verify sessions and job
  recovery use the local database. Do not run `down --volumes` after creating
  data that must be retained.
- Start with `LOCAL_AUTH_ENABLED=true`, a stable
  `APP_DATA_ENCRYPTION_KEY`, and a temporary `LOCAL_AUTH_BOOTSTRAP_TOKEN`.
  Create the first administrator from Login, remove the bootstrap token and
  restart. Verify local sign-in survives the restart; five bad passwords lock
  the account; User Management can create a local user; password reset signs
  out that user's existing session; Team/Data Group selection and citations
  obey the same ACLs as Entra. As the local administrator, save valid Entra
  settings in **Users & Access → Authentication**, reload, verify both login
  methods, then verify **Use environment settings** restores the environment
  configuration. Open the account menu and verify the full name and sign-in ID
  are distinct, update only the editable My profile fields, and confirm account
  IDs/privileges remain read-only. For a Local user, reject a wrong current
  password, change to a different 12+ character password, verify all previous
  Local sessions are rejected, and sign in with the new password. Confirm an
  Entra-only profile shows Microsoft-managed password guidance. Perform this
  over HTTPS outside local development.
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
- Open **Team settings** for two different Teams and confirm Members, Data
  access, and Roles & permissions always remain on the Team named in the dialog
  header. Create one Entire team Data Group and one Selected users group; verify
  the access badges and member identities, then confirm an assigned member sees
  both in Chat/Ask while another Team member sees only the Team-wide group.
  Confirm a user without the relevant management permission cannot create,
  edit, or delete the group through a direct API request. Verify a Team
  permission editor cannot grant a System permission or change `is_sys_admin`.
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
  Create separate Datadog connections for two Teams, verify each Team can list,
  bind, test, and invoke only its own connection, and confirm a direct
  cross-Team connection ID is rejected. For a pre-existing unassigned MCP
  connection, remove any legacy Agent binding before using **Assign team**.
- Configure a managed Azure connection as System Admin and connect the official
  Draw.io hosted endpoint to one Team. Confirm enabling Azure creates exactly
  one connection-specific container, disable stops it, re-enable/restart
  reconciles it, and delete removes it. Assign both connections to a LangGraph
  Agent and request a diagram for one small resource group. Confirm Azure
  Test/runtime report write-oriented tools as blocked, the Azure identity cannot
  modify resources, the Draw.io output contains only returned resources with
  their resource IDs in metadata, and another Team cannot list or invoke either
  connection.
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
and do not discard unrelated changes. Validate the managed Azure MCP slice with
a verified digest of the official image and a least-privilege test tenant. Run
the enable, Test, Azure inventory to Draw.io, disable, restart/reconcile, and
delete lifecycle. Preserve read-only enforcement, Team ownership, encrypted
secrets, and metadata-only lifecycle audit. Do not add Azure write/provisioning
tools until an architecture-schema, IaC What-If, and explicit approval workflow
have been designed.
```
