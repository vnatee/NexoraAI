# Product backlog

Items in this document are proposals only. Their architecture, scope, priority, and acceptance criteria must be discussed before implementation.

## Deferred — Playground next phases

The product owner moved the following items to an unscheduled backlog on
2026-11-22. Do not expand them until their scope and priority are discussed:

1. Automated Playground test cases and evaluation sets.
2. Side-by-side Active Agent versus private-revision comparison.
3. Playground attachments.
4. Approval-gated testing of write-capable tools.
5. Trace export and comparison across revisions.

## Deferred — Full external Customer Portal

The External Customer API/channel foundation remains implemented. The product
owner moved the complete customer-facing Portal scope below to an unscheduled
backlog on 2026-11-22:

1. Branded external-customer Chat experience.
2. Customer login and governed guest-access policy.
3. Explicit Internal versus External information separation in the Portal.
4. Rate limits, abuse controls, and customer-channel analytics.
5. Customer feedback and escalation to a human operator.
6. Read-only SAP Business One integration through the governed integration
   boundary.

Do not begin this Portal slice until product scope, identity model, data
publication policy, and acceptance criteria are discussed.

## Deferred — Datadog monitoring demo

The provider-neutral observability foundation remains implemented: OpenTelemetry,
JSON logs, detail-free health endpoints, and content-free Agent/Tool spans. The
product owner moved the live Datadog demo scope below to an unscheduled backlog
on 2026-11-22:

1. Install and configure a real Datadog Agent Compose overlay.
2. Export application logs, host/container metrics, and traces to Datadog.
3. Build Platform and LLM/Agent dashboards.
4. Configure monitors for HTTP 5xx, latency, LLM/tool failure, container
   restart, and CPU/memory/disk pressure.
5. Verify that prompts, responses, tool arguments/output, credentials,
   Knowledge, and attachments are absent from exported telemetry.
6. Validate a real Agent → LLM → RAG/Tool/MCP trace in Datadog.

Do not install Datadog or introduce vendor-specific runtime dependencies until
this backlog item is explicitly resumed.

## In progress — 2.3.0 production readiness gate

The current priority is to qualify the enterprise-authentication and Agent
Catalog checkpoint for deployment before starting another large feature slice.
A real isolated MongoDB/MinIO/Qdrant backup and destructive restore drill passed
on 2026-09-15, and the product owner accepted public HTTPS deployment testing on
2026-10-12. Live deployment/upgrade acceptance remains required. Real-IdP SAML
acceptance is deferred post-release; SAML stays disabled by default and Preview
until it passes. The product version stays at `2.2.0` until all required gates in
`docs/release-readiness-2.3.md` pass.

## In progress — governed private LLM and AI Gateway

Priority order agreed with the product owner:

1. **P1.1 Generic BYO AI Gateway foundation — implemented.** Deployment-wide
   Built-in, External, and gated Direct Development
   modes; OpenAI-compatible routing; encrypted API key/OAuth2/mTLS/custom-CA
   credentials; model aliases; System Admin UI; health test; metadata-only
   audit; and fail-closed prevention of direct-provider bypass. See
   `docs/byo-ai-gateway.md`.
2. **P1.2 Gateway conformance and MuleSoft profile — implemented and accepted
   against the real gateway.** MuleSoft template and Client ID Enforcement headers;
   safe HTTP/correlation diagnostics; and bounded Chat, streaming, Tool, and
   Vision conformance checks. **P1.2.1 Semantic Routing is implemented pending
   live acceptance:** the reorganized AI Runtime & Models administration area
   separates routing, built-in providers, enterprise gateways and private
   infrastructure. MuleSoft is configured as one Gateway with multiple Model
   Proxies (`Base URL + Proxy Path`); each proxy has Model-Based/Semantic
   strategy and its own Test/Conformance actions. Semantic tests use an
   operator-supplied, non-persisted topic-matching probe prompt, and Semantic
   Chat requests omit `model`. Preserve InsightSphere Agent, Knowledge, Tool,
   and Team governance.
3. **P1.3 Private model control plane — P1.3a implemented.** The supported
   InsightSphere Gateway + GPUStack + vLLM topology now has a pinned optional
   Compose control plane, private health visibility, worker/model lifecycle,
   sizing, controlled rollout/rollback, backup and production-acceptance
   runbooks. P1.3b remains: governed inventory/capacity visibility and tested
   multi-worker rollout/rollback automation.
