# Codex handoff — NexoraAI

Last updated: 2026-08-20 UTC

This document replaces a raw chat transcript as the engineering handoff. It
captures the decisions and evidence needed to continue without storing copied
logs, credentials, attachments, or repetitive conversational text.

## Repository state

- Workspace: `/workspaces/NexoraAI`
- Branch: `feature/agent-platform-foundation`
- Latest checkpoint commit: `fba5481 feat: checkpoint agent platform foundation`
- Azure baseline: `8ee1e8a` / `origin/Release-2.2.0`
- The working tree is intentionally dirty. It contains substantial post-
  checkpoint implementation across Agent Runtime, integrations, audit, mail,
  messaging, and document processing. Do not reset or replace it.
- No commit was created for the current post-checkpoint work during this
  handoff. Review the diff and create a new checkpoint only after the current
  manual smoke tests are accepted.

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
- Optional Compose services and a PaddleOCR CPU Dockerfile are present.
- Docling URL normalization accepts a base URL or a URL ending in `/health`,
  `/ready`, `/docs`, or `/ui`. Runtime always derives the service base before
  health and conversion calls.
- Manual connectivity evidence: from the backend environment,
  `http://host.docker.internal:5001/health` returned HTTP 200; the Docling root
  returned 404, which is normal for that image.

Important validation boundary:

- Docling health/connectivity was manually verified.
- PaddleOCR Compose schema and adapter response parsing were tested, but the
  large Paddle image/model was not fully built and inference-smoke-tested in
  this session.
- Google Document AI was not called against a real Google project/processor in
  this session.

See `docs/document-processing.md`, `docs/ocr-provider-contract.md`,
`docker-compose.ocr.yml`, and `services/paddleocr/Dockerfile`.

## Current OCR routing behavior and immediate design gap

All Personal, Team, and Global uploads use the same `CONFIG_INGESTER`. The
managed parser currently resolves only:

```text
default processing profile + file extension
```

The same selected provider therefore applies to all document scopes. Only one
profile can be marked default because saving a default unsets every other
default. A non-default profile is stored but is not selected during upload. No
Provider/Profile selector exists on Personal, Team, or Global upload pages.

If the default profile does not include the uploaded extension, the system
falls back to the startup Azure/local parser configuration.

Recommended next slice, pending explicit product-owner confirmation:

1. Replace the single-global-default lookup with OCR Routing Rules containing:
   scope (`all`, `personal`, `team`, `global`), optional team ID, file types,
   processing profile/provider, priority, enabled state, and fallback behavior.
2. Resolve in this order: authorized upload override → team rule → scope rule →
   file-type/all rule → system fallback.
3. Add an optional Upload control defaulting to `Auto — use routing rules`.
   Restrict manual provider/profile override by backend permission.
4. Pass routing context (`scope`, team, user, explicit profile) into the ingester
   rather than relying on the file stream alone.
5. Preserve Personal/Team/Global ACL construction exactly as it is today.
6. Add conflict validation and an admin “Explain route” test before activating a
   rule set.

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

1. OCR Routing Rules and upload Auto/Profile selector.
2. Persistent ingestion jobs and status UI for `Uploaded`, `Extracting`,
   `Chunking`, `Embedding`, `Indexed`, and `Failed`, including provider, timing,
   error, and Retry.
3. Page-aware Docling output so citations use real page numbers rather than one
   logical page.
4. Persist/index selected safe OCR metadata such as provider and confidence.
5. Chat image attachments: upload/preview/remove, file limits, Agent image
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

- **Admin authorization:** several newer management routes use the generic
  authenticated decorator and may rely partly on UI visibility. Before
  production, audit every LLM/MCP/OCR/mail/messaging/audit management route and
  enforce system/team-admin authorization server-side.
- **OCR routing:** currently one global default profile, extension-only, shared
  by Personal/Team/Global as described above.
- **Local mode:** LLM/provider work is ahead of search, storage, authentication,
  and deployment migration; this is not yet a fully local product.
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
450 passed, 1 deselected
```

Command:

```bash
.venv/bin/pytest -q -m 'not data_integration'
```

Latest focused OCR/config validation:

```text
43 passed
```

Frontend typecheck and production build passed. Use:

```bash
cd app/frontend
npx tsc --noEmit
NODE_OPTIONS=--max-old-space-size=4096 npm run build
```

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
- At least one Agent per OpenAI/Gemini/Ollama provider and a tool-capable model.
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
Read AGENTS.md and docs/CODEX_HANDOFF.md completely. Preserve the dirty working
tree and do not commit or discard unrelated changes. Inspect the existing OCR
provider/profile implementation, then propose a focused implementation plan for
OCR Routing Rules across Personal, Team, and Global uploads. Preserve existing
ACL behavior and Azure fallback. Add backend authorization, conflict resolution,
an Explain Route test, optional authorized upload override, focused tests, full
service-free regression, and frontend production validation. Do not begin a
different roadmap item until this slice is accepted.
```

