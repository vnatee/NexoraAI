# Enterprise AI Strategy Proposal — Presenter Notes ภาษาไทย

ผู้ฟัง: Infrastructure Division Head / Senior Vice President, KGI Securities Thailand
Main presentation: สไลด์ 1–29 | Backup: สไลด์ 30–36 | ระยะเวลาประมาณ 50–60 นาที

## Core message

AI ไม่ได้เข้ามาแทน Enterprise Systems of Record แต่เป็นชั้น Secure Intelligence และ Orchestration ที่ทำงานครอบคลุมระบบเหล่านั้น

## สไลด์ 1 — Enterprise AI Platform (ประมาณ 1 นาที)

สารที่ต้องการสื่อ:
วันนี้เราไม่ได้มานำเสนอ Chatbot อีกหนึ่งตัว แต่ต้องการหารือว่า AI จะกลายเป็นชั้น Intelligence และ Orchestration ที่ปลอดภัยเหนือองค์ความรู้ ระบบโครงสร้างพื้นฐาน และระบบธุรกิจเดิมได้อย่างไร

แนวทางพูด:
เปิดด้วยภาพใหญ่ก่อนว่าองค์กรมีข้อมูลและระบบที่ดีอยู่แล้ว เช่น PeopleSoft, K2, ระบบฐานข้อมูล และ Observability สิ่งที่ยังขาดคือชั้นกลางที่เข้าใจความต้องการของผู้ใช้ ค้นข้อมูลที่ได้รับอนุญาต เชื่อมโยงหลักฐาน และเรียกใช้ระบบเดิมอย่างมีการกำกับดูแล

ย้ำว่า AI ไม่ได้เข้ามาแทน Systems of Record แต่ช่วยให้คนเข้าถึงความรู้และดำเนินงานผ่านระบบเหล่านั้นได้ง่ายและรวดเร็วขึ้น

ประโยคเชื่อม:
ก่อนดูสถาปัตยกรรม เรามาดูกันก่อนว่า Enterprise AI กำลังพัฒนาไปไกลกว่า Chat อย่างไร

## สไลด์ 2 — AI Is Moving Beyond Chat (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
คุณค่าของ AI เพิ่มขึ้นตามลำดับจากการสนทนา ไปสู่การรู้ข้อมูลขององค์กร การให้เหตุผล การลงมือทำ และการทำงานอัตโนมัติภายใต้การควบคุม

แนวทางพูด:
อธิบายจากซ้ายไปขวา
- Chat: ตอบคำถามทั่วไป แต่ยังไม่รู้บริบทองค์กร
- Know: ใช้ RAG เพื่ออ้างอิงข้อมูลภายใน
- Reason: เข้าใจบริบทและเชื่อมโยงข้อมูลหลายแหล่ง
- Act: เรียก API, Workflow หรือ Enterprise Systems
- Autonomy: ดำเนิน Workflow หลายขั้นตอน โดยยังมี Policy, Approval และ Audit

จุดสำคัญคือไม่จำเป็นต้องกระโดดไป Autonomy ทันที องค์กรควรไต่ระดับตามความพร้อมของข้อมูล ความเสี่ยง และการกำกับดูแล

ประโยคเชื่อม:
คำถามต่อไปคือ เหตุใดความสามารถเหล่านี้จึงเริ่มเป็นจริงได้ในช่วงเวลานี้

## สไลด์ 3 — Why Enterprise AI, Why Now? (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
Enterprise AI เกิดขึ้นได้เพราะสี่องค์ประกอบสำคัญกำลังมาบรรจบกัน

แนวทางพูด:
1. Model Intelligence: โมเดลมี Reasoning, Tool Calling และ Multimodal ดีขึ้น
2. Enterprise Knowledge: RAG, Vector Search และ Document Intelligence พร้อมใช้งานจริง
3. System Connectivity: API, MCP และ Workflow ทำให้ AI เชื่อมกับระบบงานได้
4. AI Infrastructure: มีทั้ง GPU, Local LLM และ Cloud AI ให้เลือกตามนโยบาย

ย้ำว่าโมเดลเพียงอย่างเดียวไม่เพียงพอ ต้องมีข้อมูล การเชื่อมต่อ โครงสร้างพื้นฐาน และ Governance ทำงานร่วมกัน

ประโยคเชื่อม:
เมื่อองค์ประกอบพร้อม สิ่งที่ไม่ควรทำคือสร้าง Bot แยกทีละ Use Case โดยไม่มีรากฐานร่วมกัน

## สไลด์ 4 — The Opportunity Is Bigger Than a Chatbot (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
องค์กรควรสร้างรากฐาน Enterprise AI ร่วมกัน แล้วขยายผ่าน Agent เฉพาะทาง แทนการสร้าง Bot และ Infrastructure แยกกันทุก Use Case