4. **P1.4 Usage and policy reconciliation — foundation implemented.** The
   versioned USD Price Catalog, provider-token and Local AI TCO estimates,
   pricing coverage, Raw CSV, and PDF report are implemented without prompt or
   response content. Gateway/provider billing reconciliation, THB conversion,
   budgets, and policy decisions remain backlog work.
5. **P1 security gate.** Run dependency/secret/SAST/container/IaC scans and a
   focused penetration test after the gateway slices stabilize. Existing ACL,
   read-only database, tool-policy, guardrail, encrypted-secret and audit
   contracts remain release blockers.

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
- Add an explicit source-scope choice for overriding the current Auto classifier:
  **Attached files only** (the safe default), **Knowledge only**, or **Both**.
  Auto already recognizes explicit Thai/English comparison/RAG intent and
  otherwise remains attachment-only.
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
per-model Portal configuration and live image-input capability probes,
controlled capability errors, citation separation, and diagnostic redaction.
Managed Legacy models no longer require the Azure Knowledge Vision environment
feature merely to process a user attachment. Milestone 2 has started with a
provider-neutral async `AttachmentStore` contract and a private local/container
reference adapter covering owner/conversation ACLs, filename normalization,
atomic writes, integrity checks, TTL, and fail-closed cleanup. Chat/Ask now send
a stable conversation UUID independently from history, and an ACL/expiry-scoped
Mongo-compatible repository stores bounded metadata without exposing storage
keys or owner IDs. Private local/container and Azure Blob adapters now share the
same ACL, integrity and TTL contract; startup selects them through an opt-in
factory and coordinates object-first/Mongo-metadata expiry cleanup. No public
attachment URLs are produced. Authenticated private document upload/list/delete
APIs now validate PDF, Office Open XML, and UTF-8 text formats with bounded
size/page/archive controls, idempotent submission, a malware-scanner hook, and
object rollback when metadata creation fails. The current scanner is explicitly
unconfigured. Native bounded extraction and a
Mongo/local-compatible temporary AttachmentIndex
are now present with file/page provenance, TTL, exact owner/conversation scope,
background status transitions, local lexical ranking, and deletion-race cleanup.
Ready-only temporary retrieval is now integrated into Legacy and LangGraph
Chat/Ask. It rechecks owner/conversation scope, bounds source text, labels
extracted chunks as untrusted evidence, and returns sanitized file/page citation
names without storage paths. LangGraph can search selected temporary documents
even when enterprise Knowledge is disabled. The shared Chat/Ask composer now
selects supported documents locally, uploads them on Send with stable idempotency
IDs, displays extraction progress/errors/removal, and sends only ready IDs.
Chat Retry reuses the ready IDs. Image input and document attachments are now
independent per-Agent policies; the composer no longer owns a Vision toggle,
and the backend replaces client-supplied image policy, classifies validated
request attachments deterministically, selects Vision only when an image is
present, and rejects disabled document retrieval. Selected documents now use a
Thai/English prompt-intent scope (`uploaded_only`, `knowledge_only`, or `both`)
in both Legacy and LangGraph, with attachment-only as the safe fallback so
unrelated permanent RAG results are not merged into summaries. Temporary
citations now open through a private ready-only owner/conversation-scoped route,
not the permanent Knowledge content route. Scanned-document OCR fallback and
interrupted-extraction recovery are implemented. A real malware-scanner
adapter, LangGraph image input, and finer per-model OCR/vision routing remain
pending.

The first requirement-to-evidence slice is implemented in the shared Chat/Ask
composer. After attaching a requirements file, users can enable **Evidence
matrix** and select **Knowledge only** (the recommended default), **Attached
files only**, or **Attached files + Knowledge**. The request sends explicit,
validated fields rather than relying on prompt wording. The backend treats the
first attachment as the checklist, preserves owner/conversation checks and the
Knowledge ACL filter, prohibits the checklist from being treated as proof,
broadens Knowledge retrieval, and enforces a fixed Markdown matrix with
requirement, status, explanation, evidence quote, source file, page,
confidence, and gap columns. Legacy and LangGraph receive the same
backend-enforced workflow contract. This synchronous first slice reads at most
20 temporary chunks / 24,000 source characters; long-document batch
evaluation, server-validated row JSON, and CSV/Excel export remain future
phases.

