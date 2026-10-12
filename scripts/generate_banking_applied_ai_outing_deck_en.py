import re
import sys
from pathlib import Path

from pptx import Presentation


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_banking_applied_ai_outing_deck as source  # noqa: E402


OUTPUT = ROOT / "docs" / "presentations" / "Banking_Operational_Excellence_Applied_AI_EN.pptx"
NOTES_OUTPUT = ROOT / "docs" / "presentations" / "Banking_Operational_Excellence_Applied_AI_notes_EN.md"
DEMO_OUTPUT = ROOT / "docs" / "presentations" / "Banking_Datadog_AI_Demo_Runbook_EN.md"

THAI_RE = re.compile(r"[\u0e00-\u0e7f]")


TRANSLATIONS = {
    "จากข้อมูลกระจัดกระจาย → หลักฐานที่เชื่อมโยง → การตัดสินใจที่เร็วและปลอดภัย":
        "From fragmented data → Connected evidence → Faster, safer decisions",
    "วันนี้เราจะเดินทางอย่างไร": "Our journey today",
    "Applied AI Platform\nแบบเข้าใจง่าย": "Applied AI Platform\nin plain language",
    "45 นาทีแรก: เข้าใจและเห็นของจริง  |  15 นาทีท้าย: เล่นเกมและทบทวน":
        "First 45 minutes: learn and see it live  |  Final 15 minutes: play and review",
    "เวลาเกิด Incident อะไรทำให้เราเสียเวลามากที่สุด?":
        "During an incident, what consumes the most time?",
    "หา Signal ที่ใช่": "Find the right signal",
    "Alert, log และ metric มีจำนวนมาก": "Too many alerts, logs and metrics",
    "หา Context": "Find the context",
    "ไม่รู้ว่าเพิ่งเปลี่ยนอะไร ใครเป็น owner": "What changed, and who owns it?",
    "หา Knowledge": "Find the knowledge",
    "Runbook อยู่หลายที่หรือไม่ทันสมัย": "Runbooks are fragmented or outdated",
    "ประสานงาน": "Coordinate teams",
    "หลายทีมเห็นข้อมูลคนละชุด": "Each team sees a different picture",
    "Operational Excellence วัดจากผลลัพธ์ ไม่ใช่จำนวน AI Tools":
        "Operational Excellence Is Measured by Outcomes — Not the Number of AI Tools",
    "แก้เหตุขัดข้องเร็วขึ้น": "Restore service faster",
    "บริการสำคัญมีเสถียรภาพ": "More reliable critical services",
    "ทุกการตัดสินใจมีหลักฐาน": "Evidence behind every decision",
    "ทีมใช้เวลากับงานมูลค่าสูง": "More time for high-value work",
    "AI ที่ดีต้องช่วยให้คนเห็นเหตุการณ์เดียวกัน ตัดสินใจบนหลักฐานเดียวกัน\nและดำเนินการภายใต้นโยบายเดียวกัน":
        "Good AI helps people see the same incident, decide from the same evidence,\nand act under the same policy",
    "Banking IT: ระบบต้องเร็ว ปลอดภัย และตรวจสอบย้อนหลังได้":
        "Banking IT Must Be Fast, Secure and Auditable",
    "Mobile, payment, transfer และ customer channels":
        "Mobile, payments, transfers and customer channels",
    "Cloud, on-prem, mainframe, database และ network":
        "Cloud, on-premises, mainframe, databases and networks",
    "Release, configuration และ dependency เปลี่ยนทุกวัน":
        "Releases, configurations and dependencies change every day",
    "Access control, evidence, audit และ segregation of duties":
        "Access control, evidence, audit and segregation of duties",
    "ความรู้สำคัญกระจุกอยู่กับผู้เชี่ยวชาญบางคน":
        "Critical knowledge is concentrated among a few experts",
    "Alert, log และ ticket มากกว่าที่คนจะอ่านทั้งหมด":
        "More alerts, logs and tickets than people can review",
    "จาก Chatbot สู่ Operational Capability": "From Chatbot to Operational Capability",
    "ตอบคำถามทั่วไป": "General questions",
    "ค้น Knowledge พร้อม citation": "Search Knowledge with citations",
    "เชื่อม signal และ context": "Connect signals and context",
    "เรียก tool ภายใต้นโยบาย": "Call tools under policy",
    "เก็บผลลัพธ์เป็นวิธีทำงาน": "Turn outcomes into reusable practice",
    "Applied AI ไม่ใช่แค่สร้างคำตอบ แต่ช่วยทำงานที่มี Context, Evidence และ Control":
        "Applied AI does more than generate answers — it supports work with Context, Evidence and Control",
    "Applied AI แบบเข้าใจง่าย: รับรู้ → เข้าใจ → แนะนำ → ช่วยดำเนินการ":
        "Applied AI in Plain Language: Sense → Understand → Recommend → Orchestrate",
    "อ่าน alert, metric, log, ticket": "Read alerts, metrics, logs and tickets",
    "เชื่อม service, change, owner, runbook": "Connect service, change, owner and runbook",
    "สรุปสาเหตุและทางเลือกพร้อม evidence": "Explain causes and options with evidence",
    "ส่งต่อหรือทำ action ที่ policy อนุญาต": "Route or execute policy-approved actions",
    "ทุกขั้นต้องรู้ว่า ใครถาม • เห็นข้อมูลอะไร • ใช้ tool ใด • ผลลัพธ์ถูกอนุมัติหรือไม่":
        "Every step must know: who asked • what data is visible • which tool is used • whether the result is approved",
    "AI Operations Platform คือชั้นเชื่อม ไม่ใช่ระบบใหม่ที่มาแทนทุกอย่าง":
        "An AI Operations Platform Is a Connecting Layer — Not a Replacement for Everything",
    "Systems of Record ยังคงเป็นแหล่งข้อมูลจริง — AI เพิ่ม intelligence และ orchestration คร่อมระบบเหล่านั้น":
        "Systems of Record remain authoritative — AI adds intelligence and orchestration across them",
    "หกความสามารถที่เปลี่ยน AI จาก Demo ให้เป็นงานจริง":
        "Six Capabilities That Move AI from Demo to Daily Operations",
    "ผู้เชี่ยวชาญเฉพาะงาน\nเช่น Operations Analyst":
        "Task-specific expertise\nsuch as an Operations Analyst",
    "RAG พร้อม source, page\nและ access control":
        "RAG with source, page\nand access control",
    "API / MCP เชื่อมระบบ\nแบบ read-only ก่อน":
        "API / MCP connectivity\nstarting read-only",
    "Metric, log, trace, event\nจาก Datadog":
        "Metrics, logs, traces and events\nfrom Datadog",
    "PII/DLP, tool policy\nและ least privilege":
        "PII/DLP, tool policy\nand least privilege",
    "ใครเรียก agent/tool ใด\nเมื่อไรและผลสำเร็จหรือไม่":
        "Who called which agent/tool,\nwhen, and with what outcome",
    "ใครรับผิดชอบอะไร?": "Who Is Responsible for What?",
    "เก็บข้อมูลจริง": "Own authoritative data",
    "บังคับ transaction rule": "Enforce transaction rules",
    "คง ownership เดิม": "Retain existing ownership",
    "เชื่อม context": "Connect context",
    "สรุปและจัดลำดับ": "Summarize and prioritize",
    "เสนอ action พร้อม evidence": "Recommend actions with evidence",
    "ตัดสินใจความเสี่ยง": "Make risk decisions",
    "อนุมัติ write action": "Approve write actions",
    "รับผิดชอบผลลัพธ์": "Remain accountable for outcomes",
    "AI ช่วยตัดสินใจได้ดีขึ้น แต่ Accountability ยังอยู่กับเจ้าของบริการและนโยบายขององค์กร":
        "AI improves decisions, but accountability remains with service owners and organizational policy",
    "เริ่มเล็ก แต่สร้างทางไปสู่ความสามารถใหม่":
        "Start Small — Build a Path to New Capabilities",
    "ค้น Knowledge\nสรุปข้อมูล": "Search Knowledge\nand summarize",
    "เชื่อม evidence\nจัดลำดับ hypothesis": "Connect evidence\nand rank hypotheses",
    "แนะนำ action\nพร้อม risk/owner": "Recommend actions\nwith risk and owner",
    "ดำเนิน workflow\nเมื่อได้รับอนุมัติ": "Execute workflows\nafter approval",
    "เป้าหมายไม่ใช่กระโดดไป Autonomous ทันที แต่เพิ่มความสามารถพร้อม Control ในแต่ละขั้น":
        "The goal is not instant autonomy — add capability and control at every stage",
    "Banking IT Use Cases: จัดลำดับด้วยเกณฑ์ที่ตรวจสอบได้":
        "Banking IT Use Cases: Prioritize with Auditable Criteria",
    "Priority Score = 0.35V + 0.30E + 0.20F + 0.15C  •  ให้คะแนน 1 (ต่ำ) – 5 (สูง)":
        "Priority Score = 0.35V + 0.30E + 0.20F + 0.15C  •  Score 1 (low) – 5 (high)",
    "Telemetry พร้อม • Read-only": "Telemetry available • Read-only",
    "Impact สูง • Signals พร้อม": "High impact • Signals available",
    "ขึ้นกับคุณภาพ Knowledge": "Depends on Knowledge quality",
    "ขึ้นกับ Change coverage": "Depends on Change coverage",
    "Write risk • ต้องอนุมัติ": "Write risk • Approval required",
    "ตัวอย่างคะแนน (ไม่ใช่ Banking benchmark): สมมติว่ามี Datadog telemetry แบบ read-only; ความพร้อมของ KM/Change แตกต่างตาม use case":
        "Illustrative scores (not a banking benchmark): read-only Datadog telemetry is assumed; KM/Change readiness varies by use case",
    "Use Case 1 — Morning Operations Briefing ใน 3 นาที":
        "Use Case 1 — A Three-Minute Morning Operations Briefing",
    "ผลกระทบและบริการสำคัญ": "Impact and critical services",
    "เรียงตาม severity และ customer impact": "Prioritized by severity and customer impact",
    "ใครต้องทำอะไรภายในเมื่อไร": "Who does what, and by when",
    "Use Case 2 — ลูกค้ารายงานว่า Mobile Banking Transfer ช้า":
        "Use Case 2 — Customers Report Slow Mobile Banking Transfers",
    "“โอนเงินแล้วหน้าจอ\nหมุนนานกว่าปกติ”": "“The transfer screen\nis taking unusually long”",
    "คำถามของทีมปฏิบัติการ": "Questions for the operations team",
    "เกิดกับใครและช่องทางใด?": "Who is affected, and through which channel?",
    "เริ่มเมื่อไรและสัมพันธ์กับ Change ใด?": "When did it start, and what changed?",
    "Bottleneck อยู่ที่ App, DB, Network หรือ Dependency?":
        "Is the bottleneck in the app, database, network or a dependency?",
    "มี Runbook และ action ที่ปลอดภัยอะไรบ้าง?":
        "Which runbook and safe actions are available?",
    "คำถามง่ายหนึ่งประโยค ต้องใช้หลักฐานจากหลายระบบจึงจะตอบได้อย่างรับผิดชอบ":
        "One simple question requires evidence from multiple systems to answer responsibly",
    "AI Operations Agent เชื่อมหลักฐานก่อนให้คำแนะนำ":
        "The AI Operations Agent Connects Evidence Before Recommending Action",
    "ผลลัพธ์: Timeline + Ranked hypotheses + Evidence + Runbook + Approval-ready action":
        "Outcome: Timeline + Ranked hypotheses + Evidence + Runbook + Approval-ready action",
    "Live Demo — NexoraAI + Datadog จากคำถามสู่การตัดสินใจ":
        "Live Demo — NexoraAI + Datadog: From Question to Decision",
    "ใช้ Datadog demo tenant และ Knowledge ที่ไม่ใช่ข้อมูลลูกค้าจริง":
        "Using a Datadog demo tenant and non-customer Knowledge",
    "“ช่วยตรวจสอบเหตุการณ์\nMobile Banking ช้า”":
        "“Investigate the slow\nMobile Banking incident”",
    "ดึง alert, event, metric\nและ time window จาก Datadog":
        "Retrieve alerts, events, metrics\nand the time window from Datadog",
    "เทียบ change timeline\nและค้น runbook ใน KM":
        "Compare the change timeline\nand search KM runbooks",
    "สร้างกราฟ severity / latency\nจากข้อมูล tool จริง":
        "Chart severity / latency\nfrom exact tool data",
    "เสนอ next action, owner,\nrisk และ approval":
        "Recommend next action, owner,\nrisk and approval",
    "Demo success ไม่ใช่แค่ได้คำตอบ แต่ต้องเห็น source, tool, chart และขอบเขตการอนุมัติ":
        "Demo success means seeing the source, tool, chart and approval boundary — not only an answer",
    "Demo 1 — เริ่มจากสถานการณ์ปัจจุบัน": "Demo 1 — Establish the Current Situation",
    "ช่วยสรุป Alert และเหตุการณ์สำคัญที่เกี่ยวข้องกับ Mobile Banking ในช่วง 60 นาทีล่าสุด พร้อมระบุผลกระทบและข้อมูลที่ยังขาด":
        "Summarize important alerts and events related to Mobile Banking during the last 60 minutes. Identify the impact and any missing data.",
    "สิ่งที่ต้องเห็น": "What we must see",
    "Executive summary, time window, affected service และ evidence links":
        "Executive summary, time window, affected service and evidence links",
    "หลักฐานที่ใช้": "Evidence used",
    "Datadog monitor/event results พร้อม timestamp":
        "Datadog monitor/event results with timestamps",
    "Demo 2 — เปลี่ยนข้อมูลเป็นภาพ": "Demo 2 — Turn Data into a Visual",
    "สร้างกราฟแนวโน้ม Alert แยกตาม Severity ในช่วงเวลาที่ตรวจสอบ และสรุปจุดเปลี่ยนที่สำคัญ โดยใช้เฉพาะข้อมูลที่ดึงได้จริง":
        "Create an alert trend chart by severity for the investigated period and summarize major turning points. Use only exact retrieved data.",
    "กราฟที่อ่านง่ายและไม่มีตัวเลขที่ model สร้างเอง":
        "A readable chart with no model-invented numbers",
    "Demo 3 — เชื่อม Datadog กับ Knowledge": "Demo 3 — Connect Datadog with Knowledge",
    "เชื่อม Timeline ของ Alert กับ Change ที่เกี่ยวข้อง ค้น Runbook ที่ได้รับอนุญาต แล้วจัดลำดับสมมติฐาน สาเหตุ หลักฐาน Gap และ Next Action ที่ต้องขออนุมัติ":
        "Correlate the alert timeline with relevant changes, search authorized runbooks, then rank hypotheses with evidence, gaps and approval-required next actions.",
    "Ranked hypotheses, confidence, gap, owner และ approval boundary":
        "Ranked hypotheses, confidence, gaps, owner and approval boundary",
    "ผลลัพธ์ที่ดีต้องตอบได้ว่า “รู้อะไร เพราะอะไร และทำอะไรต่อ”":
        "A Good Result Explains What We Know, Why We Know It and What Comes Next",
    "จาก Incident หนึ่งเหตุการณ์ สู่ Operational Capabilities ทั้งองค์กร":
        "From One Incident to Enterprise-Wide Operational Capabilities",
    "ตรวจ job delay, dependency และผลกระทบต่อ settlement":
        "Investigate job delays, dependencies and settlement impact",
    "สรุป availability ตามพื้นที่และจัดลำดับ dispatch":
        "Summarize availability by area and prioritize dispatch",
    "เชื่อม release กับ error/latency ก่อน–หลัง change":
        "Correlate releases with error/latency before and after change",
    "รวบรวม evidence พร้อม source และ timestamp":
        "Collect evidence with sources and timestamps",
    "หา saturation trend ก่อนชน threshold":
        "Detect saturation trends before thresholds are breached",
    "ร่าง timeline, lessons learned และ KM update":
        "Draft the timeline, lessons learned and KM update",
    "Enterprise AI ต้องปลอดภัยตั้งแต่ Identity ถึง Action":
        "Enterprise AI Must Be Secure from Identity to Action",
    "Guardrail ที่มีผลต่อสิทธิ์และ Tool ต้องบังคับใช้ฝั่ง Server — ไม่ใช่พึ่ง Prompt เพียงอย่างเดียว":
        "Guardrails governing access and tools must be enforced server-side — never by prompt alone",
    "90-Day Pilot: พิสูจน์ Value และ Control ไปพร้อมกัน":
        "90-Day Pilot: Prove Value and Control Together",
    "เลือก 1 service": "Select one service",
    "เชื่อม Datadog read-only": "Connect Datadog read-only",
    "เตรียม runbook/KM": "Prepare runbooks / KM",
    "กำหนด baseline": "Establish the baseline",
    "วัด accuracy/MTTR": "Measure accuracy / MTTR",
    "UAT กับ NOC/SRE": "UAT with NOC / SRE",
    "สามเรื่องที่อยากให้จำก่อนเริ่มเกม": "Three Ideas to Remember Before the Game",
    "AI เชื่อม Systems of Record\nไม่ใช่แทนที่ทุกระบบ":
        "AI connects Systems of Record\nwithout replacing every system",
    "คำตอบที่ดีต้องมี source, context,\nconfidence และ gap":
        "Good answers include source, context,\nconfidence and gaps",
    "สิทธิ์, guardrail, approval และ audit\nต้องมากับ use case ตั้งแต่วันแรก":
        "Access, guardrails, approval and audit\nmust exist from day one",
    "จาก Observability → Understanding → Decision → Governed Action":
        "From Observability → Understanding → Decision → Governed Action",
    "เลือก A / B / C / D  •  ข้อละประมาณ 45 วินาที  •  ห้ามเปิด Google":
        "Choose A / B / C / D  •  About 45 seconds each  •  No Google",
    "วิธีเล่น": "How to play",
    "แบ่งเป็นทีมตามโต๊ะ": "Form one team per table",
    "ตอบผ่าน Kahoot / Slido หรือชูป้าย": "Answer in Kahoot / Slido or raise a card",
    "ตอบถูก 1 คะแนน": "One point for each correct answer",
    "กรณีเสมอ: ทีมที่ตอบข้อสุดท้ายเร็วกว่า":
        "Tie-breaker: fastest correct answer on the final question",
    "พร้อมหรือยัง?": "Ready?",
    "เลือกคำตอบภายใน 15 วินาที": "Choose your answer within 15 seconds",
    "เลือก 1 Critical Service\n\nเชื่อม Datadog แบบ Read-only\n\nเตรียม Runbook / KM\n\nพิสูจน์ผลใน 90 วัน":
        "Select one Critical Service\n\nConnect Datadog Read-only\n\nPrepare Runbooks / KM\n\nProve value in 90 days",

    "เป้าหมายหลักของ Applied AI ใน IT Operations คืออะไร?":
        "What is the primary goal of Applied AI in IT Operations?",
    "A  เพิ่มจำนวน Dashboard": "A  Increase the number of dashboards",
    "B  เชื่อมข้อมูลเป็นการตัดสินใจที่เร็วและปลอดภัย":
        "B  Turn connected data into faster, safer decisions",
    "C  แทนที่ทีม IT ทั้งหมด": "C  Replace the entire IT team",
    "D  ย้ายทุกระบบขึ้น Cloud": "D  Move every system to the cloud",
    "AI Operations Platform ควรมีบทบาทอย่างไรต่อ Systems of Record?":
        "How should an AI Operations Platform relate to Systems of Record?",
    "A  ลบทิ้งและสร้างใหม่": "A  Remove and rebuild them",
    "B  คัดลอกข้อมูลทั้งหมดมาไว้ที่ AI": "B  Copy all data into the AI platform",
    "C  เป็น intelligence/orchestration layer คร่อมระบบเดิม":
        "C  Act as an intelligence/orchestration layer across them",
    "D  ปิดการตรวจสอบสิทธิ์": "D  Disable access control",
    "ข้อใดเป็นลำดับ Applied AI ที่ถูกต้อง?":
        "Which is the correct Applied AI sequence?",
    "เมื่อผู้ใช้บอกว่า Mobile Banking ช้า สิ่งแรกที่ AI ควรทำคืออะไร?":
        "When a user reports slow Mobile Banking, what should AI do first?",
    "A  Restart production ทันที": "A  Restart production immediately",
    "B  เดา root cause": "B  Guess the root cause",
    "C  รวบรวม signal และกำหนด scope/time window":
        "C  Collect signals and define the scope/time window",
    "D  ปิด alert": "D  Close the alert",
    "Datadog มีบทบาทหลักอะไรใน demo?":
        "What is Datadog's primary role in the demo?",
    "A  เป็นแหล่ง telemetry และ event evidence":
        "A  Provide telemetry and event evidence",
    "B  เป็น HR system": "B  Act as an HR system",
    "C  เป็นระบบอนุมัติสินเชื่อ": "C  Approve loans",
    "D  เป็น document editor": "D  Edit documents",
    "Knowledge / Runbook เติมสิ่งใดที่ telemetry อย่างเดียวมักไม่มี?":
        "What do Knowledge and runbooks add that telemetry often lacks?",
    "A  สีของ dashboard": "A  Dashboard colors",
    "B  Known fix, owner และขั้นตอนปฏิบัติ":
        "B  Known fixes, owners and operating procedures",
    "C  Password ผู้ดูแล": "C  Administrator passwords",
    "D  ข้อมูลลูกค้าทั้งหมด": "D  All customer data",
    "ผลลัพธ์ Incident Analysis ที่ดีควรมีอะไร?":
        "What should a good incident analysis contain?",
    "A  คำตอบสั้นโดยไม่มีที่มา": "A  A short answer without sources",
    "B  Root cause เดียวแบบมั่นใจ 100%":
        "B  One root cause stated with 100% confidence",
    "C  Timeline, hypotheses, evidence, confidence และ gap":
        "C  Timeline, hypotheses, evidence, confidence and gaps",
    "D  Raw logs ทั้งหมด": "D  Every raw log",
    "ทำไม Pilot ควรเริ่มแบบ Read-only?":
        "Why should a pilot start read-only?",
    "A  เพราะ AI อ่านไม่ได้": "A  Because AI cannot read",
    "B  ลดความเสี่ยงขณะพิสูจน์ value และ accuracy":
        "B  Reduce risk while proving value and accuracy",
    "C  ไม่ต้องมี audit": "C  Avoid audit requirements",
    "D  ทำให้ข้อมูลหายเร็วขึ้น": "D  Delete data faster",
    "ข้อใดเป็น Guardrail ที่เหมาะสม?":
        "Which is an appropriate guardrail?",
    "A  Tool allowlist และ least privilege":
        "A  Tool allowlists and least privilege",
    "B  แชร์ API key ให้ทุกทีม": "B  Share one API key across all teams",
    "C  เก็บ credential ใน prompt": "C  Store credentials in prompts",
    "D  ปิด access control": "D  Disable access control",
    "เหตุใด Guardrail ที่สำคัญจึงไม่ควรพึ่ง Prompt อย่างเดียว?":
        "Why must important guardrails not rely on prompts alone?",
    "A  Prompt ใช้ภาษาไทยไม่ได้": "A  Prompts cannot use Thai",
    "B  Policy ที่มีผลต่อสิทธิ์ต้องบังคับใช้ฝั่ง Server":
        "B  Access and tool policy must be enforced server-side",
    "C  Prompt ไม่มีข้อความ": "C  Prompts contain no text",
    "D  Server ไม่รู้จัก User": "D  Servers cannot identify users",
    "Metric ใดสัมพันธ์กับ Incident Response โดยตรงที่สุด?":
        "Which metric is most directly related to incident response?",
    "A  จำนวนสไลด์": "A  Number of slides",
    "C  จำนวน model": "C  Number of models",
    "D  จำนวน dashboard theme": "D  Number of dashboard themes",
    "กราฟที่ AI สร้างเพื่อใช้ตัดสินใจควรมาจากอะไร?":
        "What should an AI-generated decision chart be based on?",
    "A  ตัวเลขที่ model คาดเดา": "A  Numbers guessed by the model",
    "B  ข้อมูล exact จาก tool ที่สำเร็จ":
        "B  Exact data from successful tool calls",
    "C  ข่าวลือใน chat": "C  Rumors in chat",
    "D  ค่า random": "D  Random values",
    "Use case ใดเหมาะเป็น Pilot แรกมากที่สุด?":
        "Which use case is best suited for the first pilot?",
    "B  Incident triage และ morning briefing แบบ read-only":
        "B  Read-only incident triage and morning briefing",
    "C  เปลี่ยน core banking": "C  Replace core banking",
    "D  อนุมัติธุรกรรมอัตโนมัติ": "D  Approve transactions automatically",
    "Audit ของ AI Platform ควรหลีกเลี่ยงการเก็บอะไร?":
        "What should AI Platform audit records avoid storing?",
    "A  เวลาและ actor": "A  Time and actor",
    "B  Tool name และ outcome": "B  Tool name and outcome",
    "C  Raw prompt, credential และ sensitive tool output":
        "C  Raw prompts, credentials and sensitive tool output",
    "ประโยคใดสรุปแนวคิดวันนี้ได้ดีที่สุด?":
        "Which statement best summarizes today's message?",
    "A  AI แทนที่ทุกระบบ": "A  AI replaces every system",
    "B  AI เชื่อม Evidence และ Context เพื่อช่วยคนตัดสินใจภายใต้ Control":
        "B  AI connects Evidence and Context to support decisions under Control",
    "C  AI ไม่ต้องใช้ข้อมูลจริง": "C  AI does not need real data",
    "D  AI ที่ดีไม่ต้องมี owner": "D  Good AI needs no owner",
}


