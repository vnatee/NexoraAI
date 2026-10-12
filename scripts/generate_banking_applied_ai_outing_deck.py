from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "presentations" / "Banking_Operational_Excellence_Applied_AI.pptx"
NOTES_OUTPUT = ROOT / "docs" / "presentations" / "Banking_Operational_Excellence_Applied_AI_notes_TH.md"
DEMO_OUTPUT = ROOT / "docs" / "presentations" / "Banking_Datadog_AI_Demo_Runbook_TH.md"

W, H = Inches(13.333), Inches(7.5)
FONT = "Arial"
FOOTER = "Operational Excellence Through Applied AI | Banking IT Outing"

NAVY = RGBColor(9, 25, 44)
NAVY_2 = RGBColor(19, 43, 70)
BLUE = RGBColor(31, 111, 214)
CYAN = RGBColor(34, 181, 193)
ORANGE = RGBColor(245, 127, 34)
GREEN = RGBColor(34, 153, 103)
RED = RGBColor(202, 65, 70)
PURPLE = RGBColor(111, 79, 196)
INK = RGBColor(24, 38, 53)
MUTED = RGBColor(89, 105, 120)
MID = RGBColor(170, 185, 198)
LINE = RGBColor(215, 224, 232)
LIGHT = RGBColor(246, 249, 252)
PALE_BLUE = RGBColor(233, 243, 255)
PALE_CYAN = RGBColor(230, 248, 249)
PALE_ORANGE = RGBColor(255, 242, 228)
PALE_GREEN = RGBColor(232, 248, 240)
PALE_PURPLE = RGBColor(243, 238, 255)
WHITE = RGBColor(255, 255, 255)


def new_slide(prs, color=WHITE):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color
    return slide


def shape(slide, x, y, w, h, fill=WHITE, line=LINE, radius=True):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    item = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    item.fill.solid()
    item.fill.fore_color.rgb = fill
    item.line.color.rgb = line
    item.line.width = Pt(0.8)
    if radius:
        try:
            item.adjustments[0] = 0.12
        except (IndexError, ValueError):
            pass
    return item


def circle(slide, x, y, d, fill=BLUE, line=None):
    item = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    item.fill.solid()
    item.fill.fore_color.rgb = fill
    item.line.color.rgb = line or fill
    return item


def text(slide, value, x, y, w, h, size=18, color=INK, bold=False,
         align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, margin=0.04, shrink=True):
    item = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = item.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = Inches(margin)
    frame.margin_top = frame.margin_bottom = Inches(margin)
    frame.vertical_anchor = valign
    if shrink:
        frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    paragraph = frame.paragraphs[0]
    paragraph.text = value
    paragraph.alignment = align
    paragraph.font.name = FONT
    paragraph.font.size = Pt(size)
    paragraph.font.bold = bold
    paragraph.font.color.rgb = color
    return item


def line(slide, x1, y1, x2, y2, color=LINE, width=1.5, arrow=False):
    item = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1),
        Inches(y1),
        Inches(x2),
        Inches(y2),
    )
    item.line.color.rgb = color
    item.line.width = Pt(width)
    if arrow:
        item.line.end_arrowhead = True
    return item


def pill(slide, label, x, y, w, fill=PALE_BLUE, color=BLUE, size=10):
    shape(slide, x, y, w, 0.34, fill, fill, True)
    text(slide, label, x, y + 0.01, w, 0.28, size, color, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)


def icon(slide, glyph, x, y, d=0.55, fill=BLUE, size=16):
    circle(slide, x, y, d, fill)
    text(slide, glyph, x, y + 0.01, d, d - 0.02, size, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)


def header(slide, title, section, page, subtitle=None, dark=False):
    foreground = WHITE if dark else INK
    secondary = RGBColor(182, 202, 220) if dark else MUTED
    text(slide, section.upper(), 0.62, 0.24, 3.6, 0.25, 9, CYAN if dark else BLUE, True)
    text(slide, title, 0.62, 0.63, 12.0, 0.58, 27, foreground, True)
    rule_y = 1.56 if subtitle else 1.38
    if subtitle:
        text(slide, subtitle, 0.64, 1.2, 11.9, 0.3, 11, secondary)
    line(slide, 0.62, rule_y, 12.72, rule_y, NAVY_2 if dark else LINE, 0.8)
    text(slide, FOOTER, 0.62, 7.08, 8.2, 0.18, 7.5, secondary)
    text(slide, f"{page:02d}", 12.15, 7.06, 0.55, 0.2, 8, secondary, True, PP_ALIGN.RIGHT)


def card(slide, title, body, x, y, w, h, accent=BLUE, fill=WHITE, glyph=None):
    shape(slide, x, y, w, h, fill, LINE)
    shape(slide, x, y, 0.07, h, accent, accent, False)
    tx = x + 0.28
    if glyph:
        icon(slide, glyph, x + 0.28, y + 0.22, 0.48, accent, 14)
        tx = x + 0.9
    text(slide, title, tx, y + 0.2, w - (tx - x) - 0.2, 0.4, 14, INK, True)
    text(slide, body, x + 0.28, y + 0.75, w - 0.52, h - 0.9, 10.5, MUTED)


def metric(slide, value, label, x, y, w, color=BLUE):
    shape(slide, x, y, w, 1.18, WHITE, LINE)
    text(slide, value, x + 0.12, y + 0.17, w - 0.24, 0.48, 23, color, True, PP_ALIGN.CENTER)
    text(slide, label, x + 0.12, y + 0.72, w - 0.24, 0.25, 9.5, MUTED, False, PP_ALIGN.CENTER)


def statement(slide, value, y=6.3, color=BLUE, dark=False):
    line(slide, 0.85, y - 0.16, 12.48, y - 0.16, NAVY_2 if dark else LINE, 0.8)
    text(slide, value, 1.0, y, 11.3, 0.48, 14, WHITE if dark else color, True, PP_ALIGN.CENTER)


def notes(title, timing, talking_points, transition=""):
    body = [f"{title} ({timing})", ""]
    body.extend(f"- {point}" for point in talking_points)
    if transition:
        body.extend(["", f"Transition: {transition}"])
    return "\n".join(body)


def add_notes(slide, value):
    slide.notes_slide.notes_text_frame.text = value


