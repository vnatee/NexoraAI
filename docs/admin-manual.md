# NexoraAI Administrator Manual

**Language:** English  
**Audience:** System Administrators, Team Administrators, security administrators, and platform operators  
**Last verified:** 2026-09-27
**Applies to:** The current NexoraAI web application on the local/container or Azure runtime

This is the stable Administrator Manual for NexoraAI. Update this file in place
when an administrative feature, field, workflow, permission, or menu changes.
Do not create a dated replacement manual unless a separately maintained release
manual is explicitly requested.

The formatted Word deliverable is `NexoraAI-Administrator-Manual.docx`.
Regenerate both Word manuals after updating their Markdown sources with:
` .venv/bin/python scripts/build_manual_docx.py `.

## 1. Administrative model

NexoraAI separates two management contexts:

| Context | Scope | Typical administrators |
| --- | --- | --- |
| **Team workspace** | Members, roles, data, Agents, integrations, and policies for one Team | Team Administrator, delegated manager, System Administrator |
| **System administration** | Organization-wide users, Teams, providers, governance, health, licensing, and authentication | System Administrator |

The settings header identifies the active context as **TEAM WORKSPACE** or
**SYSTEM ADMINISTRATION**. Always verify this header before editing. A Team
setting must not be assumed to affect the entire System, and a System default
may be narrowed by a Team or Agent policy where the security contract allows it.

Menus are permission-aware. A missing menu normally means the current account
does not have its required permission.

## 2. Recommended initial setup order

1. Configure **Sign-in & authentication**.
2. Create or verify System users and System permissions.
3. Configure **LLM providers** and test every model capability.
4. Create Teams and assign Team members.
5. Define Team roles and permissions.
6. Create Data Groups and their access mode.
7. Add Team integrations and test each connection.
8. Create Agents, select their model/runtime, and assign integrations.
9. Configure Guardrails, Usage quotas, and Chat history retention.
10. Verify **System health**, backup, TLS, and the License status.

Use a non-production Team for initial provider, tool, and prompt validation.

## 3. Open Administration

Open the account menu and select **Administration**. The System view opens with
collapsed menu groups. Select a group to expand it.

### System Administration menu map

| Group | Menu | Purpose |
| --- | --- | --- |
| **Organization** | Teams | Create Teams and open their Team workspace |
|  | Users | Review and manage registered users |
|  | Identity links | Approve, reject, and unlink federated OIDC/SAML identities |
|  | User permissions | Assign System Admin and direct System/Team permissions |
| **Governance** | Agent audit | Review metadata-only Agent/tool activity |
|  | Guardrail policy | Set the System guardrail baseline |
|  | Usage quotas | Set System and global user ceilings |
|  | System chat history | Set maximum conversation retention |
| **System administration** | System health | Run an on-demand operational snapshot |
|  | LLM providers | Manage model-provider connections and model profiles |
|  | Integration catalog | Manage unassigned connections before Team assignment |
|  | License | Start Trial or activate an offline license |
|  | Sign-in & authentication | Configure Microsoft Entra ID and view local-auth source |

### Team workspace menu map

| Group | Menu | Purpose |
| --- | --- | --- |
| **Team · _name_** | Members | Approve, add, view, activate, or remove Team members |
|  | Roles & permissions | Create role presets and assign Team permissions |
|  | Data access | Create Data Groups and select the authorized audience |
| **AI workspace** | Agents | Configure Team Agents and their tool assignments |
|  | Team integrations | Add and manage Team-owned connections |
| **Governance** | Guardrail policy | Configure a Team policy without weakening its parent |
|  | Usage quotas | Configure Team totals and per-member limits |
|  | Team chat history | Shorten Team retention within the System maximum |

## 4. Organization

### 4.1 Teams

Use **Organization → Teams** to search, create, open, rename, or delete a Team.

| Field | Required | Description | Example |
| --- | --- | --- | --- |
| Team name | Yes | Human-readable unique Team name | `Presale` |

Select a Team's manage/view action to enter its Team workspace. Renaming a Team
does not change its internal ID. Before deleting a Team, review its users, Data
Groups, Agents, integrations, and retained records.

### 4.2 Users

**Organization → Users** displays registered local and/or Entra identities.
Common user data includes:

