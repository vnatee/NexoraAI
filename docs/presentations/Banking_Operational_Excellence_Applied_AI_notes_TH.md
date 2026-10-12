# Banking IT Outing — Speaker Notes ภาษาไทย

หัวข้อ: **Operational Excellence Through Applied AI to New IT Operational Capabilities**
รูปแบบ: เนื้อหา 45 นาที + เกม 15 นาที
ผู้ฟัง: ผู้บริหารระดับสูงและพนักงาน IT ประมาณ 120 คน

## Timing

- Slides 1–5: Opening and operational pressure — 8 minutes
- Slides 6–12: Applied AI and platform — 14 minutes
- Slides 13–21: Banking use cases and Datadog demo — 16 minutes
- Slides 22–24: Governance, roadmap and takeaways — 7 minutes
- Slides 25–40: Game — 15 minutes
- Slide 41: Closing — 1 minute or use inside Q&A buffer

## Slide-by-slide notes

### 1. สไลด์ 1 — เปิดเรื่อง (1 นาที)

- วันนี้ไม่ใช่การบรรยายว่า AI เก่งแค่ไหน แต่จะคุยว่า AI ทำให้ทีม IT ทำงานดีขึ้นอย่างไร
- กลุ่มผู้ฟังมีทั้งผู้บริหารและทีมปฏิบัติการ จึงจะเชื่อม Business Outcome กับ Technical Evidence
- ช่วงท้ายมีเกม 15 ข้อจากเนื้อหาที่พูด ขอให้สังเกตคำว่า Evidence, Context และ Guardrail

Transition: เริ่มจากปัญหาที่ทุกทีม IT เคยเจอร่วมกัน

### 2. สไลด์ 2 — Agenda (1 นาที)

- บอกผู้ฟังว่าจะมีทั้งมุมผู้บริหาร สถาปัตยกรรม และ demo
- เนื้อหาไม่ได้พยายามแทนที่เครื่องมือเดิม แต่เพิ่มความสามารถในการเชื่อมข้อมูลและตัดสินใจ

### 3. สไลด์ 3 — Opening poll (2 นาที)

- ให้ยกมือเลือกได้มากกว่าหนึ่งข้อ หรือให้แต่ละโต๊ะเลือกข้อหลัก
- เฉลยเชิงแนวคิดคือทุกข้อเกี่ยวข้องกัน ปัญหาไม่ได้อยู่ที่ไม่มีข้อมูล แต่อยู่ที่ข้อมูลไม่เชื่อมเป็นเรื่องเดียว
- ใช้คำตอบของผู้ฟังอ้างกลับในช่วง demo

Transition: Applied AI ต้องลดเวลาทั้ง Signal, Context, Knowledge และ Coordination

### 4. สไลด์ 4 — Business outcome (2 นาที)

- ผู้บริหารสนใจ reliability, risk และ capacity มากกว่า model benchmark
- AI use case ทุกตัวควรผูกกับตัววัด เช่น MTTR, false escalation, repeat incident และเวลาทำรายงาน
- คำว่า Capacity หมายถึงเพิ่มกำลังทีม ไม่ใช่ลดจำนวนคน

### 5. สไลด์ 5 — Banking reality (2 นาที)

- เน้นว่าความท้าทายไม่ใช่เฉพาะเทคโนโลยี แต่รวม operating model และ regulatory evidence
- ระบบธนาคารมี dependency สูง การมอง signal แยกส่วนจึงทำให้ diagnosis ช้า
- Applied AI เหมาะกับงานที่ต้องอ่านข้อมูลหลายชนิดและเชื่อมบริบท

### 6. สไลด์ 6 — AI evolution (2 นาที)

- Chat เป็นเพียง interface; คุณค่าจริงเกิดเมื่อ AI เข้าถึง Knowledge และเครื่องมือที่ได้รับอนุญาต
- คำว่า Act ไม่ได้แปลว่าให้ AI เปลี่ยน production ทันที การอนุมัติยังเป็น policy ขององค์กร
- Learn คือทำให้ผลการแก้ปัญหากลับมาเป็น Knowledge ที่ใช้ซ้ำได้

### 7. สไลด์ 7 — Applied AI in plain language (2 นาที)

