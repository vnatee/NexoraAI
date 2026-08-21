# Codex handoff — NexoraAI

Last updated: 2026-08-21 UTC

This document replaces a raw chat transcript as the engineering handoff. It
captures the decisions and evidence needed to continue without storing copied
logs, credentials, attachments, or repetitive conversational text.

## Repository state

- Workspace: `/workspaces/NexoraAI`
- Branch: `feature/agent-platform-foundation`
- Previous checkpoint: `2d65a0e` / `feat: add vision chat attachments and math
  rendering`. This handoff revision accompanies the next AttachmentStore/
  conversation-metadata checkpoint; use `git log -1 --oneline` for its hash.
- Azure baseline: `8ee1e8a` / `origin/Release-2.2.0`
- This checkpoint includes the accepted request-local Chat/Ask image slice,
  per-model Vision probing/configuration, sent-image thumbnails, stale Agent
  profile reconciliation, and KaTeX math rendering in addition to the earlier
  OCR/ingestion work.
- The current checkpoint starts milestone 2 with a provider-neutral `AttachmentStore`
  contract, private local/container filesystem reference adapter, stable Chat/
  Ask conversation UUIDs, and an ACL-scoped Mongo-compatible metadata
  repository. Document bytes are not connected to Chat routes yet.

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
and work whose process lease expired after restart. This remains an in-process
worker rather than an external durable queue; see `docs/ingestion-jobs.md` for
the contract and scaling limitation.

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

Current boundaries are deliberate: document attachments, route-integrated
private storage, temporary attachment RAG, OCR-only fallback, and LangGraph
multimodal messages are not implemented in this checkpoint.
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

### AttachmentStore foundation — current checkpoint

`core/attachment_store.py` defines an async provider-neutral contract plus a
`LocalAttachmentStore` reference adapter for local/container deployments. The
adapter uses opaque UUID storage keys, basename-only normalized filenames,
private `0700` directories and `0600` files, atomic writes, exact owner and
conversation authorization, configurable byte/TTL limits, SHA-256 verification,
read-time expiry, explicit deletion, and fail-closed cleanup for expired,
corrupt, or old orphaned payloads. Focused tests cover traversal rejection,
cross-owner/cross-conversation access, tampering, TTL, cleanup, and permissions.

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

Document bytes are intentionally not wired into the request routes yet. The
approved production design still requires a private Azure adapter/factory
(without public URLs), coordinated object/metadata cleanup, document MIME/
signature/decompression/page validation, malware-scanning hook, extraction, and
a conversation-private `AttachmentIndex`. The local JSON sidecar is an adapter
implementation detail, not the final metadata system.

## Other next work

### Near-term document work

1. Add the private Azure `AttachmentStore` adapter/factory and coordinated
   object/metadata expiry cleanup, retaining the local adapter for containers.
2. Wire approved document uploads to the store, then add bounded extraction and
   a conversation-private temporary `AttachmentIndex`. Do not auto-promote Chat
   documents into permanent Knowledge.
3. Add the requirement-to-Knowledge-evidence matrix, per-model vision/OCR
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
  No automatic ingestion-job retention/TTL policy is configured yet.
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
- **Chat attachments:** only request-local images in the Legacy vision runtime
  are supported. No private attachment store, document extraction, TTL cleanup,
  temporary RAG, LangGraph image message, or OCR-only fallback exists yet.
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

Latest service-free backend regression on 2026-08-21:

```text
524 passed, 1 deselected
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

Latest focused AttachmentStore, metadata, conversation-ID, and attachment-route
validation:

```text
36 passed
```

Latest focused OCR/upload/profile-idempotency validation:

```text
62 passed
```

Latest focused ingestion/document-processing, splitter, and search-metadata validation:

```text
79 passed, 1 deselected
```

Latest focused LLM provider/model-capability validation:

```text
18 passed
```

Frontend typecheck and production build passed. Use:

```bash
cd app/frontend
npx tsc --noEmit
NODE_OPTIONS=--max-old-space-size=4096 npm run build
```

The default Node heap still exhausted memory during Vite chunk rendering in
this environment; the documented 4 GB heap command completed successfully.

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

- Chat/Ask normal text paste remains unchanged. Verify **Vision Off** disables
  the attachment picker; turn Vision on, then paste, select, and drag/drop a
  supported image and verify preview/removal, image-only send, and limits. In
  Chat, confirm sent thumbnails and filenames remain on the correct user turn
  during loading and after the answer, and that Retry resends the same image.
  Confirm a reload/history restore does not persist the inline image bytes.
- With Legacy vision enabled, verify the real model uses the attached image and
  that the attachment is not shown as a Knowledge citation or raw data URL in
  prompt diagnostics. Verify both streamed Chat and non-streamed Ask.
- In **Admin Management → LLM Providers**, run Test for at least one real
  vision-capable managed model. Confirm the Provider card displays the Vision
  tag and the composer updates without a browser refresh. Select the profile on
  a Legacy Agent, toggle Vision On/Off (including while Agentic Retrieval was
  previously on), and verify it works without setting `USE_GPT4V` or
  `AZURE_VISION_ENDPOINT`. Reload Chat after changing the Agent profile and
  confirm it uses the backend profile rather than a stale locally cached Agent.
- With vision disabled and with a LangGraph Agent, verify the UI shows the
  controlled unsupported-image message rather than silently sending or
  ignoring the attachment.
- Verify Answer rendering with `$x^2$`, `$$\\frac{1}{2}$$`, `\\(x+y\\)`, a raw
  `\\sqrt{147}` embedded in Thai prose, and the nested raw expression
  `3\\sqrt{147} - 7\\sqrt{\\frac{1}{27}}`. Confirm the same commands remain
  literal inside a fenced code block.

- Azure startup, Personal/Team/Global upload, search, deletion, and citations.
- OCR routing precedence for Personal/Team/Global, Auto selection, authorized
  manual override, conflict rejection, Explain Route, and legacy/system fallback.
- Persistent job stages for Personal/Team/Global, selected provider/profile/rule,
  controlled failure and Retry, page refresh persistence, and restart recovery
  after the worker lease expires. Confirm Indexed leaves Recent after about one
  minute while Indexed Time remains visible in the relevant file list.
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
and do not discard unrelated changes. Start the Chat image attachments slice:
inspect existing chat request/model capability contracts, then implement safe
upload/preview/remove, size/type/count limits, per-Agent image capability,
OCR-only versus multimodal handling, and safe provider-neutral prompt/request
composition. Keep Legacy and LangGraph rollback behavior working and add focused
tests before live smoke testing.
```