| Field | Description | Example |
| --- | --- | --- |
| First name / Last name | Display name | `Alex Morgan` |
| Email | Primary sign-in/contact address | `alex@example.com` |
| AD email | Microsoft Entra identity when applicable | `alex@example.onmicrosoft.com` |
| Employee ID | Organization identifier | `EMP-1042` |
| Telephone | Optional contact number | `+66 2 000 0000` |
| Active | Whether the user may use the application | Enabled |

For a managed local user, create/reset credentials through the provided local
account actions. Never send a permanent password over an unprotected channel.
For Entra users, password and MFA lifecycle remain in Microsoft Entra ID.

### 4.3 User permissions

Select a user, then configure:

- **System Admin** — grants complete System Administration authority;
- **System Permissions** — direct organization-wide permissions; and
- **Team** plus **Team Permissions** — direct authority within a selected Team.

Prefer role-based Team permissions for routine administration. Grant System
Admin only to operators who must control authentication, providers, licensing,
and organization-wide policy.

## 4.4 Approved Web Sources

Use **Approved Web Sources** to add a bounded public website snapshot to
Company or Team Knowledge. Company scope requires **Manage global uploads**;
Team scope requires **Manage team uploads** and at least one Data Group owned by
the active Team. Enter a public root URL without credentials, query parameters,
or a custom port. Select crawl depth **0** for the root only, **1** for the
recommended root-plus-direct-links scope, or **2** for one additional link
level. Keep **Auto** fetch mode for normal use: it starts with standard HTTP and
automatically renders a page in an isolated browser when it detects a JavaScript
application shell. Use **Standard HTTP** to prohibit JavaScript, or
**Browser-rendered** when every page must be rendered. Select **Standard** limits
for routine documentation or **Extended** only
after reviewing the website scope.

Select **Scan & Verify** first. The result is staged temporarily and is not yet
available to Agents or RAG. Review the URLs, page count, extracted size,
skipped-page issues, and any **Partial snapshot** warning. Select **Confirm
Index** to queue only the checked pages; all pages are checked initially and
**Select all pages** can clear or restore the full set. The confirmation request
returns immediately and indexing continues in the background, so the page can
be closed safely. Use **Recent indexing jobs** to see status, attempt number,
and page progress such as `53/100`. A failed job lists the error for each
affected URL. Select **Retry failed pages** to resume only unsuccessful pages;
successfully indexed pages are not repeated. Select **Discard Scan** before
confirmation to delete the staged scan. SHA-256 remains an internal integrity
check and is hidden from the normal UI. Unconfirmed scans expire automatically
after 24 hours by default. Repeating and confirming the same URL refreshes its
indexed snapshot; stale pages are removed only after replacement pages index
successfully.

The crawler stays on the approved hostname/path, follows only the selected
depth, honors `robots.txt`, and records source URL, retrieval time, and content
hash. Browser mode does not sign in, reuse user cookies, solve CAPTCHAs, or
bypass access controls. Approved Web Sources does not perform live web search.
See [Approved Web Sources](approved-web-sources.md) for limits and security
controls.

## 5. Team workspace

### 5.1 Members

Use **Members** to search current and waiting users, inspect account details,
approve membership, activate/deactivate access, or remove membership.

Removing Team membership must remove access to that Team's Agents, Data Groups,
and integrations. It does not necessarily delete the global user identity.

### 5.2 Roles & permissions

The page contains **Role Preset** and **User Permission** views.

| Field | Description | Example |
| --- | --- | --- |
| Role Name | Reusable Team role | `Knowledge Curator` |
| System Permissions | Organization-level permissions; use sparingly | None for a Team-only role |
| Team Permissions | Actions allowed inside the Team | `Manage team data groups` |
| User | Member receiving the preset or custom permissions | `alex@example.com` |
| Role preset | Reusable role selection; Custom allows direct choices | `Knowledge Curator` |

Security-sensitive examples:

- A content curator may manage Team Data Groups but should not manage LLM
  provider secrets.
- An Agent owner may manage Agents and integrations without becoming System
  Admin.
- Dashboard permissions should match the allowed personal, Team, or System
  reporting scope.

### 5.3 Data access

Data Groups are retrieval authorization boundaries.

| Field | Required | Description | Example |
| --- | --- | --- | --- |
| Data Group Name | Yes | Human-readable Knowledge group | `Presale Knowledge` |
| Access mode | Yes | **Entire team** or **Selected users only** | `Selected users only` |
| Selected users | Conditional | Users allowed when selected-user mode is used | `alex@example.com` |