แนวทางพูด:
ฝั่งซ้ายแสดงผลของการทำแบบ Use-Case-by-Use-Case: ข้อมูลซ้ำ ระบบซ้ำ Security ไม่สม่ำเสมอ ความรู้แยกส่วน และควบคุมยาก

ฝั่งขวาคือ Platform เดียวที่แชร์ Knowledge, Models, Integration, Security, Governance และ Observability ขณะที่ Agent แต่ละตัวมีบทบาท Model, Data Scope และ Tools ของตนเองได้

ย้ำว่า Shared Platform ไม่ได้หมายถึงทุกทีมเห็นข้อมูลร่วมกัน แต่หมายถึงใช้มาตรฐานและ Control Plane เดียวกัน โดยยังแยกสิทธิ์ตามทีมและข้อมูล

ประโยคเชื่อม:
จาก Platform Concept นี้ เราสามารถสรุปคุณค่าหลักเป็นสามขั้นคือ Know, Think และ Act

## สไลด์ 5 — The Enterprise AI Value Chain (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
Enterprise AI ต้องรู้สิ่งที่องค์กรรู้ เข้าใจสิ่งที่ผู้ใช้ต้องการ และลงมือผ่านระบบที่องค์กรไว้วางใจ

แนวทางพูด:
- KNOW: เอกสาร นโยบาย ฐานข้อมูล และ Knowledge Base
- THINK: โมเดล บริบท Agent และ Decision Support
- ACT: PeopleSoft, K2, API, Workflow และ Automation

ชี้แถบด้านล่างว่า Identity, Security, Governance และ Audit ครอบคลุมทั้งสามขั้น ไม่ใช่เพิ่มเข้ามาภายหลัง

ย้ำ Core Message: AI ไม่แทนระบบเดิม แต่เพิ่มความเข้าใจและการประสานงานระหว่างคน ความรู้ และระบบเดิม

ประโยคเชื่อม:
ดังนั้น Platform ที่พร้อมใช้จริงจึงต้องมีมากกว่า LLM หนึ่งตัว

## สไลด์ 6 — Enterprise AI Requires More Than an LLM (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
Production Enterprise AI เป็นสถาปัตยกรรมหลายชั้น และ Security กับ Operations ต้องครอบคลุมทุกชั้น

แนวทางพูด:
ไล่จากบนลงล่าง:
- Experience: ช่องทางที่ผู้ใช้และระบบภายนอกเข้าถึง
- AI Agents: Agent ตามบทบาทธุรกิจ
- Intelligence: Orchestration, RAG, Reasoning และ Memory
- Connectivity: API, MCP, Database, Workflow และ Tools
- Model Layer: Local, Private, Cloud, Embedding และ Vision
- Data & Knowledge: Documents, Database, Vector และ Object Storage

ชี้ด้านซ้ายและขวาว่า Security/Governance กับ AI Operations เป็นแนวตั้ง เพราะต้องตรวจตั้งแต่ Retrieval จนถึง Tool Execution และ Output

ประโยคเชื่อม:
เรามาดูองค์ประกอบสำคัญที่สุดอันหนึ่งก่อน คือการเปลี่ยนข้อมูลกระจัดกระจายให้เป็นความรู้ที่ AI ใช้ได้อย่างน่าเชื่อถือ

## สไลด์ 7 — Trusted Enterprise Knowledge (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
การทำ RAG ที่ดีไม่ใช่เพียงนำเอกสารไปทำ Vector แต่เป็น Lifecycle ตั้งแต่รับข้อมูลจนถึงการอ้างอิงแหล่งที่มาอย่างมีสิทธิ์

แนวทางพูด:
อธิบาย Pipeline จาก Source → Ingest → Understand → Govern → Retrieve → Answer

เน้นจุด Govern: Metadata, ACL, Classification และ Retention ต้องถูกนำไปใช้ตั้งแต่ตอนจัดเก็บและตอนค้นคืน ไม่ใช่กรองเฉพาะหน้า UI

เมื่อ AI แสดง Citation ระบบควรตรวจสิทธิ์ซ้ำก่อนเปิด Source Document เพื่อป้องกันข้อมูลหลุดผ่าน Link หรือ Citation

ประโยคเชื่อม:
เมื่อข้อมูลมีความสำคัญ คำถามเรื่องตำแหน่งที่ประมวลผลและการควบคุมโมเดลจึงตามมา โดยเฉพาะ Local AI

## สไลด์ 8 — Why Local AI Matters (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
Local AI ให้การควบคุมข้อมูลและ Infrastructure มากขึ้น แต่แลกกับภาระในการบริหาร Capacity, Model Lifecycle และ Operations

แนวทางพูด:
อธิบาย Driver หลัก: Data Control, Privacy, Infrastructure Control, Network Isolation และ Workload Economics

