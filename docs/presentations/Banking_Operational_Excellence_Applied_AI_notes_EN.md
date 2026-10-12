# Banking IT Outing — English Presenter Notes

Topic: **Operational Excellence Through Applied AI to New IT Operational Capabilities**
Format: 45-minute presentation + 15-minute game
Audience: Senior executives and approximately 120 IT staff

## Timing

- Slides 1–5: Opening and operational pressure — 8 minutes
- Slides 6–12: Applied AI and platform — 14 minutes
- Slides 13–21: Banking use cases and Datadog demo — 16 minutes
- Slides 22–24: Governance, roadmap and takeaways — 7 minutes
- Slides 25–40: Game — 15 minutes
- Slide 41: Closing — 1 minute or use inside the Q&A buffer

## Slide-by-slide notes

### 1. Opening (1 minute)

- This is not a talk about model benchmarks. It is about how AI can improve the way IT teams operate.
- The audience includes executives and practitioners, so connect business outcomes to technical evidence.
- Ask everyone to remember the words Evidence, Context and Guardrail for the game.

### 2. Session map (1 minute)

- Set expectations: business framing, plain-language platform, live demo, governance and a 15-question game.
- The platform complements existing tools rather than replacing them.

### 3. Opening poll (2 minutes)

- Let each table choose one or more answers.
- All four are valid: the real problem is that signals, context, knowledge and coordination are disconnected.

### 4. Business outcomes (2 minutes)

- Executives care about reliability, risk and capacity more than model benchmarks.
- Tie every AI use case to measurable outcomes such as MTTR, repeat incidents and briefing time.

### 5. Banking reality (2 minutes)

- Banking operations combine high dependency, high change and strict evidence requirements.
- Applied AI is valuable where teams must read and correlate many types of operational data.

### 6. AI evolution (2 minutes)

- Chat is only an interface. Value appears when AI can access authorized Knowledge and tools.
- Act does not mean uncontrolled production change; organizational approval policy still applies.

### 7. Applied AI in plain language (2 minutes)

- Use Sense, Understand, Recommend and Orchestrate as the mental model for the rest of the talk.
- Every recommendation must be grounded in evidence and policy.

### 8. Platform concept (3 minutes)

- Describe the platform as a secure layer connecting people, knowledge and existing systems.
- Datadog, Service Desk and CMDB remain authoritative systems.
- The AI layer applies access control, tool policy and metadata-only audit.

### 9. Platform capabilities (2 minutes)

- A model alone is not an enterprise AI platform.
- Agents, Knowledge, integrations, observability, guardrails and audit must work together.

### 10. Responsibility (2 minutes)

- Use this slide to address fears about AI replacing systems or accountability.
- Begin with read-only recommendations and add actions only when controls are ready.

### 11. Maturity (2 minutes)

- Analyze and Recommend provide high value with lower risk than autonomous write actions.
- Today's demo is intentionally at these two maturity levels.

### 12. Use-case portfolio (2 minutes)

- This is a transparent internal scoring framework, not an industry or banking benchmark.
- Score each criterion from 1 to 5 in a customer discovery workshop; the proposed 35/30/20/15 weights should be reviewed and approved by service owners.
- The example assumes read-only Datadog telemetry. Knowledge, Change and approval readiness must be verified using customer evidence.
- NIST AI RMF informs risk/control criteria and Google SRE informs incident-response outcomes; neither source defines this formula or its weights.
- For a production decision, record the score owner, evidence, assessment date and rationale for every score.

### 13. Morning briefing (2 minutes)

- Executives receive a concise summary with links back to evidence rather than another dashboard.
- The result should expose uncertainty and missing information.

### 14. Incident story (2 minutes)

- A customer symptom does not identify the root cause.
- The Agent must decompose the question and retrieve evidence from multiple systems.

### 15. Correlation (3 minutes)

- Datadog supplies detailed telemetry; Change and Knowledge provide operational context.
- Rank hypotheses and show supporting, conflicting and missing evidence.

### 16. Demo flow (1 minute)

- Use a demo tenant and a read-only Agent.
- Keep the full demo below eight minutes and retain a clearly labeled recording or screenshots as fallback.

### 17. Demo 1 (1–2 minutes)

- Show that a natural-language request invokes authorized Datadog tools.
- Confirm the response includes scope, time window, evidence links and missing data.

### 18. Demo 2 (1–2 minutes)

- The chart must be created from exact successful tool output.
- Call out that the model is not allowed to invent metrics.

### 19. Demo 3 (1–2 minutes)