Changing Data Group access affects future retrieval authorization. Do not move a
sensitive document into a broader group merely to make search easier.

For customer-facing channels, a Team data curator may mark an **Entire team**
Data Group as an **External draft**. A System Administrator must review and
publish it before an External Customer API key can retrieve it. Publishing
increments its version and records who published it and when. **Retire** removes
it from External Customer keys immediately; it does not delete the underlying
internal Knowledge. Selected-user Data Groups cannot be published externally.

Treat publication as a security approval: confirm that every document is safe
for the intended customer audience and contains no internal-only pricing,
credentials, personal data, or operational instructions.

## 6. Agents

Use **AI workspace → Agents** to search, create, edit, activate, and delete Team
Agents. Save a new Agent before assigning integrations.

### 6.1 Agent Info fields

| Field | Description | Example / guidance |
| --- | --- | --- |
| Agent Name | User-facing name | `Azure Engineer` |
| LLM Profile | Managed provider/model or System default | `Azure Production · GPT-4.1` |
| Agent Runtime | `Legacy` or `LangGraph (Tools / MCP)` | Use LangGraph for tool execution |
| Enable image input | Allows images when the model supports vision | Enabled for architecture review |
| Enable document attachments | Allows temporary document retrieval | Enabled for policy analysis |
| Temperature | Response variability | `0.1` for factual inventory work |
| Seed | Optional deterministic sampling hint | `42` |
| Min Search Score | Minimum Knowledge result score | Validate with representative data |
| Max Search Results | Maximum Knowledge items supplied | `5` |
| Max Tokens | Maximum answer tokens | `4096` |

### 6.2 Prompt fields

| Field | Purpose | Example |
| --- | --- | --- |
| Role | Defines professional identity | `You are an Azure infrastructure reviewer.` |
| Task | Defines primary responsibilities | `Inventory Azure resources and explain architecture risks.` |
| Detail Context | Adds environment and decision context | `Prefer read-only operations and distinguish observed from inferred relationships.` |
| Output Format | Defines response structure | `Return summary, findings table, risks, and recommended actions.` |
| Constraints | Defines mandatory boundaries | `Never provision, delete, or modify resources without explicit approval.` |

Do not place credentials, tokens, copied customer data, or mutable connection
details in Agent prompts. Use the encrypted provider/integration configuration.

### 6.3 Knowledge Search and delegation

**Knowledge Search (RAG)** modes:

- **Auto — model decides**;
- **Always search — Legacy-like**; or
- **Disabled** — the Knowledge tool schema is not sent.

When sub-agents are enabled, select only approved Agents in the same Team and
set **Maximum Delegation Depth** conservatively. Tool-call and delegation limits
protect against loops and unexpected cost.

### 6.4 Agent guardrails and tool policy

Agent-level controls include maximum input characters, prompt injection,
secrets in input/output, PII input/output, unsafe content, blocked phrases,
blocked tool names, and blocked tool-source prefixes.

Typical actions are **Block**, **Redact**, **Audit only**, and **Allow**. An
Agent policy cannot weaken an enforced parent System or Team policy.

### 6.4.1 Governed Live Web Search

For current public information that may not yet exist in Knowledge, a
LangGraph Agent can use the optional read-only **Governed Web Search** tool.
First open **Integrations → Web Search**, add Brave Search or SearXNG, save it,
run **Test**, and assign a System-scoped connection to the target Team. Then in
**Built-in Tools → External Web Search**, enable the tool, select the Team
connection, and enter one or more allowed domains such as
`docs.datadoghq.com`. Brave API keys are encrypted and never returned by the
API.

The domain list is mandatory and is enforced again after search results are
returned. Set **Maximum Results** from 1–10 and **Search Timeout** from 1–30
seconds. External snippets are untrusted evidence; the Agent must cite each URL
and search date and distinguish the result from enterprise Knowledge. Search
results are not automatically indexed.

See [Governed Live Web Search](governed-web-search.md) for connection management,
security behavior, limitations, and examples.


### 6.5 Integrations tab

Assignments are grouped into REST APIs, Databases, Web Search, Mail, Documents,
Messaging, MCP, and Visualization. Only assign capabilities required by the Agent.