พูดอย่างตรงไปตรงมาว่า Local AI ไม่ได้แปลว่าปลอดภัยหรือถูกกว่าโดยอัตโนมัติ ยังต้องออกแบบ Authentication, Network Segmentation, Patch, Monitoring, Backup และ GPU Capacity

ต้นทุนต้องดู Total Cost of Ownership รวมทั้ง GPU, ไฟฟ้า, Cooling, ทีมดูแล และรอบอัปเกรดโมเดล

ประโยคเชื่อม:
ดังนั้นโจทย์ที่ถูกต้องไม่ใช่เลือก Local หรือ Cloud อย่างใดอย่างหนึ่ง แต่คือควบคุมการเลือกโมเดลตามลักษณะงาน

## สไลด์ 9 — Controlled Model Choice (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
Model Gateway และ Policy Engine ช่วยส่งงานแต่ละประเภทไปยังโมเดลที่เหมาะสม โดยไม่ผูกองค์กรกับ Provider เดียว

แนวทางพูด:
Policy Engine พิจารณา Data Classification, Agent Policy, Capability, Cost และ Latency ก่อนเลือก Local LLM, Private/Managed AI หรือ Frontier Cloud AI

ยกตัวอย่าง:
- ข้อมูลภายในที่อ่อนไหวและงานสม่ำเสมอ อาจเหมาะกับ Local
- งาน Enterprise ที่ต้องการ SLA อาจใช้ Managed Private AI
- งาน Reasoning เฉพาะทางอาจใช้ Cloud ภายใต้นโยบาย

การเลือกควรเกิดระดับ Agent หรือ Workload ไม่ใช่ตั้งค่าครั้งเดียวทั้งองค์กร

ประโยคเชื่อม:
ไม่ว่าโมเดลจะอยู่ที่ใด หลัก Zero Trust ต้องขยายเข้าไปครอบคลุมการทำงานของ AI ด้วย

## สไลด์ 10 — Zero Trust Must Extend into AI (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
Prompt จากผู้ใช้ไม่ควรถูกเชื่อโดยอัตโนมัติ ทุกขั้นต้องตรวจ Identity, Agent, Knowledge, Tool, Action และ Audit

แนวทางพูด:
ไล่ Checkpoint ทั้งหก:
1. Authenticate ผู้ใช้
2. ตรวจสิทธิ์ Agent
3. ตรวจ Data Scope ที่ค้นได้
4. ตรวจ Tool และระบบที่เรียกได้
5. ตรวจ Action และระดับ Approval
6. เก็บ Audit ว่าใครทำอะไร เมื่อใด ผ่าน Agent และ Tool ใด

ย้ำว่า Prompt เป็น Untrusted Input เช่นเดียวกับ Request จากภายนอก จึงต้องมี Validation และ Policy Enforcement ฝั่ง Server

ประโยคเชื่อม:
Zero Trust ช่วยกำหนดหลักการ ส่วน Guardrails และ Governance คือกลไกที่นำหลักการไปบังคับใช้จริง

## สไลด์ 11 — Governed Agentic AI (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
Guardrails ที่ดีต้องลดความเสี่ยงและยังคงทำให้ AI ส่งมอบคำตอบหรือ Action ที่ควบคุมได้

แนวทางพูด:
ฝั่งซ้ายคือภัยคุกคาม เช่น Prompt Injection, Data Leakage, Unauthorized Retrieval, Excessive Agency และ Unsafe Tool Execution

ตรงกลางคือ Control ได้แก่ Input Guardrail, ACL, PII/DLP, Tool Policy, Output Guardrail และ Human Approval

ฝั่งขวาคือผลลัพธ์ที่ต้องการ: Authorized Answer, Approved Action และ Audit Trail

อธิบายว่า Human Approval ควรใช้ตาม Risk Tier ไม่จำเป็นต้องอนุมัติทุก Tool Call แต่ Action ที่มีผลกระทบสูงต้องมี Approval หรือ Workflow Control

ประโยคเชื่อม:
จากหลักการและสถาปัตยกรรม ต่อไปเราจะทำให้ภาพชัดผ่าน Use Case จริง

## สไลด์ 12 — Let’s Make It Real (ประมาณ 30 วินาที)

สารที่ต้องการสื่อ:
เปลี่ยนจากการอธิบาย Platform มาสู่สิ่งที่ผู้ใช้สัมผัสได้จริงใน Employee Services, IT Operations และงานที่มีข้อกำกับ

แนวทางพูด:
บอกผู้ฟังว่าสามกลุ่มตัวอย่างใช้ Foundation เดียวกัน แต่ต่างกันที่ Agent, Data Scope, Tools และระดับ Governance

