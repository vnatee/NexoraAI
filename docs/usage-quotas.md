# Usage quotas

Usage quotas provide provider-independent limits for cloud and local models and
document processors. Configure them under **Administration / Team settings →
Usage Quotas**.

Policies are evaluated at System, Team, and User levels. A System Admin can
switch between **Entire system**, **Current team**, and **Specific user** on the
same Usage Quotas page. Team administrators can configure their current Team
and its member overrides. The smallest applicable non-zero total ceiling
applies; zero means unlimited at that level. Global User ceilings remain
available to System Admins through the Administration quota page.

Each enabled Team policy may also define **Default monthly tokens per member**.
A Team-member override is stored against the `(team_id, user_id)` pair and
replaces that Team default for only that member. It is not added to the default
and it never bypasses the Team total or System total. For example, Team A can
have a 10M total with 1M per member while Team B has 20M total with 2M per
member. A Team A member overridden to 3M can use up to 3M only while Team A and
the System still have capacity.

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
global User, Team-member, Overall, provider, model, and workload rule must
pass. If a user changes Teams, the old Team-member override remains attached
to the old Team and does not follow the user. An override can only be viewed or
edited while the user is a current member of that Team.

Token totals include prompt/input, completion/output, and reasoning tokens
reported by the provider. Historical records created before provider/profile
dimensions were introduced remain in Overall totals but cannot be attributed
retroactively to a provider/model rule. Current provider/model enforcement is
for the selected request profile. Exact per-call attribution inside a
multi-model sub-agent run and embedding token quotas require finer-grained
metering and remain follow-up work.

Checks happen before the LLM call or document extraction. Each Chat/Ask request
has a UUID and creates an idempotent, 15-minute token reservation before the
provider is called. The reservation uses the configured maximum output plus a
bounded approximation of submitted text tokens. Completed usage is persisted
synchronously with the same UUID and the reservation is then finalized. This
prevents duplicate usage rows and substantially reduces concurrent quota
overshoot across application replicas. A duplicate in-flight/completed UUID is
rejected rather than billed twice.

If an application process stops, an active reservation stops counting after 15
minutes even if MongoDB TTL cleanup has not physically deleted it. Completed
and released reservation records, quota threshold events, and block events are
retained for 90 days. The Portal shows used and currently reserved tokens,
80/90/100 percent status, and recent threshold/block events. Metering failures
do not discard a successful model response; the reservation remains counted
for 15 minutes and a safe metadata-only event is recorded.

Knowledge document-processing telemetry now uses the persistent ingestion job
ID as its idempotency key, so restart recovery cannot count the same successful
job twice. Exact page reservation before extraction remains future work because
the authoritative page count may only be known after parsing.

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
8. Set a token limit slightly above current usage, start a long Chat request,
   and refresh Usage Quotas. Confirm the reserved amount is visible while the
   call is active and disappears after completion.
9. At 80%, 90%, and 100% projected usage, confirm the status changes and a
   metadata-only threshold/block event appears. No prompt or response text
   should appear in the event list.
10. In browser developer tools, retry the same Chat request with the same
    `usage_request_id`. Confirm the duplicate is rejected and only one usage
    event is counted.
11. Set Team A total to `10,000`, its default per-member limit to `1,000`, and
    give one member a `2,000` custom override. Confirm another member is blocked
    at 1,000, the overridden member can pass 1,000, and both are blocked once
    the Team total reaches 10,000.
12. Add the same user to Team B with a different default. Confirm Team A and
    Team B usage and overrides are evaluated independently according to the
    active Team selected for the request.

This is durable operational metering, but it is not yet a contractual billing
ledger: provider-side corrections, streamed responses without final usage,
exact per-model-call/sub-agent attribution, embedding usage, document-page
reservations, notification delivery, and periodic reconciliation remain future
work. Product-license entitlements are deliberately separate from these
operational quotas; see the licensing roadmap in `product-backlog.md`.