## Approved roadmap — governed web knowledge

Phase 1 is implemented as **Approved Web Sources**: permission-enforced
Company/Team ingestion, Team Data Group validation, same-host/path bounded HTML
crawling, public-address and redirect checks, `robots.txt`, Standard/Extended
resource profiles, and administrator-selectable depth 0–2. The delivered
Scan & Verify workflow stages extracted evidence, exposes a review manifest,
keeps it out of RAG until explicit confirmation, verifies exact bytes by hash,
and automatically expires unconfirmed scans. Confirmed refreshes retain page
URL/time/hash evidence metadata. See `docs/approved-web-sources.md`.

Next delivery order:

1. **Phase 2.1 — governed live web search (implemented):** provider-neutral
   Brave Search and SearXNG adapters, encrypted Integration CRUD, connectivity
   testing, System-to-Team assignment, Team-owned Agent selection, per-Agent
   opt-in and allowed-domain policy, result/time limits, external-evidence
   citations, existing guardrail/tool-policy enforcement, and metadata-only
   audit. This slice returns
   search snippets only and never persists them into Knowledge. See
   `docs/governed-web-search.md`.
2. **Phase 2.2 — controlled page retrieval:** fetch explicitly selected search
   results through the existing SSRF, redirect, DNS/IP, content-type, byte, and
   timeout protections; add short-lived cache and provenance/freshness metadata.
3. **Phase 2.3 — reviewed promotion to Knowledge:** allow an authorized user to
   review selected external evidence and explicitly promote it to a permitted
   Personal, Team, or Global Knowledge scope.
4. **Phase 3 — authenticated sources:** extend the delivered public-page
   browser renderer with an isolated authenticated worker, encrypted connector
   credentials, host/redirect allowlists, egress policy,
   MFA/session-expiry behavior, bounded downloads, and complete audit.
   Evaluate Moli and comparable agent-oriented headless-browser providers at
   this phase; do not add one to the current public crawler. Any selected
   provider must remain behind a provider-neutral browser integration, default
   to read-only access, isolate sessions per Team or user, keep credentials out
   of model context, resist page-based prompt injection, and require an
   approval gate for form submission or other write actions. Playwright remains
   the current bounded renderer for public JavaScript pages.
5. Extend the implemented durable indexing jobs with manual/daily/weekly
   refresh policy, conditional requests, change summaries, and an external
   worker option for high-volume or multi-replica deployments. This may be
   delivered before or together with Phase 2 without changing Agent access semantics.


## In progress — AI guardrails

Add configurable safeguards around agent input, model output, retrieved content, and tool execution.

Initial discussion scope:

- Implemented first slice: Agent-level provider-independent policy, request
  size limits, high-confidence prompt-injection blocking, credential/secret
  input blocking, output redaction/blocking, literal blocked phrases,
  untrusted Knowledge/attachment/tool-output neutralization, metadata-only
  audit events, and server-enforced Agent-management authorization. See
  `docs/ai-guardrails.md`.
- Implemented second slice: deterministic PII/DLP redaction and policy actions,
  narrow high-confidence English/Thai content-safety controls, and optional
  System → Team → Agent policy inheritance where lower levels cannot weaken an
  enabled parent policy.
- Next guardrail slices: pluggable semantic multilingual classifiers,
  groundedness validation, human review, versioned evaluation datasets, wider
  jurisdiction-specific PII coverage, and production malware scanning.

Deferred after manual acceptance on 2026-09-02. Resume these advanced slices
later as separate, measured work; the current deterministic Guardrails scope is
complete for this checkpoint.

- Guardrail levels: system, team, agent, and individual tool.
- Input controls: prompt-injection detection, sensitive-data detection, topic/policy rules, and request-size limits.
- Output controls: sensitive-data redaction, groundedness/citation checks, unsafe-content handling, and structured-output validation.
- Tool controls: argument validation, allow/deny policies, risk classification, execution limits, and audit events.
- Provider strategy: provider-native guardrails versus a provider-independent local implementation.
- Policy outcomes: allow, block, redact, warn, retry, or route for human review.
- Evaluation: policy test sets, false-positive/false-negative targets, and bypass testing.

## Authentication federation — follow-up backlog