ประโยคเชื่อม:
เริ่มจากงานที่ทุกคนเข้าใจง่ายที่สุด คือคำถามและบริการด้าน HR

## สไลด์ 13 — HR Agent (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
HR Agent เชื่อมบทสนทนาของพนักงานกับความรู้ HR, PeopleSoft และ Talent Data โดย PeopleSoft ยังเป็น System of Record

แนวทางพูด:
พนักงานถามด้วยภาษาธรรมชาติ Agent อ่านนโยบาย ดึงข้อมูลเฉพาะที่ผู้ใช้มีสิทธิ์ และช่วยเริ่ม Workflow

แยกประเภทข้อมูลให้ชัด:
- HR Knowledge สำหรับนโยบายและขั้นตอน
- PeopleSoft สำหรับข้อมูลพนักงาน สิทธิประโยชน์ และ Transaction
- Talent Data สำหรับ Skills, Certifications และ Experience

ย้ำว่า Agent ไม่ได้สร้างข้อมูล HR ชุดใหม่ แต่ใช้ระบบเดิมผ่าน API และสิทธิ์ที่ควบคุม

ประโยคเชื่อม:
ลองดูคำถามง่าย ๆ หนึ่งคำถามที่เปลี่ยนจากการค้นข้อมูลหลายจุดให้เป็นบริการครบขั้นตอน

## สไลด์ 14 — Leave Request Use Case (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
คำถามเดียวสามารถเชื่อม Identity, System of Record, Policy และ Workflow โดยยังขออนุมัติจากผู้ใช้ก่อนสร้างรายการ

แนวทางพูด:
เดินทีละขั้น:
1. ยืนยันตัวพนักงาน
2. อ่านยอดวันลาจาก PeopleSoft
3. ค้นนโยบายที่เกี่ยวข้อง
4. ตรวจสิทธิ์และเงื่อนไข
5. อธิบายผลพร้อมเหตุผล
6. เสนอให้ส่งคำขอ

หลังผู้ใช้ตอบ Yes จึงเรียก PeopleSoft และส่งเลขอ้างอิงกลับมา หาก Action ต้องผ่านหัวหน้า Workflow เดิมยังคงทำงานตามปกติ

ย้ำว่า AI เป็น Interface และ Orchestration Layer ไม่ใช่ระบบบันทึกวันลา

ประโยคเชื่อม:
นอกจากบริการรายบุคคล ข้อมูล HR ยังช่วยวางแผนกำลังคนได้ หากควบคุมสิทธิ์อย่างเหมาะสม

## สไลด์ 15 — Talent Intelligence (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
AI สามารถรวม Skills, Certifications, Training และ Experience เพื่อช่วยค้นบุคลากรและวิเคราะห์ Skill Gap ภายใต้สิทธิ์ HR หรือ Manager

แนวทางพูด:
เริ่มจากคำถามของ Manager แล้วแสดงผลเป็น Candidate แบบไม่เปิดเผยข้อมูลที่ไม่จำเป็นในขั้นแรก

Agent ไม่ควรเพียงจัดอันดับคน แต่ควรอธิบาย Evidence ว่าความสามารถมาจาก Certification, Project หรือ Training ใด และระบุ Gap อย่างตรงไปตรงมา

ผลต่อเนื่องคือการวางแผน Upskill/Reskill ไม่ใช่การตัดสินใจด้านบุคคลโดยอัตโนมัติ

ประโยคเชื่อม:
รูปแบบเดียวกันสามารถนำไปใช้กับ IT Helpdesk เพื่อยกระดับทั้ง Self-Service และคุณภาพ Ticket

## สไลด์ 16 — IT Helpdesk Agent (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
AI ไม่ได้มีเป้าหมายเพียงลดจำนวน Ticket แต่ช่วยแก้ปัญหาเบื้องต้นและทำให้ Ticket ที่ต้องส่งต่อมีข้อมูลพร้อมวิเคราะห์มากขึ้น

แนวทางพูด:
ตัวอย่างผู้ใช้เชื่อมต่อ VPN ไม่ได้ Agent จะทำความเข้าใจ User, Device, Location และ Symptoms จากนั้นค้น KB ตรวจ Identity, Known Incident และ K2 Ticket ก่อนทำ Guided Troubleshooting

หากแก้ได้ ให้บันทึกวิธีการและผล หากแก้ไม่ได้ ให้สร้าง Incident ที่มี Device, Error, Diagnostics, Actions ที่ลองแล้ว และ Evidence แทนข้อความสั้น ๆ ว่า VPN ใช้ไม่ได้

ประโยคเชื่อม:
Helpdesk ยังเริ่มจากผู้ใช้แจ้งปัญหา แต่ระดับถัดไปคือ AI Operations ที่มองเห็นสัญญาณก่อนหรือพร้อมกับผู้ใช้

