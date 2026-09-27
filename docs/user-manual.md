# NexoraAI User Manual

**Language:** English  
**Audience:** End users, business users, analysts, and team members  
**Last verified:** 2026-09-27
**Applies to:** The current NexoraAI web application on the local/container or Azure runtime

This is the stable User Manual for NexoraAI. Update this file in place when a
user-facing feature, field, workflow, permission, or menu changes. Do not create
a dated replacement manual unless a separately maintained release manual is
explicitly requested.

The formatted Word deliverable is `NexoraAI-User-Manual.docx`. Regenerate both
Word manuals after updating their Markdown sources with:
` .venv/bin/python scripts/build_manual_docx.py `.

## 1. What NexoraAI does

NexoraAI provides a governed AI workspace where users can:

- chat with approved AI Agents;
- search authorized Knowledge sources;
- attach images and documents to a conversation;
- compare requirements with available evidence;
- use tools and business integrations assigned to an Agent;
- receive citations, tables, charts, and downloadable artifacts; and
- review personal usage and retained conversation history.

Available features depend on the selected Team, Agent, data access, model
capabilities, integration assignments, and permissions configured by an
administrator.

## 2. Sign in

NexoraAI may offer one or both of these sign-in methods:

| Method | Information required | Example |
| --- | --- | --- |
| Local account | Email address and password issued by an administrator | `alex@example.com` |
| Microsoft Entra ID | Your organization Microsoft account | `alex@example.com` |

If **Waiting for approval** is displayed, your identity is valid but an
administrator has not activated or assigned the account yet. Contact your Team
Administrator or System Administrator.

Never share passwords, access tokens, API keys, or copied browser session
values in a chat message.

## 3. Workspace overview

### 3.1 Header and account menu

The header contains the NexoraAI logo, the **Chat** page, and your account menu.
The account menu can include:

- **My profile** — view your account details and, for local accounts, change
  your password;
- **Team selection** — switch the active Team when you belong to more than one;
- **Administration** — available only when your permissions allow it; and
- **Sign out**.

Changing Team changes the Agents, Knowledge scopes, integrations, permissions,
and Team usage context available to you.

### 3.2 Chat context selector

The context card above the conversation identifies the active configuration:

| Item | Meaning | Example |
| --- | --- | --- |
| Agent | The AI role, instructions, model, and tools used for the request | `Azure Engineer` |
| Model | The friendly model label selected by the Agent | `GPT-4.1` |
| Team | The active Team and its access boundary | `Presale` |
| Data | The selected Knowledge scope | `Global`, `Team`, or `Personal` |

Select **Change** to choose another available Agent or data scope. If an Agent
is not listed, it is inactive, belongs to another Team, or has not been granted
to your account.

## 4. Chat sidebar

The sidebar is grouped by purpose. It can be collapsed to provide more room for
wide answers and tables.

### Workspace

| Menu | Purpose |
| --- | --- |
| **New Chat** | Start a clean conversation and new conversation context |
| **Search History** | Find a retained conversation by its searchable metadata |
| **Feedback** | Send product feedback when enabled for your account |
| **Upload** | Add documents to an authorized Knowledge scope |

### Management

This group appears only when you have management or upload permissions. It can
contain **Admin Management**, Global Knowledge upload, and web content
ingestion controls. See the [Administrator Manual](admin-manual.md).

### Insights

| Menu | Purpose |
| --- | --- |
| **My Usage** | Personal request, token, and document-processing usage |
| **Usage Analytics** | Team or System reporting when you have elevated permission |
| **Feedback Dashboard** | Review feedback when permission is granted |

### Recent chats

Lists retained conversations for the signed-in owner. Selecting an item restores
its messages and conversation context. A conversation can disappear because it
was manually deleted or reached the configured retention period.

## 5. Ask a question

1. Confirm the Agent, Team, and Data selections.
2. Type a clear request in **Type a new question**.
3. Attach a file if the Agent permits the required attachment type.
4. Select **Send**.
5. Review the answer, citations, tool sources, and generated artifact before
   using the result operationally.

Example:

> Summarize the approved remote-work policy. Cite the source file and page for
> each eligibility requirement. If the evidence is missing, say so explicitly.

Good requests state the task, scope, expected output, and constraints. For
example:

> Compare the attached requirements with Team Knowledge. Return a table with
> Requirement, Status, Evidence, Source File, Page, and Gap. Do not infer a
> requirement when no evidence is available.

## 6. Attachments

### 6.1 Images

Paste, drag, or select an image. Image analysis is available only when the Agent
has **Enable image input** and its selected model supports vision. Otherwise the
application may reject the image or use an approved OCR path.

Example:

> Read this architecture screenshot and list the visible components. Separate
> observed connections from inferred connections.

### 6.2 Documents

Supported deployments can accept PDF, Microsoft Office Open XML, and UTF-8 text
documents. The Agent must allow document attachments. The interface displays
upload and extraction status; only ready documents are sent as temporary
conversation evidence.

Attached documents are private to the authenticated owner and conversation.
They are not automatically added to permanent Knowledge.

### 6.3 Evidence matrix

When a requirements document is attached, enable **Evidence matrix** and choose
the evidence scope:

| Scope | Use when |
| --- | --- |
| **Knowledge only (recommended)** | The attachment is the checklist and permanent Knowledge is the evidence |
| **Attached files only** | Evidence is contained only in the uploaded files |
| **Attached files + Knowledge** | Both temporary files and authorized Knowledge may provide evidence |