Generic OIDC now supports multiple confidential providers, authorization code
with PKCE, issuer/audience/signature/nonce validation, optional domain-restricted
JIT users, work-email domain routing, and opaque Nexora sessions. SAML 2.0 now
supports multiple managed IdPs, signed assertion validation, SP-initiated
request correlation/replay protection, domain-restricted JIT, reviewed identity
linking, and local session revocation. Follow-up work:

1. SCIM 2.0 user/group provisioning and deprovisioning with Team mapping.
2. SAML metadata import, planned signing-certificate rollover, SP-signed
   metadata/AuthnRequests, IdP single logout, and encrypted assertions where required.
3. Local TOTP and WebAuthn/passkeys, recovery codes, and step-up authentication
   for sensitive System Administration operations.
4. Optional LDAPS for disconnected installations, without storing directory
   passwords or weakening the internal authorization model.
5. IdP group-to-Team/role mapping, with System Admin assignment excluded from
   automatic mapping unless separately reviewed and explicitly enabled.
6. Login/security audit UI, global/user session revocation, IdP health testing, and
   metadata-only retention controls.

Delivered: administrator-reviewed OIDC/SAML identity linking/unlinking. A verified
email collision creates a seven-day pending request; approval is explicit,
unlinking revokes sessions, the only remaining sign-in identity cannot be
removed, and audit records contain metadata only.

## Agent Catalog — Phase 2 backlog

Phase 1 of the internal Agent Catalog is implemented. It provides versioned,
Team-safe template publication, Team/all/selected-Team visibility, metadata-only
browse responses, Team-local installation, and metadata-only lifecycle audit.
See `docs/agent-catalog.md`.

Prioritized follow-up work:

1. Controlled upgrade with version diff, explicit approval, rollback, and
   preservation of Team-local MCP/integration/Data Group bindings.
   Include editing/versioning of System-owned templates through the same review
   workflow; Phase 1 creates their initial immutable version.
2. Strong revocation policy for already installed copies, including active-run
   behavior, notification, grace periods, and emergency disable semantics.
3. Catalog approval workflow and separation of publisher/reviewer duties.
4. Catalog audit query/export UI and retention policy.
5. Dependency compatibility report before installation, with model/profile,
   integration type, Knowledge, and license checks.
6. Export/import of signed Agent packages for disconnected installations and
   verification of publisher identity/package integrity.
7. Usage/adoption analytics, favorites, recommendations, ratings, and reviews.
8. License entitlement gates and capacity ceilings for publishing/installing.
9. Public/vendor marketplace, commercial listings, billing, and support/SLA
   metadata. These remain out of scope until package trust and licensing are
   complete.

## Proposed — Agent Skills and secure Skill import

Add reusable Skills as a governed layer below Agents. A Skill contains bounded
instructions, references, templates, examples, and declared capability
requirements. It is not an identity, permission set, credential container, or
automatically active Agent. The first compatibility target is the portable
subset of Claude-style `SKILL.md` packages, normalized into a provider-neutral
InsightSphere Skill manifest.

### Required governance model

- Support System-owned and Team-owned Skills with Draft, In review, Published,
  Deprecated, and Retired lifecycle states, immutable published versions, and
  metadata-only lifecycle audit.
- Separate import/publish/review authorities. Importing a package must never
  grant a Team permission, create an integration, expose Knowledge, or activate
  an Agent.
- Record publisher/provenance, source type, package SHA-256, compatible schema,
  declared license, requested capabilities, dependencies, and version history.
  Add signature verification for signed packages without treating an unsigned
  package as trusted.
- Preserve Team isolation. Catalog browse responses expose safe metadata only;
  complete Skill instructions and files remain server-side and are available
  only to authorized reviewers and runtime assembly.
- Retirement prevents new bindings. Emergency revocation, installed-version
  notification, in-flight behavior, rollback, and retention require an
  explicit policy consistent with Agent Catalog governance.

### Import and review pipeline

1. Accept a bounded local package upload first; repository URL import follows
   only through an allowlisted, SSRF-protected fetcher. Reject absolute paths,
   traversal, symlinks, device files, archive bombs, unsupported encodings,
   excessive file counts/sizes, and duplicate ambiguous manifests.
2. Parse `SKILL.md` and declared references without executing scripts, loading
   remote resources, resolving credentials, or following instructions inside
   imported content.