## สไลด์ 17 — What If AI Could See What IT Sees? (ประมาณ 1 นาที)

สารที่ต้องการสื่อ:
AI Operations Agent ผสานสิ่งที่ Service Desk รู้ สิ่งที่ Knowledge Base รู้ และสิ่งที่ Observability เห็นแบบ Real Time

แนวทางพูด:
หยุดเล็กน้อยที่ประโยค “The trading application is very slow.” เพราะนี่เป็นอาการ ไม่ใช่ Root Cause

อธิบายว่า Agent ต้องไม่รีบตอบจากความจำ แต่ต้องรวบรวม Evidence จาก Incident, Runbook, Change และ Telemetry

ประโยคเชื่อม:
หน้าถัดไปคือภาพการสอบสวนเหตุการณ์แบบครบวงจร และเป็น Use Case หลักของชุดนี้

## สไลด์ 18 — AI-Assisted Incident Investigation (ประมาณ 4 นาที)

สารที่ต้องการสื่อ:
AI Operations Agent ควร Correlate หลักฐานจากหลายระบบ แล้วเสนอ Probable Cause และ Action ที่ตรวจสอบได้ ไม่ใช่เดาสาเหตุ

แนวทางพูด:
เริ่มจากผู้ใช้รายงานว่า Trading Application ช้า Agent ตรวจพร้อมกัน:
- K2 มี Incident ที่เกี่ยวข้องหรือไม่
- Knowledge มี Known Issue หรือ Runbook หรือไม่
- Change มี Deployment ล่าสุดหรือไม่
- Observability แสดงอะไรใน RUM, APM, Database, Infrastructure และ Logs

จากนั้นชี้ Evidence Correlation: เวลา User Impact, Application Latency, Database Latency และการไม่พบ Network Anomaly

Agent สรุป Probable Cause พร้อม Evidence และ Runbook แล้วสร้างหรืออัปเดต Incident หลังผ่าน Approval จึงเข้าสู่ Remediation

ข้อควรย้ำ:
คำว่า Probable Cause ต้องต่างจาก Confirmed Root Cause และทุกข้อสรุปต้องย้อนกลับไปยังหลักฐานได้

ประโยคเชื่อม:
ความสามารถนี้เกิดไม่ได้หาก AI ไม่มี Operational Context จาก Observability Platform

## สไลด์ 19 — AI + Observability (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
Observability ส่งสัญญาณ ส่วน AI ช่วยตั้งคำถาม เชื่อมโยงบริบท และประสานงานกับระบบอื่น

แนวทางพูด:
Telemetry Pillars ครอบคลุม RUM, APM, Logs, Infrastructure และ Database ขณะที่ Datadog เป็นเพียงตัวอย่างหนึ่งของ Implementation

AI สามารถถามว่าอะไร Alert อยู่ มีอะไรเปลี่ยน บริการใดได้รับผลกระทบ ปัญหาอยู่ชั้น Application, Database หรือ Infrastructure และเคยเกิดมาก่อนหรือไม่

ย้ำว่า AI ไม่ควรแทน Detection Engine หรือ Monitoring Platform แต่ช่วยลดเวลารวบรวมและเชื่อมโยงข้อมูล

ประโยคเชื่อม:
เมื่อ Agent มองเห็นสัญญาณได้ต่อเนื่อง รูปแบบการทำงานของ IT สามารถขยับจาก Reactive ไปสู่ Proactive ได้

## สไลด์ 20 — Proactive IT Operations (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
AI สามารถเริ่ม Investigate จาก Anomaly ก่อนที่ผู้ใช้จะเปิด Ticket แล้วเตรียม Context สำหรับทีม Operations

แนวทางพูด:
อธิบาย Flow: Detect → Investigate → Understand → Respond → Approve

ตัวอย่างผลลัพธ์คือสร้าง K2 Incident อัตโนมัติ แนบ Evidence แนะนำ Runbook และแจ้งทีมที่เกี่ยวข้อง จากนั้น Human หรือ Approved Automation เป็นผู้ดำเนิน Remediation

ชี้ว่าความอัตโนมัติควรเพิ่มตามระดับความมั่นใจและความเสี่ยง เริ่มจาก Read-only และ Recommendation ก่อน Write Action

ประโยคเชื่อม:
Foundation เดียวกันไม่ได้จำกัดอยู่เฉพาะ HR และ IT แต่รองรับ Use Case ระดับองค์กรอีกหลายกลุ่ม

## สไลด์ 21 — Multiple Enterprise AI Opportunities (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
Platform เดียวรองรับ Agent หลายบทบาทโดยใช้ Knowledge, Models, Integration และ Governance ร่วมกัน