For a new Agent, enter **Agent Name** and select **Integrations**. NexoraAI
automatically creates a private draft so integration bindings have a stable
Agent ID. The draft appears only in **Agent Management** with a **Draft** badge;
it cannot be selected in Chat, delegated to, or published to Agent Catalog.
Select **Finish setup** to save the latest Agent fields and activate it, or
**Cancel setup** to immediately remove the draft and all of its bindings.
Abandoned drafts expire after 24 hours by default and are removed by the
background cleanup worker. Operators may set `AGENT_DRAFT_RETENTION_HOURS`
(1–168) and `AGENT_DRAFT_CLEANUP_INTERVAL_SECONDS` (minimum 60).

For MCP Agents configure:

| Field | Description | Recommended value |
| --- | --- | --- |
| Invocation Mode | Auto calls when relevant; Required calls an assigned MCP first | `Auto` for general Agents; `Required` for dedicated inventory Agents |
| Agent MCP Timeout | Agent-level maximum execution time | Lower than the overall request timeout |

### 6.6 Agent API access

Use **Team governance → Agent API access** to allow a server-side application
to invoke selected Team Agents. The administrator must have **Manage agents**.

Choose the key type deliberately:

- **Internal Service** is for trusted internal applications. It can use selected
  Team-wide Data Groups and, when explicitly enabled, Global Knowledge. Agent
  integrations remain governed by the Agent's normal tool policy.
- **External Customer** is for a customer-facing website or BFF. Only a System
  Administrator can create this key type. It can retrieve only explicitly
  published External Knowledge and cannot use Global Knowledge, Web Search,
  databases, REST, mail, business documents, messaging, MCP, sub-agents, or
  chart tools.

Never place an Agent key in browser JavaScript. The customer website must call
its own server/BFF, which retrieves the key from a secret store and calls
NexoraAI over HTTPS.

When creating a key, enter a clear application/environment name, select one or
more active LangGraph Agents, choose only the Team-wide Data Groups that the
application needs, optionally allow Global Knowledge, then set expiry and the
per-minute request limit. The default expiry is 90 days.

The generated secret is displayed once. Copy it directly to the application's
secret store. The Portal later shows only its non-secret prefix, status, expiry,
scope and last-used time. Use **Rotate** to issue a replacement and immediately
revoke the old key, or **Revoke** to stop access.

Personal Knowledge and selected-user Data Groups are intentionally unavailable
to service keys. Invocations retain the Agent's guardrails, tool policy,
licensing and Team usage quota. See
[Agent Invocation API](agent-invocation-api.md) for the request format and
operational guidance.

Application developers should start with the
[Agent API Developer Guide](agent-api-developer-guide.md), which includes curl,
Python, TypeScript, C#, Postman, and acceptance-test examples.
The same page provides a **Developer Guide** button with a safe quick start,
copyable Sync/Background examples, and the deployment's OpenAPI link.

## 7. Unified integrations

**Team integrations** and **Integration catalog** present Native and MCP
connections in one experience. Use:

- **Configured connections** to search/filter existing connections; and
- **Browse catalog** to add a supported connection.

The connection type filter supports **All**, **MCP**, and **Native**. A System
Admin may create an unassigned connection and then assign it to exactly one
Team. Connections, credentials, and Agent assignments remain Team-scoped.

### 7.1 MCP common fields

| Field | Description | Example |
| --- | --- | --- |
| Server Name | Friendly connection name; multiple tenants may use separate names | `Datadog Production EU` |
| Category | Catalog grouping | `Observability` |
| Streamable HTTP URL | Reachable MCP endpoint from the app container | `https://mcp.example.com/mcp` |
| Allowed Tools | Comma-separated allowlist; blank allows discovered tools | `subscription_list,group_list` |
| Operation Mode | Read only or Read / Write | Start with `Read only` |
| Headers JSON | Additional encrypted HTTP headers | `{"X-Tenant":"team-a"}` |
| Timeout | Per-server request timeout in seconds | `30` |
| Enabled | Makes the connection eligible for Agent assignment | Enabled after Test succeeds |

Use **Test** and inspect discovered tools before assigning the connection.

### 7.2 Datadog MCP

| Field | Description | Example |
| --- | --- | --- |
| Datadog Site | Tenant region/site | `EU (datadoghq.eu)` |
| Datadog Toolsets | Comma-separated server toolsets | `core,synthetics` |
| Authentication | PAT/SAT or API Key + Application Key | PAT/SAT recommended |
| PAT / SAT | Datadog personal/service access token | Secret; never document the value |
| API Key / Application Key | Alternative Datadog credentials | Secret |