CONTENT_NOTES = [
    ("Opening", "1 minute", [
        "This is not a talk about model benchmarks. It is about how AI can improve the way IT teams operate.",
        "The audience includes executives and practitioners, so connect business outcomes to technical evidence.",
        "Ask everyone to remember the words Evidence, Context and Guardrail for the game.",
    ]),
    ("Session map", "1 minute", [
        "Set expectations: business framing, plain-language platform, live demo, governance and a 15-question game.",
        "The platform complements existing tools rather than replacing them.",
    ]),
    ("Opening poll", "2 minutes", [
        "Let each table choose one or more answers.",
        "All four are valid: the real problem is that signals, context, knowledge and coordination are disconnected.",
    ]),
    ("Business outcomes", "2 minutes", [
        "Executives care about reliability, risk and capacity more than model benchmarks.",
        "Tie every AI use case to measurable outcomes such as MTTR, repeat incidents and briefing time.",
    ]),
    ("Banking reality", "2 minutes", [
        "Banking operations combine high dependency, high change and strict evidence requirements.",
        "Applied AI is valuable where teams must read and correlate many types of operational data.",
    ]),
    ("AI evolution", "2 minutes", [
        "Chat is only an interface. Value appears when AI can access authorized Knowledge and tools.",
        "Act does not mean uncontrolled production change; organizational approval policy still applies.",
    ]),
    ("Applied AI in plain language", "2 minutes", [
        "Use Sense, Understand, Recommend and Orchestrate as the mental model for the rest of the talk.",
        "Every recommendation must be grounded in evidence and policy.",
    ]),
    ("Platform concept", "3 minutes", [
        "Describe the platform as a secure layer connecting people, knowledge and existing systems.",
        "Datadog, Service Desk and CMDB remain authoritative systems.",
        "The AI layer applies access control, tool policy and metadata-only audit.",
    ]),
    ("Platform capabilities", "2 minutes", [
        "A model alone is not an enterprise AI platform.",
        "Agents, Knowledge, integrations, observability, guardrails and audit must work together.",
    ]),
    ("Responsibility", "2 minutes", [
        "Use this slide to address fears about AI replacing systems or accountability.",
        "Begin with read-only recommendations and add actions only when controls are ready.",
    ]),
    ("Maturity", "2 minutes", [
        "Analyze and Recommend provide high value with lower risk than autonomous write actions.",
        "Today's demo is intentionally at these two maturity levels.",
    ]),
    ("Use-case portfolio", "2 minutes", [
        "This is a transparent internal scoring framework, not an industry or banking benchmark.",
        "Score each criterion from 1 to 5 in a customer discovery workshop; the proposed 35/30/20/15 weights should be reviewed and approved by service owners.",
        "The example assumes read-only Datadog telemetry. Knowledge, Change and approval readiness must be verified using customer evidence.",
        "NIST AI RMF informs risk/control criteria and Google SRE informs incident-response outcomes; neither source defines this formula or its weights.",
        "For a production decision, record the score owner, evidence, assessment date and rationale for every score.",
    ]),
    ("Morning briefing", "2 minutes", [
        "Executives receive a concise summary with links back to evidence rather than another dashboard.",
        "The result should expose uncertainty and missing information.",
    ]),
    ("Incident story", "2 minutes", [
        "A customer symptom does not identify the root cause.",
        "The Agent must decompose the question and retrieve evidence from multiple systems.",
    ]),
    ("Correlation", "3 minutes", [
        "Datadog supplies detailed telemetry; Change and Knowledge provide operational context.",
        "Rank hypotheses and show supporting, conflicting and missing evidence.",
    ]),
    ("Demo flow", "1 minute", [
        "Use a demo tenant and a read-only Agent.",
        "Keep the full demo below eight minutes and retain a clearly labeled recording or screenshots as fallback.",
    ]),
    ("Demo 1", "1–2 minutes", [
        "Show that a natural-language request invokes authorized Datadog tools.",
        "Confirm the response includes scope, time window, evidence links and missing data.",
    ]),
    ("Demo 2", "1–2 minutes", [
        "The chart must be created from exact successful tool output.",
        "Call out that the model is not allowed to invent metrics.",
    ]),
    ("Demo 3", "1–2 minutes", [
        "Show correlation between observability evidence, Change and approved runbooks.",
        "The final action must identify owner, risk and approval boundary.",
    ]),
    ("Demo result", "2 minutes", [
        "The values shown are an illustrative result format, not customer data.",
        "A useful answer states what is known, why, confidence, gaps and the next approved step.",
    ]),
    ("More banking use cases", "2 minutes", [
        "Reuse the platform capabilities with different Agents, Knowledge and integrations.",
        "Every Agent still needs an owner, measurable outcome and lifecycle.",
    ]),
    ("Governance", "3 minutes", [
        "Explain defense in depth from identity through action.",
        "Enforce access and tool policy server-side and keep sensitive raw content out of audit records.",
    ]),
    ("Pilot roadmap", "2 minutes", [
        "Limit the pilot to one critical service and one accountable team.",
        "Capture the baseline before implementation and assess value, accuracy, adoption and controls at day 90.",
    ]),
    ("Takeaways", "1 minute", [
        "Repeat the three ideas: AI is a Layer, Evidence First and Control by Design.",
        "Tell the audience that the game draws directly from these ideas and the demo.",
    ]),
    ("Game instructions", "1 minute", [
        "Use Kahoot, Slido or A/B/C/D cards by table.",
        "Allow about 20 seconds to read, 15 seconds to answer and 10–15 seconds for the explanation.",
    ]),
]