แนวทางพูด:
แบ่งโอกาสเป็นสี่กลุ่ม: Employee, IT & Security, Risk & Compliance และ Business

อย่านำเสนอว่าจะทำทุก Use Case พร้อมกัน จุดประสงค์ของสไลด์คือแสดงว่า Foundation ที่ลงทุนใน Pilot สามารถนำกลับมาใช้ซ้ำได้

เลือก Use Case ด้วยเกณฑ์: มี Owner, มีข้อมูลที่เข้าถึงได้, Pain Point ชัด, ความเสี่ยงควบคุมได้ และมี KPI วัดผล

ประโยคเชื่อม:
สำหรับธุรกิจหลักทรัพย์ ตัวอย่างที่เห็นคุณค่าชัดคือการเตรียมหลักฐานสำหรับ KYC/CDD Review

## สไลด์ 22 — AI-Assisted KYC/CDD Review (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
AI ช่วยรวบรวมและจัดโครงสร้าง Evidence แต่ไม่เป็นผู้ตัดสินใจด้าน Compliance

แนวทางพูด:
Input ได้แก่ Customer Profile, KYC Documents, UBO, Risk Classification, Transaction Alerts และ Previous Review

Agent สร้าง Review Pack ที่มี Identity Summary, UBO Structure, Missing Documents, Risk Indicators, Inconsistencies และ Supporting Evidence

ผลลัพธ์ทั้งหมดต้องมี Citation และสถานะความมั่นใจ ประเด็นที่ไม่พบข้อมูลต้องระบุว่า Gap ไม่ควรเติมข้อมูลจากการคาดเดา

ท้ายที่สุด Human Compliance Officer เป็นผู้ตรวจสอบและตัดสินใจตาม Policy และ Regulation

ประโยคเชื่อม:
นอกจากทบทวนลูกค้า AI ยังช่วยวิเคราะห์ผลกระทบจากกฎใหม่ต่อ Policy และ Process ภายในได้

## สไลด์ 23 — Regulatory Knowledge (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
AI ลดเวลาการเปรียบเทียบ Regulation กับ Policy, Procedure, SOP และ Control โดยแสดง Gap พร้อม Citation

แนวทางพูด:
เริ่มจาก Regulatory Change จากนั้น Agent แยก Requirement และค้นเอกสารภายในที่เกี่ยวข้อง

Gap/Impact View ควรแสดง Requirement, Existing Policy, Potential Gap, Affected Process และ Evidence

อธิบายว่า AI ช่วยเตรียม Analysis แต่ Compliance ยังต้องตีความและอนุมัติการแก้ไข การไม่มีหลักฐานต้องแสดงเป็น Not Found ไม่ใช่ Supported

ประโยคเชื่อม:
Use Case ทั้งหมดนี้สามารถวางอยู่บน Target Architecture เดียวกันได้

## สไลด์ 24 — Target Enterprise AI Architecture (ประมาณ 4 นาที)

สารที่ต้องการสื่อ:
Target Architecture วาง Enterprise AI เป็นชั้นกลางระหว่างผู้ใช้กับระบบเดิม โดยมี Security และ AI Operations ครอบทุกส่วน

แนวทางพูด:
ไล่จากบนลงล่าง:
1. Users หลายกลุ่มเข้าผ่าน Web, Teams, Mobile หรือ API
2. Agent Runtime แยก Agent ตามบทบาท
3. Intelligence จัดการ RAG, Reasoning, Memory และ Orchestration
4. Model Gateway เลือก Local, Private หรือ Cloud
5. Integration Gateway เชื่อม API, MCP, Workflow และ Tools
6. Enterprise Systems และ Data ยังคงเป็น Source of Truth

ด้านซ้ายคือ Identity, RBAC/ABAC, Guardrails, DLP และ Audit ด้านขวาคือ Quality, Latency, Usage, Cost และ LLM Observability

ประโยคเชื่อม:
หากเลือกประมวลผล Local ส่วนล่างของ Architecture ต้องถูกออกแบบเป็น Infrastructure Platform ที่พร้อมใช้งานจริง

## สไลด์ 25 — Production Local AI Infrastructure (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
Local AI สำหรับ Production ต้องมีหลาย Tier และ Operations ครบ ไม่ใช่เพียงติดตั้ง LLM บน GPU หนึ่งเครื่อง

แนวทางพูด:
อธิบาย Stack: Access, Application, Processing, Data และ AI Inference

ด้าน Operations ต้องมี Monitoring, Backup, HA/DR, Security และ Capacity Planning

ย้ำว่า GPU Sizing ไม่ได้คำนวณจากจำนวนพนักงาน แต่จาก Concurrent Generations, Model Size, Context Length, Tokens per Second, RAG และ Tool Workload

Pilot อาจเริ่มจาก Single Node ได้ แต่ต้องระบุข้อจำกัดและแผนยกระดับอย่างชัดเจน