- ใช้สี่คำนี้เป็น mental model ตลอดการนำเสนอ
- Sense มาจากระบบจริง เช่น Datadog; Understand ต้องมี business/technical context
- Recommend ต้องอ้าง evidence; Orchestrate ต้องผ่านสิทธิ์และ policy

### 8. สไลด์ 8 — Platform concept (3 นาที)

- อธิบายแพลตฟอร์มโดยไม่เริ่มจากชื่อเทคโนโลยี: เป็นชั้นกลางที่เชื่อมคน ความรู้ และระบบ
- Datadog, Service Desk, CMDB และ Knowledge ยังเป็นเจ้าของข้อมูลของตนเอง
- AI ต้องเรียกใช้ข้อมูลตามสิทธิ์ของทีมและบันทึก audit metadata

### 9. สไลด์ 9 — Platform capabilities (2 นาที)

- เน้นว่าการมี model อย่างเดียวไม่เท่ากับมี enterprise platform
- RAG ต้องรักษา ACL และ citation; Integration ต้องจำกัด connection/tool ตามทีม
- Guardrail และ Audit เป็น capability ของ platform ไม่ควรฝากไว้กับ prompt เพียงอย่างเดียว

### 10. สไลด์ 10 — Responsibility (2 นาที)

- ใช้สไลด์นี้ลดความกังวลว่า AI จะเข้ามาแทนระบบหรือผู้รับผิดชอบ
- AI ไม่ควรเปลี่ยนข้อมูลสำคัญโดยข้าม validation ของ system of record
- เริ่มจาก read-only recommendation แล้วค่อยเพิ่ม action เมื่อ control พร้อม

### 11. สไลด์ 11 — Maturity (2 นาที)

- Pilot ที่ดีควรเริ่มระดับ Analyze/Recommend ซึ่งให้คุณค่าสูงและความเสี่ยงต่ำกว่า write automation
- แต่ละขั้นต้องมี acceptance criteria และ owner ชัดเจน
- Demo วันนี้อยู่ระดับ Analyze และ Recommend

### 12. สไลด์ 12 — Use-case portfolio (2 นาที)

- นี่คือกรอบให้คะแนนภายในที่เปิดเผยวิธีคิด ไม่ใช่ผลสำรวจหรือ benchmark ของอุตสาหกรรมธนาคาร
- ให้ทีมลูกค้าให้คะแนนแต่ละเกณฑ์ 1–5 ใน discovery workshop; น้ำหนัก 35/30/20/15 เป็นค่าเริ่มต้นที่เสนอและปรับได้เมื่อเจ้าของบริการเห็นชอบ
- คะแนนตัวอย่างสมมติว่ามี Datadog telemetry แบบ read-only; ความพร้อมของ Knowledge, Change และ approval ต้องตรวจสอบกับข้อมูลจริง
- NIST AI RMF ใช้อ้างอิงแนวคิด risk/control และ Google SRE ใช้อ้างอิงแนวคิด incident response/operational outcomes; ทั้งสองแหล่งไม่ได้กำหนดสูตรหรือน้ำหนักนี้
- ก่อนนำไปใช้ตัดสินใจจริง ให้บันทึกเจ้าของคะแนน หลักฐาน วันที่ประเมิน และเหตุผลของคะแนนทุกช่อง

### 13. สไลด์ 13 — Morning briefing (2 นาที)

- แทนที่จะเปิด dashboard หลายหน้า ผู้บริหารได้ summary ที่มี link กลับไปยัง evidence
- AI ไม่ควรซ่อน uncertainty ต้องระบุข้อมูลที่ยังขาด
- เหมาะเป็น use case แรกเพราะเป็น read-only และวัดเวลาที่ประหยัดได้ง่าย

### 14. สไลด์ 14 — Incident story (2 นาที)

- ให้ผู้ฟังจินตนาการเหตุการณ์ที่คุ้นเคย ไม่ต้องใช้ข้อมูลลูกค้าจริง
- ประเด็นสำคัญคือ user symptom ไม่ได้บอก root cause
- AI ที่ดีต้องแตกคำถามและรู้ว่าควรเรียก evidence ใด

Transition: ต่อไปคือภาพการเชื่อม evidence ที่เป็นหัวใจของ demo

### 15. สไลด์ 15 — Correlation visual (3 นาที)