QUIZ_NOTES = [
    ("B", "Applied AI connects information into faster, safer and repeatable operational decisions."),
    ("C", "Systems of Record stay authoritative while AI adds intelligence and orchestration."),
    ("B", "The four stages are Sense, Understand, Recommend and Orchestrate."),
    ("C", "Start with evidence and the incident scope before proposing any action."),
    ("A", "Datadog supplies telemetry and event evidence such as RUM, APM, logs and infrastructure signals."),
    ("B", "Knowledge adds approved procedures, owners and known fixes."),
    ("C", "Auditable analysis includes a timeline, hypotheses, evidence, confidence and gaps."),
    ("B", "Read-only pilots reduce operational risk while value and accuracy are measured."),
    ("A", "Tool allowlists and least privilege are appropriate platform guardrails."),
    ("B", "Policies affecting access and tools must be enforced at the server boundary."),
    ("B", "MTTR directly reflects how quickly service is restored or resolved."),
    ("B", "Decision visuals must trace back to exact successful tool results."),
    ("B", "Read-only incident triage and briefing combine high readiness, measurable value and lower risk."),
    ("C", "Audit should retain necessary metadata without raw prompts, credentials or sensitive tool outputs."),
    ("B", "The core idea is connecting Evidence and Context to support governed human decisions."),
]