The first attachment is treated as the checklist. In **Knowledge only** mode it
must not be cited as proof of its own requirements.

## 7. Read and verify an answer

### Citations

Citation numbers open the authorized source. Permanent Knowledge citations and
temporary attachment citations use different protected routes. Access is
checked again when the citation is opened.

### Tool sources

An answer may show tool-source labels such as Azure MCP, Database, REST, or
Knowledge. These labels identify where structured information came from; they
do not by themselves prove that every relationship in a generated diagram is
explicitly present in the source.

### Live Web Search

Some Agents can search current public information within domains approved by
an administrator. Ask for the relevant external source and request citations,
for example:

> Search current Datadog documentation for monitor recovery thresholds.
> Cite the URLs and state the search date.

Web results are external, untrusted snippets—not enterprise Knowledge. Verify
important statements by opening the cited URL. The Agent should say when no
allowed result was found and must not send secrets, personal data, or
confidential company content in a web query.

### Tables and wide content

Markdown tables render responsively within the answer area. On a narrow screen,
the table itself may scroll horizontally while the whole page remains fitted to
the viewport.

### Charts

When an Agent has Visualization enabled and a tool returns suitable structured
data, the answer can include a chart and source-data panel. Available actions
can include:

- download the chart as PNG;
- download chart data as CSV; and
- inspect row count, source tool, and truncation indicators.

### Generated files

Generated files such as Draw.io diagrams appear as an artifact card. Select the
file name or download action rather than copying the displayed label as plain
text. Open `.drawio` files with diagrams.net/draw.io.

## 8. Common workflows

### Knowledge-grounded answer

1. Select the correct Team and Agent.
2. Select the Team or Global data scope you are authorized to use.
3. Ask for citations and page numbers.
4. Open at least one citation and verify the supporting text.

### Azure inventory to Draw.io

This workflow is available only when the Agent has both an Azure MCP connection
and Draw.io MCP connection assigned.

Example:

> Read all resources in resource group `NT_ChatAISearch`. Create a Draw.io
> architecture diagram using Azure icons. Use solid lines for relationships
> present in resource data and dashed lines labelled `inferred` for assumptions.
> Return a downloadable `.drawio` file.

### Business document workflow

If Microsoft 365 or Google Workspace connections are assigned, specify the
document or location precisely and request a non-destructive operation first.

Example:

> Read the approved sales workbook and summarize quarterly revenue by region.
> Do not modify the workbook. Return a table and identify the worksheet used.

## 9. Knowledge upload

The upload interface and permitted scopes depend on your role.

Typical information includes:

| Field | Description | Example |
| --- | --- | --- |
| File | Supported document to index | `remote-work-policy.pdf` |
| Data scope/Data Group | Who may retrieve the document | `Presale Knowledge` |
| Processing profile | OCR/document parser selection; Auto uses routing rules | `Auto — use routing rules` |

After submission, processing may pass through uploaded, extraction, chunking,
embedding, ready, or failed states. A successful upload is not searchable until
processing reaches ready.

Do not upload credentials, private keys, license keys, or data outside the
approved Team classification.

## 10. My Usage

**My Usage** shows only your authorized personal usage. Depending on available
data, filters include date range, daily/weekly/monthly bucket, Provider, Model,
Agent, processing Profile, File type, and Document scope.

Team or System administrators may see broader **Usage Analytics** scopes. A
missing Team or User breakdown usually means your role is intentionally limited
to personal data.

## 11. Profile and password

Open the account menu and select **My profile**. Account information can include
name, email, employee ID, telephone number, active status, and Teams.

For a local account, use the password-change action and enter the current and
new passwords. Microsoft Entra passwords are managed by your organization and
cannot be changed in NexoraAI.

## 12. Troubleshooting

| Symptom | What to check |
| --- | --- |
| Agent is missing | Confirm the active Team and ask an administrator whether the Agent is active and assigned |
| Upload is disabled | The Agent or your role may not allow that attachment/document scope |
| Tool is not called | Confirm the selected Agent has the integration and that its invocation mode/policy permits the tool |
| Citation does not open | The item may have expired or your owner/Team access changed |
| Answer has no evidence | Select the correct data scope and ask explicitly for citations; do not treat an unsupported answer as verified |
| Table appears as `|` text | Start a new response and request a valid Markdown table with one header row and one separator row |
| Generated file does not open | Download from the artifact card and confirm the file extension; ask the Agent to regenerate valid XML if it is a Draw.io file |
| Session expired | Sign in again; unsent draft content may need to be entered again |
| Feature/menu is missing | Menus are permission-, Team-, deployment-, and license-dependent |

If the problem continues, record the time, active Team, Agent name, action, and
safe error message. Do not include passwords, tokens, full prompts containing
sensitive data, or raw tool output in a support ticket.

## 13. Current limitations

- AI output can be incomplete or incorrect and must be reviewed before an
  operational change.
- Tool availability does not guarantee the selected model can perform reliable
  tool calling; administrators should test model capabilities.
- Some integration catalog entries are marked **Coming soon**.
- In-product System Health cannot detect a complete outage when the application
  itself is unavailable; production deployments also require external
  monitoring.

## Related documentation

- [Administrator Manual](admin-manual.md)
- [Azure inventory to Draw.io](azure-drawio-mcp.md)
- [Usage analytics](usage-analytics.md)
- [Local authentication](local-authentication.md)
- [AI guardrails](ai-guardrails.md)
