# InsightSphere Product Sales Deck — Presenter Notes

## 1. Cover

Position InsightSphere as an enterprise AI agent and knowledge platform—not a
standalone chatbot. It turns governed data and existing systems into AI that
can search, reason, and act.

## 2. Executive summary

Anchor the story on three capabilities: Know—answer from trusted knowledge;
Think—analyze documents and images; Act—invoke enterprise systems under policy.

## 3. Customer challenges

Focus on the two or three issues most relevant to the customer. Expand on ACLs
and audit for security stakeholders, or repetitive work and search time for
business sponsors.

## 4. Platform overview

Walk from user experience down through agents, knowledge, integrations,
governance, and deployment. Security is enforced across retrieval, citations,
and tool execution—not only at login.

## 5. Knowledge and RAG

Explain the governed lifecycle: upload, extract/OCR, embed and index, retrieve,
and cite. Users can open citations only when they are authorized to access the
source document.

## 6. AI agents

Each agent has its own model, instructions, data scope, and tools. This enables
role-specific agents without granting excessive data or execution privileges.

## 7. Document intelligence

For RFP, TOR, and compliance use cases, the requirements document is treated as
a checklist—not evidence. The platform searches governed Knowledge and shows
found items, missing items, confidence, sources, and gaps.

## 8. Security and governance

Cover local and Entra identities, Team/Data Group ACLs, encrypted secrets, tool
policy, audit, and user/conversation isolation. Do not claim certifications that
have not been formally obtained.

## 9. Model flexibility

Models differ in capability, cost, and latency. The platform tests tool calling
and vision support, then allows model selection per agent. Customers do not
need to migrate every workload at once.

## 10. Deployment

Azure provides managed services, local deployment provides data control, and
hybrid deployment allows provider choice by workload. Production scope must
include TLS, backup, monitoring, capacity planning, and operations.

## 11. Use cases

Select one or two use cases with a committed owner, accessible data, and clear
KPIs for the initial pilot.

## 12. Business benefits

Do not promise arbitrary savings percentages. Establish a baseline and measure
time per case, acceptance and rework, policy coverage, cost per task, and
latency during the pilot.

## 13. Engagement approach

Propose discover, pilot, validate, and scale. Separate functional pilot success
from production-hardening scope and acceptance criteria.

## 14. Differentiators

Summarize the platform as evidence-first, access-aware, governed but agentic,
provider-neutral, operations-ready, and extensible.

## 15. Enterprise AI guardrails and usage governance

Explain the System → Team → Agent/User hierarchy. Downstream policies can be
stricter but cannot weaken the enterprise minimum. Guardrails cover prompt
injection, secrets, PII/DLP, and high-confidence harmful instructions. Usage
quotas cover tokens, provider/model rules, document pages, and requests per
minute. Audit remains metadata-only.

## 16. Team-scoped integration and MCP catalog

Connections belong to one Team. A System Administrator can create an
Unassigned connection and assign it once; cross-Team Agent binding and runtime
invocation are rejected server-side. Multiple Datadog or Azure connections can
represent different tenants without sharing credentials between Teams.

## 17. Azure inventory to Draw.io architecture

Walk through the read-only flow from Azure inventory to an editable `.drawio`
artifact. Resource IDs and evidenced relationships are preserved. Conventional
relationships may be drawn only as explicitly labelled inferred connectors.
The current workflow does not provision or modify Azure resources.

## 18. Durable operations

Cover database-backed owner-isolated Chat History, System and Team retention,
dependency-aware deletion, metadata-only deletion audit, persistent ingestion
jobs, restart recovery, and consistent MongoDB/MinIO/Qdrant backup. This slide
shows that operational lifecycle is part of the product, not an afterthought.

## 19. Close

End with a specific ask: schedule the use-case workshop, complete a technical
assessment, and agree on pilot scope and success criteria.

## 20. Backup — Capacity framing

Use this slide when asked how many users the platform supports. Separate total
accounts, active users, concurrent requests, and simultaneous LLM generations.
The figures are planning baselines until they are validated against the
customer's actual model, context size, RAG flow, and tool workload.

## 21. Backup — Hardware sizing

Use the table as a budgeting baseline, not a capacity guarantee. Cloud LLM
deployments are commonly constrained by provider quota and latency. Local LLM
deployments must be sized around GPU throughput, VRAM, context length, and
parallel generation slots. Storage must include source documents, vector data,
retention, and backups.

## 22. Backup — Scaling roadmap

State clearly that the current Compose topology is appropriate for a pilot and
contains single points of failure. Production scale requires separate app,
worker, stateful data, and inference tiers. Scale using measured p95 latency,
queue depth, provider throttling, GPU utilization, and ingestion backlog—not
account count alone.