CLOSING_NOTE = (
    "Closing",
    "1 minute",
    [
        "Announce the winning team and connect the game back to the 90-day pilot.",
        "Invite the customer to select one critical service for a NexoraAI + Datadog discovery workshop.",
    ],
)


def note_text(title, timing, points):
    return "\n".join([f"{title} ({timing})", "", *(f"- {point}" for point in points)])


def translate_shape(shape):
    if not getattr(shape, "has_text_frame", False) or not shape.text.strip():
        return
    current = shape.text.replace("\v", "\n")
    translated = TRANSLATIONS.get(current)
    if translated is None:
        if THAI_RE.search(current):
            raise ValueError(f"Missing visible-text translation: {current!r}")
        return
    frame = shape.text_frame
    if len(frame.paragraphs) != 1:
        raise ValueError(f"Unexpected multi-paragraph shape: {current!r}")
    frame.paragraphs[0].text = translated


def build_english_deck():
    source.build_deck()
    presentation = Presentation(source.OUTPUT)

    for slide in presentation.slides:
        for item in slide.shapes:
            translate_shape(item)

    note_values = [note_text(*entry) for entry in CONTENT_NOTES]
    for number, (answer, reason) in enumerate(QUIZ_NOTES, start=1):
        note_values.append(note_text(
            f"Quiz {number}",
            "45–60 seconds",
            [f"Answer: {answer}", f"Why: {reason}", "Record the score before moving to the next question."],
        ))
    note_values.append(note_text(*CLOSING_NOTE))

    if len(note_values) != len(presentation.slides):
        raise ValueError(f"Expected {len(presentation.slides)} notes, found {len(note_values)}")

    remaining = []
    for slide_number, (slide, note) in enumerate(zip(presentation.slides, note_values), start=1):
        for item in slide.shapes:
            if getattr(item, "has_text_frame", False) and THAI_RE.search(item.text):
                remaining.append((slide_number, item.text))
        slide.notes_slide.notes_text_frame.text = note

    if remaining:
        raise ValueError(f"Thai text remains in English deck: {remaining!r}")

    presentation.core_properties.title = (
        "Operational Excellence Through Applied AI to New IT Operational Capabilities — English"
    )
    presentation.core_properties.comments = (
        "English banking IT outing deck with NexoraAI and Datadog demonstration"
    )
    presentation.save(OUTPUT)
    return note_values


