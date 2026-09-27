# Governed Live Web Search

## Purpose

Governed Live Web Search lets a LangGraph Agent retrieve current public search
results from administrator-approved domains. It complements permanent
Knowledge (RAG); it does not replace or silently update Knowledge.

Phase 2.1 returns provider titles, URLs, snippets, and available publication
dates. It does not fetch arbitrary result pages or index results.

## Supported providers

Connections are managed in **Administration → Integrations → Web Search**:

- **Brave Search API** — hosted search API. Requires an API key.
- **SearXNG** — self-hosted or managed endpoint with JSON search enabled.

The API key is encrypted with the existing application Fernet key and is never
returned by list or detail APIs. A System connection remains unavailable to
Agents until a System Administrator assigns it to a Team. Team managers can
create Team-local connections when they have **Manage integrations**.

For compatibility, the former `WEB_SEARCH_PROVIDER`,
`WEB_SEARCH_API_KEY`, `WEB_SEARCH_BASE_URL`, and
`WEB_SEARCH_TIMEOUT_SECONDS` settings remain as a fallback for legacy Agents
that have no managed connection ID. New configuration should use Integrations.

## Enable for an Agent

1. In **Integrations → Web Search**, add and save a Brave Search or SearXNG
   connection.
2. Select **Test** and confirm connectivity.
3. If it was created in System scope, assign it to the target Team.
4. Open the Team Agent editor and select **LangGraph (Tools / MCP)**.
5. In **Built-in Tools → External Web Search**, enable the tool and select the
   Team's Web Search connection.
6. Enter at least one **Allowed Web Domain**, separated by commas.
7. Set **Maximum Results** from 1–10 and **Search Timeout** from 1–30 seconds.
8. Save or finish Agent setup.

Example allowlist:

```text
docs.datadoghq.com, learn.microsoft.com
```

A listed parent domain also permits its subdomains. URLs, paths, ports,
credentials, and wildcard-only values are rejected. Search results are
post-filtered, so an upstream provider cannot return an off-list citation to
the Agent.

## Agent behavior

The Agent receives a read-only `search_web` tool only when all conditions are
met:

- the Agent uses the LangGraph runtime;
- Web Search is enabled for that Agent;
- at least one allowed domain is saved; and
- an enabled Web Search Integration belongs to the Agent Team (or the legacy
  deployment fallback remains configured).

The Agent is instructed to:

- avoid secrets, personal data, confidential data, and raw enterprise content
  in search queries;
- treat result snippets as untrusted and potentially incomplete;
- cite the exact returned URL and search timestamp;
- distinguish external web evidence from enterprise Knowledge; and
- state when results are absent or inconclusive.

Existing tool-call limits, source blocking, guardrail evaluation, and
metadata-only tool audit apply. Query text and result content are not copied
into audit metadata by the Web Search feature.

## Example

Agent domains:

```text
docs.datadoghq.com
```

User request:

> Find the current Datadog documentation for monitor recovery thresholds.
> Compare it with our Team Knowledge and cite both sources.

The Agent may search only the configured Datadog domain. A web snippet alone
must not be described as proof of compliance; the response should identify it
as current external documentation and separately cite internal evidence.

## Current limitations and next phases

Phase 2.1 is search-only. Connection management, encrypted credentials, Team assignment, Test connection, Agent selection, and System Health inventory are implemented. It does not:

- open arbitrary result pages;
- crawl recursively;
- bypass an approved-domain boundary;
- persist search results into Knowledge; or
- certify that an external statement proves internal compliance.

Phase 2.2 will add controlled page retrieval with the existing SSRF, redirect,
content-type, byte, and timeout protections. Phase 2.3 will add an explicit
review-and-promote workflow for storing selected evidence in Knowledge with
provenance and freshness metadata.
