# Usage analytics

NexoraAI records provider-neutral operational metadata for LLM requests and
document processing. It does not store prompts, model responses, extracted
document text, credentials, or tool output in the analytics records.

## Access

- **Entire system** requires the System permission `View system dashboard` (or
  System Admin).
- **Team** requires membership in that Team and the Team permission `View team
  dashboard` (or System Admin).
- **My usage** is always forced to the signed-in application user. A supplied
  user ID cannot broaden this scope.

The backend applies these rules before querying MongoDB. The browser receives
aggregates, not the underlying usage records.

## Available views and filters

Open **Usage Analytics** from the Chat navigation. The first slice provides:

- LLM request, input-token, output-token, reasoning-token, and total-token
  counts;
- token breakdowns by model, provider, Agent, Team, and user;
- estimated USD cost, pricing coverage, unpriced tokens/calls, and cost
  breakdowns by model, provider, route, Agent, Team, and user;
- document and processed-page counts with breakdowns by processing provider,
  profile, file type, and document scope;
- document-processing breakdowns by user for authorized Team/System views and
  by Team for the System view;
- System, Team, and Personal views;
- date range (maximum 366 days) and daily/weekly/monthly buckets;
- Team/user filters where authorized, Agent/model filters for LLM usage, and
  provider/profile/file-type/document-scope filters for document processing.

## Cost accounting and exports

System Administrators manage **Price catalog** from Usage Analytics. A price
version has an effective date range and optional exact matches for provider,
provider/gateway ID, resolved model, LLM profile, and route. Empty dimensions
are wildcards. When more than one version matches, the most specific match is
used and then the latest effective start date. Versions are created and
retired; they are not edited in place. Retiring closes the effective range so
historical usage inside that range remains reproducible.

Two pricing methods are supported:

- **Provider token rates** — USD per one million normal input, cached input,
  and output tokens. Reasoning tokens are reported but not charged again when
  they are already part of provider output-token usage.
- **Local AI TCO** — hardware purchase less residual value over useful life,
  annual maintenance/operations, electricity adjusted by PUE, optional cloud
  GPU hourly cost, aggregate token throughput, and utilization. The resulting
  loaded hourly cost is converted to a blended USD-per-million-token estimate.

NexoraAI does not seed or scrape provider prices automatically. Administrators
must enter a documented contract, provider price-list version, or Local AI
assumption. Usage without a matching price remains **Unpriced** and is never
reported as zero cost. The displayed total is an estimate rather than a
provider invoice.

**Raw CSV** exports metadata, token counts, price status, cost components, and
the applied price version under the same System/Team/Personal ACL and filters
as the page. It does not include prompts, responses, Knowledge, tool data, or
credentials. **PDF report** exports the visible period summary, coverage, and
top model costs. Currency is USD in this slice; THB conversion is deferred.

Records created before this feature remain visible, but dimensions that were
not stored historically appear as `Unknown`. Legacy Azure Document
Intelligence page records are included in System and Team summaries when they
can be scoped safely. They are excluded from Personal reports because the old
schema stored an email rather than an immutable application user ID. In
authorized aggregate breakdowns, dimensions that cannot be attributed safely
are labeled `Unknown / legacy`; the application does not infer an identity from
the historical email value.

## Validation

1. Assign `View system dashboard` to a System role, or use a System Admin.
2. For a Team manager, assign `View team dashboard` in the Team role.
3. Send Chat and Ask requests through at least two Agents/models.
4. Upload and index documents through two configured processing profiles.
5. Open **Usage Analytics**, change the View and date bucket, and verify the
   LLM totals and breakdowns.
6. Open **Document processing** and verify provider, profile, file type, and
   document-scope filters. In System view verify Team and User breakdowns; in
   Team view verify only User; in My usage verify neither User nor Team is
   shown.
7. Verify a Team viewer cannot request another Team, and a normal user selecting
   My usage sees only their own records.
8. As System Admin, add one provider-token price version and one Local AI TCO
   version. Verify matching usage is priced and unmatched usage stays Unpriced.
9. Export Raw CSV and PDF report, then verify their scope, date range, cost
   disclaimer, and absence of prompt/response content.

Focused automated tests:

```bash
.venv/bin/pytest -q tests/test_token_usage.py tests/test_usage_pricing.py tests/test_usage_analytics.py tests/test_usage_analytics_routes.py
```

## Deferred work

Provider billing reconciliation/import, THB conversion policy, budgets/alerts,
Excel export, scheduled reports, tool/error/latency telemetry,
retention/rollups, and database indexes for very large deployments remain
follow-up slices.