def notes_markdown(note_values):
    lines = [
        "# Banking IT Outing — English Presenter Notes",
        "",
        "Topic: **Operational Excellence Through Applied AI to New IT Operational Capabilities**  ",
        "Format: 45-minute presentation + 15-minute game  ",
        "Audience: Senior executives and approximately 120 IT staff  ",
        "",
        "## Timing",
        "",
        "- Slides 1–5: Opening and operational pressure — 8 minutes",
        "- Slides 6–12: Applied AI and platform — 14 minutes",
        "- Slides 13–21: Banking use cases and Datadog demo — 16 minutes",
        "- Slides 22–24: Governance, roadmap and takeaways — 7 minutes",
        "- Slides 25–40: Game — 15 minutes",
        "- Slide 41: Closing — 1 minute or use inside the Q&A buffer",
        "",
        "## Slide-by-slide notes",
        "",
    ]
    for number, note in enumerate(note_values, start=1):
        title, _, body = note.partition("\n")
        lines.extend([f"### {number}. {title}", "", body.strip(), ""])
    lines.extend([
        "## Quiz answer key",
        "",
        "| Question | Answer |",
        "| ---: | :---: |",
    ])
    for number, (answer, _) in enumerate(QUIZ_NOTES, start=1):
        lines.append(f"| {number} | {answer} |")
    return "\n".join(lines).rstrip() + "\n"


