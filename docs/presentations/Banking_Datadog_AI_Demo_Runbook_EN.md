# Banking Datadog + NexoraAI Demo Runbook

## Demo goal

Show that a NexoraAI Operations Agent can retrieve authorized Datadog evidence,
correlate it with approved operational Knowledge, create a chart from exact tool
results, and produce an approval-ready recommendation without modifying
production.

## Safety boundary

- Use a demonstration tenant and synthetic service names.
- Never show customer names, account numbers, tokens, host identifiers or raw
  production logs.
- Bind the Agent only to the intended Team-owned Datadog connection and approved
  Knowledge Data Groups.
- Keep Datadog and every other integration read-only.
- Pre-test the exact prompts and time ranges on the same day as the event.
- Keep screenshots or a short recording as fallback and label them clearly.

## Recommended scenario

Service: Mobile Banking Transfer
Symptom: P95 latency and error rate increase after a demonstration deployment.
Evidence: Datadog monitor events, latency/error time series, a synthetic change
record and a fictional connection-pool runbook.

## Live prompts

1. Current state

   Summarize important alerts and events related to Mobile Banking during the
   last 60 minutes. Identify the impact and any missing data.

2. Visualization

   Create an alert trend chart by severity for the investigated period and
   summarize major turning points. Use only exact retrieved data.

3. Correlation and Knowledge

   Correlate the alert timeline with relevant changes, search authorized
   runbooks, then rank hypotheses with evidence, gaps and approval-required next
   actions.

## Presenter checklist

- [ ] The Agent uses a tested tool-capable LLM profile.
- [ ] The Datadog MCP connection test succeeds and discovered tools are visible.
- [ ] The Agent binding permits only the required read tools.
- [ ] Knowledge search is enabled for synthetic Change and Runbook sources.
- [ ] Chart integration is enabled and tested with exact tool output.
- [ ] Each response shows source/time context and no fabricated metric.
- [ ] The final recommendation identifies owner, risk and approval requirement.
- [ ] Screenshot/video fallback is ready.