3. Normalize the package into a versioned manifest and show a review preview:
   purpose, instructions, included files, requested tools/network/filesystem,
   required integrations/Knowledge, unsupported features, and compatibility
   warnings.
4. Pass imported files through the production malware-scanning boundary before
   they can enter review or publication. Keep packages quarantined until every
   validation succeeds.
5. Require an authorized reviewer to approve and publish the exact reviewed
   digest. Any content or manifest change creates a new Draft version and
   invalidates the previous approval.

### Agent usage

- Attach one or more published Skill versions to an existing Team Agent. Agent
  save and runtime independently revalidate Team ownership, publication state,
  compatibility, and license entitlement.
- Provide **Create Agent draft from Skill** as a convenience workflow only. It
  may suggest Role, Task, context, and output format, but a manager must still
  choose the model, Team, Knowledge scope, integrations, tool policy,
  Guardrails, and attachment policy before activation.
- Assemble Skill instructions below the platform security contract and Agent
  policy. A Skill cannot replace system instructions, reduce inherited
  Guardrails, expand an API key/Data Group scope, or register an undeclared
  tool.
- Resolve multiple Skills deterministically, report conflicts before save, pin
  the selected versions, and require explicit review for upgrades. Do not
  silently mutate installed Agents when a Skill is republished.
- Expose safe dependency and compatibility status in Agent Management and the
  Catalog without exposing Skill source, credentials, prompts, or tool output.

### Executable content boundary

Phase 1 is instruction/reference/template-only. Imported scripts are retained
as disabled review artifacts and are never executed during import, preview,
publication, installation, or ordinary prompt assembly.

Executable Skills are a later phase and require a separate isolated runner:
ephemeral filesystem, non-root identity, read-only package mount, no host or
Docker socket, deny-by-default network, allowlisted tools, bounded CPU/memory/
time/output, explicit secret handles rather than secret values in model
context, argument/result validation, approval for write actions, and
metadata-only audit. Failure must not fall back to unrestricted local
execution.

### Delivery order

1. Canonical Skill manifest, Claude-compatible `SKILL.md` parser, bounded
   upload, quarantine, static validation, and dependency preview.
2. Internal Skill Catalog, versioning, approval/publish/retire workflow, Team
   ownership, RBAC, provenance, digest/signature status, and audit.
3. Published Skill binding to Agents plus **Create Agent draft from Skill**,
   deterministic composition, conflict detection, version pinning, upgrade
   diff, rollback, and runtime revalidation.
4. Signed export/import for disconnected installations and controlled
   allowlisted repository import.
5. Optional sandboxed executable Skills after threat modeling and production
   malware-scanner acceptance; external Skill marketplace discovery remains a
   separate later decision.

Security acceptance must cover malicious `SKILL.md` prompt injection,
cross-Team package/binding attempts, hidden files and archive attacks,
dependency substitution, signature/digest mismatch, retired versions,
credential references, unauthorized tool/network requests, Guardrail
weakening, runtime package tampering, and audit records containing no imported
secrets, raw user prompts, or tool results.

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

## Approved direction — Subscription licensing and entitlements

Add commercial licensing after usage metering and quota behavior are stable.
Licensing must answer what a deployment is entitled to use; quota policy must
continue to answer how much an entitled System, Team, or User may consume.
They are separate layers and a license must never silently rewrite customer
quota configuration.

Planned commercial capabilities:

- Time-bound subscriptions such as one year, with `not_before`, `expires_at`,
  renewal, configurable grace period, and explicit active/grace/expired/
  revoked/invalid states.
- Edition and feature entitlements for limits such as users, Teams, Agents,
  managed providers/models, OCR engines, LangGraph, MCP/tools, dashboards,
  API access, HA replicas, and local/cloud deployment modes.
- Signed license key or license document import for offline/on-premises
  deployments, plus optional online activation and revocation for connected
  deployments. Use asymmetric signatures: the product contains only the
  verification public key; the private signing key remains in the vendor
  licensing service.
- Stable claims including license/customer/product identifiers, edition,
  validity, feature flags, capacity ceilings, deployment binding policy, issuer,
  schema version, and key ID for signing-key rotation.
- A backend-authoritative entitlement service consumed consistently by routes,
  workers, and the Portal. Hiding a disabled feature in the UI is not an
  authorization boundary.
- A System Administration license page showing edition, status, expiry,
  entitled features/capacities, deployment identity, last validation, and safe
  renewal/import actions. Never log or expose the raw license key.