Create a separate connection for each Datadog tenant and assign it only to the
appropriate Team.

### 7.3 Azure MCP

For **Managed on-prem container**:

| Field | Source | Example |
| --- | --- | --- |
| Azure Tenant ID | Entra ID → Overview → Tenant ID | UUID |
| Azure Client ID | App registration → Application (client) ID | UUID |
| Azure Client Secret | App registration secret **Value**, not Secret ID | Secret |
| Subscription IDs | Subscriptions accessible to this Team, comma-separated | `sub-id-1,sub-id-2` |

Grant the Service Principal the minimum required Azure RBAC role. Use **Reader**
at the required subscription/resource-group scope for inventory-only workflows.

For an **Existing remote Azure MCP server (advanced)**, additional fields can
include Nexora OAuth Client ID, Nexora OAuth Client Secret, and OAuth Scope such
as `api://<remote-mcp-app-id>/.default`.

See [Azure inventory to Draw.io](azure-drawio-mcp.md).

### 7.4 Draw.io MCP

Use the official hosted Streamable HTTP endpoint when approved by the
organization. Test tool discovery before assigning it. A diagram Agent should
distinguish real resource relationships from inferred connections and return a
downloadable `.drawio` artifact.

### 7.5 Native business integrations

Supported connection families include REST APIs, read-only Databases, Mail,
Business Documents, and Messaging.

- REST: name, base URL, authentication, endpoints, request/response fields.
- Database: provider/driver, host, port, database, encrypted credentials, and a
  read-only query profile.
- Mail: provider, mailbox, OAuth or IMAP/POP3/SMTP settings, and read/send Agent
  permissions.
- Documents: Microsoft 365 or Google Workspace identity and approved document
  scopes.
- Messaging: LINE, Slack, or Discord target plus encrypted token/webhook.

Provider-specific instructions:

- [Database integrations](database-integrations.md)
- [Mail integrations](mail-integrations.md)
- [Business document integrations](business-document-integrations.md)
- [Messaging integrations](messaging-integrations.md)
- [Jira, Confluence, and ServiceNow MCP](jira-servicenow-mcp.md)

## 8. Governance

### 8.1 Guardrail policy

| Field | Description |
| --- | --- |
| Policy enabled | Activates the policy at the selected level |
| Maximum Input Characters | Rejects oversized input before model execution |
| Prompt Injection | Block, Audit only, or Allow |
| Secrets in Input | Block, Audit only, or Allow |
| Secrets in Output | Redact, Block response, Audit only, or Allow |
| PII in Input/Output | Applies the configured PII action |
| Unsafe Content in Input/Output | Applies deterministic content controls |
| Blocked Phrases | Optional comma-separated literal phrases; case-insensitive |

Start with Audit only only when measuring false positives in a controlled
environment. Do not allow a lower-level policy to weaken mandatory controls.

### 8.2 Usage quotas

Choose **Configure level**:

- Entire system;
- Current Team;
- Global user ceiling; or
- Specific member override.

Core fields include policy enabled, monthly LLM tokens, monthly tokens per user,
monthly document pages, and LLM requests per minute. Optional provider/profile
rules select **Limit by**, Provider or Model profile, Workload (`All requests`,
`Chat`, or `Ask`), and Monthly tokens.

Example Team policy:

| Field | Value |
| --- | ---: |
| Monthly LLM tokens | 10,000,000 |
| Monthly tokens per user | 500,000 |
| Monthly document pages | 20,000 |
| LLM requests per minute | 30 |

A member override replaces the Team per-member default; it does not add more
capacity than the Team or System ceiling.

### 8.3 Chat history retention

Choose **Retention period**. Supported policies include 30, 90, 180, or 365
days, with No expiry available only where the System policy permits it.

- Default recommendation: 90 days from last conversation activity.
- A Team may select a shorter period than the System maximum, not a longer one.
- User Delete removes the conversation immediately.
- Scheduled cleanup also removes messages, citations, diagram artifacts, and
  attachment objects; audit records contain deletion metadata, not content.

### 8.4 Agent audit

Use Agent audit to investigate controlled metadata such as actor, Agent, tool,
action, status, and timestamp. It must not contain raw prompts, tool output, or
credentials. Treat audit access as privileged.

