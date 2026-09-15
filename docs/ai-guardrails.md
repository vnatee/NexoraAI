# AI guardrails

NexoraAI applies a provider-independent guardrail layer before and after model
execution. The same policy is used by Legacy and LangGraph Agents, so selecting
Azure OpenAI, OpenAI-compatible, or a local model does not bypass the controls.

## Implemented controls

Each Agent has an **AI Guardrails** section in Agent configuration. New and
existing Agents use safe defaults when no explicit policy has been saved:

- guardrails enabled;
- maximum latest-user-message length of 20,000 characters;
- high-confidence prompt-injection patterns blocked;
- credentials and secrets in input blocked;
- credentials and secrets in model output redacted;
- PII values and high-confidence requests to disclose identifiers are blocked
  in input by default, while PII in output is redacted by default;
- high-confidence unsafe-content requests and responses blocked;
- optional case-insensitive literal blocked phrases.

The deterministic PII/DLP detectors currently cover email addresses, Thai
telephone numbers, US Social Security numbers, checksum-valid Thai national
IDs, and checksum-valid payment-card numbers. Credential detectors remain
separate so operators can apply stricter policy to secrets than ordinary
personal data. The content-safety detector intentionally targets narrow,
high-confidence harmful instructions (including selected Thai patterns) to
avoid blocking ordinary security, health, or policy discussion. It is not a
replacement for a multilingual semantic safety model.

Input is checked before attachment retrieval or model execution. Retrieved
Knowledge text, temporary document excerpts, and LangGraph tool results are
treated as untrusted data; high-confidence embedded instruction patterns are
neutralized before they can be consumed as instructions. Output filtering is
performed before response text is released to the client. A policy configured
to redact or block output therefore buffers model text until the check is
complete, while non-content stream metadata is preserved.

Guardrail events use the existing Agent Audit store. Events contain only the
direction, detector identifiers, categories, finding count, and outcome. Raw
prompts, matched secrets, retrieved text, tool output, and model output are not
persisted by the guardrail audit path.

Agent create, edit, and delete routes enforce the Team `Manage agents`
permission server-side. An Agent ID must belong to the Team supplied by the
request, preventing a caller from changing another Team's policy by submitting
an arbitrary ID.

## Policy inheritance

Guardrails support an optional **System → Team → Agent** hierarchy. System
administrators configure the system minimum in **Administration → Guardrail
Policy**. Team administrators with `Manage agents` configure the Team minimum
in **Team settings → Guardrail Policy**. Agent settings remain in Agent Info.

At runtime the backend—not the browser—combines all configured levels. The
smallest input-size limit, strictest action, and union of blocked phrases wins.
An enabled parent policy cannot be disabled or weakened by a Team or Agent.
Until a System or Team policy is explicitly saved at that level, existing
Agent behavior is preserved.

## Operational guidance

- Keep **Prompt Injection** and **Secrets in Input** set to `Block` for
  production Agents.
- Keep **Secrets in Output** set to `Redact`, or use `Block response` for Agents
  handling high-value credentials.
- Keep **PII in Input** at `Block` for Agents that must never process or reveal
  personal data. Use `Audit only` only when legitimate workflows commonly
  contain contact data. Keep **PII in Output** at `Redact` unless the workflow explicitly
  permits disclosure.
- Keep unsafe content at `Block` for external-facing Agents. The current local
  detector favors precision over recall; pair it with a provider moderation
  service when broader multilingual classification is required.
- Use `Audit only` temporarily while measuring false positives. Review events
  in **Admin Management → Agent Audit**.
- Blocked phrases are literal organization-specific controls. They are not a
  semantic topic classifier.
- Never use a guardrail setting as a substitute for Team/Data Group ACLs,
  least-privilege integration credentials, tool allowlists, or network policy.

## Known limitations and planned hardening

The current implementation uses deliberately narrow deterministic detectors.
It does not yet provide a semantic multilingual jailbreak/safety classifier,
full jurisdiction-specific PII coverage, groundedness scoring, human-review
queues, or a production malware scanner. Those controls should be added behind
the same provider-neutral policy boundary, with versioned evaluation datasets
and measured false-positive/false-negative rates.