Important design and operational requirements:

- Expiry should enter a documented grace/read-only mode and must not delete or
  corrupt customer data. Define which security, backup/export, and
  administration functions remain available after expiry.
- License ceilings and usage quotas both apply. For example, a license may
  allow 100 users while Team token quotas independently control consumption.
- Subscription editions may provide Team default per-member allowances, but
  contractual enforcement must preserve independent Team totals and
  `(team_id, user_id)` overrides. A member override replaces the Team default;
  it does not create capacity beyond the licensed System or Team ceiling.
- Do not treat the current asynchronous usage collection as a billing ledger.
  Contractual consumption needs durable idempotent usage events, reservations
  or reconciliation, immutable period boundaries, and explicit handling of
  provider usage corrections and telemetry-write failures.
- New providers/models inherit the Overall operational quota, but their use may
  also require a provider/model/feature entitlement from the license.
- Support HA without consuming a license per restart. If deployment binding is
  used, bind to a stable installation ID rather than ephemeral container or
  host identifiers, and provide a controlled re-host procedure.
- Define clock rollback/tamper handling, signing-key rotation, offline
  revocation limits, backup/restore behavior, audit metadata, and a recovery
  path when a valid license cannot be read.
- Usage reporting or online activation must disclose exactly what telemetry
  leaves the deployment. Offline installations must not require hidden
  phone-home behavior.
- Do not store licensing private keys, customer credentials, raw prompts, or
  tool output in this repository or application audit records.

Recommended delivery order:

1. Finish the durable metering foundation with provider reconciliation,
   per-model-call/sub-agent and embedding attribution, document-page
   reservations, and immutable billing-period rollups. Request-level LLM
   reservations, idempotent LLM/document events, and threshold/block audit
   events are implemented and validated on `feature/durable-usage-metering`.
2. Versioned entitlement schema and in-process evaluator with deterministic
   tests; no enforcement yet. **Implemented** in `core/licensing.py`; see
   `docs/licensing.md`.
3. Signed offline license verification, stable installation identity, secure
   persistence, and System Admin status/import UI. **Implemented in audit
   mode**, including one-time 14-day Trial activation and a vendor-side issuer
   tool; see `docs/licensing.md`.
4. Feature gates and capacity ceilings enforced server-side, starting in audit
   mode before blocking production operations.
5. Grace/expiry/renewal/re-host workflows and audit events.
6. Optional activation/revocation service, customer portal integration, and
   subscription SKU catalog.

## Discussion order

Recommended order when these items are scheduled:

1. Define the usage-event and audit-event schemas shared by all three features.
2. Design AI guardrails and tool-execution policies before exposing agents externally.
3. **Implemented (Phase 1):** synchronous Team-scoped Agent Invocation API with
   expiring, restricted API keys; per-key rate limits; existing Agent
   guardrails/tool policy/usage quotas; metadata-only audit; and Portal
   create/list/rotate/revoke workflows. See `docs/agent-invocation-api.md`.
4. Build dashboard aggregation and reporting from the collected events.
5. **Implemented (Phase 2 core):** lifecycle SSE, encrypted durable asynchronous
   jobs, polling, retry/lease recovery, TTL retention, and `Idempotency-Key`
   deduplication.
6. **Implemented (Phase 3A):** published OpenAPI 3.0 contract, developer guide,
   curl/Python/TypeScript/C# examples, Postman collection, and contract tests.
   Next: generated client SDK packages, webhooks, cancellation, true token-delta
   streaming, and optional enterprise gateway integration.
7. **Implemented (External Channel foundation):** Internal Service and External
   Customer key profiles, explicitly published Team-wide External Knowledge,
   draft/published/retired lifecycle with version/audit metadata, fail-closed
   runtime tool isolation, immediate retirement enforcement, and Portal
   governance controls.

External Channel follow-up slices:

1. **Implemented:** dedicated **Manage external channels** permission with
   idempotent startup migration. Add a configurable multi-person approval
   workflow when customer governance requires maker-checker separation.
2. Add document-level review status, audience/product metadata, effective and
   expiry dates, and a safe public citation projection.
3. Add daily/concurrent/session/end-user limits, abuse controls, and customer-
   channel analytics without storing raw prompts or responses.
4. Add SAP Business One read-only integration behind the existing integration,
