# Enterprise AI Strategy Proposal — Presenter Notes

Audience: Infrastructure Division Head / Senior Vice President, KGI Securities Thailand.
Main presentation: slides 1–29. Backup: slides 30–36. Target duration: 50–60 minutes.

## Core message

AI does not replace enterprise systems of record. AI becomes the secure intelligence and orchestration layer across them.

## Slide-by-slide notes

1. **Cover (1 min)** — This is not another chatbot discussion. Frame AI as a secure intelligence layer across enterprise knowledge, infrastructure and business systems.
2. **Beyond chat (2 min)** — Enterprise value increases as AI moves from conversation to grounded knowledge, reasoning and governed action.
3. **Why now (2 min)** — Models, knowledge technology, connectivity and infrastructure are converging at production maturity.
4. **Bigger than a chatbot (2 min)** — Avoid isolated bots. Build shared capabilities once and specialize through governed agents.
5. **Value chain (2 min)** — Know what the enterprise knows, understand the user need, then act through trusted systems.
6. **Platform layers (3 min)** — Security and AI operations are cross-cutting concerns, not single components.
7. **Enterprise knowledge (2 min)** — Stress authorization before retrieval and again before source access.
8. **Why local AI (3 min)** — Local AI improves control but creates capacity, lifecycle and operations responsibility.
9. **Controlled model choice (3 min)** — Route by policy, capability, cost and latency. Do not force one provider for every workload.
10. **Zero Trust for AI (3 min)** — Verify identity, agent, knowledge, tool and action; retain an auditable trace.
11. **Governed agentic AI (2 min)** — Guardrails turn threats into controlled answers and approved actions.
12. **Transition (30 sec)** — Move from principles to practical workflows.
13. **HR agent (2 min)** — AI improves access to PeopleSoft and knowledge; PeopleSoft remains the record.
14. **Leave request (3 min)** — Walk the sequence from identity through policy reasoning to an optional approved transaction.
15. **Talent intelligence (2 min)** — Show authorized workforce insight and skill-gap planning without exposing unnecessary personal data.
16. **IT helpdesk (3 min)** — AI improves self-service and enriches incidents that still need human support.
17. **Operations transition (1 min)** — Introduce evidence from service desk, knowledge and real-time telemetry.
18. **Trading application is slow (4 min)** — This is the hero slide. Correlate K2, runbooks, changes and RUM/APM/DB/infrastructure/logs. AI should not guess root cause.
19. **Observability (3 min)** — Datadog is one possible implementation. Signals come from observability; context and orchestration come from AI.
20. **Proactive operations (2 min)** — Show the shift from user-reported incidents to AI-assisted detection and response.
21. **Broader opportunities (2 min)** — HR and IT are starting points, not the final scope.
22. **KYC/CDD (3 min)** — AI prepares evidence; accountable compliance staff make regulated decisions.
23. **Regulatory knowledge (2 min)** — Accelerate impact analysis while preserving human judgment.
24. **Target architecture (4 min)** — Walk top to bottom. Security and AI operations frame the platform; systems of record stay authoritative.
25. **Local AI infrastructure (3 min)** — Production local AI needs resilient app, worker, data and inference tiers.
26. **Roadmap (3 min)** — Build foundation, assist, act, add intelligence, then scale. People/process/technology move together.
27. **Starting point (2 min)** — Recommend a reusable foundation plus one HR and one IT pilot with owners and measurable KPIs.
28. **Measurement (2 min)** — Establish baselines. Avoid arbitrary savings claims.
29. **Closing (1 min)** — Propose use-case workshop, technical assessment and pilot.

## Backup guidance

30. Select local models using real workload benchmarks: model size alone is insufficient.
31. Capacity is governed by concurrent generations, context, KV cache, tokens per second, RAG and tools.
32. Local and cloud are workload choices under policy, not mutually exclusive strategies.
33. RAG security must filter before retrieval and re-authorize citation access.
34. MCP and APIs are complementary governed integration patterns.
35. Protect each stage from prompt injection, data exfiltration and tool abuse; retain an auditable trace.
36. Design HA, backup and DR as one consistent application recovery architecture, then prove it with restore drills.