## 9. LLM providers

Use **System administration → LLM providers → Add Provider**.

| Field | Description | Example |
| --- | --- | --- |
| Provider Name | Friendly administrative name | `Azure OpenAI Production` |
| Provider Type | Azure OpenAI, OpenAI, Gemini, Claude, Ollama, Groq, OpenRouter, Mistral, DeepSeek, Together, vLLM, LocalAI, or compatible | `Azure OpenAI` |
| Azure Endpoint | Azure OpenAI resource endpoint | `https://example.openai.azure.com/` |
| Base URL | OpenAI-compatible API root | `http://ollama:11434/v1` |
| API Version | Azure OpenAI API version | `2024-10-21` |
| API Key | Encrypted provider credential; blank may use supported identity/local mode | Secret |
| Model ID | Stable profile identifier | `gpt41` |
| Display Label | Name shown to administrators/users | `GPT-4.1` |
| Model Name | Provider model identifier | `gpt-4.1` |
| Azure Deployment | Azure deployment name | `gpt41-prod` |
| Tools / Vision | Model capability declarations verified by Test | Enable only when supported |

Select **Test** for every configured model. Connection success alone does not
prove tool calling or vision support. Containerized local providers must use a
container-reachable host such as `ollama:11434` or `host.docker.internal`, not
container-local `localhost` unless the model server runs in that same container.

See [Runtime and model provider configuration](model_provider_configuration.md).

## 10. System health

System Health is on-demand and does not continuously poll. Select **Refresh** to
collect a new snapshot.

It reports:

- CPU, memory, disk, process RSS, core/load information;
- application, MongoDB, MinIO/Azure Storage, Qdrant/Azure Search, model runtime,
  and Integration Controller status;
- Live web search provider readiness when Brave Search or SearXNG is configured
  (connectivity is verified when an Agent performs a search);
- **HTTPS gateway · Nginx** when the TLS overlay is enabled;
- integration totals and attention states; and
- ingestion/attachment queues, failures, recovery, and cleanup workers.

`Unavailable` for a required service degrades the overall status. Azure remote
clients may show configured/initialized without performing a costly remote call.
System Health cannot alert when the whole application is down; use external
monitoring in production. Certificate-expiry monitoring remains pending.

## 11. License

The License page shows the Installation ID and current state.

### Trial

Select **Start 14-day trial** and confirm. Trial activation is one-time per
persisted installation and cannot be restarted through the Portal.

### Offline license

Paste the complete `NX1.<payload>.<signature>` value into **License key**, then
select **Verify and activate**. The raw key is encrypted at rest and never
returned to the browser. The page displays only safe claims such as edition,
customer, dates, features, and capacities.

License operation currently runs in audit mode: entitlements are visible but do
not yet block features. Key generation and activation are documented in
[Product licensing and entitlements](licensing.md).

## 12. Sign-in & authentication

Local authentication is controlled by deployment setting `LOCAL_AUTH_ENABLED`.
The Portal manages Microsoft Entra and multiple standards-based OpenID Connect
(OIDC) and SAML 2.0 connections. Configure Entra with:

| Field | Source | Example |
| --- | --- | --- |
| Enable Microsoft Entra ID | Enables Entra sign-in after valid configuration | On |
| Tenant ID | Entra tenant Overview | UUID |
| API application (server) ID | Backend/API app registration | UUID |
| SPA application (client) ID | Frontend SPA app registration | UUID |
| API client secret | Secret **Value** for the API application | Secret |

Saved managed values override environment defaults and secrets are encrypted.
Use **Use environment settings** to remove the managed override. Reload the page
before testing a changed Entra configuration. Configure the SPA redirect URI to
the actual HTTPS origin used by users.

For OIDC, select **Add OIDC connection** and provide a connection name, exact
HTTPS issuer URL, client ID, client secret, token-endpoint authentication
method, allowed email domains, and optional JIT provisioning. Copy the displayed
callback URI into the provider application. Select **Test discovery** before
enabling the connection. Each enabled connection must own a distinct set of
email domains. Disabling or deleting one revokes its active OIDC sessions.