- Datadog ให้ telemetry ที่ละเอียด ส่วน Knowledge/Change เติมบริบทที่ telemetry อย่างเดียวไม่มี
- Agent ไม่ควรเดา root cause จาก alert เดียว แต่ต้องจัดลำดับ hypothesis พร้อมหลักฐานสนับสนุนและหลักฐานที่ขัดแย้ง
- ผลลัพธ์สุดท้ายต้องบอก gap และ confidence ไม่ใช่ตอบอย่างมั่นใจเกินจริง

### 16. สไลด์ 16 — Demo flow (1 นาที)

- แจ้งว่าจะใช้ข้อมูลสาธิตและ Agent แบบ read-only
- ถ้า live connection ไม่พร้อม ให้ใช้ screenshot/video fallback โดยบอกผู้ฟังอย่างตรงไปตรงมา
- จับเวลารวม demo ไม่เกิน 8 นาที

### 17. สไลด์ 17 — Demo 1 — เริ่มจากสถานการณ์ปัจจุบัน (1–2 นาที)

- อ่าน prompt ให้ผู้ฟังเห็นว่าเป็นภาษาธรรมดา ไม่ต้องรู้ชื่อ query หรือ dashboard
- ชี้ผลลัพธ์ที่คาดหวัง: Executive summary, time window, affected service และ evidence links
- ชี้แหล่งหลักฐาน: Datadog monitor/event results พร้อม timestamp

### 18. สไลด์ 18 — Demo 2 — เปลี่ยนข้อมูลเป็นภาพ (1–2 นาที)

- อ่าน prompt ให้ผู้ฟังเห็นว่าเป็นภาษาธรรมดา ไม่ต้องรู้ชื่อ query หรือ dashboard
- ชี้ผลลัพธ์ที่คาดหวัง: กราฟที่อ่านง่ายและไม่มีตัวเลขที่ model สร้างเอง
- ชี้แหล่งหลักฐาน: Exact successful Datadog tool output

### 19. สไลด์ 19 — Demo 3 — เชื่อม Datadog กับ Knowledge (1–2 นาที)

- อ่าน prompt ให้ผู้ฟังเห็นว่าเป็นภาษาธรรมดา ไม่ต้องรู้ชื่อ query หรือ dashboard
- ชี้ผลลัพธ์ที่คาดหวัง: Ranked hypotheses, confidence, gap, owner และ approval boundary
- ชี้แหล่งหลักฐาน: Datadog evidence + authorized Change/Runbook Knowledge

### 20. สไลด์ 20 — Demo result (2 นาที)

- ตัวเลขบนสไลด์เป็นตัวอย่างรูปแบบผลลัพธ์ ไม่ใช่ข้อมูลจริงของธนาคาร
- ชี้ว่าคำแนะนำผูกกับ evidence chain และมี confidence/gap
- Action ที่เปลี่ยน production ต้องมี owner และ approval

### 21. สไลด์ 21 — More banking use cases (2 นาที)

- แต่ละ use case ใช้ platform capability เดิม แต่เปลี่ยน Agent, Knowledge และ Integration
- เริ่มจาก use case ที่ read-only และมีข้อมูลพร้อม
- ไม่ควรสร้าง agent จำนวนมากโดยไม่มี owner, metric และ lifecycle

### 22. สไลด์ 22 — Governance (3 นาที)

- อธิบาย defense in depth ตั้งแต่ใครเรียก ไปจนถึง action ใดได้รับอนุญาต
- Audit ที่ดีเก็บ metadata ที่จำเป็น โดยไม่เก็บ raw prompt, credential หรือ tool output ที่อ่อนไหว
- สำหรับธนาคารควรเริ่ม read-only, least privilege และ segregation of duties

### 23. สไลด์ 23 — Pilot roadmap (2 นาที)

- จำกัด pilot ให้หนึ่ง critical service และหนึ่งทีม owner
- เก็บ baseline ก่อนเริ่ม เช่น investigation time, MTTR, repeat incident และเวลาเตรียม briefing
- Scale decision ต้องดูทั้ง value, accuracy, adoption และ control evidence

### 24. สไลด์ 24 — Takeaways (1 นาที)

- ทวนสามคำสำคัญ: Layer, Evidence, Control
- บอกผู้ฟังว่าคำถามในเกมทั้งหมดมาจากหลักการเหล่านี้และ demo