def add_cover(prs, note_list):
    slide = new_slide(prs, NAVY)
    shape(slide, 0, 0, 0.17, 7.5, ORANGE, ORANGE, False)
    text(slide, "BANKING IT OUTING • APPLIED AI", 0.82, 0.68, 5.6, 0.3, 11, CYAN, True)
    text(slide, "Operational Excellence\nThrough Applied AI", 0.82, 1.43, 7.1, 1.55, 35, WHITE, True)
    text(slide, "to New IT Operational Capabilities", 0.85, 3.2, 6.7, 0.5, 21, RGBColor(197, 217, 234))
    pill(slide, "45 MIN TALK", 0.85, 4.18, 1.55, NAVY_2, CYAN)
    pill(slide, "15 MIN GAME", 2.58, 4.18, 1.55, NAVY_2, ORANGE)
    text(slide, "จากข้อมูลกระจัดกระจาย → หลักฐานที่เชื่อมโยง → การตัดสินใจที่เร็วและปลอดภัย",
         0.85, 4.82, 6.6, 0.7, 14, WHITE, True)
    line(slide, 8.2, 3.73, 11.82, 3.73, RGBColor(83, 120, 153), 2.2)
    icon(slide, "D", 7.55, 3.17, 1.1, PURPLE, 26)
    circle(slide, 9.44, 2.64, 2.18, NAVY_2, BLUE)
    text(slide, "AI", 9.44, 3.23, 2.18, 0.58, 28, ORANGE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    icon(slide, "A", 11.48, 3.17, 1.1, GREEN, 26)
    text(slide, "Datadog", 7.28, 4.55, 1.7, 0.32, 10, RGBColor(186, 204, 221), True, PP_ALIGN.CENTER)
    text(slide, "Applied AI", 9.52, 5.0, 2.0, 0.32, 10, RGBColor(186, 204, 221), True, PP_ALIGN.CENTER)
    text(slide, "Action", 11.3, 4.55, 1.5, 0.32, 10, RGBColor(186, 204, 221), True, PP_ALIGN.CENTER)
    text(slide, "For Banking Technology Operations", 0.85, 6.82, 4.8, 0.25, 9, RGBColor(145, 169, 191))
    note_list.append(notes(
        "สไลด์ 1 — เปิดเรื่อง",
        "1 นาที",
        [
            "วันนี้ไม่ใช่การบรรยายว่า AI เก่งแค่ไหน แต่จะคุยว่า AI ทำให้ทีม IT ทำงานดีขึ้นอย่างไร",
            "กลุ่มผู้ฟังมีทั้งผู้บริหารและทีมปฏิบัติการ จึงจะเชื่อม Business Outcome กับ Technical Evidence",
            "ช่วงท้ายมีเกม 15 ข้อจากเนื้อหาที่พูด ขอให้สังเกตคำว่า Evidence, Context และ Guardrail",
        ],
        "เริ่มจากปัญหาที่ทุกทีม IT เคยเจอร่วมกัน",
    ))


def add_session_map(prs, note_list):
    slide = new_slide(prs)
    header(slide, "วันนี้เราจะเดินทางอย่างไร", "Session map", 2)
    stages = [
        ("01", "WHY", "Operational pressure\nin banking", BLUE),
        ("02", "WHAT", "Applied AI Platform\nแบบเข้าใจง่าย", CYAN),
        ("03", "SHOW", "Datadog + AI\nincident demo", ORANGE),
        ("04", "CONTROL", "Security, governance\nand human approval", GREEN),
        ("05", "PLAY", "15-question\nteam challenge", PURPLE),
    ]
    x = 0.72
    for index, (number, title_, body, color) in enumerate(stages):
        shape(slide, x, 2.15, 2.2, 2.7, WHITE, LINE)
        circle(slide, x + 0.73, 2.48, 0.75, color)
        text(slide, number, x + 0.73, 2.65, 0.75, 0.3, 12, WHITE, True, PP_ALIGN.CENTER)
        text(slide, title_, x + 0.18, 3.42, 1.84, 0.4, 15, color, True, PP_ALIGN.CENTER)
        text(slide, body, x + 0.2, 3.95, 1.8, 0.62, 10.5, MUTED, False, PP_ALIGN.CENTER)
        if index < len(stages) - 1:
            line(slide, x + 2.2, 3.5, x + 2.5, 3.5, color, 2, True)
        x += 2.5
    statement(slide, "45 นาทีแรก: เข้าใจและเห็นของจริง  |  15 นาทีท้าย: เล่นเกมและทบทวน", 6.12)
    note_list.append(notes(
        "สไลด์ 2 — Agenda",
        "1 นาที",
        [
            "บอกผู้ฟังว่าจะมีทั้งมุมผู้บริหาร สถาปัตยกรรม และ demo",
            "เนื้อหาไม่ได้พยายามแทนที่เครื่องมือเดิม แต่เพิ่มความสามารถในการเชื่อมข้อมูลและตัดสินใจ",
        ],
    ))


def add_opening_poll(prs, note_list):
    slide = new_slide(prs, LIGHT)
    header(slide, "เวลาเกิด Incident อะไรทำให้เราเสียเวลามากที่สุด?", "Warm-up", 3)
    options = [
        ("A", "หา Signal ที่ใช่", "Alert, log และ metric มีจำนวนมาก", BLUE),
        ("B", "หา Context", "ไม่รู้ว่าเพิ่งเปลี่ยนอะไร ใครเป็น owner", CYAN),
        ("C", "หา Knowledge", "Runbook อยู่หลายที่หรือไม่ทันสมัย", ORANGE),
        ("D", "ประสานงาน", "หลายทีมเห็นข้อมูลคนละชุด", PURPLE),
    ]
    positions = [(0.8, 1.9), (6.82, 1.9), (0.8, 4.25), (6.82, 4.25)]
    for item, (x, y) in zip(options, positions):
        letter, title_, body, color = item
        shape(slide, x, y, 5.7, 1.72, WHITE, LINE)
        icon(slide, letter, x + 0.28, y + 0.36, 0.72, color, 20)
        text(slide, title_, x + 1.22, y + 0.3, 4.1, 0.38, 16, INK, True)
        text(slide, body, x + 1.22, y + 0.84, 4.1, 0.42, 11, MUTED)
    note_list.append(notes(
        "สไลด์ 3 — Opening poll",
        "2 นาที",
        [
            "ให้ยกมือเลือกได้มากกว่าหนึ่งข้อ หรือให้แต่ละโต๊ะเลือกข้อหลัก",
            "เฉลยเชิงแนวคิดคือทุกข้อเกี่ยวข้องกัน ปัญหาไม่ได้อยู่ที่ไม่มีข้อมูล แต่อยู่ที่ข้อมูลไม่เชื่อมเป็นเรื่องเดียว",
            "ใช้คำตอบของผู้ฟังอ้างกลับในช่วง demo",
        ],
        "Applied AI ต้องลดเวลาทั้ง Signal, Context, Knowledge และ Coordination",
    ))


def add_outcomes(prs, note_list):
    slide = new_slide(prs)
    header(slide, "Operational Excellence วัดจากผลลัพธ์ ไม่ใช่จำนวน AI Tools", "Outcome", 4)
    metric(slide, "↓ MTTR", "แก้เหตุขัดข้องเร็วขึ้น", 0.78, 1.85, 2.7, BLUE)
    metric(slide, "↑ Reliability", "บริการสำคัญมีเสถียรภาพ", 3.78, 1.85, 2.7, GREEN)
    metric(slide, "↓ Risk", "ทุกการตัดสินใจมีหลักฐาน", 6.78, 1.85, 2.7, ORANGE)
    metric(slide, "↑ Capacity", "ทีมใช้เวลากับงานมูลค่าสูง", 9.78, 1.85, 2.7, PURPLE)
    shape(slide, 0.8, 3.65, 11.7, 1.82, NAVY, NAVY)
    text(slide, "AI ที่ดีต้องช่วยให้คนเห็นเหตุการณ์เดียวกัน ตัดสินใจบนหลักฐานเดียวกัน\nและดำเนินการภายใต้นโยบายเดียวกัน",
         1.2, 4.05, 10.9, 0.78, 19, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    statement(slide, "Success = Faster understanding + Safer decision + Repeatable operation", 6.2)
    note_list.append(notes(
        "สไลด์ 4 — Business outcome",
        "2 นาที",
        [
            "ผู้บริหารสนใจ reliability, risk และ capacity มากกว่า model benchmark",
            "AI use case ทุกตัวควรผูกกับตัววัด เช่น MTTR, false escalation, repeat incident และเวลาทำรายงาน",
            "คำว่า Capacity หมายถึงเพิ่มกำลังทีม ไม่ใช่ลดจำนวนคน",
        ],
    ))


def add_banking_reality(prs, note_list):
    slide = new_slide(prs, LIGHT)
    header(slide, "Banking IT: ระบบต้องเร็ว ปลอดภัย และตรวจสอบย้อนหลังได้", "Reality", 5)
    items = [
        ("24×7 DIGITAL", "Mobile, payment, transfer และ customer channels", "24", BLUE),
        ("HYBRID ESTATE", "Cloud, on-prem, mainframe, database และ network", "H", CYAN),
        ("HIGH CHANGE", "Release, configuration และ dependency เปลี่ยนทุกวัน", "Δ", ORANGE),
        ("REGULATED", "Access control, evidence, audit และ segregation of duties", "G", GREEN),
        ("SKILL PRESSURE", "ความรู้สำคัญกระจุกอยู่กับผู้เชี่ยวชาญบางคน", "K", PURPLE),
        ("SIGNAL VOLUME", "Alert, log และ ticket มากกว่าที่คนจะอ่านทั้งหมด", "!", RED),
    ]
    positions = [(0.72, 1.8), (4.55, 1.8), (8.38, 1.8), (0.72, 4.1), (4.55, 4.1), (8.38, 4.1)]
    for item, (x, y) in zip(items, positions):
        title_, body, glyph, color = item
        card(slide, title_, body, x, y, 3.55, 1.72, color, WHITE, glyph)
    note_list.append(notes(
        "สไลด์ 5 — Banking reality",
        "2 นาที",
        [
            "เน้นว่าความท้าทายไม่ใช่เฉพาะเทคโนโลยี แต่รวม operating model และ regulatory evidence",
            "ระบบธนาคารมี dependency สูง การมอง signal แยกส่วนจึงทำให้ diagnosis ช้า",
            "Applied AI เหมาะกับงานที่ต้องอ่านข้อมูลหลายชนิดและเชื่อมบริบท",
        ],
    ))


def add_ai_evolution(prs, note_list):
    slide = new_slide(prs)
    header(slide, "จาก Chatbot สู่ Operational Capability", "Applied AI", 6)
    levels = [
        ("ASK", "ตอบคำถามทั่วไป", 1.0, 0.78, MID),
        ("KNOW", "ค้น Knowledge พร้อม citation", 3.35, 0.98, BLUE),
        ("REASON", "เชื่อม signal และ context", 5.8, 1.18, CYAN),
        ("ACT", "เรียก tool ภายใต้นโยบาย", 8.45, 1.38, ORANGE),
        ("LEARN", "เก็บผลลัพธ์เป็นวิธีทำงาน", 10.95, 1.58, GREEN),
    ]
    line(slide, 1.35, 4.25, 12.0, 4.25, LINE, 5)
    for index, (name, body, x, diameter, color) in enumerate(levels):
        circle(slide, x, 4.25 - diameter / 2, diameter, color)
        text(slide, name, x - 0.22, 2.28, diameter + 0.44, 0.35, 13, color, True, PP_ALIGN.CENTER)
        text(slide, body, x - 0.42, 2.82, diameter + 0.84, 0.62, 10, MUTED, False, PP_ALIGN.CENTER)
        if index < len(levels) - 1:
            line(slide, x + diameter + 0.2, 3.95, x + diameter + 0.48, 3.95, color, 1.7, True)
    statement(slide, "Applied AI ไม่ใช่แค่สร้างคำตอบ แต่ช่วยทำงานที่มี Context, Evidence และ Control", 6.18)
    note_list.append(notes(
        "สไลด์ 6 — AI evolution",
        "2 นาที",
        [
            "Chat เป็นเพียง interface; คุณค่าจริงเกิดเมื่อ AI เข้าถึง Knowledge และเครื่องมือที่ได้รับอนุญาต",
            "คำว่า Act ไม่ได้แปลว่าให้ AI เปลี่ยน production ทันที การอนุมัติยังเป็น policy ขององค์กร",
            "Learn คือทำให้ผลการแก้ปัญหากลับมาเป็น Knowledge ที่ใช้ซ้ำได้",
        ],
    ))


def add_plain_language(prs, note_list):
    slide = new_slide(prs, NAVY)
    header(slide, "Applied AI แบบเข้าใจง่าย: รับรู้ → เข้าใจ → แนะนำ → ช่วยดำเนินการ", "Applied AI", 7, dark=True)
    stages = [
        ("1", "SENSE", "อ่าน alert, metric, log, ticket", BLUE),
        ("2", "UNDERSTAND", "เชื่อม service, change, owner, runbook", CYAN),
        ("3", "RECOMMEND", "สรุปสาเหตุและทางเลือกพร้อม evidence", ORANGE),
        ("4", "ORCHESTRATE", "ส่งต่อหรือทำ action ที่ policy อนุญาต", GREEN),
    ]
    x = 0.78
    for index, (number, title_, body, color) in enumerate(stages):
        shape(slide, x, 2.0, 2.75, 2.65, NAVY_2, NAVY_2)
        circle(slide, x + 0.94, 2.34, 0.82, color)
        text(slide, number, x + 0.94, 2.53, 0.82, 0.3, 14, WHITE, True, PP_ALIGN.CENTER)
        text(slide, title_, x + 0.25, 3.37, 2.25, 0.36, 14, color, True, PP_ALIGN.CENTER)
        text(slide, body, x + 0.3, 3.86, 2.15, 0.55, 10.5, RGBColor(190, 209, 225), False, PP_ALIGN.CENTER)
        if index < len(stages) - 1:
            line(slide, x + 2.76, 3.25, x + 3.05, 3.25, color, 2.0, True)
        x += 3.05
    statement(slide, "ทุกขั้นต้องรู้ว่า ใครถาม • เห็นข้อมูลอะไร • ใช้ tool ใด • ผลลัพธ์ถูกอนุมัติหรือไม่", 6.2, CYAN, True)
    note_list.append(notes(
        "สไลด์ 7 — Applied AI in plain language",
        "2 นาที",
        [
            "ใช้สี่คำนี้เป็น mental model ตลอดการนำเสนอ",
            "Sense มาจากระบบจริง เช่น Datadog; Understand ต้องมี business/technical context",
            "Recommend ต้องอ้าง evidence; Orchestrate ต้องผ่านสิทธิ์และ policy",
        ],
    ))


def add_platform(prs, note_list):
    slide = new_slide(prs)
    header(slide, "AI Operations Platform คือชั้นเชื่อม ไม่ใช่ระบบใหม่ที่มาแทนทุกอย่าง", "Platform", 8)
    text(slide, "PEOPLE & CHANNELS", 0.75, 1.72, 2.1, 0.3, 10, MUTED, True)
    for i, label in enumerate(["Executives", "NOC / SRE", "Service Desk", "Application Teams"]):
        pill(slide, label, 0.75 + i * 3.05, 2.08, 2.7, PALE_BLUE, BLUE, 10)
    line(slide, 6.65, 2.48, 6.65, 2.9, BLUE, 2, True)
    shape(slide, 1.35, 2.92, 10.6, 1.28, NAVY, NAVY)
    text(slide, "SECURE AI OPERATIONS LAYER", 1.65, 3.2, 3.7, 0.34, 17, WHITE, True)
    text(slide, "Agents  •  Knowledge  •  Reasoning  •  Tools  •  Guardrails  •  Audit",
         5.0, 3.22, 6.55, 0.32, 12, RGBColor(198, 217, 234), False, PP_ALIGN.RIGHT)
    line(slide, 6.65, 4.2, 6.65, 4.63, GREEN, 2, True)
    systems = [
        ("Datadog", PURPLE),
        ("Service Desk", BLUE),
        ("CMDB / Change", CYAN),
        ("Runbooks / KM", ORANGE),
        ("Cloud / Infra", GREEN),
        ("Security Tools", RED),
    ]
    x = 0.75
    for label, color in systems:
        shape(slide, x, 4.68, 1.83, 0.92, WHITE, color)
        text(slide, label, x + 0.08, 4.94, 1.67, 0.28, 10, color, True, PP_ALIGN.CENTER)
        x += 2.02
    statement(slide, "Systems of Record ยังคงเป็นแหล่งข้อมูลจริง — AI เพิ่ม intelligence และ orchestration คร่อมระบบเหล่านั้น", 6.25)
    note_list.append(notes(
        "สไลด์ 8 — Platform concept",
        "3 นาที",
        [
            "อธิบายแพลตฟอร์มโดยไม่เริ่มจากชื่อเทคโนโลยี: เป็นชั้นกลางที่เชื่อมคน ความรู้ และระบบ",
            "Datadog, Service Desk, CMDB และ Knowledge ยังเป็นเจ้าของข้อมูลของตนเอง",
            "AI ต้องเรียกใช้ข้อมูลตามสิทธิ์ของทีมและบันทึก audit metadata",
        ],
    ))


def add_capabilities(prs, note_list):
    slide = new_slide(prs, LIGHT)
    header(slide, "หกความสามารถที่เปลี่ยน AI จาก Demo ให้เป็นงานจริง", "Platform", 9)
    items = [
        ("AGENT", "ผู้เชี่ยวชาญเฉพาะงาน\nเช่น Operations Analyst", "A", BLUE),
        ("KNOWLEDGE", "RAG พร้อม source, page\nและ access control", "K", CYAN),
        ("INTEGRATION", "API / MCP เชื่อมระบบ\nแบบ read-only ก่อน", "I", ORANGE),
        ("OBSERVABILITY", "Metric, log, trace, event\nจาก Datadog", "O", PURPLE),
        ("GUARDRAIL", "PII/DLP, tool policy\nและ least privilege", "G", GREEN),
        ("AUDIT", "ใครเรียก agent/tool ใด\nเมื่อไรและผลสำเร็จหรือไม่", "T", RED),
    ]
    positions = [(0.72, 1.82), (4.55, 1.82), (8.38, 1.82), (0.72, 4.14), (4.55, 4.14), (8.38, 4.14)]
    for item, (x, y) in zip(items, positions):
        title_, body, glyph, color = item
        card(slide, title_, body, x, y, 3.55, 1.75, color, WHITE, glyph)
    note_list.append(notes(
        "สไลด์ 9 — Platform capabilities",
        "2 นาที",
        [
            "เน้นว่าการมี model อย่างเดียวไม่เท่ากับมี enterprise platform",
            "RAG ต้องรักษา ACL และ citation; Integration ต้องจำกัด connection/tool ตามทีม",
            "Guardrail และ Audit เป็น capability ของ platform ไม่ควรฝากไว้กับ prompt เพียงอย่างเดียว",
        ],
    ))


def add_responsibility(prs, note_list):
    slide = new_slide(prs)
    header(slide, "ใครรับผิดชอบอะไร?", "Operating model", 10)
    columns = [
        ("SYSTEMS OF RECORD", ["เก็บข้อมูลจริง", "บังคับ transaction rule", "คง ownership เดิม"], BLUE),
        ("APPLIED AI", ["เชื่อม context", "สรุปและจัดลำดับ", "เสนอ action พร้อม evidence"], ORANGE),
        ("HUMAN OWNER", ["ตัดสินใจความเสี่ยง", "อนุมัติ write action", "รับผิดชอบผลลัพธ์"], GREEN),
    ]
    x = 0.78
    for title_, bullets, color in columns:
        shape(slide, x, 1.85, 3.85, 3.55, WHITE, LINE)
        shape(slide, x, 1.85, 3.85, 0.7, color, color)
        text(slide, title_, x + 0.18, 2.04, 3.5, 0.28, 12, WHITE, True, PP_ALIGN.CENTER)
        for index, bullet in enumerate(bullets):
            icon(slide, str(index + 1), x + 0.3, 2.87 + index * 0.72, 0.38, color, 10)
            text(slide, bullet, x + 0.82, 2.87 + index * 0.72, 2.65, 0.32, 11, INK, index == 0)
        x += 4.05
    statement(slide, "AI ช่วยตัดสินใจได้ดีขึ้น แต่ Accountability ยังอยู่กับเจ้าของบริการและนโยบายขององค์กร", 6.2)
    note_list.append(notes(
        "สไลด์ 10 — Responsibility",
        "2 นาที",
        [
            "ใช้สไลด์นี้ลดความกังวลว่า AI จะเข้ามาแทนระบบหรือผู้รับผิดชอบ",
            "AI ไม่ควรเปลี่ยนข้อมูลสำคัญโดยข้าม validation ของ system of record",
            "เริ่มจาก read-only recommendation แล้วค่อยเพิ่ม action เมื่อ control พร้อม",
        ],
    ))


def add_maturity(prs, note_list):
    slide = new_slide(prs, LIGHT)
    header(slide, "เริ่มเล็ก แต่สร้างทางไปสู่ความสามารถใหม่", "Maturity", 11)
    levels = [
        ("1", "ASSIST", "ค้น Knowledge\nสรุปข้อมูล", BLUE, PALE_BLUE),
        ("2", "ANALYZE", "เชื่อม evidence\nจัดลำดับ hypothesis", CYAN, PALE_CYAN),
        ("3", "RECOMMEND", "แนะนำ action\nพร้อม risk/owner", ORANGE, PALE_ORANGE),
        ("4", "ORCHESTRATE", "ดำเนิน workflow\nเมื่อได้รับอนุมัติ", GREEN, PALE_GREEN),
    ]
    x = 0.85
    for index, (number, title_, body, color, fill) in enumerate(levels):
        y = 4.85 - index * 0.66
        height = 1.25 + index * 0.66
        shape(slide, x + index * 3.0, y, 2.65, height, fill, color)
        text(slide, number, x + index * 3.0 + 0.18, y + 0.18, 0.38, 0.32, 12, color, True, PP_ALIGN.CENTER)
        text(slide, title_, x + index * 3.0 + 0.62, y + 0.18, 1.75, 0.32, 13, color, True)
        text(slide, body, x + index * 3.0 + 0.22, y + 0.75, 2.2, 0.62, 10.5, INK, False, PP_ALIGN.CENTER)
    statement(slide, "เป้าหมายไม่ใช่กระโดดไป Autonomous ทันที แต่เพิ่มความสามารถพร้อม Control ในแต่ละขั้น", 6.25)
    note_list.append(notes(
        "สไลด์ 11 — Maturity",
        "2 นาที",
        [
            "Pilot ที่ดีควรเริ่มระดับ Analyze/Recommend ซึ่งให้คุณค่าสูงและความเสี่ยงต่ำกว่า write automation",
            "แต่ละขั้นต้องมี acceptance criteria และ owner ชัดเจน",
            "Demo วันนี้อยู่ระดับ Analyze และ Recommend",
        ],
    ))


def add_use_case_portfolio(prs, note_list):
    slide = new_slide(prs)
    header(slide, "Banking IT Use Cases: จัดลำดับด้วยเกณฑ์ที่ตรวจสอบได้", "Use cases", 12)
    criteria = [
        ("OPERATIONAL VALUE", "35%", "Customer impact • MTTR • risk", BLUE, PALE_BLUE),
        ("EVIDENCE READINESS", "30%", "Telemetry • KM • provenance", CYAN, PALE_CYAN),
        ("DELIVERY FEASIBILITY", "20%", "Integration • process • effort", ORANGE, PALE_ORANGE),
        ("CONTROL READINESS", "15%", "Read-only • approval • audit", GREEN, PALE_GREEN),
    ]
    for index, (label, weight, detail, color, fill) in enumerate(criteria):
        x = 0.62 + index * 3.08
        shape(slide, x, 1.58, 2.82, 0.88, fill, color)
        text(slide, label, x + 0.16, 1.72, 1.98, 0.22, 8.5, color, True)
        text(slide, weight, x + 2.12, 1.67, 0.54, 0.3, 14, color, True, PP_ALIGN.RIGHT)
        text(slide, detail, x + 0.16, 2.08, 2.5, 0.22, 8.2, MUTED)

    shape(slide, 0.62, 2.62, 12.02, 0.48, NAVY, NAVY)
    text(slide, "Priority Score = 0.35V + 0.30E + 0.20F + 0.15C  •  ให้คะแนน 1 (ต่ำ) – 5 (สูง)",
         0.82, 2.74, 11.62, 0.24, 11, WHITE, True, PP_ALIGN.CENTER)

    columns = [
        ("Use case", 0.62, 2.74), ("V", 3.36, 0.54), ("E", 3.90, 0.54),
        ("F", 4.44, 0.54), ("C", 4.98, 0.54), ("Score", 5.52, 0.92),
        ("Phase", 6.44, 1.18), ("Basis / assumption", 7.62, 5.02),
    ]
    for label, x, width in columns:
        shape(slide, x, 3.30, width, 0.40, PALE_BLUE, MID, False)
        text(slide, label, x + 0.05, 3.38, width - 0.1, 0.22, 8.5, INK, True,
             PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)

    rows = [
        ("Morning briefing", 4, 5, 5, 5, "4.65", "START", "Telemetry พร้อม • Read-only"),
        ("Incident triage", 5, 5, 4, 4, "4.65", "START", "Impact สูง • Signals พร้อม"),
        ("Runbook advisor", 4, 4, 4, 5, "4.15", "NEXT", "ขึ้นกับคุณภาพ Knowledge"),
        ("Change risk", 5, 3, 3, 4, "3.85", "PREPARE", "ขึ้นกับ Change coverage"),
        ("Auto remediation", 5, 3, 2, 1, "3.20", "LATER", "Write risk • ต้องอนุมัติ"),
    ]
    for row_index, row in enumerate(rows):
        y = 3.70 + row_index * 0.43
        fill = WHITE if row_index % 2 == 0 else LIGHT
        values = [row[0], *map(str, row[1:5]), row[5], row[6], row[7]]
        for col_index, ((_, x, width), value) in enumerate(zip(columns, values)):
            shape(slide, x, y, width, 0.43, fill, LINE, False)
            align = PP_ALIGN.LEFT if col_index in (0, 7) else PP_ALIGN.CENTER
            color = BLUE if col_index == 6 and value == "START" else INK
            text(slide, value, x + 0.06, y + 0.09, width - 0.12, 0.23, 8.5, color,
                 col_index in (5, 6), align, MSO_ANCHOR.MIDDLE)

    text(slide, "ตัวอย่างคะแนน (ไม่ใช่ Banking benchmark): สมมติว่ามี Datadog telemetry แบบ read-only; ความพร้อมของ KM/Change แตกต่างตาม use case",
         0.68, 5.98, 11.9, 0.30, 8.5, MUTED, True)
    text(slide, "Method: Proposed Solution Discovery Scoring Framework v1.0. References informing criteria—not the formula: NIST AI RMF 1.0, NIST AI 100-1 (2023), doi.org/10.6028/NIST.AI.100-1; Google SRE Workbook, Incident Response, sre.google/workbook/incident-response/",
         0.68, 6.32, 11.9, 0.52, 7.4, MUTED)
    note_list.append(notes(
        "สไลด์ 12 — Use-case portfolio",
        "2 นาที",
        [
            "นี่คือกรอบให้คะแนนภายในที่เปิดเผยวิธีคิด ไม่ใช่ผลสำรวจหรือ benchmark ของอุตสาหกรรมธนาคาร",
            "ให้ทีมลูกค้าให้คะแนนแต่ละเกณฑ์ 1–5 ใน discovery workshop; น้ำหนัก 35/30/20/15 เป็นค่าเริ่มต้นที่เสนอและปรับได้เมื่อเจ้าของบริการเห็นชอบ",
            "คะแนนตัวอย่างสมมติว่ามี Datadog telemetry แบบ read-only; ความพร้อมของ Knowledge, Change และ approval ต้องตรวจสอบกับข้อมูลจริง",
            "NIST AI RMF ใช้อ้างอิงแนวคิด risk/control และ Google SRE ใช้อ้างอิงแนวคิด incident response/operational outcomes; ทั้งสองแหล่งไม่ได้กำหนดสูตรหรือน้ำหนักนี้",
            "ก่อนนำไปใช้ตัดสินใจจริง ให้บันทึกเจ้าของคะแนน หลักฐาน วันที่ประเมิน และเหตุผลของคะแนนทุกช่อง",
        ],
    ))


def add_briefing_use_case(prs, note_list):
    slide = new_slide(prs, LIGHT)
    header(slide, "Use Case 1 — Morning Operations Briefing ใน 3 นาที", "Use cases", 13)
    sources = [("Datadog", PURPLE), ("Service Desk", BLUE), ("Change", ORANGE), ("Knowledge", CYAN)]
    x = 0.72
    for label, color in sources:
        shape(slide, x, 2.0, 2.15, 0.72, WHITE, color)
        text(slide, label, x + 0.08, 2.2, 1.99, 0.28, 11, color, True, PP_ALIGN.CENTER)
        line(slide, x + 1.08, 2.72, 6.65, 3.28, color, 1.2, True)
        x += 2.45
    shape(slide, 5.2, 3.02, 2.9, 1.14, NAVY, NAVY)
    text(slide, "OPERATIONS AGENT", 5.45, 3.39, 2.4, 0.3, 15, WHITE, True, PP_ALIGN.CENTER)
    outputs = [
        ("Executive summary", "ผลกระทบและบริการสำคัญ", BLUE),
        ("Top risks", "เรียงตาม severity และ customer impact", ORANGE),
        ("Owner & next step", "ใครต้องทำอะไรภายในเมื่อไร", GREEN),
    ]
    x = 0.95
    for title_, body, color in outputs:
        card(slide, title_, body, x, 4.85, 3.7, 1.25, color, WHITE)
        x += 4.0
    note_list.append(notes(
        "สไลด์ 13 — Morning briefing",
        "2 นาที",
        [
            "แทนที่จะเปิด dashboard หลายหน้า ผู้บริหารได้ summary ที่มี link กลับไปยัง evidence",
            "AI ไม่ควรซ่อน uncertainty ต้องระบุข้อมูลที่ยังขาด",
            "เหมาะเป็น use case แรกเพราะเป็น read-only และวัดเวลาที่ประหยัดได้ง่าย",
        ],
    ))


def add_incident_story(prs, note_list):
    slide = new_slide(prs)
    header(slide, "Use Case 2 — ลูกค้ารายงานว่า Mobile Banking Transfer ช้า", "Incident", 14)
    shape(slide, 0.72, 1.82, 3.2, 4.42, NAVY, NAVY)
    text(slide, "USER SIGNAL", 1.0, 2.18, 2.65, 0.3, 11, CYAN, True, PP_ALIGN.CENTER)
    text(slide, "“โอนเงินแล้วหน้าจอ\nหมุนนานกว่าปกติ”", 1.0, 2.88, 2.65, 1.0, 23, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    pill(slide, "CUSTOMER IMPACT", 1.3, 4.32, 2.0, NAVY_2, ORANGE)
    text(slide, "คำถามของทีมปฏิบัติการ", 4.35, 1.92, 3.5, 0.4, 17, INK, True)
    questions = [
        ("1", "เกิดกับใครและช่องทางใด?", BLUE),
        ("2", "เริ่มเมื่อไรและสัมพันธ์กับ Change ใด?", CYAN),
        ("3", "Bottleneck อยู่ที่ App, DB, Network หรือ Dependency?", ORANGE),
        ("4", "มี Runbook และ action ที่ปลอดภัยอะไรบ้าง?", GREEN),
    ]
    for index, (number, value, color) in enumerate(questions):
        y = 2.63 + index * 0.83
        icon(slide, number, 4.38, y, 0.48, color, 12)
        text(slide, value, 5.05, y + 0.05, 6.8, 0.36, 13, INK, index == 0)
    statement(slide, "คำถามง่ายหนึ่งประโยค ต้องใช้หลักฐานจากหลายระบบจึงจะตอบได้อย่างรับผิดชอบ", 6.3)
    note_list.append(notes(
        "สไลด์ 14 — Incident story",
        "2 นาที",
        [
            "ให้ผู้ฟังจินตนาการเหตุการณ์ที่คุ้นเคย ไม่ต้องใช้ข้อมูลลูกค้าจริง",
            "ประเด็นสำคัญคือ user symptom ไม่ได้บอก root cause",
            "AI ที่ดีต้องแตกคำถามและรู้ว่าควรเรียก evidence ใด",
        ],
        "ต่อไปคือภาพการเชื่อม evidence ที่เป็นหัวใจของ demo",
    ))


def add_correlation_visual(prs, note_list):
    slide = new_slide(prs, NAVY)
    header(slide, "AI Operations Agent เชื่อมหลักฐานก่อนให้คำแนะนำ", "Datadog + AI", 15, dark=True)
    sources = [
        ("RUM", "Latency by journey", 0.55, 1.92, BLUE),
        ("APM", "Trace & dependency", 0.55, 3.12, CYAN),
        ("LOGS", "Errors & patterns", 0.55, 4.32, PURPLE),
        ("INFRA / DB", "Resource saturation", 10.55, 1.92, GREEN),
        ("CHANGE", "Deployment timeline", 10.55, 3.12, ORANGE),
        ("KM / RUNBOOK", "Known fix & owner", 10.55, 4.32, RED),
    ]
    for title_, body, x, y, color in sources:
        shape(slide, x, y, 2.25, 0.82, NAVY_2, color)
        text(slide, title_, x + 0.14, y + 0.13, 0.9, 0.26, 10.5, color, True)
        text(slide, body, x + 0.95, y + 0.14, 1.15, 0.34, 8.5, RGBColor(192, 211, 228), False, PP_ALIGN.RIGHT)
        if x < 5:
            line(slide, x + 2.25, y + 0.41, 4.42, 3.51, color, 1.4, True)
        else:
            line(slide, x, y + 0.41, 8.93, 3.51, color, 1.4, True)
    circle(slide, 4.4, 2.1, 4.55, NAVY_2, BLUE)
    text(slide, "AI OPERATIONS\nAGENT", 4.86, 2.72, 3.65, 0.92, 25, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    text(slide, "Correlate • Rank • Explain", 5.12, 3.92, 3.1, 0.32, 11, CYAN, True, PP_ALIGN.CENTER)
    pill(slide, "EVIDENCE-BACKED", 5.55, 4.48, 2.2, NAVY, ORANGE)
    statement(slide, "ผลลัพธ์: Timeline + Ranked hypotheses + Evidence + Runbook + Approval-ready action", 6.35, CYAN, True)
    note_list.append(notes(
        "สไลด์ 15 — Correlation visual",
        "3 นาที",
        [
            "Datadog ให้ telemetry ที่ละเอียด ส่วน Knowledge/Change เติมบริบทที่ telemetry อย่างเดียวไม่มี",
            "Agent ไม่ควรเดา root cause จาก alert เดียว แต่ต้องจัดลำดับ hypothesis พร้อมหลักฐานสนับสนุนและหลักฐานที่ขัดแย้ง",
            "ผลลัพธ์สุดท้ายต้องบอก gap และ confidence ไม่ใช่ตอบอย่างมั่นใจเกินจริง",
        ],
    ))


def add_demo_flow(prs, note_list):
    slide = new_slide(prs)
    header(slide, "Live Demo — NexoraAI + Datadog จากคำถามสู่การตัดสินใจ", "Demo", 16, subtitle="ใช้ Datadog demo tenant และ Knowledge ที่ไม่ใช่ข้อมูลลูกค้าจริง")
    steps = [
        ("1", "ASK", "“ช่วยตรวจสอบเหตุการณ์\nMobile Banking ช้า”", BLUE),
        ("2", "OBSERVE", "ดึง alert, event, metric\nและ time window จาก Datadog", PURPLE),
        ("3", "CORRELATE", "เทียบ change timeline\nและค้น runbook ใน KM", ORANGE),
        ("4", "VISUALIZE", "สร้างกราฟ severity / latency\nจากข้อมูล tool จริง", CYAN),
        ("5", "DECIDE", "เสนอ next action, owner,\nrisk และ approval", GREEN),
    ]
    x = 0.55
    for index, (number, title_, body, color) in enumerate(steps):
        shape(slide, x, 2.08, 2.25, 3.3, WHITE, LINE)
        circle(slide, x + 0.77, 2.43, 0.72, color)
        text(slide, number, x + 0.77, 2.6, 0.72, 0.3, 13, WHITE, True, PP_ALIGN.CENTER)
        text(slide, title_, x + 0.2, 3.37, 1.85, 0.35, 13, color, True, PP_ALIGN.CENTER)
        text(slide, body, x + 0.22, 3.98, 1.8, 0.75, 10, MUTED, False, PP_ALIGN.CENTER)
        if index < len(steps) - 1:
            line(slide, x + 2.25, 3.7, x + 2.52, 3.7, color, 1.8, True)
        x += 2.55
    statement(slide, "Demo success ไม่ใช่แค่ได้คำตอบ แต่ต้องเห็น source, tool, chart และขอบเขตการอนุมัติ", 6.22)
    note_list.append(notes(
        "สไลด์ 16 — Demo flow",
        "1 นาที",
        [
            "แจ้งว่าจะใช้ข้อมูลสาธิตและ Agent แบบ read-only",
            "ถ้า live connection ไม่พร้อม ให้ใช้ screenshot/video fallback โดยบอกผู้ฟังอย่างตรงไปตรงมา",
            "จับเวลารวม demo ไม่เกิน 8 นาที",
        ],
    ))


def add_demo_prompt(prs, note_list, page, title_, prompt, objective, evidence, color):
    slide = new_slide(prs, LIGHT)
    header(slide, title_, "Live demo", page)
    text(slide, "PROMPT", 0.75, 1.8, 1.3, 0.3, 10, color, True)
    shape(slide, 0.75, 2.18, 11.85, 1.28, WHITE, color)
    text(slide, prompt, 1.08, 2.5, 11.2, 0.62, 17, INK, True, PP_ALIGN.LEFT, MSO_ANCHOR.MIDDLE)
    card(slide, "สิ่งที่ต้องเห็น", objective, 0.75, 4.0, 5.72, 1.55, color, WHITE, "✓")
    card(slide, "หลักฐานที่ใช้", evidence, 6.82, 4.0, 5.78, 1.55, CYAN, WHITE, "E")
    pill(slide, "READ-ONLY", 0.78, 6.08, 1.25, PALE_GREEN, GREEN)
    pill(slide, "AUDITABLE", 2.2, 6.08, 1.25, PALE_BLUE, BLUE)
    pill(slide, "NO CUSTOMER DATA", 3.62, 6.08, 1.65, PALE_ORANGE, ORANGE)
    note_list.append(notes(
        f"สไลด์ {page} — {title_}",
        "1–2 นาที",
        [
            "อ่าน prompt ให้ผู้ฟังเห็นว่าเป็นภาษาธรรมดา ไม่ต้องรู้ชื่อ query หรือ dashboard",
            f"ชี้ผลลัพธ์ที่คาดหวัง: {objective}",
            f"ชี้แหล่งหลักฐาน: {evidence}",
        ],
    ))


def add_demo_result(prs, note_list):
    slide = new_slide(prs)
    header(slide, "ผลลัพธ์ที่ดีต้องตอบได้ว่า “รู้อะไร เพราะอะไร และทำอะไรต่อ”", "Demo result", 20)
    shape(slide, 0.72, 1.72, 12.0, 4.82, WHITE, LINE)
    pill(slide, "INCIDENT BRIEF", 1.02, 2.03, 1.55, PALE_BLUE, BLUE)
    text(slide, "Mobile Transfer latency increased after application deployment", 1.02, 2.53, 7.8, 0.45, 18, INK, True)
    text(slide, "Impact", 1.02, 3.18, 1.2, 0.3, 11, MUTED, True)
    text(slide, "P95 latency +180% • Error rate concentrated in transfer confirmation", 2.22, 3.18, 7.0, 0.32, 11.5, INK)
    text(slide, "Evidence", 1.02, 3.83, 1.2, 0.3, 11, MUTED, True)
    text(slide, "RUM journey → APM dependency → DB wait → change at 10:05", 2.22, 3.83, 7.0, 0.32, 11.5, INK)
    text(slide, "Hypothesis", 1.02, 4.48, 1.2, 0.3, 11, MUTED, True)
    text(slide, "Connection-pool regression after release • Confidence: Medium–High", 2.22, 4.48, 7.0, 0.32, 11.5, INK)
    shape(slide, 9.42, 2.16, 2.82, 3.72, PALE_GREEN, GREEN)
    text(slide, "NEXT ACTION", 9.72, 2.47, 2.22, 0.3, 12, GREEN, True, PP_ALIGN.CENTER)
    text(slide, "Validate pool setting\nCompare previous release\nPrepare rollback\n\nOwner: App + DBA\nApproval: Required",
         9.75, 3.05, 2.15, 1.95, 12, INK, True, PP_ALIGN.CENTER)
    pill(slide, "NO AUTO-CHANGE", 9.78, 5.28, 2.08, WHITE, RED)
    note_list.append(notes(
        "สไลด์ 20 — Demo result",
        "2 นาที",
        [
            "ตัวเลขบนสไลด์เป็นตัวอย่างรูปแบบผลลัพธ์ ไม่ใช่ข้อมูลจริงของธนาคาร",
            "ชี้ว่าคำแนะนำผูกกับ evidence chain และมี confidence/gap",
            "Action ที่เปลี่ยน production ต้องมี owner และ approval",
        ],
    ))


def add_more_use_cases(prs, note_list):
    slide = new_slide(prs, LIGHT)
    header(slide, "จาก Incident หนึ่งเหตุการณ์ สู่ Operational Capabilities ทั้งองค์กร", "Banking use cases", 21)
    items = [
        ("END-OF-DAY / BATCH", "ตรวจ job delay, dependency และผลกระทบต่อ settlement", "B", BLUE),
        ("ATM / BRANCH", "สรุป availability ตามพื้นที่และจัดลำดับ dispatch", "A", CYAN),
        ("CHANGE RISK", "เชื่อม release กับ error/latency ก่อน–หลัง change", "Δ", ORANGE),
        ("AUDIT EVIDENCE", "รวบรวม evidence พร้อม source และ timestamp", "E", PURPLE),
        ("CAPACITY", "หา saturation trend ก่อนชน threshold", "C", GREEN),
        ("POST-INCIDENT", "ร่าง timeline, lessons learned และ KM update", "P", RED),
    ]
    positions = [(0.72, 1.82), (4.55, 1.82), (8.38, 1.82), (0.72, 4.14), (4.55, 4.14), (8.38, 4.14)]
    for item, (x, y) in zip(items, positions):
        title_, body, glyph, color = item
        card(slide, title_, body, x, y, 3.55, 1.75, color, WHITE, glyph)
    note_list.append(notes(
        "สไลด์ 21 — More banking use cases",
        "2 นาที",
        [
            "แต่ละ use case ใช้ platform capability เดิม แต่เปลี่ยน Agent, Knowledge และ Integration",
            "เริ่มจาก use case ที่ read-only และมีข้อมูลพร้อม",
            "ไม่ควรสร้าง agent จำนวนมากโดยไม่มี owner, metric และ lifecycle",
        ],
    ))


def add_governance(prs, note_list):
    slide = new_slide(prs, NAVY)
    header(slide, "Enterprise AI ต้องปลอดภัยตั้งแต่ Identity ถึง Action", "Governance", 22, dark=True)
    layers = [
        ("IDENTITY", "User / Team / Service identity", BLUE),
        ("DATA", "Personal / Team / Global ACL", CYAN),
        ("KNOWLEDGE", "Source, page, freshness, citation", PURPLE),
        ("TOOLS", "Connection ownership, allowlist, read-only", ORANGE),
        ("MODEL", "Guardrail, PII/DLP, prompt boundary", GREEN),
        ("ACTION", "Risk class, approval, audit", RED),
    ]
    y = 1.75
    for index, (label, body, color) in enumerate(layers):
        shape(slide, 1.1 + index * 0.32, y + index * 0.68, 10.15 - index * 0.64, 0.56, NAVY_2, color)
        text(slide, label, 1.32 + index * 0.32, y + 0.15 + index * 0.68, 1.35, 0.22, 9.5, color, True)
        text(slide, body, 2.85 + index * 0.32, y + 0.15 + index * 0.68, 7.4 - index * 0.64, 0.22, 9.5, WHITE, False, PP_ALIGN.RIGHT)
    statement(slide, "Guardrail ที่มีผลต่อสิทธิ์และ Tool ต้องบังคับใช้ฝั่ง Server — ไม่ใช่พึ่ง Prompt เพียงอย่างเดียว", 6.3, CYAN, True)
    note_list.append(notes(
        "สไลด์ 22 — Governance",
        "3 นาที",
        [
            "อธิบาย defense in depth ตั้งแต่ใครเรียก ไปจนถึง action ใดได้รับอนุญาต",
            "Audit ที่ดีเก็บ metadata ที่จำเป็น โดยไม่เก็บ raw prompt, credential หรือ tool output ที่อ่อนไหว",
            "สำหรับธนาคารควรเริ่ม read-only, least privilege และ segregation of duties",
        ],
    ))


def add_roadmap(prs, note_list):
    slide = new_slide(prs)
    header(slide, "90-Day Pilot: พิสูจน์ Value และ Control ไปพร้อมกัน", "Roadmap", 23)
    phases = [
        ("0–30 DAYS", "FOUNDATION", ["เลือก 1 service", "เชื่อม Datadog read-only", "เตรียม runbook/KM", "กำหนด baseline"], BLUE),
        ("31–60 DAYS", "PILOT", ["Incident prompts", "Evidence timeline", "Chart + citation", "วัด accuracy/MTTR"], ORANGE),
        ("61–90 DAYS", "OPERATE", ["UAT กับ NOC/SRE", "Guardrail review", "Runbook feedback", "Scale decision"], GREEN),
    ]
    x = 0.72
    for period, title_, bullets, color in phases:
        shape(slide, x, 1.82, 3.86, 4.25, WHITE, LINE)
        shape(slide, x, 1.82, 3.86, 0.76, color, color)
        text(slide, period, x + 0.2, 2.04, 3.46, 0.28, 11, WHITE, True, PP_ALIGN.CENTER)
        text(slide, title_, x + 0.25, 2.86, 3.36, 0.38, 16, color, True, PP_ALIGN.CENTER)
        for index, bullet in enumerate(bullets):
            icon(slide, "✓", x + 0.35, 3.52 + index * 0.57, 0.32, color, 9)
            text(slide, bullet, x + 0.82, 3.51 + index * 0.57, 2.55, 0.28, 10.5, INK)
        x += 4.08
    note_list.append(notes(
        "สไลด์ 23 — Pilot roadmap",
        "2 นาที",
        [
            "จำกัด pilot ให้หนึ่ง critical service และหนึ่งทีม owner",
            "เก็บ baseline ก่อนเริ่ม เช่น investigation time, MTTR, repeat incident และเวลาเตรียม briefing",
            "Scale decision ต้องดูทั้ง value, accuracy, adoption และ control evidence",
        ],
    ))


def add_takeaways(prs, note_list):
    slide = new_slide(prs, NAVY)
    header(slide, "สามเรื่องที่อยากให้จำก่อนเริ่มเกม", "Takeaways", 24, dark=True)
    items = [
        ("1", "AI IS A LAYER", "AI เชื่อม Systems of Record\nไม่ใช่แทนที่ทุกระบบ", BLUE),
        ("2", "EVIDENCE FIRST", "คำตอบที่ดีต้องมี source, context,\nconfidence และ gap", ORANGE),
        ("3", "CONTROL BY DESIGN", "สิทธิ์, guardrail, approval และ audit\nต้องมากับ use case ตั้งแต่วันแรก", GREEN),
    ]
    x = 0.8
    for number, title_, body, color in items:
        shape(slide, x, 1.92, 3.8, 3.9, NAVY_2, NAVY_2)
        circle(slide, x + 1.38, 2.28, 0.95, color)
        text(slide, number, x + 1.38, 2.51, 0.95, 0.35, 16, WHITE, True, PP_ALIGN.CENTER)
        text(slide, title_, x + 0.4, 3.62, 3.0, 0.4, 17, color, True, PP_ALIGN.CENTER)
        text(slide, body, x + 0.42, 4.34, 2.96, 0.82, 12, WHITE, False, PP_ALIGN.CENTER)
        x += 4.05
    text(slide, "จาก Observability → Understanding → Decision → Governed Action",
         1.25, 6.38, 10.85, 0.4, 16, CYAN, True, PP_ALIGN.CENTER)
    note_list.append(notes(
        "สไลด์ 24 — Takeaways",
        "1 นาที",
        [
            "ทวนสามคำสำคัญ: Layer, Evidence, Control",
            "บอกผู้ฟังว่าคำถามในเกมทั้งหมดมาจากหลักการเหล่านี้และ demo",
        ],
        "เข้าสู่เกม 15 ข้อ",
    ))


QUIZ = [
    {
        "question": "เป้าหมายหลักของ Applied AI ใน IT Operations คืออะไร?",
        "options": ["A  เพิ่มจำนวน Dashboard", "B  เชื่อมข้อมูลเป็นการตัดสินใจที่เร็วและปลอดภัย", "C  แทนที่ทีม IT ทั้งหมด", "D  ย้ายทุกระบบขึ้น Cloud"],
        "answer": "B",
        "why": "Applied AI เน้น Faster understanding, safer decision และ repeatable operation",
    },
    {
        "question": "AI Operations Platform ควรมีบทบาทอย่างไรต่อ Systems of Record?",
        "options": ["A  ลบทิ้งและสร้างใหม่", "B  คัดลอกข้อมูลทั้งหมดมาไว้ที่ AI", "C  เป็น intelligence/orchestration layer คร่อมระบบเดิม", "D  ปิดการตรวจสอบสิทธิ์"],
        "answer": "C",
        "why": "ระบบเดิมยังเป็นเจ้าของข้อมูลจริง ส่วน AI เชื่อม context และ workflow",
    },
    {
        "question": "ข้อใดเป็นลำดับ Applied AI ที่ถูกต้อง?",
        "options": ["A  Act → Guess → Hide", "B  Sense → Understand → Recommend → Orchestrate", "C  Search → Delete → Replace", "D  Train → Deploy → Forget"],
        "answer": "B",
        "why": "เป็น mental model สี่ขั้นที่ใช้ตลอดการนำเสนอ",
    },
    {
        "question": "เมื่อผู้ใช้บอกว่า Mobile Banking ช้า สิ่งแรกที่ AI ควรทำคืออะไร?",
        "options": ["A  Restart production ทันที", "B  เดา root cause", "C  รวบรวม signal และกำหนด scope/time window", "D  ปิด alert"],
        "answer": "C",
        "why": "ต้องเริ่มจากหลักฐานและขอบเขตเหตุการณ์ก่อนแนะนำ action",
    },
    {
        "question": "Datadog มีบทบาทหลักอะไรใน demo?",
        "options": ["A  เป็นแหล่ง telemetry และ event evidence", "B  เป็น HR system", "C  เป็นระบบอนุมัติสินเชื่อ", "D  เป็น document editor"],
        "answer": "A",
        "why": "Datadog ให้ RUM, APM, logs, infrastructure/database signals และ events",
    },
    {
        "question": "Knowledge / Runbook เติมสิ่งใดที่ telemetry อย่างเดียวมักไม่มี?",
        "options": ["A  สีของ dashboard", "B  Known fix, owner และขั้นตอนปฏิบัติ", "C  Password ผู้ดูแล", "D  ข้อมูลลูกค้าทั้งหมด"],
        "answer": "B",
        "why": "KM เติม operational context และวิธีปฏิบัติที่ผ่านการรับรอง",
    },
    {
        "question": "ผลลัพธ์ Incident Analysis ที่ดีควรมีอะไร?",
        "options": ["A  คำตอบสั้นโดยไม่มีที่มา", "B  Root cause เดียวแบบมั่นใจ 100%", "C  Timeline, hypotheses, evidence, confidence และ gap", "D  Raw logs ทั้งหมด"],
        "answer": "C",
        "why": "ผลลัพธ์ต้องตรวจสอบย้อนกลับและแสดง uncertainty",
    },
    {
        "question": "ทำไม Pilot ควรเริ่มแบบ Read-only?",
        "options": ["A  เพราะ AI อ่านไม่ได้", "B  ลดความเสี่ยงขณะพิสูจน์ value และ accuracy", "C  ไม่ต้องมี audit", "D  ทำให้ข้อมูลหายเร็วขึ้น"],
        "answer": "B",
        "why": "Analyze/Recommend ให้คุณค่าสูงโดยยังไม่เสี่ยงกับ production write action",
    },
    {
        "question": "ข้อใดเป็น Guardrail ที่เหมาะสม?",
        "options": ["A  Tool allowlist และ least privilege", "B  แชร์ API key ให้ทุกทีม", "C  เก็บ credential ใน prompt", "D  ปิด access control"],
        "answer": "A",
        "why": "สิทธิ์และ tool policy ต้องจำกัดตามผู้ใช้ ทีม และ use case",
    },
    {
        "question": "เหตุใด Guardrail ที่สำคัญจึงไม่ควรพึ่ง Prompt อย่างเดียว?",
        "options": ["A  Prompt ใช้ภาษาไทยไม่ได้", "B  Policy ที่มีผลต่อสิทธิ์ต้องบังคับใช้ฝั่ง Server", "C  Prompt ไม่มีข้อความ", "D  Server ไม่รู้จัก User"],
        "answer": "B",
        "why": "Server-side enforcement เป็น security boundary ที่ตรวจสอบได้",
    },
    {
        "question": "Metric ใดสัมพันธ์กับ Incident Response โดยตรงที่สุด?",
        "options": ["A  จำนวนสไลด์", "B  MTTR", "C  จำนวน model", "D  จำนวน dashboard theme"],
        "answer": "B",
        "why": "Mean Time to Restore/Resolve สะท้อนความเร็วในการกู้บริการ",
    },
    {
        "question": "กราฟที่ AI สร้างเพื่อใช้ตัดสินใจควรมาจากอะไร?",
        "options": ["A  ตัวเลขที่ model คาดเดา", "B  ข้อมูล exact จาก tool ที่สำเร็จ", "C  ข่าวลือใน chat", "D  ค่า random"],
        "answer": "B",
        "why": "Visualization ต้อง trace กลับไปยังผลลัพธ์จากระบบจริง",
    },
    {
        "question": "Use case ใดเหมาะเป็น Pilot แรกมากที่สุด?",
        "options": ["A  Autonomous production remediation", "B  Incident triage และ morning briefing แบบ read-only", "C  เปลี่ยน core banking", "D  อนุมัติธุรกรรมอัตโนมัติ"],
        "answer": "B",
        "why": "ข้อมูลพร้อม วัดผลได้ และความเสี่ยงต่ำกว่า write automation",
    },
    {
        "question": "Audit ของ AI Platform ควรหลีกเลี่ยงการเก็บอะไร?",
        "options": ["A  เวลาและ actor", "B  Tool name และ outcome", "C  Raw prompt, credential และ sensitive tool output", "D  Trace ID"],
        "answer": "C",
        "why": "เก็บ metadata ที่จำเป็นโดยไม่สร้างแหล่งข้อมูลอ่อนไหวใหม่",
    },
    {
        "question": "ประโยคใดสรุปแนวคิดวันนี้ได้ดีที่สุด?",
        "options": ["A  AI แทนที่ทุกระบบ", "B  AI เชื่อม Evidence และ Context เพื่อช่วยคนตัดสินใจภายใต้ Control", "C  AI ไม่ต้องใช้ข้อมูลจริง", "D  AI ที่ดีไม่ต้องมี owner"],
        "answer": "B",
        "why": "เป็น core message ของ Operational Excellence Through Applied AI",
    },
]


def add_game_intro(prs, note_list):
    slide = new_slide(prs, PURPLE)
    text(slide, "TEAM CHALLENGE", 0.72, 0.68, 3.5, 0.32, 11, WHITE, True)
    text(slide, "15 Questions\n15 Minutes", 0.72, 1.52, 5.0, 1.48, 38, WHITE, True)
    text(slide, "เลือก A / B / C / D  •  ข้อละประมาณ 45 วินาที  •  ห้ามเปิด Google",
         0.75, 3.48, 6.0, 0.5, 15, RGBColor(231, 224, 252), True)
    shape(slide, 7.5, 1.25, 4.75, 4.82, PALE_PURPLE, WHITE)
    text(slide, "วิธีเล่น", 7.9, 1.75, 3.95, 0.42, 20, PURPLE, True, PP_ALIGN.CENTER)
    rules = [
        "แบ่งเป็นทีมตามโต๊ะ",
        "ตอบผ่าน Kahoot / Slido หรือชูป้าย",
        "ตอบถูก 1 คะแนน",
        "กรณีเสมอ: ทีมที่ตอบข้อสุดท้ายเร็วกว่า",
    ]
    for index, rule in enumerate(rules):
        icon(slide, str(index + 1), 7.95, 2.58 + index * 0.68, 0.38, PURPLE, 10)
        text(slide, rule, 8.5, 2.61 + index * 0.68, 3.1, 0.32, 11, INK, index == 0)
    text(slide, "พร้อมหรือยัง?", 7.9, 5.45, 3.95, 0.38, 17, ORANGE, True, PP_ALIGN.CENTER)
    note_list.append(notes(
        "สไลด์ 25 — Game instructions",
        "1 นาที",
        [
            "หากไม่มีระบบตอบคำถาม ใช้วิธีให้แต่ละโต๊ะยกกระดาษ A/B/C/D",
            "เฉลยอยู่ใน Speaker Notes ของแต่ละข้อ",
            "ควรใช้เวลาอ่าน 20 วินาที ตอบ 15 วินาที และเฉลยสั้น 10–15 วินาที",
        ],
    ))


def add_quiz_slide(prs, note_list, item, number):
    colors = [BLUE, CYAN, ORANGE, GREEN]
    slide = new_slide(prs, LIGHT)
    pill(slide, f"QUESTION {number:02d} / 15", 0.72, 0.48, 1.75, PALE_PURPLE, PURPLE, 9)
    text(slide, item["question"], 0.75, 1.18, 11.85, 1.02, 25, INK, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    positions = [(0.75, 2.72), (6.82, 2.72), (0.75, 4.72), (6.82, 4.72)]
    for option, color, (x, y) in zip(item["options"], colors, positions):
        shape(slide, x, y, 5.72, 1.45, WHITE, color)
        text(slide, option, x + 0.28, y + 0.3, 5.16, 0.75, 14.5, INK, True, PP_ALIGN.LEFT, MSO_ANCHOR.MIDDLE)
    text(slide, "เลือกคำตอบภายใน 15 วินาที", 4.7, 6.63, 3.9, 0.28, 10, MUTED, True, PP_ALIGN.CENTER)
    note_list.append(notes(
        f"สไลด์ {25 + number} — Quiz {number}",
        "45–60 วินาที",
        [
            f"คำตอบ: {item['answer']}",
            f"เหตุผล: {item['why']}",
            "ให้คะแนนก่อนเลื่อนไปข้อถัดไป",
        ],
    ))


def add_closing(prs, note_list):
    slide = new_slide(prs, NAVY)
    shape(slide, 0, 0, 0.17, 7.5, ORANGE, ORANGE, False)
    text(slide, "FROM SIGNAL TO ACTION", 0.85, 0.82, 4.0, 0.3, 11, CYAN, True)
    text(slide, "Operational Excellence\nis a Team Capability", 0.85, 1.67, 7.0, 1.42, 34, WHITE, True)
    text(slide, "Datadog provides the signal.\nNexoraAI connects context, knowledge and governed action.",
         0.88, 3.48, 6.7, 0.92, 17, RGBColor(198, 217, 234))
    shape(slide, 8.05, 1.45, 4.1, 4.5, NAVY_2, NAVY_2)
    text(slide, "NEXORAAI + DATADOG PILOT", 8.45, 1.9, 3.3, 0.34, 12, ORANGE, True, PP_ALIGN.CENTER)
    text(slide, "เลือก 1 Critical Service\n\nเชื่อม Datadog แบบ Read-only\n\nเตรียม Runbook / KM\n\nพิสูจน์ผลใน 90 วัน",
         8.5, 2.66, 3.2, 2.45, 16, WHITE, True, PP_ALIGN.CENTER)
    text(slide, "Thank you", 0.88, 6.45, 3.0, 0.42, 21, ORANGE, True)
    note_list.append(notes(
        "สไลด์ 41 — Closing",
        "1 นาที",
        [
            "ประกาศทีมชนะและเชื่อมกลับไปยัง 90-day pilot",
            "ปิดด้วยข้อเสนอให้เลือกหนึ่ง critical service สำหรับ workshop ถัดไป",
            "หากต้องการขายแพลตฟอร์ม ให้เปลี่ยน Next Conversation เป็นชื่อ workshop และช่องทางติดต่อจริงก่อนนำเสนอ",
        ],
    ))


def build_deck():
    presentation = Presentation()
    presentation.slide_width = W
    presentation.slide_height = H
    presentation.core_properties.title = "Operational Excellence Through Applied AI to New IT Operational Capabilities"
    presentation.core_properties.subject = "Banking IT outing talk with Datadog and Applied AI demonstration"
    presentation.core_properties.author = "Enterprise AI Solutions Team"
    presentation.core_properties.comments = "Vendor-neutral educational story with an Applied AI platform pilot proposal"

    note_list = []
    add_cover(presentation, note_list)
    add_session_map(presentation, note_list)
    add_opening_poll(presentation, note_list)
    add_outcomes(presentation, note_list)
    add_banking_reality(presentation, note_list)
    add_ai_evolution(presentation, note_list)
    add_plain_language(presentation, note_list)
    add_platform(presentation, note_list)
    add_capabilities(presentation, note_list)
    add_responsibility(presentation, note_list)
    add_maturity(presentation, note_list)
    add_use_case_portfolio(presentation, note_list)
    add_briefing_use_case(presentation, note_list)
    add_incident_story(presentation, note_list)
    add_correlation_visual(presentation, note_list)
    add_demo_flow(presentation, note_list)
    add_demo_prompt(
        presentation,
        note_list,
        17,
        "Demo 1 — เริ่มจากสถานการณ์ปัจจุบัน",
        "ช่วยสรุป Alert และเหตุการณ์สำคัญที่เกี่ยวข้องกับ Mobile Banking ในช่วง 60 นาทีล่าสุด พร้อมระบุผลกระทบและข้อมูลที่ยังขาด",
        "Executive summary, time window, affected service และ evidence links",
        "Datadog monitor/event results พร้อม timestamp",
        BLUE,
    )
    add_demo_prompt(
        presentation,
        note_list,
        18,
        "Demo 2 — เปลี่ยนข้อมูลเป็นภาพ",
        "สร้างกราฟแนวโน้ม Alert แยกตาม Severity ในช่วงเวลาที่ตรวจสอบ และสรุปจุดเปลี่ยนที่สำคัญ โดยใช้เฉพาะข้อมูลที่ดึงได้จริง",
        "กราฟที่อ่านง่ายและไม่มีตัวเลขที่ model สร้างเอง",
        "Exact successful Datadog tool output",
        PURPLE,
    )
    add_demo_prompt(
        presentation,
        note_list,
        19,
        "Demo 3 — เชื่อม Datadog กับ Knowledge",
        "เชื่อม Timeline ของ Alert กับ Change ที่เกี่ยวข้อง ค้น Runbook ที่ได้รับอนุญาต แล้วจัดลำดับสมมติฐาน สาเหตุ หลักฐาน Gap และ Next Action ที่ต้องขออนุมัติ",
        "Ranked hypotheses, confidence, gap, owner และ approval boundary",
        "Datadog evidence + authorized Change/Runbook Knowledge",
        ORANGE,
    )
    add_demo_result(presentation, note_list)
    add_more_use_cases(presentation, note_list)
    add_governance(presentation, note_list)
    add_roadmap(presentation, note_list)
    add_takeaways(presentation, note_list)
    add_game_intro(presentation, note_list)
    for number, item in enumerate(QUIZ, start=1):
        add_quiz_slide(presentation, note_list, item, number)
    add_closing(presentation, note_list)

    if len(presentation.slides) != 41:
        raise ValueError(f"Expected 41 slides, found {len(presentation.slides)}")
    if len(note_list) != len(presentation.slides):
        raise ValueError("Speaker note count does not match slide count")

    for slide, note in zip(presentation.slides, note_list):
        add_notes(slide, note)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(OUTPUT)
    return note_list


def notes_markdown(note_list):
    lines = [
        "# Banking IT Outing — Speaker Notes ภาษาไทย",
        "",
        "หัวข้อ: **Operational Excellence Through Applied AI to New IT Operational Capabilities**  ",
        "รูปแบบ: เนื้อหา 45 นาที + เกม 15 นาที  ",
        "ผู้ฟัง: ผู้บริหารระดับสูงและพนักงาน IT ประมาณ 120 คน  ",
        "",
        "## Timing",
        "",
        "- Slides 1–5: Opening and operational pressure — 8 minutes",
        "- Slides 6–12: Applied AI and platform — 14 minutes",
        "- Slides 13–21: Banking use cases and Datadog demo — 16 minutes",
        "- Slides 22–24: Governance, roadmap and takeaways — 7 minutes",
        "- Slides 25–40: Game — 15 minutes",
        "- Slide 41: Closing — 1 minute or use inside Q&A buffer",
        "",
        "## Slide-by-slide notes",
        "",
    ]
    for number, note in enumerate(note_list, start=1):
        title, _, body = note.partition("\n")
        lines.extend([f"### {number}. {title}", "", body.strip(), ""])
    lines.extend([
        "## Quiz answer key",
        "",
        "| Question | Answer |",
        "| ---: | :---: |",
    ])
    for number, item in enumerate(QUIZ, start=1):
        lines.append(f"| {number} | {item['answer']} |")
    return "\n".join(lines).rstrip() + "\n"


def demo_runbook():
    return """# Banking Datadog + Applied AI Demo Runbook

## Demo goal

Show that a NexoraAI Operations Agent can retrieve authorized Datadog evidence,
correlate it with approved operational Knowledge, create a chart from exact tool results,
and produce an approval-ready recommendation without modifying production.

## Safety boundary

- Use a demonstration tenant and synthetic service names; do not show customer
  names, account numbers, tokens, host identifiers, or raw production logs.
- Bind the Agent only to the intended Team-owned Datadog connection and approved
  Knowledge Data Groups.
- Keep Datadog and every other integration read-only.
- Pre-test the exact prompts and time ranges on the same day as the event.
- Keep screenshots or a short recording as a fallback and label them clearly.

## Recommended scenario

Service: Mobile Banking Transfer
Symptom: P95 latency and error rate increase after a demonstration deployment.
Evidence: Datadog monitor events, latency/error time series, a synthetic change
record, and a fictional connection-pool runbook.

## Live prompts

1. Current state

   ช่วยสรุป Alert และเหตุการณ์สำคัญที่เกี่ยวข้องกับ Mobile Banking ในช่วง 60
   นาทีล่าสุด พร้อมระบุผลกระทบและข้อมูลที่ยังขาด

2. Visualization

   สร้างกราฟแนวโน้ม Alert แยกตาม Severity ในช่วงเวลาที่ตรวจสอบ และสรุปจุดเปลี่ยน
   ที่สำคัญ โดยใช้เฉพาะข้อมูลที่ดึงได้จริง

3. Correlation and Knowledge

   เชื่อม Timeline ของ Alert กับ Change ที่เกี่ยวข้อง ค้น Runbook ที่ได้รับอนุญาต
   แล้วจัดลำดับสมมติฐาน สาเหตุ หลักฐาน Gap และ Next Action ที่ต้องขออนุมัติ

## Presenter checklist

- [ ] Agent uses a tested tool-capable LLM profile.
- [ ] Datadog MCP connection test succeeds and discovered tools are visible.
- [ ] The Agent binding permits only the required read tools.
- [ ] Knowledge search is enabled for the synthetic Change and Runbook sources.
- [ ] Chart integration is enabled and tested with exact tool output.
- [ ] Each response shows source/time context and no fabricated metric.
- [ ] The final recommendation identifies owner, risk and approval requirement.
- [ ] Screenshot/video fallback is ready.
"""


if __name__ == "__main__":
    generated_notes = build_deck()
    NOTES_OUTPUT.write_text(notes_markdown(generated_notes), encoding="utf-8")
    DEMO_OUTPUT.write_text(demo_runbook(), encoding="utf-8")
    print(OUTPUT)
    print(NOTES_OUTPUT)
    print(DEMO_OUTPUT)