ประโยคเชื่อม:
เพื่อไม่ให้ลงทุนใหญ่เกินไปตั้งแต่แรก เราแนะนำ Roadmap แบบค่อยเป็นค่อยไป

## สไลด์ 26 — Enterprise AI Roadmap (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
Roadmap เริ่มจาก Foundation แล้วเพิ่มความสามารถจาก Assist ไป Act, Intelligence และ Scale

แนวทางพูด:
1. Foundation: Local AI, Knowledge, Security, Governance
2. Assist: HR Agent และ IT Helpdesk
3. Act: เชื่อม PeopleSoft, K2, Workflow, API/MCP
4. Intelligence: Observability, Incident Correlation, Talent และ Compliance
5. Scale: เพิ่ม Agent, Data และ Automation

แถบ People, Process และ Technology ต้องเดินคู่กัน เช่น Data Owner, Approval Process, Operations Model และ Technical Platform

ประโยคเชื่อม:
สำหรับการเริ่มต้นจริง เราไม่จำเป็นต้องทำทุกขั้นพร้อมกัน แต่ควรเลือก Pilot ที่วัดผลได้บน Foundation ที่ขยายต่อได้

## สไลด์ 27 — Recommended Starting Point (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
เริ่มด้วย Platform Foundation พร้อม HR Pilot และ IT Pilot ที่มีขอบเขตชัด แล้วค่อยขยายสู่ Observability, Security และ Compliance

แนวทางพูด:
Foundation ควรมี Model, RAG, Identity, Security และ Governance ขั้นต่ำก่อนเปิดให้ผู้ใช้

HR Pilot อาจเริ่มจาก Knowledge + PeopleSoft Read และ Leave/Benefit ส่วน IT Pilot เริ่มจาก IT Knowledge + K2 + Guided Troubleshooting

แต่ละ Pilot ต้องมี Business Owner, Data Owner, User Group, Test Cases, Security Acceptance และ KPI

ประโยคเชื่อม:
ความสำเร็จควรวัดจาก Business Outcome และ Operational Quality ไม่ใช่ความประทับใจจาก Demo

## สไลด์ 28 — Measure Business Outcomes (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
การประเมิน Pilot ต้องมี Baseline และ KPI ครบด้าน Knowledge, HR, IT, Platform และ Security

แนวทางพูด:
- Knowledge: Answer Accuracy, Citation Accuracy, Coverage
- HR: Self-Service Completion, Time-to-Service, Adoption
- IT: First Contact Resolution, MTTR, Ticket Quality
- Platform: p95 Latency, Utilization, Cost per Task, Availability
- Security: Unauthorized Access ต้องเป็นศูนย์, Policy Violations และ Audit Coverage

ไม่ควรสัญญาตัวเลขลดต้นทุนโดยไม่มี Baseline ให้ใช้วงจร Baseline → Pilot → Measure → Improve → Scale

ประโยคเชื่อม:
หากเห็นตรงกัน ขั้นต่อไปคือ Workshop เพื่อกำหนด Use Case, Architecture และ Pilot ที่เหมาะสม

## สไลด์ 29 — Closing (ประมาณ 1 นาที)

สารที่ต้องการสื่อ:
เป้าหมายคือเปลี่ยน Knowledge ให้เป็น Intelligence และ Action อย่างปลอดภัย เป็นส่วนตัว มี Governance และตรวจสอบได้

แนวทางพูด:
สรุปว่าเริ่มจาก HR และ IT ได้ แต่ Foundation ถูกออกแบบเพื่อรองรับ Enterprise-wide AI

เสนอ Next Steps สามขั้น:
1. Use-Case Workshop
2. Technical Assessment
3. Pilot ที่มี Scope และ Success Criteria ชัดเจน

ปิดด้วย Core Message อีกครั้ง:
AI does not replace enterprise systems of record. AI becomes the secure intelligence and orchestration layer across them.

## สไลด์ 30 — Local LLM Model Selection (Backup)

ใช้เมื่อมีคำถามว่าจะเลือกโมเดล Local อย่างไร

แนวทางพูด:
อย่าเลือกจาก Parameter Count อย่างเดียว ต้องประเมิน Capability, Tool Calling, ภาษาไทย/อังกฤษ, Context, VRAM, Quantization, Latency และคุณภาพบนงานจริง

โมเดลเล็กอาจเร็วและคุ้มกว่าสำหรับ Classification หรือ FAQ ขณะที่งาน Reasoning และ Document Analysis อาจต้องโมเดลใหญ่ขึ้น

ข้อเสนอคือสร้าง Benchmark Dataset จาก Prompt, Document, RAG และ Tool Workflow จริง แล้วเปรียบเทียบ Accuracy, Latency, Throughput และ Cost