Transition: เข้าสู่เกม 15 ข้อ

### 25. สไลด์ 25 — Game instructions (1 นาที)

- หากไม่มีระบบตอบคำถาม ใช้วิธีให้แต่ละโต๊ะยกกระดาษ A/B/C/D
- เฉลยอยู่ใน Speaker Notes ของแต่ละข้อ
- ควรใช้เวลาอ่าน 20 วินาที ตอบ 15 วินาที และเฉลยสั้น 10–15 วินาที

### 26. สไลด์ 26 — Quiz 1 (45–60 วินาที)

- คำตอบ: B
- เหตุผล: Applied AI เน้น Faster understanding, safer decision และ repeatable operation
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 27. สไลด์ 27 — Quiz 2 (45–60 วินาที)

- คำตอบ: C
- เหตุผล: ระบบเดิมยังเป็นเจ้าของข้อมูลจริง ส่วน AI เชื่อม context และ workflow
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 28. สไลด์ 28 — Quiz 3 (45–60 วินาที)

- คำตอบ: B
- เหตุผล: เป็น mental model สี่ขั้นที่ใช้ตลอดการนำเสนอ
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 29. สไลด์ 29 — Quiz 4 (45–60 วินาที)

- คำตอบ: C
- เหตุผล: ต้องเริ่มจากหลักฐานและขอบเขตเหตุการณ์ก่อนแนะนำ action
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 30. สไลด์ 30 — Quiz 5 (45–60 วินาที)

- คำตอบ: A
- เหตุผล: Datadog ให้ RUM, APM, logs, infrastructure/database signals และ events
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 31. สไลด์ 31 — Quiz 6 (45–60 วินาที)

- คำตอบ: B
- เหตุผล: KM เติม operational context และวิธีปฏิบัติที่ผ่านการรับรอง
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 32. สไลด์ 32 — Quiz 7 (45–60 วินาที)

- คำตอบ: C
- เหตุผล: ผลลัพธ์ต้องตรวจสอบย้อนกลับและแสดง uncertainty
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 33. สไลด์ 33 — Quiz 8 (45–60 วินาที)

- คำตอบ: B
- เหตุผล: Analyze/Recommend ให้คุณค่าสูงโดยยังไม่เสี่ยงกับ production write action
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 34. สไลด์ 34 — Quiz 9 (45–60 วินาที)

- คำตอบ: A
- เหตุผล: สิทธิ์และ tool policy ต้องจำกัดตามผู้ใช้ ทีม และ use case
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 35. สไลด์ 35 — Quiz 10 (45–60 วินาที)

- คำตอบ: B
- เหตุผล: Server-side enforcement เป็น security boundary ที่ตรวจสอบได้
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 36. สไลด์ 36 — Quiz 11 (45–60 วินาที)

- คำตอบ: B
- เหตุผล: Mean Time to Restore/Resolve สะท้อนความเร็วในการกู้บริการ
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 37. สไลด์ 37 — Quiz 12 (45–60 วินาที)

- คำตอบ: B
- เหตุผล: Visualization ต้อง trace กลับไปยังผลลัพธ์จากระบบจริง
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 38. สไลด์ 38 — Quiz 13 (45–60 วินาที)

- คำตอบ: B
- เหตุผล: ข้อมูลพร้อม วัดผลได้ และความเสี่ยงต่ำกว่า write automation
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 39. สไลด์ 39 — Quiz 14 (45–60 วินาที)

- คำตอบ: C
- เหตุผล: เก็บ metadata ที่จำเป็นโดยไม่สร้างแหล่งข้อมูลอ่อนไหวใหม่
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 40. สไลด์ 40 — Quiz 15 (45–60 วินาที)

- คำตอบ: B
- เหตุผล: เป็น core message ของ Operational Excellence Through Applied AI
- ให้คะแนนก่อนเลื่อนไปข้อถัดไป

### 41. สไลด์ 41 — Closing (1 นาที)

- ประกาศทีมชนะและเชื่อมกลับไปยัง 90-day pilot
- ปิดด้วยข้อเสนอให้เลือกหนึ่ง critical service สำหรับ workshop ถัดไป
- หากต้องการขายแพลตฟอร์ม ให้เปลี่ยน Next Conversation เป็นชื่อ workshop และช่องทางติดต่อจริงก่อนนำเสนอ

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
