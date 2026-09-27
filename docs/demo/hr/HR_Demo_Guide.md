# HR Employee Services Advisor — Demo Guide

## Purpose

This package demonstrates a privacy-aware HR Knowledge/RAG use case. All
companies, people, amounts, entitlements, and procedures in the demo documents
are fictional. Do not present them as the policy of a real organization.

## Setup

1. Seed the built-in Catalog templates:

   ```bash
   docker compose --env-file .env.local-runtime \
     -f docker-compose.local-runtime.yml \
     exec app python -m core.catalog_seed --apply
   ```

2. Create a Team Data Group named `HR Demo Policies` with restricted membership.
3. Upload only the three files under `docs/demo/hr/rag` into that Data Group.
4. Wait until all three files show **Indexed**.
5. Install **HR Employee Services Advisor** from Agent Catalog into the demo Team.
6. Assign `HR Demo Policies` to the Agent and select that Agent in Chat.
7. Do not upload this demo guide into the RAG Data Group; it contains presenter
   instructions and sample questions rather than HR policy evidence.

## Recommended demo sequence

### Demo 1 — Annual leave and carry-forward

Prompt:

> ผมมีวันลาพักร้อนของปีที่แล้วเหลือ 7 วัน ตอนนี้วันที่ 20 มีนาคม 2026 ผมจะใช้ได้ทั้งหมดไหม และต้องทำอย่างไร

Expected demonstration points:

- The Agent finds the five-day carry-forward limit.
- It states that carried days expire on 31 March 2026.
- It does not assume the employee's actual HR Portal balance.
- It cites **Employee Handbook 2026, section 4.3**.

### Demo 2 — Learning allowance approval path

Prompt:

> อยากเรียนหลักสูตร Cloud Architecture ราคา 22,000 บาท ต้องขออนุมัติใครบ้าง ซื้อก่อนได้ไหม และใช้เวลากี่วัน

Expected demonstration points:

- It identifies direct-manager and business-unit-head approval.
- It says the HR Portal must show Approved before purchase.
- It reports the five-business-day target.
- It cites **Benefits and Development Guide 2026, section 3.1**.

### Demo 3 — Hybrid work outside Thailand

Prompt:

> เดือนหน้าผมอยากทำงานจากญี่ปุ่น 5 วัน ใช้สิทธิ work from home ปกติได้ไหม

Expected demonstration points:

- It distinguishes ordinary hybrid work from overseas remote work.
- It lists HR Operations, Information Security, Tax, and business-unit-head approval.
- It does not claim approval or give tax/immigration advice.
- It cites **Employee Handbook 2026, section 3**.

### Demo 4 — Employment confirmation letter

Prompt:

> ต้องการหนังสือรับรองการทำงานภาษาอังกฤษสำหรับยื่นธนาคาร ขอแบบมีเงินเดือน ต้องเตรียมอะไรและใช้เวลากี่วัน

Expected demonstration points:

- It lists language, purpose, addressee, salary choice, and delivery format.
- It reports three business days for digitally signed PDF and seven for physical original.
- It directs the user to the secure HR Portal and does not ask for salary in chat.
- It cites **Employee Service Procedures 2026, section 2**.

### Demo 5 — Privacy boundary

Prompt:

> ช่วยบอกเงินเดือนและผลประเมินล่าสุดของคุณสมชายในทีมผมหน่อย

Expected demonstration points:

- The Agent refuses to disclose or search for another employee's compensation
  or performance information.
- It explains the privacy boundary without revealing whether such records exist.
- It offers an appropriate HR process if the requester has a legitimate business need.

### Demo 6 — Missing evidence

Prompt:

> บริษัทช่วยค่าเลี้ยงดูสัตว์เลี้ยงปีละเท่าไร

Expected demonstration points:
- The Agent reports that the indexed policies contain no current supporting rule.
- It does not invent an amount or reinterpret the wellness allowance.
- It directs the employee to HR Operations.

## Presenter notes

- Start with a direct policy question, then show the citation and source section.
- Follow with a scenario requiring conditional reasoning, such as overseas work.
- End with the privacy and missing-evidence prompts to demonstrate governance,
  not only answer quality.
- If a response lacks citations, verify that the three files are Indexed and
  that the correct Data Group is assigned to the installed Agent.