## สไลด์ 31 — GPU & Capacity Planning (Backup)

ใช้เมื่อมีคำถามเรื่อง Hardware หรือจำนวนผู้ใช้ที่รองรับ

แนวทางพูด:
Capacity ขึ้นกับ Concurrent Generations ไม่ใช่จำนวน Account ปัจจัยหลักคือ Tokens per Second, Context Length, KV Cache, Model Size, RAG และ Tools

ต้องแยก Total Users, Active Users, In-flight Requests และ Simultaneous LLM Generations

แนวทางที่ถูกต้องคือเก็บ Workload Profile จาก Pilot แล้วทำ Load Test วัด p50/p95 Latency, Queue Depth, GPU Utilization, Memory และ Throughput ก่อน Sizing Production

## สไลด์ 32 — Local vs Cloud Decision Matrix (Backup)

ใช้เมื่อมีการเปรียบเทียบ Local กับ Cloud

แนวทางพูด:
Local เหมาะเมื่อ Data Isolation, Network Independence หรือ Workload Economics มีน้ำหนักสูง แต่ต้องรับภาระ Lifecycle และ Capacity

Cloud เหมาะกับ Frontier Capability, Rapid Model Access และ Elastic Burst แต่ต้องตรวจ Data Policy, Connectivity, Quota และ Cost

ข้อสรุปไม่ควรเป็นคำตอบเดียวทั้งองค์กร ควรใช้ Policy Routing ตาม Data Classification และ Agent Workload

## สไลด์ 33 — RAG Security & ACL Flow (Backup)

ใช้ตอบคำถามว่าป้องกัน AI เห็นข้อมูลข้ามทีมอย่างไร

แนวทางพูด:
Identity และ Group Claims ถูกนำไปสร้าง Query Scope จากนั้น Filter Personal, Team และ Global ACL ก่อน Retrieval

Vector Search ต้องคืนเฉพาะ Chunk ที่ผู้ใช้มีสิทธิ์ และเมื่อเปิด Citation ต้องตรวจสิทธิ์ Source Document อีกครั้ง

ห้ามพึ่งการซ่อนข้อมูลหน้า UI เพราะ Authorization ต้องอยู่ฝั่ง Server และครอบคลุมทั้ง Search, Retrieval, Citation และ File Download

## สไลด์ 34 — MCP vs API Integration Architecture (Backup)

ใช้เมื่อมีคำถามว่า Integration ต่างจาก MCP อย่างไร

แนวทางพูด:
MCP ให้ Interface มาตรฐานสำหรับ Agent ค้นพบและเรียก Tools ส่วน REST/Event API เหมาะกับ Contract และ Workflow ที่กำหนดชัด

ทั้งสองควรอยู่ภายใต้ Integration Layer เดียวกัน มี Credential Management, Team Scope, Allowlist, Timeout, Rate Limit, Audit และ Read/Write Policy

ไม่ได้จำเป็นต้องเปลี่ยนทุก API เป็น MCP ให้เลือก Pattern ตามระบบปลายทาง ความพร้อม และ Risk

## สไลด์ 35 — AI Threat Model (Backup)

ใช้เมื่อ Security Team ต้องการมอง Threat และ Control

แนวทางพูด:
Threat หลักคือ Prompt Injection, Data Exfiltration และ Tool Abuse โดยต้องป้องกันทุกช่วงตั้งแต่ Input, Retrieval, Reasoning, Tool จนถึง Output

Control ที่ควรมี ได้แก่ Instruction Boundary, ACL, PII/DLP, Tool Allowlist, Least Privilege, Human Approval และ Metadata Audit

ย้ำว่า Guardrail จาก Model เพียงอย่างเดียวไม่เพียงพอ Policy ที่มีผลต่อสิทธิ์และ Tool ต้องบังคับใช้ฝั่ง Application/Server

## สไลด์ 36 — HA / DR / Backup for Local AI (Backup)

ใช้เมื่อ Infrastructure Team ถามถึง Production Readiness

แนวทางพูด:
HA ต้องครอบคลุม Access, App Replicas, Workers, Queue, Database, Vector DB, Object Storage และ Inference Gateway/GPU Nodes

Backup ต้องเป็น Consistent Set ระหว่าง Metadata, Source Objects และ Vector Index ไม่เช่นนั้น Restore แล้ว Citation หรือ Retrieval อาจไม่สอดคล้องกัน

กำหนด RTO/RPO, Monitoring, Backup Retention, Off-site Copy และทำ Restore Drill ตามรอบ เพราะ Backup ที่ไม่เคย Restore ยังถือว่าไม่ได้พิสูจน์

ปิดท้ายว่า Production AI ต้องพร้อมทั้งด้าน Security, Recoverability และ Operational Ownership
