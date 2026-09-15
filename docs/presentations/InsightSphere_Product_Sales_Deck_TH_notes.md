# InsightSphere Product Sales Deck — Presenter notes

## 1. Cover

เปิดด้วย positioning ว่า InsightSphere ไม่ใช่ chatbot แต่เป็น Enterprise AI
Agent & Knowledge Platform ที่ทำให้ข้อมูลและระบบเดิมของลูกค้ากลายเป็น AI ที่
ค้นหา วิเคราะห์ และลงมือทำได้

## 2. Executive summary

ย้ำ 3 แกน: Know — ตอบจากความรู้จริง, Think — วิเคราะห์เอกสาร/ภาพ, Act — เรียก
เครื่องมือและระบบงาน ภายใต้ Governance เดียวกัน

## 3. Customer challenges

เลือกเน้น pain ที่ตรงกับลูกค้า อย่าอ่านครบทุกข้อ หากลูกค้ากังวล Security ให้
ขยายเรื่อง ACL/Audit หากกังวล ROI ให้ขยายเรื่องงานซ้ำและเวลาค้นหา

## 4. Platform overview

อธิบายเป็น layer จากผู้ใช้ลงไปถึง Deployment จุดสำคัญคือ Security ไม่ได้อยู่
เฉพาะหน้า Login แต่ครอบคลุม retrieval, citation และ tool execution

## 5. Knowledge & RAG

สาธิตแนวคิด upload → extract/OCR → embed/index → retrieve → cite และย้ำว่า
ผู้ใช้เปิด Citation ได้เฉพาะเอกสารที่ตนมีสิทธิ์

## 6. AI Agents

Agent แต่ละตัวมี model, prompt, data scope และ tools ของตนเอง จึงสร้าง agent
เฉพาะบทบาทได้โดยไม่เปิดข้อมูลหรือความสามารถเกินจำเป็น

## 7. Document intelligence

ใช้กับ RFP/TOR/Compliance: requirement file เป็น checklist ไม่ใช่หลักฐาน ระบบ
ค้นหลักฐานจาก Knowledge แล้วแสดงข้อที่พบ ไม่พบ confidence และ gap

## 8. Security & governance

ย้ำ Local user + Entra, Team/Data Group ACL, encrypted secrets, tool policy,
audit และ user/conversation isolation หลีกเลี่ยงการอ้าง certification ที่ยัง
ไม่ได้รับ

## 9. Model flexibility

อธิบายว่าความสามารถและต้นทุนของแต่ละ model ต่างกัน Platform จึงทดสอบ tool
calling/vision และเลือก model ต่อ Agent ได้ ไม่จำเป็นต้องย้ายทุกอย่างพร้อมกัน

## 10. Deployment

Azure เหมาะกับ managed service, Local เหมาะกับ data control และ Hybrid ช่วย
เลือกรูปแบบตาม workload การ deploy production ต้องรวม TLS, backup, monitoring
และ capacity design

## 11. Use cases

เลือก 1–2 use case ที่มี owner, ข้อมูลพร้อม และมี KPI ชัด เพื่อทำ pilot

## 12. Business benefits

ไม่เสนอเปอร์เซ็นต์ประหยัดล่วงหน้า ให้เก็บ baseline ก่อน pilot แล้ววัด time per
case, acceptance/rework, policy coverage, cost per task และ latency

## 13. Engagement

เสนอ workshop → pilot → validate → scale โดยกำหนด production hardening แยกจาก
functional pilot ให้ชัด

## 14. Differentiators

สรุปความต่าง: evidence-first, access-aware, governed agent, provider-neutral,
operations-ready และ expandable architecture

## 15. Close

ปิดด้วยคำขอที่ชัดเจน: นัด workshop, technical assessment และตกลง pilot scope
พร้อม success criteria

## 16. Backup — Capacity framing

ใช้เมื่อผู้ฟังถามว่าระบบรองรับผู้ใช้ได้กี่คน แยก Registered, Active,
Concurrent request และ LLM generation ให้ชัด เพราะจำนวน account ไม่ได้บอกภาระ
ประมวลผลโดยตรง ตัวเลขทั้งหมดเป็น planning baseline จนกว่าจะทดสอบกับ model,
context, RAG และ tools ของลูกค้าจริง

## 17. Backup — Hardware sizing

ตารางเป็นจุดเริ่มต้นสำหรับทำงบประมาณ ไม่ใช่ capacity guarantee หากใช้ Cloud LLM
คอขวดมักเป็น quota/latency ของ provider แต่ถ้าใช้ Local LLM ต้องออกแบบจาก GPU,
VRAM, context length และจำนวน generation พร้อมกัน พื้นที่ disk ต้องรวม source,
vector, retention และ backup ด้วย

## 18. Backup — Scaling roadmap

อธิบายตรงไปตรงมาว่า Compose ปัจจุบันเหมาะกับ Pilot และยังเป็น single point of
failure ก่อนขยายต้องแยก App, worker, stateful data และ inference จากกัน ใช้ p95,
queue depth, throttling, GPU utilization และ ingestion backlog เป็นสัญญาณ scale
แทนการเดาจากจำนวน user อย่างเดียว