def demo_runbook():
    return """# Banking Datadog + NexoraAI Demo Runbook

## Demo goal

Show that a NexoraAI Operations Agent can retrieve authorized Datadog evidence,
correlate it with approved operational Knowledge, create a chart from exact tool
results, and produce an approval-ready recommendation without modifying
production.

## Safety boundary

- Use a demonstration tenant and synthetic service names.
- Never show customer names, account numbers, tokens, host identifiers or raw
  production logs.
- Bind the Agent only to the intended Team-owned Datadog connection and approved
  Knowledge Data Groups.
- Keep Datadog and every other integration read-only.
- Pre-test the exact prompts and time ranges on the same day as the event.
- Keep screenshots or a short recording as fallback and label them clearly.

## Recommended scenario

Service: Mobile Banking Transfer
Symptom: P95 latency and error rate increase after a demonstration deployment.
Evidence: Datadog monitor events, latency/error time series, a synthetic change
record and a fictional connection-pool runbook.

## Live prompts

1. Current state

   Summarize important alerts and events related to Mobile Banking during the
   last 60 minutes. Identify the impact and any missing data.

2. Visualization

   Create an alert trend chart by severity for the investigated period and
   summarize major turning points. Use only exact retrieved data.

3. Correlation and Knowledge

   Correlate the alert timeline with relevant changes, search authorized
   runbooks, then rank hypotheses with evidence, gaps and approval-required next
   actions.

## Presenter checklist

- [ ] The Agent uses a tested tool-capable LLM profile.
- [ ] The Datadog MCP connection test succeeds and discovered tools are visible.
- [ ] The Agent binding permits only the required read tools.
- [ ] Knowledge search is enabled for synthetic Change and Runbook sources.
- [ ] Chart integration is enabled and tested with exact tool output.
- [ ] Each response shows source/time context and no fabricated metric.
- [ ] The final recommendation identifies owner, risk and approval requirement.
- [ ] Screenshot/video fallback is ready.
"""


if __name__ == "__main__":
    generated_notes = build_english_deck()
    NOTES_OUTPUT.write_text(notes_markdown(generated_notes), encoding="utf-8")
    DEMO_OUTPUT.write_text(demo_runbook(), encoding="utf-8")
    print(OUTPUT)
    print(NOTES_OUTPUT)
    print(DEMO_OUTPUT)
