# Usage quotas

Usage quotas provide provider-independent limits for cloud and local models and
document processors. Configure them under **Administration / Team settings →
Usage Quotas**.

Policies are evaluated at System, Team, and User levels. A System Admin can
switch between **Entire system**, **Current team**, and **Specific user** on the
same Usage Quotas page, even while Team settings is open. Team administrators
see only their current Team. The smallest enabled,
non-zero limit applies; zero means unlimited at that level. User overrides are
available to System Admins through the System quota page.

The first enforcement slice supports:

- monthly total LLM tokens across every provider/model (Overall);
- optional monthly token rules for a configured provider or exact model
  profile, optionally limited to Chat or Ask workloads;
- monthly processed document pages;
- atomic LLM requests-per-minute counters.

Provider/model rules use immutable provider/profile identifiers rather than
editable display names. Adding a provider automatically remains covered by the
Overall limit. Deleting a provider does not silently delete its rule: the
Portal retains its label snapshot and marks it unavailable until an
administrator removes or replaces the rule. Every applicable System, Team,
User, Overall, provider, model, and workload rule must pass.

Token totals include prompt/input, completion/output, and reasoning tokens
reported by the provider. Historical records created before provider/profile
dimensions were introduced remain in Overall totals but cannot be attributed
retroactively to a provider/model rule. Current provider/model enforcement is
for the selected request profile. Exact per-call attribution inside a
multi-model sub-agent run and embedding token quotas require finer-grained
metering and remain follow-up work.

Checks happen before the LLM call or document extraction. Monthly token/page
usage is based on completed persisted events, so one in-flight operation can
finish slightly above a monthly boundary. Requests-per-minute is enforced with
an atomic MongoDB counter and is suitable for multiple application replicas.
LLM usage persistence currently runs asynchronously and is operational
metering, not a billing-grade ledger. A failed telemetry write must be alerted
and reconciled before token quotas can be used for contractual billing or hard
license consumption.

When a limit is reached, Chat/Ask returns HTTP 429. A document job is marked
failed without calling the configured parser. Administrators can raise the
limit and retry the operation. `DISABLE_USAGE_QUOTAS=true` is intended only for
automated tests or emergency diagnosis; do not use it to bypass production
policy.

Recommended smoke test:

1. Set System requests/minute to `2`, save, and send three prompts in one
   minute. The third must return a quota error.
2. Set a Team monthly token limit below its current usage and verify Chat is
   blocked only for that Team.
3. From the System page select a user, set a stricter user limit, and verify it
   follows that user across Teams.
4. Set monthly document pages below current usage, upload a document, and
   verify the job fails before extraction. Raise the quota and retry.
5. Set all values to `0` or disable the policy and verify normal behavior.
6. Add a provider rule below that provider's current usage and verify only
   requests selecting that provider are blocked. Repeat with one model profile.
7. Delete or disable a configured provider and verify its saved quota rule is
   shown as unavailable rather than silently reassigned by display name.

Future work includes advance token reservations, per-model-call/sub-agent and
embedding metering, warning thresholds, approval workflows, budgets/cost
pricing, notifications, and quota audit history. Product-license entitlements
are deliberately separate from these operational quotas; see the licensing
roadmap in `product-backlog.md`.