For SAML, select **Add SAML connection**. Enter the IdP Entity ID, HTTPS SSO URL,
X.509 signing certificate, attribute names, allowed domains, and JIT policy.
Copy the generated **ACS / Reply URL** and **SP Entity ID / Audience** into the
IdP application. Create the connection disabled, select **Validate
configuration**, complete the IdP setup, then enable it. A public deployment
must set `NEXORA_PUBLIC_URL` before these URLs are copied. NexoraAI requires a
signed assertion and SP-initiated request correlation; private IdP or SP keys
must never be pasted into the certificate field.

Use **Organization → Identity links** to review verified OIDC or SAML users whose email
already belongs to an internal account. Confirm the identity outside NexoraAI,
select the intended user, then choose **Approve link** or **Reject**. The linked
identity list supports **Unlink**, but the system blocks removal of a user's
only sign-in method. Approval, rejection, and unlink operations are audited
without retaining tokens or raw provider claims.

See [Local and Microsoft Entra authentication](local-authentication.md).

## 13. Knowledge ingestion

Administrators with upload permission can manage Global or Team documents and
web ingestion. Select the correct Data Group and processing profile. **Auto —
use routing rules** is the recommended processing default unless a specific OCR
profile is required.

Monitor persistent job states and failures. Deleting metadata without deleting
the corresponding object or vector records is not an acceptable cleanup path;
use the supported application actions.

See [Document Processing and OCR](document-processing.md) and [Persistent
ingestion jobs](ingestion-jobs.md).

## 14. Production operations

### TLS

The optional Nginx overlay terminates TLS, redirects HTTP to HTTPS, and keeps
stateful services private. Supply `fullchain.pem` and `privkey.pem` outside the
repository. See [Production TLS](production-tls.md).

### Backup and restore

Back up MongoDB plus object/vector data required by the selected providers.
Preserve `APP_DATA_ENCRYPTION_KEY`; changing it makes encrypted application
secrets and stored licenses unreadable. See [Local backup and restore](local-backup-restore.md).

### Secrets

- Do not commit `.env` files, private signing keys, certificates' private keys,
  service-account JSON, access tokens, or connection strings.
- Leave a secret field blank during Edit when the UI says blank keeps the
  stored value.
- Rotate credentials through their provider and update the encrypted Portal
  field deliberately.
- Do not paste secrets into Agent prompts, audit tickets, screenshots, or chat.

## 15. Administrative acceptance checklist

- Sign-in succeeds through every enabled authentication method.
- At least two System Administrators exist for recovery, where policy allows.
- Team membership and permission boundaries have been tested with a non-admin
  account.
- Data Group access prevents unauthorized retrieval and citation opening.
- Every LLM model has connection, tools, and vision results recorded.
- Every integration passes Test and is assigned only to intended Agents.
- Azure inventory Service Principals use Reader or narrower scope.
- Guardrails, quotas, and retention match organizational policy.
- System Health is healthy, including Nginx when TLS is enabled.
- Backups are validated with a non-destructive restore verification.
- License status and expiry are reviewed.
- External monitoring and certificate renewal are configured for production.

## 16. Troubleshooting

| Symptom | Likely check |
| --- | --- |
| Menu is missing | Confirm System/Team context and required permission |
| Provider Test succeeds but tools fail | Check model tool capability, Agent LangGraph runtime, and tool assignment |
| Local Ollama is unreachable | Use `ollama:11434` inside Compose or `host.docker.internal` for a host service |
| MCP test reports name resolution failure | The URL hostname is not resolvable/reachable from the app container |
| Azure MCP has no resources | Verify tenant, subscription list, Client ID/secret, and Reader RBAC scope |
| Managed Azure MCP provisioning unavailable | Verify Integration Controller health and Docker socket/runtime access |
| License page returns HTTP error | Check app logs, MongoDB health, `APP_DATA_ENCRYPTION_KEY`, and trusted public-key mount |
| Nginx missing from System Health | The TLS overlay was not used when recreating the app, or its internal health URL is absent |
| Chat history disappears early | Check System and Team retention policies and manual deletion audit metadata |

When collecting diagnostics, record time, component, safe status code, Team,
and action. Do not copy secrets, raw prompts, raw tool output, or customer
document content into logs or support cases.

## Related documentation

- [User Manual](user-manual.md)
- [System Health](system-health.md)
- [Production TLS](production-tls.md)
- [Product licensing](licensing.md)
- [Usage quotas](usage-quotas.md)
- [AI guardrails](ai-guardrails.md)
- [Integration control plane](integration-control-plane.md)
