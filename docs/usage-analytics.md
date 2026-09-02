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
- document and processed-page counts by document-processing provider;
- System, Team, and Personal views;
- date range (maximum 366 days), daily/weekly/monthly buckets, and Team, user,
  Agent, provider, and model filters.

Records created before this feature remain visible, but dimensions that were
not stored historically appear as `Unknown`. Legacy Azure Document
Intelligence page records are included in System and Team summaries when they
can be scoped safely. They are excluded from Personal reports because the old
schema stored an email rather than an immutable application user ID.

## Validation

1. Assign `View system dashboard` to a System role, or use a System Admin.
2. For a Team manager, assign `View team dashboard` in the Team role.
3. Send Chat and Ask requests through at least two Agents/models.
4. Upload and index documents through two configured processing profiles.
5. Open **Usage Analytics**, change the View and date bucket, and verify the
   totals and breakdowns.
6. Verify a Team viewer cannot request another Team, and a normal user selecting
   My usage sees only their own records.

Focused automated tests:

```bash
.venv/bin/pytest -q tests/test_token_usage.py tests/test_usage_analytics.py tests/test_usage_analytics_routes.py
```

## Deferred work

Estimated cost needs a versioned pricing catalog and currency policy before it
can be reliable. Budgets/alerts, CSV/Excel export, scheduled reports, tool/error/
latency telemetry, retention/rollups, and database indexes for very large
deployments remain follow-up slices.