- Show correlation between observability evidence, Change and approved runbooks.
- The final action must identify owner, risk and approval boundary.

### 20. Demo result (2 minutes)

- The values shown are an illustrative result format, not customer data.
- A useful answer states what is known, why, confidence, gaps and the next approved step.

### 21. More banking use cases (2 minutes)

- Reuse the platform capabilities with different Agents, Knowledge and integrations.
- Every Agent still needs an owner, measurable outcome and lifecycle.

### 22. Governance (3 minutes)

- Explain defense in depth from identity through action.
- Enforce access and tool policy server-side and keep sensitive raw content out of audit records.

### 23. Pilot roadmap (2 minutes)

- Limit the pilot to one critical service and one accountable team.
- Capture the baseline before implementation and assess value, accuracy, adoption and controls at day 90.

### 24. Takeaways (1 minute)

- Repeat the three ideas: AI is a Layer, Evidence First and Control by Design.
- Tell the audience that the game draws directly from these ideas and the demo.

### 25. Game instructions (1 minute)

- Use Kahoot, Slido or A/B/C/D cards by table.
- Allow about 20 seconds to read, 15 seconds to answer and 10–15 seconds for the explanation.

### 26. Quiz 1 (45–60 seconds)

- Answer: B
- Why: Applied AI connects information into faster, safer and repeatable operational decisions.
- Record the score before moving to the next question.

### 27. Quiz 2 (45–60 seconds)

- Answer: C
- Why: Systems of Record stay authoritative while AI adds intelligence and orchestration.
- Record the score before moving to the next question.

### 28. Quiz 3 (45–60 seconds)

- Answer: B
- Why: The four stages are Sense, Understand, Recommend and Orchestrate.
- Record the score before moving to the next question.

### 29. Quiz 4 (45–60 seconds)

- Answer: C
- Why: Start with evidence and the incident scope before proposing any action.
- Record the score before moving to the next question.

### 30. Quiz 5 (45–60 seconds)

- Answer: A
- Why: Datadog supplies telemetry and event evidence such as RUM, APM, logs and infrastructure signals.
- Record the score before moving to the next question.

### 31. Quiz 6 (45–60 seconds)

- Answer: B
- Why: Knowledge adds approved procedures, owners and known fixes.
- Record the score before moving to the next question.

### 32. Quiz 7 (45–60 seconds)

- Answer: C
- Why: Auditable analysis includes a timeline, hypotheses, evidence, confidence and gaps.
- Record the score before moving to the next question.

### 33. Quiz 8 (45–60 seconds)

- Answer: B
- Why: Read-only pilots reduce operational risk while value and accuracy are measured.
- Record the score before moving to the next question.

### 34. Quiz 9 (45–60 seconds)

- Answer: A
- Why: Tool allowlists and least privilege are appropriate platform guardrails.
- Record the score before moving to the next question.

### 35. Quiz 10 (45–60 seconds)

- Answer: B
- Why: Policies affecting access and tools must be enforced at the server boundary.
- Record the score before moving to the next question.

### 36. Quiz 11 (45–60 seconds)

- Answer: B
- Why: MTTR directly reflects how quickly service is restored or resolved.
- Record the score before moving to the next question.

### 37. Quiz 12 (45–60 seconds)

- Answer: B
- Why: Decision visuals must trace back to exact successful tool results.
- Record the score before moving to the next question.

### 38. Quiz 13 (45–60 seconds)

- Answer: B
- Why: Read-only incident triage and briefing combine high readiness, measurable value and lower risk.
- Record the score before moving to the next question.

### 39. Quiz 14 (45–60 seconds)

- Answer: C
- Why: Audit should retain necessary metadata without raw prompts, credentials or sensitive tool outputs.
- Record the score before moving to the next question.

### 40. Quiz 15 (45–60 seconds)

- Answer: B
- Why: The core idea is connecting Evidence and Context to support governed human decisions.
- Record the score before moving to the next question.

### 41. Closing (1 minute)

- Announce the winning team and connect the game back to the 90-day pilot.
- Invite the customer to select one critical service for a NexoraAI + Datadog discovery workshop.

## Quiz answer key

| Question | Answer |
| ---: | :---: |
| 1 | B |
| 2 | C |
| 3 | B |
| 4 | C |
| 5 | A |
| 6 | B |
| 7 | C |
| 8 | B |
| 9 | A |
| 10 | B |
| 11 | B |
| 12 | B |
| 13 | B |
| 14 | C |
| 15 | B |
