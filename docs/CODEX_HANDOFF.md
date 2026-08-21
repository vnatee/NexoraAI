# Codex handoff — NexoraAI

Last updated: 2026-08-20 UTC

This document replaces a raw chat transcript as the engineering handoff. It
captures the decisions and evidence needed to continue without storing copied
logs, credentials, attachments, or repetitive conversational text.

## Repository state

- Workspace: `/workspaces/NexoraAI`
- Branch: `feature/agent-platform-foundation`
- Latest pushed checkpoint: `05b791a` / `feat: add persistent document
  ingestion jobs` on `origin/feature/agent-platform-foundation`.
- Azure baseline: `8ee1e8a` / `origin/Release-2.2.0`
- This checkpoint includes OCR routing/provider tooling plus persistent
  ingestion jobs, upload status UI, Retry, worker leases, restart recovery, and
  Indexed Time file details.
- The current slice implements provider-neutral page-aware Docling
  normalization and focused tests. The product owner accepted the live
  multi-page Docling citation smoke test on 2026-08-21; this slice is ready for
  checkpointing.
- Automated validation passed at checkpoint time. The live OCR routing checks
  in the manual smoke-test section remain deployment acceptance work; do not
  treat the checkpoint itself as evidence that those external services passed.

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
  a live tool-call probe. Results are stored as `supported`, `unsupported`, or
  `unknown`. Confirmed unsupported models are forced off and the frontend switch
  is disabled; inconclusive network/quota/provider errors remain editable.
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
  metadata. RAG currently indexes page number and text; optional metadata is not
  yet persisted in the search index.
- Docling Serve and embedded Docling normalize structured provenance into real
  document pages before chunking. Tables remain on their source page, and the
  existing `SplitPage.page_num` contract produces page-aware PDF citations
  without binding the parser to Azure AI Search. Serve requests JSON first and
  sends a separate Markdown request when that format is rejected or does not
  contain recognized pages; Markdown still ingests as one logical page.
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

## Other next work

### Near-term document work

1. Persist/index selected safe OCR metadata such as provider and confidence.
2. Chat image attachments: upload/preview/remove, file limits, Agent image
   capability, OCR-only versus multimodal vision, and safe prompt composition.

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

Latest service-free backend regression on 2026-08-20:

```text
480 passed, 1 deselected
```

Command:

```bash
.venv/bin/pytest -q -m 'not data_integration'
```

Latest focused OCR/upload/profile-idempotency validation:

```text
62 passed
```

Latest focused ingestion-job and document-processing validation:

```text
45 passed
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
- PyMongo can emit a Cosmos DB feature-compatibility warning.

## Manual smoke-test checklist before the next checkpoint

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
and do not discard unrelated changes. Continue with safe provider-neutral OCR
metadata indexing: carry selected provider/profile/confidence metadata from
normalized pages into chunks and search documents without persisting raw
provider responses or credentials. Keep Azure behavior working and design the
metadata contract so a future local vector adapter can reuse it.
```
