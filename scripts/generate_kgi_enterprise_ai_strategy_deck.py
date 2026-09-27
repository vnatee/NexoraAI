from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "presentations" / "KGI_Enterprise_AI_Strategy_Proposal.pptx"
NOTES = ROOT / "docs" / "presentations" / "KGI_Enterprise_AI_Strategy_Proposal_notes.md"
NOTES_TH = ROOT / "docs" / "presentations" / "KGI_Enterprise_AI_Strategy_Proposal_notes_TH.md"

W, H = Inches(13.333), Inches(7.5)
FONT = "Arial"

NAVY = RGBColor(8, 24, 43)
NAVY_2 = RGBColor(16, 40, 65)
NAVY_3 = RGBColor(26, 55, 84)
BLUE = RGBColor(28, 112, 202)
CYAN = RGBColor(37, 177, 205)
ORANGE = RGBColor(244, 126, 32)
GREEN = RGBColor(36, 148, 101)
RED = RGBColor(190, 61, 61)
INK = RGBColor(24, 38, 53)
MUTED = RGBColor(91, 108, 123)
MID = RGBColor(176, 190, 202)
LINE = RGBColor(214, 224, 232)
LIGHT = RGBColor(245, 248, 251)
PALE_BLUE = RGBColor(232, 242, 252)
PALE_ORANGE = RGBColor(255, 242, 228)
PALE_GREEN = RGBColor(231, 247, 239)
WHITE = RGBColor(255, 255, 255)


def bg(slide, color=WHITE):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def box(slide, x, y, w, h, fill=WHITE, line=LINE, radius=0.1):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line
    shape.line.width = Pt(0.8)
    if radius:
        try:
            shape.adjustments[0] = min(radius, 0.5)
        except (IndexError, ValueError):
            pass
    return shape


def circle(slide, x, y, d, fill=BLUE, line=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line or fill
    return shape


def text(slide, value, x, y, w, h, size=18, color=INK, bold=False,
         align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, margin=0.03, font=FONT):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.text = value
    p.alignment = align
    p.font.name = font
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    return shape


def rich(slide, parts, x, y, w, h, size=18, align=PP_ALIGN.LEFT,
         valign=MSO_ANCHOR.TOP):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.03)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    for value, color, bold in parts:
        run = p.add_run()
        run.text = value
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
    return shape


def line(slide, x1, y1, x2, y2, color=MID, width=1.5, arrow=False):
    shape = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
    )
    shape.line.color.rgb = color
    shape.line.width = Pt(width)
    if arrow:
        shape.line.end_arrowhead = True
    return shape


def chevron(slide, x, y, w=0.45, h=0.55, color=BLUE):
    shape = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.color.rgb = color
    return shape


def pill(slide, label, x, y, w, fill=PALE_BLUE, color=BLUE, size=10):
    box(slide, x, y, w, 0.34, fill, fill, 0.5)
    text(slide, label, x, y + 0.01, w, 0.3, size, color, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)


def new_slide(prs, color=WHITE):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg(slide, color)
    return slide


def header(slide, title, section, page, dark=False, subtitle=None):
    fg = WHITE if dark else INK
    muted = RGBColor(172, 193, 213) if dark else MUTED
    text(slide, section.upper(), 0.58, 0.25, 3.4, 0.25, 9, BLUE if not dark else CYAN, True)
    text(slide, title, 0.58, 0.68, 12.0, 0.55, 26, fg, True)
    if subtitle:
        text(slide, subtitle, 0.61, 1.28, 11.9, 0.35, 11, muted)
    line(slide, 0.58, 1.58 if subtitle else 1.42, 12.72, 1.58 if subtitle else 1.42, NAVY_3 if dark else LINE, 0.8)
    text(slide, f"{page:02d}", 12.2, 7.08, 0.5, 0.2, 8, muted, True, PP_ALIGN.RIGHT)


def footer(slide, label="Enterprise AI Strategy | KGI Securities Thailand", dark=False):
    text(slide, label, 0.58, 7.08, 7.8, 0.2, 7.5,
         RGBColor(145, 165, 184) if dark else RGBColor(130, 145, 160))


def icon(slide, glyph, x, y, d=0.58, fill=BLUE, size=19):
    circle(slide, x, y, d, fill)
    text(slide, glyph, x, y + 0.01, d, d - 0.02, size, WHITE, True,
         PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)


def card(slide, title, body, x, y, w, h, accent=BLUE, fill=WHITE, glyph=None):
    box(slide, x, y, w, h, fill, LINE, 0.08)
    box(slide, x, y, 0.07, h, accent, accent, 0)
    tx = x + 0.28
    if glyph:
        icon(slide, glyph, x + 0.28, y + 0.25, 0.48, accent, 14)
        tx = x + 0.9
    text(slide, title, tx, y + 0.23, w - (tx - x) - 0.2, 0.38, 15, INK, True)
    text(slide, body, x + 0.28, y + 0.78, w - 0.52, h - 0.94, 10.5, MUTED)


def stage(slide, number, title, body, x, y, w, color=BLUE, dark=False):
    fg = WHITE if dark else INK
    muted = RGBColor(190, 208, 225) if dark else MUTED
    circle(slide, x, y, 0.52, color)
    text(slide, str(number), x, y + 0.01, 0.52, 0.49, 12, WHITE, True,
         PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    text(slide, title, x + 0.68, y - 0.01, w - 0.68, 0.3, 12, color, True)
    text(slide, body, x + 0.68, y + 0.31, w - 0.68, 0.6, 10, muted)


def band(slide, label, items, y, color, label_w=2.0, x=1.0, total_w=11.3, dark=False):
    fill = NAVY_3 if dark else WHITE
    body_color = WHITE if dark else INK
    box(slide, x, y, total_w, 0.62, fill, NAVY_3 if dark else LINE, 0.04)
    box(slide, x, y, label_w, 0.62, color, color, 0.04)
    text(slide, label, x + 0.08, y + 0.11, label_w - 0.16, 0.32, 10, WHITE, True,
         PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    text(slide, "   |   ".join(items), x + label_w + 0.18, y + 0.12,
         total_w - label_w - 0.35, 0.32, 10.5, body_color, False,
         PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)


def statement(slide, value, y=6.35, color=BLUE, dark=False):
    line(slide, 0.8, y - 0.18, 12.5, y - 0.18, NAVY_3 if dark else LINE, 0.8)
    text(slide, value, 0.85, y, 11.65, 0.45, 14, WHITE if dark else color, True, PP_ALIGN.CENTER)


def section_slide(prs, page, eyebrow, title, subtitle):
    slide = new_slide(prs, NAVY)
    box(slide, 0, 0, 0.16, 7.5, ORANGE, ORANGE, 0)
    text(slide, eyebrow.upper(), 0.85, 1.05, 3.8, 0.32, 11, CYAN, True)
    text(slide, title, 0.85, 2.0, 11.5, 1.1, 38, WHITE, True, PP_ALIGN.CENTER)
    line(slide, 3.75, 3.43, 9.58, 3.43, BLUE, 2.2)
    text(slide, subtitle, 1.55, 3.83, 10.25, 0.52, 17,
         RGBColor(196, 215, 233), False, PP_ALIGN.CENTER)
    text(slide, f"{page:02d}", 12.2, 7.08, 0.5, 0.2, 8, RGBColor(150, 175, 198), True, PP_ALIGN.RIGHT)
    footer(slide, dark=True)
    return slide


def build_deck():
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    prs.core_properties.title = "Enterprise AI Platform — From Enterprise Knowledge to Intelligent Action"
    prs.core_properties.subject = "Enterprise AI strategy and solution architecture proposal"
    prs.core_properties.author = "Enterprise AI Strategy Team"
    prs.core_properties.comments = "Prepared for KGI Securities Thailand"

    # 1 — Cover
    s = new_slide(prs, NAVY)
    box(s, 0, 0, 0.16, 7.5, ORANGE, ORANGE, 0)
    text(s, "ENTERPRISE AI STRATEGY", 0.75, 0.62, 4.5, 0.28, 10, CYAN, True)
    text(s, "Enterprise AI\nPlatform", 0.75, 1.38, 6.2, 1.55, 38, WHITE, True)
    text(s, "From Enterprise Knowledge\nto Intelligent Action", 0.78, 3.2, 5.75, 0.92, 22,
         RGBColor(201, 219, 235), False)
    pill(s, "DISCUSSION PROPOSAL", 0.78, 4.55, 1.85, NAVY_3, CYAN, 9)
    text(s, "Local AI  •  Agentic AI  •  Enterprise Knowledge  •  Secure Integration",
         0.78, 5.14, 6.15, 0.38, 11, RGBColor(160, 186, 210))
    # abstract People → AI → Enterprise visual
    line(s, 8.0, 3.75, 11.85, 3.75, RGBColor(87, 122, 155), 2.0)
    icon(s, "P", 7.35, 3.18, 1.1, BLUE, 28)
    circle(s, 9.65, 2.72, 2.05, NAVY_3, BLUE)
    text(s, "AI", 9.65, 3.18, 2.05, 0.58, 27, ORANGE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    icon(s, "E", 11.55, 3.18, 1.1, GREEN, 28)
    for x, y, d in [(8.65, 2.45, .18), (8.82, 4.85, .14), (11.6, 2.2, .15), (12.35, 4.62, .2), (10.65, 5.55, .13)]:
        circle(s, x, y, d, CYAN if x < 10 else GREEN)
        line(s, 10.68, 3.75, x + d / 2, y + d / 2, RGBColor(70, 105, 138), 0.9)
    text(s, "AI becomes the secure intelligence and orchestration layer across existing systems.",
         7.15, 6.08, 5.45, 0.58, 13, WHITE, True, PP_ALIGN.CENTER)
    text(s, "Prepared for KGI Securities Thailand", 0.78, 6.8, 4.2, 0.25, 9, RGBColor(139, 166, 190))

    # 2 — Evolution
    s = new_slide(prs)
    header(s, "AI Is Moving Beyond Chat", "Why", 2)
    labels = [
        ("CHAT", "General conversation", 0.78, 0.64, MID),
        ("KNOW", "Enterprise RAG", 3.2, 0.82, BLUE),
        ("REASON", "Understand context", 5.75, 1.03, CYAN),
        ("ACT", "Call enterprise systems", 8.45, 1.24, ORANGE),
        ("AUTONOMY", "Execute governed workflows", 10.7, 1.48, GREEN),
    ]
    line(s, 1.2, 4.16, 12.1, 4.16, LINE, 5)
    for i, (name, body, x, d, color) in enumerate(labels):
        circle(s, x, 4.16 - d / 2, d, color)
        text(s, name, x - 0.2, 2.35, d + 0.4, 0.42, 13, color, True, PP_ALIGN.CENTER)
        text(s, body, x - 0.35, 2.88, d + 0.7, 0.65, 10.5, MUTED, False, PP_ALIGN.CENTER)
        if i < 4:
            chevron(s, x + d + 0.34, 3.88, 0.38, 0.52, color)
    statement(s, "The next wave of enterprise AI is not only about generating answers — it is about completing work.", 6.15)
    footer(s)

    # 3 — Convergence
    s = new_slide(prs, LIGHT)
    header(s, "Why Enterprise AI, Why Now?", "Why", 3)
    center_x, center_y = 5.18, 2.92
    box(s, center_x, center_y, 3.0, 1.35, NAVY, NAVY, 0.12)
    text(s, "ENTERPRISE AI", center_x, center_y + 0.31, 3.0, 0.55, 22, WHITE, True,
         PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    forces = [
        ("MODEL INTELLIGENCE", "Reasoning  •  Tool calling  •  Multimodal", 0.72, 1.82, BLUE),
        ("ENTERPRISE KNOWLEDGE", "RAG  •  Vector search  •  Document intelligence", 0.72, 4.78, CYAN),
        ("SYSTEM CONNECTIVITY", "API  •  MCP  •  Workflow", 9.08, 1.82, ORANGE),
        ("AI INFRASTRUCTURE", "GPU  •  Local LLM  •  Cloud AI", 9.08, 4.78, GREEN),
    ]
    for title_, body_, x, y, color in forces:
        card(s, title_, body_, x, y, 3.55, 1.23, color, WHITE)
        line(s, 4.27 if x < 5 else 9.08, y + 0.61, 5.18 if x < 5 else 8.18, 3.59,
             color, 1.8, True)
    statement(s, "The capabilities required to move AI from experimentation into enterprise operations are now converging.", 6.48)
    footer(s)

    # 4 — Fragmented vs platform
    s = new_slide(prs)
    header(s, "The Opportunity Is Bigger Than a Chatbot", "Why", 4)
    text(s, "USE-CASE-BY-USE-CASE", 0.72, 1.72, 4.7, 0.3, 11, RED, True, PP_ALIGN.CENTER)
    bots = [("HR", 0.82, 2.35), ("IT", 2.5, 2.1), ("DOC", 4.08, 2.45), ("SEC", 1.65, 3.85), ("R&D", 3.32, 3.82)]
    for label, x, y in bots:
        box(s, x, y, 1.2, 0.72, WHITE, LINE, 0.08)
        text(s, label, x, y + 0.15, 1.2, 0.36, 12, INK, True, PP_ALIGN.CENTER)
    text(s, "Duplicated infrastructure\nInconsistent security\nIsolated knowledge\nDifficult governance",
         0.92, 5.12, 4.25, 0.92, 11, MUTED, False, PP_ALIGN.CENTER)
    chevron(s, 6.0, 3.42, 0.72, 0.85, ORANGE)
    text(s, "BUILD ONCE", 5.7, 4.44, 1.25, 0.25, 9, ORANGE, True, PP_ALIGN.CENTER)
    box(s, 7.22, 1.92, 5.35, 3.92, NAVY, NAVY, 0.12)
    text(s, "ENTERPRISE AI PLATFORM", 7.62, 2.22, 4.55, 0.4, 17, WHITE, True, PP_ALIGN.CENTER)
    text(s, "HR    |    IT    |    SECURITY    |    COMPLIANCE    |    RESEARCH",
         7.53, 2.93, 4.75, 0.4, 10.5, CYAN, True, PP_ALIGN.CENTER)
    line(s, 7.62, 3.5, 12.18, 3.5, NAVY_3, 1)
    shared = ["Knowledge", "Models", "Integration", "Security", "Governance", "Observability"]
    for i, label in enumerate(shared):
        x = 7.62 + (i % 3) * 1.54
        y = 3.84 + (i // 3) * 0.68
        box(s, x, y, 1.35, 0.46, NAVY_3, NAVY_3, 0.06)
        text(s, label, x, y + 0.08, 1.35, 0.27, 9, WHITE, True, PP_ALIGN.CENTER)
    statement(s, "Build the AI foundation once. Extend it through specialized agents.", 6.42)
    footer(s)

    # 5 — Know Think Act
    s = new_slide(prs)
    header(s, "The Enterprise AI Value Chain", "What the Platform Should Be", 5)
    circles = [
        ("KNOW", "Enterprise knowledge", "Documents\nPolicies\nDatabases\nKnowledge bases", 1.25, BLUE),
        ("THINK", "Reason & understand", "LLM\nContext\nAgent\nDecision support", 5.15, CYAN),
        ("ACT", "Enterprise systems", "PeopleSoft\nK2\nAPI\nWorkflow / Automation", 9.05, ORANGE),
    ]
    for i, (label, sub, body_, x, color) in enumerate(circles):
        circle(s, x, 2.0, 2.52, color)
        text(s, label, x, 2.55, 2.52, 0.48, 24, WHITE, True, PP_ALIGN.CENTER)
        text(s, sub, x, 3.12, 2.52, 0.35, 10, WHITE, False, PP_ALIGN.CENTER)
        text(s, body_, x - 0.08, 4.73, 2.68, 1.05, 11, MUTED, False, PP_ALIGN.CENTER)
        if i < 2:
            chevron(s, x + 2.95, 2.94, 0.48, 0.64, color)
    box(s, 0.95, 6.08, 11.45, 0.52, NAVY, NAVY, 0.05)
    text(s, "IDENTITY  •  SECURITY  •  GOVERNANCE  •  AUDIT", 0.95, 6.18, 11.45, 0.28,
         10.5, WHITE, True, PP_ALIGN.CENTER)
    footer(s)

    # 6 — Layered platform
    s = new_slide(prs, LIGHT)
    header(s, "Enterprise AI Requires More Than an LLM", "What the Platform Should Be", 6)
    bands = [
        ("EXPERIENCE", ["Web", "Mobile", "Teams", "API"], BLUE),
        ("AI AGENTS", ["HR", "IT", "Security", "Compliance", "Business"], CYAN),
        ("INTELLIGENCE", ["Orchestration", "RAG", "Reasoning", "Memory"], ORANGE),
        ("CONNECTIVITY", ["API", "MCP", "Database", "Workflow", "Tools"], GREEN),
        ("MODEL LAYER", ["Local", "Private", "Cloud", "Embedding", "Vision"], BLUE),
        ("DATA & KNOWLEDGE", ["Documents", "Database", "Vector", "Object storage"], NAVY_3),
    ]
    for i, (label, items, color) in enumerate(bands):
        band(s, label, items, 1.78 + i * 0.72, color, 2.15, 1.35, 10.65)
    box(s, 0.58, 1.78, 0.54, 4.22, NAVY, NAVY, 0.04)
    text(s, "SECURITY\n&\nGOVERNANCE", 0.58, 2.4, 0.54, 2.95, 9, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    box(s, 12.22, 1.78, 0.54, 4.22, NAVY, NAVY, 0.04)
    text(s, "AI\nOPERATIONS", 12.22, 2.56, 0.54, 2.35, 9, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    statement(s, "Security and observability span every layer — from retrieval through tool execution.", 6.42)
    footer(s)

    # 7 — Knowledge pipeline
    s = new_slide(prs)
    header(s, "Turn Enterprise Information into Trusted AI Knowledge", "Enterprise Knowledge", 7)
    stages = [
        ("SOURCE", "PDF\nOffice\nSharePoint\nDatabase\nInternal web", BLUE),
        ("INGEST", "Extract\nOCR\nClassify\nChunk", CYAN),
        ("UNDERSTAND", "Metadata\nEmbedding\nIndex", ORANGE),
        ("GOVERN", "ACL\nClassification\nRetention", NAVY_3),
        ("RETRIEVE", "Semantic\nHybrid\nMetadata filter", GREEN),
        ("ANSWER", "Grounded response\nCitation\nSource", BLUE),
    ]
    for i, (title_, body_, color) in enumerate(stages):
        x = 0.52 + i * 2.12
        box(s, x, 2.15, 1.72, 2.75, LIGHT if i != 3 else NAVY, color, 0.08)
        icon(s, title_[0], x + 0.56, 2.43, 0.6, color, 16)
        text(s, title_, x + 0.12, 3.19, 1.48, 0.28, 10, color if i != 3 else CYAN, True, PP_ALIGN.CENTER)
        text(s, body_, x + 0.12, 3.63, 1.48, 0.95, 10, WHITE if i == 3 else MUTED, False, PP_ALIGN.CENTER)
        if i < 5:
            chevron(s, x + 1.77, 3.13, 0.3, 0.5, color)
    box(s, 1.25, 5.58, 10.83, 0.62, PALE_ORANGE, ORANGE, 0.05)
    text(s, "The AI should only retrieve information the user is authorized to see.",
         1.25, 5.73, 10.83, 0.32, 16, ORANGE, True, PP_ALIGN.CENTER)
    footer(s)

    # 8 — Local AI
    s = new_slide(prs, LIGHT)
    header(s, "Why Local AI Matters for the Enterprise", "Local AI", 8)
    circle(s, 5.18, 2.22, 2.92, NAVY)
    text(s, "LOCAL\nAI", 5.18, 2.93, 2.92, 0.92, 25, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    drivers = [
        ("DATA CONTROL", 0.82, 2.0, BLUE), ("PRIVACY", 1.08, 4.7, CYAN),
        ("INFRASTRUCTURE CONTROL", 9.63, 1.98, GREEN), ("NETWORK ISOLATION", 9.76, 4.72, BLUE),
        ("WORKLOAD ECONOMICS", 4.76, 5.57, ORANGE),
    ]
    for label, x, y, color in drivers:
        box(s, x, y, 2.75, 0.72, WHITE, color, 0.08)
        text(s, label, x, y + 0.18, 2.75, 0.32, 11, color, True, PP_ALIGN.CENTER)
        line(s, x + 1.38, y + (0.72 if y < 3 else 0), 6.64, 3.68, color, 1.3)
    box(s, 8.88, 5.56, 3.6, 0.98, PALE_ORANGE, ORANGE, 0.08)
    text(s, "Operational responsibility", 9.12, 5.74, 3.1, 0.28, 11, ORANGE, True)
    text(s, "GPU capacity  •  Lifecycle  •  Performance  •  AI Ops", 9.12, 6.08, 3.1, 0.25, 8.5, MUTED)
    footer(s)

    # 9 — Model gateway
    s = new_slide(prs)
    header(s, "The Target Is Controlled Model Choice", "Local AI", 9)
    box(s, 0.75, 2.02, 2.7, 3.35, NAVY, NAVY, 0.1)
    text(s, "POLICY ENGINE", 0.75, 2.34, 2.7, 0.38, 17, WHITE, True, PP_ALIGN.CENTER)
    text(s, "Data classification\nAgent policy\nModel capability\nCost\nLatency", 1.08, 3.05, 2.05, 1.68, 12, RGBColor(199, 217, 234), False, PP_ALIGN.CENTER)
    chevron(s, 3.8, 3.33, 0.65, 0.76, ORANGE)
    box(s, 4.75, 2.02, 2.25, 3.35, PALE_ORANGE, ORANGE, 0.1)
    text(s, "AI MODEL\nGATEWAY", 4.75, 3.12, 2.25, 0.9, 20, ORANGE, True, PP_ALIGN.CENTER)
    targets = [
        ("LOCAL LLM", "Sensitive / internal", 7.42, 1.95, BLUE),
        ("PRIVATE / MANAGED AI", "Controlled enterprise", 7.42, 3.23, GREEN),
        ("FRONTIER CLOUD AI", "Advanced / specialized", 7.42, 4.51, ORANGE),
    ]
    for title_, body_, x, y, color in targets:
        box(s, x, y, 4.65, 0.94, WHITE, color, 0.08)
        text(s, title_, x + 0.28, y + 0.18, 2.75, 0.28, 12.5, color, True)
        text(s, body_, x + 2.7, y + 0.2, 1.65, 0.28, 9.5, MUTED, False, PP_ALIGN.RIGHT)
        line(s, 7.0, 3.69, x, y + 0.47, color, 1.4, True)
    statement(s, "Route each workload to the right model under enterprise policy.", 6.3)
    footer(s)

    # 10 — Zero Trust
    s = new_slide(prs, LIGHT)
    header(s, "Zero Trust Must Extend into AI", "Security", 10)
    flow = [
        ("USER", "Identity", BLUE), ("AUTHENTICATE", "Who are you?", BLUE),
        ("AGENT", "Which agent?", CYAN), ("KNOWLEDGE", "Which data?", GREEN),
        ("TOOL", "Which system?", ORANGE), ("ACTION", "What can execute?", RED),
        ("AUDIT", "What happened?", NAVY_3),
    ]
    for i, (title_, sub, color) in enumerate(flow):
        x = 0.42 + i * 1.83
        circle(s, x + 0.41, 2.15, 0.9, color)
        text(s, str(i) if i else "U", x + 0.41, 2.33, 0.9, 0.42, 16, WHITE, True, PP_ALIGN.CENTER)
        text(s, title_, x, 3.32, 1.72, 0.28, 9.5, color, True, PP_ALIGN.CENTER)
        text(s, sub, x, 3.76, 1.72, 0.46, 9.5, MUTED, False, PP_ALIGN.CENTER)
        if i < 6:
            chevron(s, x + 1.59, 2.39, 0.28, 0.42, color)
    box(s, 0.88, 4.73, 11.58, 1.08, WHITE, NAVY_3, 0.1)
    icon(s, "✓", 1.18, 4.98, 0.55, NAVY_3, 15)
    text(s, "Never trust the prompt.", 1.98, 4.93, 3.05, 0.32, 16, NAVY, True)
    text(s, "Verify identity, data, tools and actions.", 5.0, 4.93, 6.5, 0.32, 16, BLUE, True)
    footer(s)

    # 11 — Guardrails
    s = new_slide(prs)
    header(s, "From AI Guardrails to Controlled Action", "Security", 11)
    text(s, "THREATS", 0.68, 1.82, 3.25, 0.3, 11, RED, True, PP_ALIGN.CENTER)
    box(s, 0.68, 2.18, 3.25, 3.35, LIGHT, RED, 0.1)
    text(s, "Prompt injection\n\nSensitive data leakage\n\nUnauthorized retrieval\n\nExcessive agency\n\nUnsafe tool execution",
         1.0, 2.57, 2.62, 2.56, 11, MUTED, False, PP_ALIGN.CENTER)
    chevron(s, 4.23, 3.5, 0.55, 0.72, RED)
    box(s, 5.0, 1.94, 3.35, 3.86, NAVY, NAVY, 0.1)
    text(s, "AI GOVERNANCE", 5.0, 2.25, 3.35, 0.35, 16, WHITE, True, PP_ALIGN.CENTER)
    text(s, "Input guardrail\nACL\nPII / DLP\nTool policy\nOutput guardrail\nHuman approval",
         5.42, 2.93, 2.5, 2.23, 12, RGBColor(205, 221, 236), False, PP_ALIGN.CENTER)
    chevron(s, 8.65, 3.5, 0.55, 0.72, GREEN)
    text(s, "CONTROLLED OUTCOME", 9.38, 1.82, 3.25, 0.3, 11, GREEN, True, PP_ALIGN.CENTER)
    box(s, 9.38, 2.18, 3.25, 3.35, PALE_GREEN, GREEN, 0.1)
    icon(s, "✓", 10.67, 2.65, 0.66, GREEN, 18)
    text(s, "Authorized answer\n\nApproved action\n\nAudit trail", 9.8, 3.55, 2.42, 1.35, 13, INK, True, PP_ALIGN.CENTER)
    footer(s)

    # 12 — section transition
    section_slide(prs, 12, "Use cases", "Let’s make it real.", "Employee Services  →  IT Operations  →  Regulated Business")

    # 13 — HR agent
    s = new_slide(prs)
    header(s, "HR Agent — From Employee Question to HR Service", "Employee Services", 13)
    icon(s, "E", 0.86, 3.0, 1.18, BLUE, 27)
    text(s, "EMPLOYEE", 0.5, 4.35, 1.9, 0.28, 11, BLUE, True, PP_ALIGN.CENTER)
    chevron(s, 2.45, 3.25, 0.58, 0.7, BLUE)
    circle(s, 3.42, 2.54, 2.26, NAVY)
    text(s, "HR\nAGENT", 3.42, 3.0, 2.26, 0.9, 22, WHITE, True, PP_ALIGN.CENTER)
    text(s, "READ  →  ASSIST  →  ACT", 2.92, 5.18, 3.25, 0.4, 11, ORANGE, True, PP_ALIGN.CENTER)
    systems = [
        ("HR KNOWLEDGE", "Policies\nBenefits\nProcedures", 7.02, 1.82, BLUE),
        ("PEOPLESOFT", "Employee\nLeave\nBenefits / Workflow", 7.02, 3.35, ORANGE),
        ("TALENT DATA", "Skills\nCertifications\nExperience", 7.02, 4.88, GREEN),
    ]
    for title_, body_, x, y, color in systems:
        card(s, title_, body_, x, y, 4.78, 1.18, color, LIGHT)
        line(s, 5.68, 3.67, x, y + 0.59, color, 1.4, True)
    box(s, 2.0, 6.22, 9.35, 0.48, PALE_ORANGE, PALE_ORANGE, 0.05)
    text(s, "AI does not replace PeopleSoft. It makes PeopleSoft easier to access and use.",
         2.0, 6.32, 9.35, 0.27, 14, ORANGE, True, PP_ALIGN.CENTER)
    footer(s)

    # 14 — Leave conversation
    s = new_slide(prs, LIGHT)
    header(s, "A Simple Question. An End-to-End HR Service.", "Employee Services", 14)
    box(s, 0.78, 1.72, 11.8, 0.74, WHITE, BLUE, 0.12)
    icon(s, "E", 1.02, 1.81, 0.54, BLUE, 14)
    text(s, "“I want to take annual leave next Friday. Can I?”", 1.76, 1.91, 10.45, 0.32, 17, INK, True)
    steps = [
        ("1", "IDENTIFY", "Authenticate\nemployee", BLUE),
        ("2", "READ", "Leave balance\n7 days", BLUE),
        ("3", "KNOW", "Retrieve HR\npolicy", CYAN),
        ("4", "REASON", "Check\nentitlement", ORANGE),
        ("5", "ASSIST", "Eligible +\nsufficient balance", GREEN),
        ("6", "ACT", "Submit leave\nrequest?", ORANGE),
    ]
    for i, (num, title_, body_, color) in enumerate(steps):
        x = 0.52 + i * 2.08
        stage(s, num, title_, body_, x, 3.02, 1.78, color)
        if i < 5:
            chevron(s, x + 1.75, 3.13, 0.25, 0.4, color)
    box(s, 4.05, 5.13, 5.2, 0.72, PALE_GREEN, GREEN, 0.1)
    text(s, "YES  →  PeopleSoft  →  Request submitted ✓", 4.05, 5.32, 5.2, 0.32, 14, GREEN, True, PP_ALIGN.CENTER)
    text(s, "PeopleSoft remains the System of Record.", 3.95, 6.16, 5.4, 0.3, 11, MUTED, True, PP_ALIGN.CENTER)
    footer(s)

    # 15 — Talent intelligence
    s = new_slide(prs)
    header(s, "From Employee Records to Workforce Intelligence", "Employee Services", 15)
    box(s, 0.7, 1.72, 11.9, 0.66, PALE_BLUE, BLUE, 0.08)
    text(s, "Manager: “Who has Azure, Kubernetes and cybersecurity experience for our infrastructure project?”",
         0.95, 1.88, 11.4, 0.3, 14, INK, True, PP_ALIGN.CENTER)
    text(s, "Skills   +   Certifications   +   Training   +   Experience", 0.88, 2.72, 3.55, 0.55, 11, MUTED, True, PP_ALIGN.CENTER)
    chevron(s, 4.58, 2.75, 0.44, 0.55, ORANGE)
    circle(s, 5.36, 2.32, 1.45, NAVY)
    text(s, "TALENT\nAI", 5.36, 2.65, 1.45, 0.67, 14, WHITE, True, PP_ALIGN.CENTER)
    chevron(s, 7.08, 2.75, 0.44, 0.55, ORANGE)
    candidates = [
        ("A", "Azure ✓\nKubernetes ✓\nSecurity ✓", GREEN),
        ("B", "Azure ✓\nKubernetes ✓\nSecurity gap", ORANGE),
        ("C", "Azure ✓\nSecurity ✓\nKubernetes gap", ORANGE),
    ]
    for i, (name, body_, color) in enumerate(candidates):
        x = 7.8 + i * 1.53
        box(s, x, 2.22, 1.36, 1.72, WHITE, color, 0.08)
        text(s, f"CANDIDATE {name}", x, 2.43, 1.36, 0.28, 9, color, True, PP_ALIGN.CENTER)
        text(s, body_, x + 0.1, 2.91, 1.16, 0.75, 9.5, MUTED, False, PP_ALIGN.CENTER)
    box(s, 2.0, 4.72, 4.1, 0.72, LIGHT, LINE, 0.08)
    text(s, "Next question: “What skills are missing?”", 2.0, 4.93, 4.1, 0.28, 12, INK, True, PP_ALIGN.CENTER)
    chevron(s, 6.42, 4.83, 0.48, 0.55, ORANGE)
    box(s, 7.15, 4.72, 3.9, 0.72, PALE_ORANGE, ORANGE, 0.08)
    text(s, "SKILL GAP  →  TRAINING RECOMMENDATION", 7.15, 4.93, 3.9, 0.28, 11, ORANGE, True, PP_ALIGN.CENTER)
    pill(s, "AUTHORIZED HR / MANAGER ACCESS ONLY", 4.47, 5.92, 4.4, NAVY, WHITE, 9.5)
    footer(s)

    # 16 — Helpdesk
    s = new_slide(prs, LIGHT)
    header(s, "From Helpdesk Q&A to Intelligent Resolution", "IT Helpdesk", 16)
    box(s, 0.75, 1.73, 11.82, 0.63, WHITE, BLUE, 0.08)
    text(s, "Employee: “I cannot connect to VPN.”", 0.75, 1.89, 11.82, 0.3, 15, INK, True, PP_ALIGN.CENTER)
    flow = [
        ("UNDERSTAND", "User / device\nlocation / symptoms", BLUE),
        ("KNOW", "Search IT\nknowledge base", CYAN),
        ("CHECK", "Identity / incident\nK2 ticket", ORANGE),
        ("DIAGNOSE", "Guided\ntroubleshooting", NAVY_3),
    ]
    for i, (title_, body_, color) in enumerate(flow):
        x = 0.72 + i * 2.42
        card(s, title_, body_, x, 2.78, 2.0, 1.42, color, WHITE)
        if i < 3:
            chevron(s, x + 2.07, 3.22, 0.28, 0.48, color)
    line(s, 10.15, 3.49, 11.23, 2.72, GREEN, 1.5, True)
    line(s, 10.15, 3.49, 11.23, 4.27, ORANGE, 1.5, True)
    box(s, 11.23, 2.38, 1.4, 0.75, PALE_GREEN, GREEN, 0.08)
    text(s, "RESOLVED ✓", 11.23, 2.57, 1.4, 0.28, 10, GREEN, True, PP_ALIGN.CENTER)
    box(s, 11.23, 3.88, 1.4, 0.75, PALE_ORANGE, ORANGE, 0.08)
    text(s, "ESCALATE", 11.23, 4.07, 1.4, 0.28, 10, ORANGE, True, PP_ALIGN.CENTER)
    text(s, "Before: VPN doesn’t work", 0.82, 5.1, 3.15, 0.3, 11, RED, True)
    chevron(s, 4.03, 5.0, 0.48, 0.55, ORANGE)
    box(s, 4.82, 4.76, 7.1, 0.83, WHITE, GREEN, 0.08)
    text(s, "After AI: User  •  Device  •  Error  •  Diagnostics  •  Attempted actions  •  Evidence",
         5.08, 5.0, 6.6, 0.3, 11, GREEN, True, PP_ALIGN.CENTER)
    statement(s, "AI improves the quality of tickets that still require IT.", 6.2)
    footer(s)

    # 17 — dramatic transition
    s = new_slide(prs, NAVY)
    text(s, "IT OPERATIONS", 0.72, 0.58, 3.5, 0.25, 10, CYAN, True)
    text(s, "“The trading application\nis very slow.”", 0.85, 1.5, 11.65, 1.25, 34, WHITE, True, PP_ALIGN.CENTER)
    line(s, 3.1, 3.2, 10.23, 3.2, NAVY_3, 1.2)
    for i, (label, color) in enumerate([("KNOWLEDGE", BLUE), ("SERVICE DESK", ORANGE), ("REAL-TIME OBSERVABILITY", CYAN)]):
        x = 1.15 + i * 4.02
        box(s, x, 3.68, 3.2, 0.76, NAVY_3, color, 0.08)
        text(s, label, x, 3.89, 3.2, 0.3, 11, WHITE, True, PP_ALIGN.CENTER)
        line(s, x + 1.6, 4.44, 6.66, 5.14, color, 1.4, True)
    box(s, 4.65, 5.13, 4.02, 0.76, ORANGE, ORANGE, 0.08)
    text(s, "AI OPERATIONS AGENT", 4.65, 5.34, 4.02, 0.3, 14, WHITE, True, PP_ALIGN.CENTER)
    text(s, "From Helpdesk AI  →  Operations Intelligence", 3.25, 6.42, 6.8, 0.38, 14, RGBColor(196, 216, 234), True, PP_ALIGN.CENTER)
    footer(s, dark=True)

    # 18 — hero incident investigation
    s = new_slide(prs, LIGHT)
    header(s, "AI-Assisted Incident Investigation", "IT Operations", 18)
    # user and agent
    box(s, 0.55, 1.72, 2.35, 0.85, WHITE, BLUE, 0.08)
    text(s, "BUSINESS USER", 0.78, 1.88, 1.88, 0.24, 9, BLUE, True)
    text(s, "“Trading is very slow.”", 0.78, 2.19, 1.88, 0.23, 11, INK, True)
    chevron(s, 3.12, 1.92, 0.5, 0.6, BLUE)
    circle(s, 3.95, 1.57, 1.35, NAVY)
    text(s, "AI OPS\nAGENT", 3.95, 1.87, 1.35, 0.65, 13, WHITE, True, PP_ALIGN.CENTER)
    sources = [
        ("K2", "Existing incident?", 5.75, 1.64, ORANGE),
        ("KNOWLEDGE", "Known issue / runbook?", 7.55, 1.64, BLUE),
        ("CHANGE", "Recent deployment?", 9.88, 1.64, GREEN),
    ]
    for title_, sub, x, y, color in sources:
        box(s, x, y, 1.68 if title_ != "KNOWLEDGE" else 2.05, 0.9, WHITE, color, 0.06)
        text(s, title_, x, y + 0.15, 1.68 if title_ != "KNOWLEDGE" else 2.05, 0.24, 9.5, color, True, PP_ALIGN.CENTER)
        text(s, sub, x + 0.05, y + 0.51, (1.58 if title_ != "KNOWLEDGE" else 1.95), 0.21, 7.6, MUTED, False, PP_ALIGN.CENTER)
        line(s, 5.3, 2.24, x, y + 0.45, color, 1.1, True)
    # observability fan
    box(s, 5.75, 2.88, 5.82, 1.02, NAVY, NAVY, 0.08)
    text(s, "OBSERVABILITY", 5.95, 3.05, 1.45, 0.25, 9.5, CYAN, True)
    telem = ["RUM", "APM", "DB", "INFRA", "LOGS"]
    for i, label in enumerate(telem):
        x = 7.28 + i * 0.82
        pill(s, label, x, 3.0, 0.7, NAVY_3, WHITE, 8)
    line(s, 5.3, 2.24, 5.75, 3.4, CYAN, 1.2, True)
    # correlation evidence
    box(s, 0.58, 4.35, 6.13, 1.48, WHITE, ORANGE, 0.08)
    text(s, "EVIDENCE CORRELATION", 0.85, 4.58, 2.6, 0.25, 10, ORANGE, True)
    evidence = [("10:32", "User impact detected"), ("+38%", "App latency"), ("DB", "Latency correlated"), ("NET", "No anomaly")]
    for i, (metric, label) in enumerate(evidence):
        x = 0.85 + i * 1.42
        text(s, metric, x, 5.02, 1.15, 0.28, 13, INK, True, PP_ALIGN.CENTER)
        text(s, label, x, 5.35, 1.15, 0.24, 7.5, MUTED, False, PP_ALIGN.CENTER)
    chevron(s, 6.93, 4.78, 0.45, 0.62, ORANGE)
    box(s, 7.62, 4.35, 2.15, 1.48, PALE_ORANGE, ORANGE, 0.08)
    text(s, "RECOMMEND", 7.62, 4.58, 2.15, 0.24, 10, ORANGE, True, PP_ALIGN.CENTER)
    text(s, "Probable cause\nEvidence\nRelevant runbook", 7.85, 5.0, 1.7, 0.63, 9, MUTED, False, PP_ALIGN.CENTER)
    chevron(s, 9.98, 4.78, 0.45, 0.62, GREEN)
    box(s, 10.67, 4.35, 2.02, 1.48, PALE_GREEN, GREEN, 0.08)
    text(s, "ACTION", 10.67, 4.58, 2.02, 0.24, 10, GREEN, True, PP_ALIGN.CENTER)
    text(s, "Update incident\nHuman approval\nRemediation", 10.9, 5.0, 1.56, 0.63, 9, MUTED, False, PP_ALIGN.CENTER)
    statement(s, "AI should correlate evidence — not guess the root cause.", 6.34, ORANGE)
    footer(s)

    # 19 — Observability
    s = new_slide(prs)
    header(s, "Observability Gives AI the Operational Context", "IT Operations", 19)
    box(s, 0.7, 1.88, 6.5, 0.75, NAVY, NAVY, 0.08)
    text(s, "AI OPERATIONS AGENT", 0.7, 2.08, 6.5, 0.3, 15, WHITE, True, PP_ALIGN.CENTER)
    chevron(s, 3.67, 2.83, 0.54, 0.6, ORANGE)
    box(s, 0.7, 3.52, 6.5, 0.82, PALE_BLUE, BLUE, 0.08)
    text(s, "OBSERVABILITY PLATFORM  (e.g., Datadog)", 0.7, 3.75, 6.5, 0.3, 14, BLUE, True, PP_ALIGN.CENTER)
    for i, label in enumerate(["RUM", "APM", "LOGS", "INFRA", "DATABASE"]):
        x = 0.72 + i * 1.3
        box(s, x, 4.8, 1.08, 0.54, LIGHT, LINE, 0.05)
        text(s, label, x, 4.94, 1.08, 0.27, 9, INK, True, PP_ALIGN.CENTER)
        line(s, 3.95, 4.34, x + 0.54, 4.8, MID, 0.9)
    box(s, 7.62, 1.88, 4.92, 3.95, LIGHT, LINE, 0.1)
    text(s, "AI CAN ASK", 7.98, 2.23, 4.2, 0.3, 12, ORANGE, True)
    qs = ["What is currently alerting?", "What changed?", "Which services are affected?", "App, database or infrastructure?", "Have we seen this before?"]
    for i, q in enumerate(qs):
        icon(s, "?", 8.0, 2.86 + i * 0.53, 0.31, ORANGE, 9)
        text(s, q, 8.48, 2.86 + i * 0.53, 3.6, 0.27, 10.5, INK)
    statement(s, "Observability provides signals. AI provides context, correlation and orchestration.", 6.34)
    footer(s)

    # 20 — proactive operations
    s = new_slide(prs, LIGHT)
    header(s, "What If IT Knows Before the User Calls?", "IT Operations", 20)
    flow = [
        ("ANOMALY", "APM / Infra / DB", BLUE),
        ("INVESTIGATE", "Logs / metrics / traces / changes", CYAN),
        ("UNDERSTAND", "Service / impact / likely cause", ORANGE),
        ("RESPOND", "K2 / evidence / runbook / notify", GREEN),
        ("APPROVE", "Human or automation", NAVY_3),
    ]
    for i, (title_, body_, color) in enumerate(flow):
        x = 0.55 + i * 2.55
        circle(s, x + 0.65, 2.15, 1.1, color)
        text(s, str(i + 1), x + 0.65, 2.39, 1.1, 0.42, 18, WHITE, True, PP_ALIGN.CENTER)
        text(s, title_, x, 3.55, 2.4, 0.3, 11, color, True, PP_ALIGN.CENTER)
        text(s, body_, x + 0.15, 4.03, 2.1, 0.7, 9.5, MUTED, False, PP_ALIGN.CENTER)
        if i < 4:
            chevron(s, x + 2.18, 2.46, 0.34, 0.5, color)
    box(s, 2.65, 5.42, 8.05, 0.72, WHITE, ORANGE, 0.08)
    rich(s, [("REACTIVE SUPPORT", MUTED, True), ("  →  ", ORANGE, True), ("PROACTIVE OPERATIONS", GREEN, True)],
         2.65, 5.63, 8.05, 0.3, 15, PP_ALIGN.CENTER)
    footer(s)

    # 21 — landscape opportunities
    s = new_slide(prs)
    header(s, "One Platform. Multiple Enterprise AI Opportunities.", "Beyond HR & IT", 21)
    cols = [
        ("EMPLOYEE", "HR self-service\nTalent intelligence\nEmployee knowledge", BLUE),
        ("IT & SECURITY", "IT helpdesk\nIncident investigation\nSecurity operations", CYAN),
        ("RISK & COMPLIANCE", "Regulatory knowledge\nKYC / CDD assistant\nPolicy review", ORANGE),
        ("BUSINESS", "Research assistant\nDocument intelligence\nManagement intelligence", GREEN),
    ]
    for i, (title_, body_, color) in enumerate(cols):
        x = 0.52 + i * 3.2
        box(s, x, 1.95, 2.82, 2.83, LIGHT, color, 0.08)
        icon(s, title_[0], x + 1.08, 2.26, 0.66, color, 18)
        text(s, title_, x + 0.15, 3.08, 2.52, 0.3, 11, color, True, PP_ALIGN.CENTER)
        text(s, body_, x + 0.22, 3.62, 2.38, 0.9, 10.5, MUTED, False, PP_ALIGN.CENTER)
    box(s, 1.16, 5.35, 11.0, 0.78, NAVY, NAVY, 0.08)
    text(s, "SAME ENTERPRISE AI PLATFORM", 1.43, 5.51, 3.0, 0.28, 11, WHITE, True)
    text(s, "Knowledge   |   Agents   |   Models   |   Integration   |   Governance", 4.55, 5.51, 7.25, 0.28, 10.5, CYAN, True, PP_ALIGN.RIGHT)
    statement(s, "HR and IT can be the starting point — not the destination.", 6.47)
    footer(s)

    # 22 — KYC/CDD
    s = new_slide(prs, LIGHT)
    header(s, "AI-Assisted KYC / CDD Review", "Regulated Business", 22)
    box(s, 0.68, 1.73, 12.0, 0.6, WHITE, BLUE, 0.08)
    text(s, "Compliance Officer: “Prepare the review pack for this customer.”", 0.68, 1.89, 12.0, 0.28, 14, INK, True, PP_ALIGN.CENTER)
    card(s, "INPUT EVIDENCE", "Customer profile\nKYC documents\nUBO structure\nRisk classification\nTransaction alerts\nPrevious review", 0.7, 2.72, 3.0, 2.75, BLUE, WHITE)
    chevron(s, 3.95, 3.68, 0.55, 0.7, ORANGE)
    circle(s, 4.86, 3.16, 2.0, NAVY)
    text(s, "KYC / CDD\nAGENT", 4.86, 3.67, 2.0, 0.7, 17, WHITE, True, PP_ALIGN.CENTER)
    chevron(s, 7.2, 3.68, 0.55, 0.7, ORANGE)
    card(s, "REVIEW PACK", "Identity summary\nUBO structure\nMissing documents\nRisk indicators\nPotential inconsistencies\nSupporting evidence", 8.08, 2.72, 4.25, 2.75, GREEN, WHITE)
    box(s, 3.08, 5.88, 7.2, 0.58, PALE_ORANGE, ORANGE, 0.08)
    text(s, "HUMAN COMPLIANCE DECISION", 3.08, 6.03, 7.2, 0.28, 15, ORANGE, True, PP_ALIGN.CENTER)
    footer(s)

    # 23 — Regulation to action
    s = new_slide(prs)
    header(s, "From Regulation to Actionable Internal Knowledge", "Regulated Business", 23)
    box(s, 0.65, 1.73, 12.0, 0.72, PALE_BLUE, BLUE, 0.08)
    text(s, "“What policies and processes may require review based on this regulatory change?”",
         0.85, 1.93, 11.6, 0.3, 14, INK, True, PP_ALIGN.CENTER)
    stage(s, 1, "REGULATION", "New rule or supervisory guidance", 0.9, 3.0, 2.25, BLUE)
    chevron(s, 3.2, 3.13, 0.42, 0.55, BLUE)
    stage(s, 2, "AI ANALYSIS", "Compare policy / procedure / SOP / control", 3.75, 3.0, 3.2, ORANGE)
    chevron(s, 7.08, 3.13, 0.42, 0.55, ORANGE)
    box(s, 7.7, 2.66, 4.73, 1.6, LIGHT, GREEN, 0.08)
    text(s, "GAP / IMPACT VIEW", 7.95, 2.9, 4.23, 0.3, 11, GREEN, True, PP_ALIGN.CENTER)
    text(s, "Requirement  |  Existing policy  |  Potential gap\nAffected process  |  Evidence / citation",
         7.95, 3.42, 4.23, 0.57, 10, MUTED, False, PP_ALIGN.CENTER)
    line(s, 10.07, 4.27, 10.07, 5.15, GREEN, 1.6, True)
    box(s, 8.35, 5.18, 3.45, 0.64, PALE_GREEN, GREEN, 0.08)
    text(s, "COMPLIANCE REVIEW", 8.35, 5.36, 3.45, 0.28, 12, GREEN, True, PP_ALIGN.CENTER)
    statement(s, "AI accelerates analysis. It does not replace compliance judgment.", 6.32)
    footer(s)

    # 24 — architecture hero
    s = new_slide(prs, NAVY)
    header(s, "Target Enterprise AI Architecture", "Putting Everything Together", 24, True)
    band(s, "USERS", ["Employee", "HR", "IT", "Security", "Compliance", "Management"], 1.77, BLUE, 1.35, 1.0, 11.3, True)
    band(s, "CHANNELS", ["Web", "Teams", "Mobile", "API"], 2.48, CYAN, 1.35, 1.0, 11.3, True)
    box(s, 1.62, 3.22, 10.05, 2.48, NAVY_2, BLUE, 0.08)
    text(s, "ENTERPRISE AI PLATFORM", 1.88, 3.43, 9.52, 0.34, 15, WHITE, True, PP_ALIGN.CENTER)
    platform = [
        ("AGENT RUNTIME", "HR  |  IT  |  Security  |  Compliance", BLUE),
        ("INTELLIGENCE", "RAG  |  Reasoning  |  Memory  |  Orchestration", CYAN),
        ("MODEL GATEWAY", "Local  |  Private  |  Cloud", ORANGE),
        ("INTEGRATION GATEWAY", "API  |  MCP  |  Workflow  |  Tools", GREEN),
    ]
    for i, (label, items, color) in enumerate(platform):
        x = 1.98 + (i % 2) * 4.86
        y = 3.98 + (i // 2) * 0.73
        box(s, x, y, 4.5, 0.58, NAVY_3, color, 0.04)
        text(s, label, x + 0.15, y + 0.1, 1.55, 0.25, 8.5, color, True)
        text(s, items, x + 1.68, y + 0.1, 2.65, 0.25, 8.5, WHITE, False, PP_ALIGN.RIGHT)
    box(s, 0.55, 3.22, 0.74, 2.48, NAVY_3, BLUE, 0.04)
    text(s, "SECURITY\nIdentity\nRBAC / ABAC\nGuardrails\nDLP\nAudit", 0.55, 3.35, 0.74, 2.15, 7.8, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    box(s, 12.02, 3.22, 0.76, 2.48, NAVY_3, CYAN, 0.04)
    text(s, "AI OPS\nQuality\nLatency\nUsage\nCost\nObservability", 12.02, 3.35, 0.76, 2.15, 7.8, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    band(s, "SYSTEMS", ["PeopleSoft", "K2", "Identity", "Observability", "Databases", "Internal systems"], 5.95, ORANGE, 1.35, 1.0, 11.3, True)
    band(s, "DATA", ["Documents", "Vector DB", "Database", "Object storage"], 6.63, GREEN, 1.35, 1.0, 11.3, True)
    footer(s, dark=True)

    # 25 — Local AI infrastructure
    s = new_slide(prs, LIGHT)
    header(s, "Production Local AI Is an Infrastructure Platform", "Infrastructure", 25)
    layers = [
        ("ACCESS", "Load balancer  |  API gateway", BLUE),
        ("APPLICATION", "AI application  |  Agent runtime  |  API", CYAN),
        ("PROCESSING", "Workers  |  Ingestion  |  Document processing", ORANGE),
        ("DATA", "Database  |  Vector DB  |  Object storage", GREEN),
        ("AI INFERENCE", "Inference gateway  |  GPU cluster  |  Local LLM", NAVY_3),
    ]
    for i, (label, items, color) in enumerate(layers):
        band(s, label, items.split("  |  "), 1.78 + i * 0.82, color, 1.75, 1.2, 9.7)
        if i < 4:
            line(s, 6.05, 2.4 + i * 0.82, 6.05, 2.57 + i * 0.82, MID, 1.3, True)
    box(s, 11.25, 1.78, 1.3, 3.9, NAVY, NAVY, 0.06)
    text(s, "OPERATIONS\n\nMonitoring\nBackup\nHA / DR\nSecurity\nCapacity", 11.25, 2.1, 1.3, 3.12, 9.5, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    statement(s, "GPU sizing is driven by workload and concurrency — not employee count alone.", 6.32)
    footer(s)

    # 26 — Roadmap
    s = new_slide(prs)
    header(s, "Enterprise AI Roadmap — From Ambition to Adoption", "Roadmap", 26)
    steps = [
        ("01", "FOUNDATION", "Local AI\nKnowledge\nSecurity\nGovernance", BLUE),
        ("02", "ASSIST", "HR Agent\nIT Helpdesk", CYAN),
        ("03", "ACT", "PeopleSoft\nK2\nAPI / MCP", ORANGE),
        ("04", "INTELLIGENCE", "Observability\nTalent\nCompliance", GREEN),
        ("05", "SCALE", "More agents\nAutomation\nAdoption", NAVY_3),
    ]
    for i, (num, title_, body_, color) in enumerate(steps):
        x = 0.55 + i * 2.53
        y = 4.62 - i * 0.46
        box(s, x, y, 2.18, 1.55 + i * 0.46, LIGHT, color, 0.07)
        text(s, num, x + 0.18, y + 0.2, 0.48, 0.28, 12, color, True)
        text(s, title_, x + 0.62, y + 0.2, 1.34, 0.28, 10, color, True)
        text(s, body_, x + 0.22, y + 0.69, 1.74, 0.88, 9.5, MUTED, False, PP_ALIGN.CENTER)
        if i < 4:
            chevron(s, x + 2.23, y + 0.5, 0.28, 0.45, color)
    for i, (label, color) in enumerate([("PEOPLE", BLUE), ("PROCESS", ORANGE), ("TECHNOLOGY", GREEN)]):
        x = 2.14 + i * 3.25
        pill(s, label, x, 6.32, 2.55, PALE_BLUE if i == 0 else (PALE_ORANGE if i == 1 else PALE_GREEN), color, 9)
    footer(s)

    # 27 — Starting point
    s = new_slide(prs, LIGHT)
    header(s, "Start Focused. Design for Enterprise Scale.", "Roadmap", 27)
    blocks = [
        ("PLATFORM FOUNDATION", "Local LLM\nRAG\nIdentity\nSecurity\nGovernance", BLUE, 0.7, 2.0, 3.45),
        ("HR PILOT", "HR knowledge\nPeopleSoft read\nLeave / benefit\nTalent search", CYAN, 4.45, 2.0, 3.45),
        ("IT PILOT", "IT knowledge\nK2 integration\nTroubleshooting\nIncident creation", ORANGE, 8.2, 2.0, 3.45),
    ]
    for title_, body_, color, x, y, w in blocks:
        box(s, x, y, w, 3.15, WHITE, color, 0.1)
        text(s, title_, x, y + 0.3, w, 0.32, 12, color, True, PP_ALIGN.CENTER)
        text(s, body_, x + 0.35, y + 1.0, w - 0.7, 1.45, 13, MUTED, False, PP_ALIGN.CENTER)
    box(s, 11.92, 2.0, 0.68, 3.15, NAVY, NAVY, 0.08)
    text(s, "NEXT\n\nObservability\nSecurity\nCompliance", 11.92, 2.3, 0.68, 2.46, 8.3, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    statement(s, "Start with measurable use cases while building a reusable enterprise AI foundation.", 6.12)
    footer(s)

    # 28 — KPI dashboard
    s = new_slide(prs)
    header(s, "Measure Business Outcomes — Not AI Demo Quality", "Roadmap", 28)
    metrics = [
        ("KNOWLEDGE", "Accuracy\nCitation accuracy\nCoverage", BLUE),
        ("HR", "Self-service completion\nTime-to-service\nAdoption", CYAN),
        ("IT", "First-contact resolution\nMTTR\nTicket quality", ORANGE),
        ("AI PLATFORM", "p95 latency\nModel utilization\nCost per task", GREEN),
        ("SECURITY", "Unauthorized access = 0\nPolicy violation\nAudit coverage", NAVY_3),
    ]
    for i, (title_, body_, color) in enumerate(metrics):
        x = 0.5 + i * 2.55
        box(s, x, 1.93, 2.25, 3.2, LIGHT, color, 0.08)
        circle(s, x + 0.79, 2.24, 0.67, color)
        text(s, "✓" if i in (0, 4) else str(i + 1), x + 0.79, 2.39, 0.67, 0.3, 13, WHITE, True, PP_ALIGN.CENTER)
        text(s, title_, x + 0.15, 3.13, 1.95, 0.3, 10.5, color, True, PP_ALIGN.CENTER)
        text(s, body_, x + 0.17, 3.68, 1.91, 0.9, 9.7, MUTED, False, PP_ALIGN.CENTER)
    box(s, 2.0, 5.72, 9.3, 0.6, NAVY, NAVY, 0.06)
    text(s, "BASELINE  →  PILOT  →  MEASURE  →  IMPROVE  →  SCALE", 2.0, 5.88, 9.3, 0.28, 12, WHITE, True, PP_ALIGN.CENTER)
    footer(s)

    # 29 — Closing
    s = new_slide(prs, NAVY)
    box(s, 0, 0, 0.16, 7.5, ORANGE, ORANGE, 0)
    text(s, "FROM KNOWLEDGE", 0.82, 1.18, 11.7, 0.62, 30, WHITE, True, PP_ALIGN.CENTER)
    text(s, "TO INTELLIGENCE", 0.82, 2.12, 11.7, 0.62, 30, CYAN, True, PP_ALIGN.CENTER)
    text(s, "TO ACTION", 0.82, 3.06, 11.7, 0.62, 30, ORANGE, True, PP_ALIGN.CENTER)
    line(s, 3.45, 4.03, 9.88, 4.03, NAVY_3, 1.2)
    text(s, "SECURE  •  PRIVATE  •  GOVERNED  •  ACTIONABLE", 1.5, 4.43, 10.35, 0.4, 14, WHITE, True, PP_ALIGN.CENTER)
    text(s, "Start with HR and IT. Build the foundation for enterprise-wide AI.", 1.68, 5.15, 9.98, 0.38, 15, RGBColor(190, 211, 229), False, PP_ALIGN.CENTER)
    pill(s, "USE-CASE WORKSHOP", 2.15, 6.05, 2.35, NAVY_3, CYAN, 9)
    chevron(s, 4.68, 5.95, 0.4, 0.55, ORANGE)
    pill(s, "TECHNICAL ASSESSMENT", 5.2, 6.05, 2.75, NAVY_3, CYAN, 9)
    chevron(s, 8.15, 5.95, 0.4, 0.55, ORANGE)
    pill(s, "PILOT", 8.68, 6.05, 2.25, ORANGE, WHITE, 9)
    footer(s, dark=True)

    # 30 — Model selection
    s = new_slide(prs)
    header(s, "Local LLM Model Selection", "Backup", 30)
    columns = [
        ("MODEL SIZE", "Smaller\n7–14B\n\nLarger\n30–70B+", BLUE),
        ("CAPABILITY", "Reasoning\nTool calling\nMultilingual\nVision", CYAN),
        ("INFRASTRUCTURE", "VRAM\nQuantization\nContext\nKV cache", ORANGE),
        ("FIT", "Latency target\nConcurrency\nData policy\nTask quality", GREEN),
    ]
    for i, (title_, body_, color) in enumerate(columns):
        card(s, title_, body_, 0.72 + i * 3.08, 2.0, 2.75, 3.32, color, LIGHT)
    statement(s, "Benchmark with the real prompt, context, retrieval and tool workload — not model size alone.", 6.05)
    footer(s)

    # 31 — Capacity planning
    s = new_slide(prs, LIGHT)
    header(s, "GPU & Capacity Planning", "Backup", 31)
    circle(s, 4.84, 2.02, 3.0, NAVY)
    text(s, "CONCURRENT\nGENERATIONS", 4.84, 2.85, 3.0, 0.8, 20, WHITE, True, PP_ALIGN.CENTER)
    items = [
        ("TOKENS / SEC", 0.8, 2.0, BLUE), ("CONTEXT LENGTH", 0.92, 4.55, CYAN),
        ("KV CACHE", 9.58, 2.0, ORANGE), ("MODEL SIZE", 9.63, 4.55, GREEN),
        ("RAG + TOOLS", 4.85, 5.65, NAVY_3),
    ]
    for label, x, y, color in items:
        box(s, x, y, 2.55, 0.68, WHITE, color, 0.08)
        text(s, label, x, y + 0.18, 2.55, 0.28, 11, color, True, PP_ALIGN.CENTER)
        line(s, x + 1.27, y + (0.68 if y < 3 else 0), 6.34, 3.52, color, 1.1)
    footer(s)

    # 32 — Decision matrix
    s = new_slide(prs)
    header(s, "Local vs Cloud Decision Matrix", "Backup", 32)
    rows = [
        ("Sensitive data / isolation", "LOCAL", "Policy dependent"),
        ("Frontier reasoning capability", "Fit dependent", "CLOUD"),
        ("Predictable high-volume workload", "LOCAL / PRIVATE", "Possible"),
        ("Rapid model access", "Lifecycle overhead", "CLOUD"),
        ("Network-independent operation", "LOCAL", "Not suitable"),
        ("Elastic burst capacity", "Limited by owned GPU", "CLOUD"),
    ]
    text(s, "DECISION FACTOR", 0.75, 1.86, 5.2, 0.28, 11, MUTED, True)
    text(s, "LOCAL / PRIVATE", 6.05, 1.86, 2.65, 0.28, 11, BLUE, True, PP_ALIGN.CENTER)
    text(s, "CLOUD", 9.12, 1.86, 3.15, 0.28, 11, ORANGE, True, PP_ALIGN.CENTER)
    for i, (factor, local, cloud) in enumerate(rows):
        y = 2.3 + i * 0.62
        box(s, 0.72, y, 11.7, 0.52, WHITE if i % 2 == 0 else LIGHT, LINE, 0.02)
        text(s, factor, 0.95, y + 0.12, 4.85, 0.25, 10, INK, True)
        text(s, local, 6.05, y + 0.12, 2.65, 0.25, 9.5, BLUE, True, PP_ALIGN.CENTER)
        text(s, cloud, 9.12, y + 0.12, 3.15, 0.25, 9.5, ORANGE, True, PP_ALIGN.CENTER)
    statement(s, "The target architecture should support controlled choice — not ideological lock-in.", 6.42)
    footer(s)

    # 33 — RAG ACL flow
    s = new_slide(prs, LIGHT)
    header(s, "RAG Security & ACL Flow", "Backup", 33)
    stages = [
        ("IDENTITY", "User + group claims", BLUE),
        ("QUERY", "Intent + agent scope", CYAN),
        ("FILTER", "Personal / team / global ACL", ORANGE),
        ("RETRIEVE", "Authorized chunks only", GREEN),
        ("CITE", "Re-check source authorization", NAVY_3),
    ]
    for i, (title_, body_, color) in enumerate(stages):
        x = 0.55 + i * 2.55
        circle(s, x + 0.65, 2.25, 1.1, color)
        text(s, str(i + 1), x + 0.65, 2.49, 1.1, 0.42, 17, WHITE, True, PP_ALIGN.CENTER)
        text(s, title_, x, 3.65, 2.4, 0.28, 10.5, color, True, PP_ALIGN.CENTER)
        text(s, body_, x + 0.12, 4.1, 2.16, 0.62, 9.5, MUTED, False, PP_ALIGN.CENTER)
        if i < 4:
            chevron(s, x + 2.17, 2.53, 0.33, 0.48, color)
    box(s, 2.3, 5.38, 8.7, 0.68, PALE_ORANGE, ORANGE, 0.08)
    text(s, "Authorization is enforced before retrieval and again before opening the source.", 2.3, 5.57, 8.7, 0.29, 13, ORANGE, True, PP_ALIGN.CENTER)
    footer(s)

    # 34 — MCP vs API
    s = new_slide(prs)
    header(s, "MCP vs API Integration Architecture", "Backup", 34)
    box(s, 0.7, 1.95, 2.35, 3.45, NAVY, NAVY, 0.1)
    text(s, "AI AGENT", 0.7, 2.35, 2.35, 0.38, 17, WHITE, True, PP_ALIGN.CENTER)
    text(s, "Intent\nContext\nPolicy\nAudit", 0.7, 3.18, 2.35, 1.15, 12, RGBColor(200, 219, 235), False, PP_ALIGN.CENTER)
    chevron(s, 3.3, 3.24, 0.56, 0.7, ORANGE)
    box(s, 4.12, 1.88, 3.1, 1.45, PALE_BLUE, BLUE, 0.08)
    text(s, "MCP", 4.12, 2.13, 3.1, 0.32, 15, BLUE, True, PP_ALIGN.CENTER)
    text(s, "Discoverable tools\nStandard agent interface", 4.12, 2.62, 3.1, 0.48, 10, MUTED, False, PP_ALIGN.CENTER)
    box(s, 4.12, 4.03, 3.1, 1.45, PALE_ORANGE, ORANGE, 0.08)
    text(s, "REST / EVENT API", 4.12, 4.28, 3.1, 0.32, 15, ORANGE, True, PP_ALIGN.CENTER)
    text(s, "Explicit contract\nWorkflow / transaction", 4.12, 4.77, 3.1, 0.48, 10, MUTED, False, PP_ALIGN.CENTER)
    for y, color in [(2.6, BLUE), (4.75, ORANGE)]:
        chevron(s, 7.55, y, 0.56, 0.7, color)
    box(s, 8.36, 1.95, 4.2, 3.45, LIGHT, LINE, 0.1)
    text(s, "ENTERPRISE SYSTEMS", 8.36, 2.28, 4.2, 0.32, 14, INK, True, PP_ALIGN.CENTER)
    text(s, "PeopleSoft  |  K2\nObservability  |  Databases\nInternal services  |  Automation", 8.78, 3.08, 3.36, 1.25, 12, MUTED, False, PP_ALIGN.CENTER)
    statement(s, "Treat MCP and APIs as governed connection patterns inside one integration layer.", 6.22)
    footer(s)

    # 35 — AI threat model
    s = new_slide(prs, LIGHT)
    header(s, "AI Threat Model — Protect Data, Tools and Decisions", "Backup", 35)
    threats = [
        ("PROMPT INJECTION", "Input validation\nInstruction boundaries", RED),
        ("DATA EXFILTRATION", "ACL + DLP\nOutput controls", ORANGE),
        ("TOOL ABUSE", "Allowlist + policy\nHuman approval", BLUE),
    ]
    for i, (title_, body_, color) in enumerate(threats):
        card(s, title_, body_, 0.7 + i * 2.93, 1.85, 2.65, 1.7, color, WHITE)
    box(s, 9.72, 1.85, 2.9, 1.7, NAVY, NAVY, 0.08)
    text(s, "AUDIT", 9.72, 2.13, 2.9, 0.3, 13, CYAN, True, PP_ALIGN.CENTER)
    text(s, "Identity  •  Model\nTool  •  Action  •  Trace", 9.72, 2.68, 2.9, 0.52, 10, WHITE, False, PP_ALIGN.CENTER)
    line(s, 0.85, 4.08, 12.48, 4.08, LINE, 1)
    flow = [
        ("INPUT", "Validate + classify", BLUE),
        ("RETRIEVAL", "Enforce ACL", CYAN),
        ("REASONING", "Bound instructions", ORANGE),
        ("TOOL", "Allowlist + least privilege", RED),
        ("OUTPUT", "DLP + evidence", GREEN),
    ]
    for i, (title_, body_, color) in enumerate(flow):
        x = 0.55 + i * 2.55
        box(s, x, 4.55, 2.25, 1.0, WHITE, color, 0.06)
        text(s, title_, x, 4.74, 2.25, 0.25, 10, color, True, PP_ALIGN.CENTER)
        text(s, body_, x + 0.1, 5.12, 2.05, 0.25, 8.8, MUTED, False, PP_ALIGN.CENTER)
        if i < 4:
            chevron(s, x + 2.27, 4.82, 0.24, 0.4, color)
    statement(s, "Trust is earned at every step — from prompt to retrieval, tool execution and response.", 6.32)
    footer(s)

    # 36 — HA / DR / backup
    s = new_slide(prs)
    header(s, "HA / DR / Backup Architecture for Local AI", "Backup", 36)
    band(s, "ACCESS", ["Load balancer", "Health routing", "TLS"], 1.78, BLUE, 1.55, 1.2, 9.45)
    band(s, "APP TIER", ["App replicas", "Worker pool", "Queue"], 2.54, CYAN, 1.55, 1.2, 9.45)
    band(s, "DATA TIER", ["Database", "Vector DB", "Object storage"], 3.30, GREEN, 1.55, 1.2, 9.45)
    band(s, "INFERENCE", ["Gateway", "GPU nodes", "Model cache"], 4.06, ORANGE, 1.55, 1.2, 9.45)
    box(s, 11.0, 1.78, 1.58, 2.9, NAVY, NAVY, 0.06)
    text(s, "RESILIENCE\n\nHA\nBackup set\nRestore drill\nRTO / RPO\nMonitoring", 11.0, 2.08, 1.58, 2.36,
         9.5, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    line(s, 2.2, 5.22, 11.0, 5.22, MID, 1.2, True)
    box(s, 2.2, 4.92, 3.2, 0.62, PALE_BLUE, BLUE, 0.06)
    text(s, "PRIMARY SITE", 2.2, 5.08, 3.2, 0.27, 11, BLUE, True, PP_ALIGN.CENTER)
    box(s, 7.8, 4.92, 3.2, 0.62, PALE_ORANGE, ORANGE, 0.06)
    text(s, "RECOVERY SITE / RESTORE TARGET", 7.8, 5.08, 3.2, 0.27, 9.5, ORANGE, True, PP_ALIGN.CENTER)
    statement(s, "Backups are only proven when application data, vectors and objects restore as one consistent set.", 6.32)
    footer(s)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    return OUTPUT


NOTES_TEXT = """# Enterprise AI Strategy Proposal — Presenter Notes

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
"""


THAI_NOTES = [
    """สไลด์ 1 — Enterprise AI Platform (ประมาณ 1 นาที)

สารที่ต้องการสื่อ:
วันนี้เราไม่ได้มานำเสนอ Chatbot อีกหนึ่งตัว แต่ต้องการหารือว่า AI จะกลายเป็นชั้น Intelligence และ Orchestration ที่ปลอดภัยเหนือองค์ความรู้ ระบบโครงสร้างพื้นฐาน และระบบธุรกิจเดิมได้อย่างไร

แนวทางพูด:
เปิดด้วยภาพใหญ่ก่อนว่าองค์กรมีข้อมูลและระบบที่ดีอยู่แล้ว เช่น PeopleSoft, K2, ระบบฐานข้อมูล และ Observability สิ่งที่ยังขาดคือชั้นกลางที่เข้าใจความต้องการของผู้ใช้ ค้นข้อมูลที่ได้รับอนุญาต เชื่อมโยงหลักฐาน และเรียกใช้ระบบเดิมอย่างมีการกำกับดูแล

ย้ำว่า AI ไม่ได้เข้ามาแทน Systems of Record แต่ช่วยให้คนเข้าถึงความรู้และดำเนินงานผ่านระบบเหล่านั้นได้ง่ายและรวดเร็วขึ้น

ประโยคเชื่อม:
ก่อนดูสถาปัตยกรรม เรามาดูกันก่อนว่า Enterprise AI กำลังพัฒนาไปไกลกว่า Chat อย่างไร""",

    """สไลด์ 2 — AI Is Moving Beyond Chat (ประมาณ 2 นาที)

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
คำถามต่อไปคือ เหตุใดความสามารถเหล่านี้จึงเริ่มเป็นจริงได้ในช่วงเวลานี้""",

    """สไลด์ 3 — Why Enterprise AI, Why Now? (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
Enterprise AI เกิดขึ้นได้เพราะสี่องค์ประกอบสำคัญกำลังมาบรรจบกัน

แนวทางพูด:
1. Model Intelligence: โมเดลมี Reasoning, Tool Calling และ Multimodal ดีขึ้น
2. Enterprise Knowledge: RAG, Vector Search และ Document Intelligence พร้อมใช้งานจริง
3. System Connectivity: API, MCP และ Workflow ทำให้ AI เชื่อมกับระบบงานได้
4. AI Infrastructure: มีทั้ง GPU, Local LLM และ Cloud AI ให้เลือกตามนโยบาย

ย้ำว่าโมเดลเพียงอย่างเดียวไม่เพียงพอ ต้องมีข้อมูล การเชื่อมต่อ โครงสร้างพื้นฐาน และ Governance ทำงานร่วมกัน

ประโยคเชื่อม:
เมื่อองค์ประกอบพร้อม สิ่งที่ไม่ควรทำคือสร้าง Bot แยกทีละ Use Case โดยไม่มีรากฐานร่วมกัน""",

    """สไลด์ 4 — The Opportunity Is Bigger Than a Chatbot (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
องค์กรควรสร้างรากฐาน Enterprise AI ร่วมกัน แล้วขยายผ่าน Agent เฉพาะทาง แทนการสร้าง Bot และ Infrastructure แยกกันทุก Use Case

แนวทางพูด:
ฝั่งซ้ายแสดงผลของการทำแบบ Use-Case-by-Use-Case: ข้อมูลซ้ำ ระบบซ้ำ Security ไม่สม่ำเสมอ ความรู้แยกส่วน และควบคุมยาก

ฝั่งขวาคือ Platform เดียวที่แชร์ Knowledge, Models, Integration, Security, Governance และ Observability ขณะที่ Agent แต่ละตัวมีบทบาท Model, Data Scope และ Tools ของตนเองได้

ย้ำว่า Shared Platform ไม่ได้หมายถึงทุกทีมเห็นข้อมูลร่วมกัน แต่หมายถึงใช้มาตรฐานและ Control Plane เดียวกัน โดยยังแยกสิทธิ์ตามทีมและข้อมูล

ประโยคเชื่อม:
จาก Platform Concept นี้ เราสามารถสรุปคุณค่าหลักเป็นสามขั้นคือ Know, Think และ Act""",

    """สไลด์ 5 — The Enterprise AI Value Chain (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
Enterprise AI ต้องรู้สิ่งที่องค์กรรู้ เข้าใจสิ่งที่ผู้ใช้ต้องการ และลงมือผ่านระบบที่องค์กรไว้วางใจ

แนวทางพูด:
- KNOW: เอกสาร นโยบาย ฐานข้อมูล และ Knowledge Base
- THINK: โมเดล บริบท Agent และ Decision Support
- ACT: PeopleSoft, K2, API, Workflow และ Automation

ชี้แถบด้านล่างว่า Identity, Security, Governance และ Audit ครอบคลุมทั้งสามขั้น ไม่ใช่เพิ่มเข้ามาภายหลัง

ย้ำ Core Message: AI ไม่แทนระบบเดิม แต่เพิ่มความเข้าใจและการประสานงานระหว่างคน ความรู้ และระบบเดิม

ประโยคเชื่อม:
ดังนั้น Platform ที่พร้อมใช้จริงจึงต้องมีมากกว่า LLM หนึ่งตัว""",

    """สไลด์ 6 — Enterprise AI Requires More Than an LLM (ประมาณ 3 นาที)

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
เรามาดูองค์ประกอบสำคัญที่สุดอันหนึ่งก่อน คือการเปลี่ยนข้อมูลกระจัดกระจายให้เป็นความรู้ที่ AI ใช้ได้อย่างน่าเชื่อถือ""",

    """สไลด์ 7 — Trusted Enterprise Knowledge (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
การทำ RAG ที่ดีไม่ใช่เพียงนำเอกสารไปทำ Vector แต่เป็น Lifecycle ตั้งแต่รับข้อมูลจนถึงการอ้างอิงแหล่งที่มาอย่างมีสิทธิ์

แนวทางพูด:
อธิบาย Pipeline จาก Source → Ingest → Understand → Govern → Retrieve → Answer

เน้นจุด Govern: Metadata, ACL, Classification และ Retention ต้องถูกนำไปใช้ตั้งแต่ตอนจัดเก็บและตอนค้นคืน ไม่ใช่กรองเฉพาะหน้า UI

เมื่อ AI แสดง Citation ระบบควรตรวจสิทธิ์ซ้ำก่อนเปิด Source Document เพื่อป้องกันข้อมูลหลุดผ่าน Link หรือ Citation

ประโยคเชื่อม:
เมื่อข้อมูลมีความสำคัญ คำถามเรื่องตำแหน่งที่ประมวลผลและการควบคุมโมเดลจึงตามมา โดยเฉพาะ Local AI""",

    """สไลด์ 8 — Why Local AI Matters (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
Local AI ให้การควบคุมข้อมูลและ Infrastructure มากขึ้น แต่แลกกับภาระในการบริหาร Capacity, Model Lifecycle และ Operations

แนวทางพูด:
อธิบาย Driver หลัก: Data Control, Privacy, Infrastructure Control, Network Isolation และ Workload Economics

พูดอย่างตรงไปตรงมาว่า Local AI ไม่ได้แปลว่าปลอดภัยหรือถูกกว่าโดยอัตโนมัติ ยังต้องออกแบบ Authentication, Network Segmentation, Patch, Monitoring, Backup และ GPU Capacity

ต้นทุนต้องดู Total Cost of Ownership รวมทั้ง GPU, ไฟฟ้า, Cooling, ทีมดูแล และรอบอัปเกรดโมเดล

ประโยคเชื่อม:
ดังนั้นโจทย์ที่ถูกต้องไม่ใช่เลือก Local หรือ Cloud อย่างใดอย่างหนึ่ง แต่คือควบคุมการเลือกโมเดลตามลักษณะงาน""",

    """สไลด์ 9 — Controlled Model Choice (ประมาณ 3 นาที)

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
ไม่ว่าโมเดลจะอยู่ที่ใด หลัก Zero Trust ต้องขยายเข้าไปครอบคลุมการทำงานของ AI ด้วย""",

    """สไลด์ 10 — Zero Trust Must Extend into AI (ประมาณ 3 นาที)

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
Zero Trust ช่วยกำหนดหลักการ ส่วน Guardrails และ Governance คือกลไกที่นำหลักการไปบังคับใช้จริง""",

    """สไลด์ 11 — Governed Agentic AI (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
Guardrails ที่ดีต้องลดความเสี่ยงและยังคงทำให้ AI ส่งมอบคำตอบหรือ Action ที่ควบคุมได้

แนวทางพูด:
ฝั่งซ้ายคือภัยคุกคาม เช่น Prompt Injection, Data Leakage, Unauthorized Retrieval, Excessive Agency และ Unsafe Tool Execution

ตรงกลางคือ Control ได้แก่ Input Guardrail, ACL, PII/DLP, Tool Policy, Output Guardrail และ Human Approval

ฝั่งขวาคือผลลัพธ์ที่ต้องการ: Authorized Answer, Approved Action และ Audit Trail

อธิบายว่า Human Approval ควรใช้ตาม Risk Tier ไม่จำเป็นต้องอนุมัติทุก Tool Call แต่ Action ที่มีผลกระทบสูงต้องมี Approval หรือ Workflow Control

ประโยคเชื่อม:
จากหลักการและสถาปัตยกรรม ต่อไปเราจะทำให้ภาพชัดผ่าน Use Case จริง""",

    """สไลด์ 12 — Let’s Make It Real (ประมาณ 30 วินาที)

สารที่ต้องการสื่อ:
เปลี่ยนจากการอธิบาย Platform มาสู่สิ่งที่ผู้ใช้สัมผัสได้จริงใน Employee Services, IT Operations และงานที่มีข้อกำกับ

แนวทางพูด:
บอกผู้ฟังว่าสามกลุ่มตัวอย่างใช้ Foundation เดียวกัน แต่ต่างกันที่ Agent, Data Scope, Tools และระดับ Governance

ประโยคเชื่อม:
เริ่มจากงานที่ทุกคนเข้าใจง่ายที่สุด คือคำถามและบริการด้าน HR""",

    """สไลด์ 13 — HR Agent (ประมาณ 2 นาที)

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
ลองดูคำถามง่าย ๆ หนึ่งคำถามที่เปลี่ยนจากการค้นข้อมูลหลายจุดให้เป็นบริการครบขั้นตอน""",

    """สไลด์ 14 — Leave Request Use Case (ประมาณ 3 นาที)

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
นอกจากบริการรายบุคคล ข้อมูล HR ยังช่วยวางแผนกำลังคนได้ หากควบคุมสิทธิ์อย่างเหมาะสม""",

    """สไลด์ 15 — Talent Intelligence (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
AI สามารถรวม Skills, Certifications, Training และ Experience เพื่อช่วยค้นบุคลากรและวิเคราะห์ Skill Gap ภายใต้สิทธิ์ HR หรือ Manager

แนวทางพูด:
เริ่มจากคำถามของ Manager แล้วแสดงผลเป็น Candidate แบบไม่เปิดเผยข้อมูลที่ไม่จำเป็นในขั้นแรก

Agent ไม่ควรเพียงจัดอันดับคน แต่ควรอธิบาย Evidence ว่าความสามารถมาจาก Certification, Project หรือ Training ใด และระบุ Gap อย่างตรงไปตรงมา

ผลต่อเนื่องคือการวางแผน Upskill/Reskill ไม่ใช่การตัดสินใจด้านบุคคลโดยอัตโนมัติ

ประโยคเชื่อม:
รูปแบบเดียวกันสามารถนำไปใช้กับ IT Helpdesk เพื่อยกระดับทั้ง Self-Service และคุณภาพ Ticket""",

    """สไลด์ 16 — IT Helpdesk Agent (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
AI ไม่ได้มีเป้าหมายเพียงลดจำนวน Ticket แต่ช่วยแก้ปัญหาเบื้องต้นและทำให้ Ticket ที่ต้องส่งต่อมีข้อมูลพร้อมวิเคราะห์มากขึ้น

แนวทางพูด:
ตัวอย่างผู้ใช้เชื่อมต่อ VPN ไม่ได้ Agent จะทำความเข้าใจ User, Device, Location และ Symptoms จากนั้นค้น KB ตรวจ Identity, Known Incident และ K2 Ticket ก่อนทำ Guided Troubleshooting

หากแก้ได้ ให้บันทึกวิธีการและผล หากแก้ไม่ได้ ให้สร้าง Incident ที่มี Device, Error, Diagnostics, Actions ที่ลองแล้ว และ Evidence แทนข้อความสั้น ๆ ว่า VPN ใช้ไม่ได้

ประโยคเชื่อม:
Helpdesk ยังเริ่มจากผู้ใช้แจ้งปัญหา แต่ระดับถัดไปคือ AI Operations ที่มองเห็นสัญญาณก่อนหรือพร้อมกับผู้ใช้""",

    """สไลด์ 17 — What If AI Could See What IT Sees? (ประมาณ 1 นาที)

สารที่ต้องการสื่อ:
AI Operations Agent ผสานสิ่งที่ Service Desk รู้ สิ่งที่ Knowledge Base รู้ และสิ่งที่ Observability เห็นแบบ Real Time

แนวทางพูด:
หยุดเล็กน้อยที่ประโยค “The trading application is very slow.” เพราะนี่เป็นอาการ ไม่ใช่ Root Cause

อธิบายว่า Agent ต้องไม่รีบตอบจากความจำ แต่ต้องรวบรวม Evidence จาก Incident, Runbook, Change และ Telemetry

ประโยคเชื่อม:
หน้าถัดไปคือภาพการสอบสวนเหตุการณ์แบบครบวงจร และเป็น Use Case หลักของชุดนี้""",

    """สไลด์ 18 — AI-Assisted Incident Investigation (ประมาณ 4 นาที)

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
ความสามารถนี้เกิดไม่ได้หาก AI ไม่มี Operational Context จาก Observability Platform""",

    """สไลด์ 19 — AI + Observability (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
Observability ส่งสัญญาณ ส่วน AI ช่วยตั้งคำถาม เชื่อมโยงบริบท และประสานงานกับระบบอื่น

แนวทางพูด:
Telemetry Pillars ครอบคลุม RUM, APM, Logs, Infrastructure และ Database ขณะที่ Datadog เป็นเพียงตัวอย่างหนึ่งของ Implementation

AI สามารถถามว่าอะไร Alert อยู่ มีอะไรเปลี่ยน บริการใดได้รับผลกระทบ ปัญหาอยู่ชั้น Application, Database หรือ Infrastructure และเคยเกิดมาก่อนหรือไม่

ย้ำว่า AI ไม่ควรแทน Detection Engine หรือ Monitoring Platform แต่ช่วยลดเวลารวบรวมและเชื่อมโยงข้อมูล

ประโยคเชื่อม:
เมื่อ Agent มองเห็นสัญญาณได้ต่อเนื่อง รูปแบบการทำงานของ IT สามารถขยับจาก Reactive ไปสู่ Proactive ได้""",

    """สไลด์ 20 — Proactive IT Operations (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
AI สามารถเริ่ม Investigate จาก Anomaly ก่อนที่ผู้ใช้จะเปิด Ticket แล้วเตรียม Context สำหรับทีม Operations

แนวทางพูด:
อธิบาย Flow: Detect → Investigate → Understand → Respond → Approve

ตัวอย่างผลลัพธ์คือสร้าง K2 Incident อัตโนมัติ แนบ Evidence แนะนำ Runbook และแจ้งทีมที่เกี่ยวข้อง จากนั้น Human หรือ Approved Automation เป็นผู้ดำเนิน Remediation

ชี้ว่าความอัตโนมัติควรเพิ่มตามระดับความมั่นใจและความเสี่ยง เริ่มจาก Read-only และ Recommendation ก่อน Write Action

ประโยคเชื่อม:
Foundation เดียวกันไม่ได้จำกัดอยู่เฉพาะ HR และ IT แต่รองรับ Use Case ระดับองค์กรอีกหลายกลุ่ม""",

    """สไลด์ 21 — Multiple Enterprise AI Opportunities (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
Platform เดียวรองรับ Agent หลายบทบาทโดยใช้ Knowledge, Models, Integration และ Governance ร่วมกัน

แนวทางพูด:
แบ่งโอกาสเป็นสี่กลุ่ม: Employee, IT & Security, Risk & Compliance และ Business

อย่านำเสนอว่าจะทำทุก Use Case พร้อมกัน จุดประสงค์ของสไลด์คือแสดงว่า Foundation ที่ลงทุนใน Pilot สามารถนำกลับมาใช้ซ้ำได้

เลือก Use Case ด้วยเกณฑ์: มี Owner, มีข้อมูลที่เข้าถึงได้, Pain Point ชัด, ความเสี่ยงควบคุมได้ และมี KPI วัดผล

ประโยคเชื่อม:
สำหรับธุรกิจหลักทรัพย์ ตัวอย่างที่เห็นคุณค่าชัดคือการเตรียมหลักฐานสำหรับ KYC/CDD Review""",

    """สไลด์ 22 — AI-Assisted KYC/CDD Review (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
AI ช่วยรวบรวมและจัดโครงสร้าง Evidence แต่ไม่เป็นผู้ตัดสินใจด้าน Compliance

แนวทางพูด:
Input ได้แก่ Customer Profile, KYC Documents, UBO, Risk Classification, Transaction Alerts และ Previous Review

Agent สร้าง Review Pack ที่มี Identity Summary, UBO Structure, Missing Documents, Risk Indicators, Inconsistencies และ Supporting Evidence

ผลลัพธ์ทั้งหมดต้องมี Citation และสถานะความมั่นใจ ประเด็นที่ไม่พบข้อมูลต้องระบุว่า Gap ไม่ควรเติมข้อมูลจากการคาดเดา

ท้ายที่สุด Human Compliance Officer เป็นผู้ตรวจสอบและตัดสินใจตาม Policy และ Regulation

ประโยคเชื่อม:
นอกจากทบทวนลูกค้า AI ยังช่วยวิเคราะห์ผลกระทบจากกฎใหม่ต่อ Policy และ Process ภายในได้""",

    """สไลด์ 23 — Regulatory Knowledge (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
AI ลดเวลาการเปรียบเทียบ Regulation กับ Policy, Procedure, SOP และ Control โดยแสดง Gap พร้อม Citation

แนวทางพูด:
เริ่มจาก Regulatory Change จากนั้น Agent แยก Requirement และค้นเอกสารภายในที่เกี่ยวข้อง

Gap/Impact View ควรแสดง Requirement, Existing Policy, Potential Gap, Affected Process และ Evidence

อธิบายว่า AI ช่วยเตรียม Analysis แต่ Compliance ยังต้องตีความและอนุมัติการแก้ไข การไม่มีหลักฐานต้องแสดงเป็น Not Found ไม่ใช่ Supported

ประโยคเชื่อม:
Use Case ทั้งหมดนี้สามารถวางอยู่บน Target Architecture เดียวกันได้""",

    """สไลด์ 24 — Target Enterprise AI Architecture (ประมาณ 4 นาที)

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
หากเลือกประมวลผล Local ส่วนล่างของ Architecture ต้องถูกออกแบบเป็น Infrastructure Platform ที่พร้อมใช้งานจริง""",

    """สไลด์ 25 — Production Local AI Infrastructure (ประมาณ 3 นาที)

สารที่ต้องการสื่อ:
Local AI สำหรับ Production ต้องมีหลาย Tier และ Operations ครบ ไม่ใช่เพียงติดตั้ง LLM บน GPU หนึ่งเครื่อง

แนวทางพูด:
อธิบาย Stack: Access, Application, Processing, Data และ AI Inference

ด้าน Operations ต้องมี Monitoring, Backup, HA/DR, Security และ Capacity Planning

ย้ำว่า GPU Sizing ไม่ได้คำนวณจากจำนวนพนักงาน แต่จาก Concurrent Generations, Model Size, Context Length, Tokens per Second, RAG และ Tool Workload

Pilot อาจเริ่มจาก Single Node ได้ แต่ต้องระบุข้อจำกัดและแผนยกระดับอย่างชัดเจน

ประโยคเชื่อม:
เพื่อไม่ให้ลงทุนใหญ่เกินไปตั้งแต่แรก เราแนะนำ Roadmap แบบค่อยเป็นค่อยไป""",

    """สไลด์ 26 — Enterprise AI Roadmap (ประมาณ 3 นาที)

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
สำหรับการเริ่มต้นจริง เราไม่จำเป็นต้องทำทุกขั้นพร้อมกัน แต่ควรเลือก Pilot ที่วัดผลได้บน Foundation ที่ขยายต่อได้""",

    """สไลด์ 27 — Recommended Starting Point (ประมาณ 2 นาที)

สารที่ต้องการสื่อ:
เริ่มด้วย Platform Foundation พร้อม HR Pilot และ IT Pilot ที่มีขอบเขตชัด แล้วค่อยขยายสู่ Observability, Security และ Compliance

แนวทางพูด:
Foundation ควรมี Model, RAG, Identity, Security และ Governance ขั้นต่ำก่อนเปิดให้ผู้ใช้

HR Pilot อาจเริ่มจาก Knowledge + PeopleSoft Read และ Leave/Benefit ส่วน IT Pilot เริ่มจาก IT Knowledge + K2 + Guided Troubleshooting

แต่ละ Pilot ต้องมี Business Owner, Data Owner, User Group, Test Cases, Security Acceptance และ KPI

ประโยคเชื่อม:
ความสำเร็จควรวัดจาก Business Outcome และ Operational Quality ไม่ใช่ความประทับใจจาก Demo""",

    """สไลด์ 28 — Measure Business Outcomes (ประมาณ 2 นาที)

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
หากเห็นตรงกัน ขั้นต่อไปคือ Workshop เพื่อกำหนด Use Case, Architecture และ Pilot ที่เหมาะสม""",

    """สไลด์ 29 — Closing (ประมาณ 1 นาที)

สารที่ต้องการสื่อ:
เป้าหมายคือเปลี่ยน Knowledge ให้เป็น Intelligence และ Action อย่างปลอดภัย เป็นส่วนตัว มี Governance และตรวจสอบได้

แนวทางพูด:
สรุปว่าเริ่มจาก HR และ IT ได้ แต่ Foundation ถูกออกแบบเพื่อรองรับ Enterprise-wide AI

เสนอ Next Steps สามขั้น:
1. Use-Case Workshop
2. Technical Assessment
3. Pilot ที่มี Scope และ Success Criteria ชัดเจน

ปิดด้วย Core Message อีกครั้ง:
AI does not replace enterprise systems of record. AI becomes the secure intelligence and orchestration layer across them.""",

    """สไลด์ 30 — Local LLM Model Selection (Backup)

ใช้เมื่อมีคำถามว่าจะเลือกโมเดล Local อย่างไร

แนวทางพูด:
อย่าเลือกจาก Parameter Count อย่างเดียว ต้องประเมิน Capability, Tool Calling, ภาษาไทย/อังกฤษ, Context, VRAM, Quantization, Latency และคุณภาพบนงานจริง

โมเดลเล็กอาจเร็วและคุ้มกว่าสำหรับ Classification หรือ FAQ ขณะที่งาน Reasoning และ Document Analysis อาจต้องโมเดลใหญ่ขึ้น

ข้อเสนอคือสร้าง Benchmark Dataset จาก Prompt, Document, RAG และ Tool Workflow จริง แล้วเปรียบเทียบ Accuracy, Latency, Throughput และ Cost""",

    """สไลด์ 31 — GPU & Capacity Planning (Backup)

ใช้เมื่อมีคำถามเรื่อง Hardware หรือจำนวนผู้ใช้ที่รองรับ

แนวทางพูด:
Capacity ขึ้นกับ Concurrent Generations ไม่ใช่จำนวน Account ปัจจัยหลักคือ Tokens per Second, Context Length, KV Cache, Model Size, RAG และ Tools

ต้องแยก Total Users, Active Users, In-flight Requests และ Simultaneous LLM Generations

แนวทางที่ถูกต้องคือเก็บ Workload Profile จาก Pilot แล้วทำ Load Test วัด p50/p95 Latency, Queue Depth, GPU Utilization, Memory และ Throughput ก่อน Sizing Production""",

    """สไลด์ 32 — Local vs Cloud Decision Matrix (Backup)

ใช้เมื่อมีการเปรียบเทียบ Local กับ Cloud

แนวทางพูด:
Local เหมาะเมื่อ Data Isolation, Network Independence หรือ Workload Economics มีน้ำหนักสูง แต่ต้องรับภาระ Lifecycle และ Capacity

Cloud เหมาะกับ Frontier Capability, Rapid Model Access และ Elastic Burst แต่ต้องตรวจ Data Policy, Connectivity, Quota และ Cost

ข้อสรุปไม่ควรเป็นคำตอบเดียวทั้งองค์กร ควรใช้ Policy Routing ตาม Data Classification และ Agent Workload""",

    """สไลด์ 33 — RAG Security & ACL Flow (Backup)

ใช้ตอบคำถามว่าป้องกัน AI เห็นข้อมูลข้ามทีมอย่างไร

แนวทางพูด:
Identity และ Group Claims ถูกนำไปสร้าง Query Scope จากนั้น Filter Personal, Team และ Global ACL ก่อน Retrieval

Vector Search ต้องคืนเฉพาะ Chunk ที่ผู้ใช้มีสิทธิ์ และเมื่อเปิด Citation ต้องตรวจสิทธิ์ Source Document อีกครั้ง

ห้ามพึ่งการซ่อนข้อมูลหน้า UI เพราะ Authorization ต้องอยู่ฝั่ง Server และครอบคลุมทั้ง Search, Retrieval, Citation และ File Download""",

    """สไลด์ 34 — MCP vs API Integration Architecture (Backup)

ใช้เมื่อมีคำถามว่า Integration ต่างจาก MCP อย่างไร

แนวทางพูด:
MCP ให้ Interface มาตรฐานสำหรับ Agent ค้นพบและเรียก Tools ส่วน REST/Event API เหมาะกับ Contract และ Workflow ที่กำหนดชัด

ทั้งสองควรอยู่ภายใต้ Integration Layer เดียวกัน มี Credential Management, Team Scope, Allowlist, Timeout, Rate Limit, Audit และ Read/Write Policy

ไม่ได้จำเป็นต้องเปลี่ยนทุก API เป็น MCP ให้เลือก Pattern ตามระบบปลายทาง ความพร้อม และ Risk""",

    """สไลด์ 35 — AI Threat Model (Backup)

ใช้เมื่อ Security Team ต้องการมอง Threat และ Control

แนวทางพูด:
Threat หลักคือ Prompt Injection, Data Exfiltration และ Tool Abuse โดยต้องป้องกันทุกช่วงตั้งแต่ Input, Retrieval, Reasoning, Tool จนถึง Output

Control ที่ควรมี ได้แก่ Instruction Boundary, ACL, PII/DLP, Tool Allowlist, Least Privilege, Human Approval และ Metadata Audit

ย้ำว่า Guardrail จาก Model เพียงอย่างเดียวไม่เพียงพอ Policy ที่มีผลต่อสิทธิ์และ Tool ต้องบังคับใช้ฝั่ง Application/Server""",

    """สไลด์ 36 — HA / DR / Backup for Local AI (Backup)

ใช้เมื่อ Infrastructure Team ถามถึง Production Readiness

แนวทางพูด:
HA ต้องครอบคลุม Access, App Replicas, Workers, Queue, Database, Vector DB, Object Storage และ Inference Gateway/GPU Nodes

Backup ต้องเป็น Consistent Set ระหว่าง Metadata, Source Objects และ Vector Index ไม่เช่นนั้น Restore แล้ว Citation หรือ Retrieval อาจไม่สอดคล้องกัน

กำหนด RTO/RPO, Monitoring, Backup Retention, Off-site Copy และทำ Restore Drill ตามรอบ เพราะ Backup ที่ไม่เคย Restore ยังถือว่าไม่ได้พิสูจน์

ปิดท้ายว่า Production AI ต้องพร้อมทั้งด้าน Security, Recoverability และ Operational Ownership""",
]


def thai_notes_markdown():
    lines = [
        "# Enterprise AI Strategy Proposal — Presenter Notes ภาษาไทย",
        "",
        "ผู้ฟัง: Infrastructure Division Head / Senior Vice President, KGI Securities Thailand  ",
        "Main presentation: สไลด์ 1–29 | Backup: สไลด์ 30–36 | ระยะเวลาประมาณ 50–60 นาที",
        "",
        "## Core message",
        "",
        "AI ไม่ได้เข้ามาแทน Enterprise Systems of Record แต่เป็นชั้น Secure Intelligence และ Orchestration ที่ทำงานครอบคลุมระบบเหล่านั้น",
        "",
    ]
    for note in THAI_NOTES:
        title, _, body = note.partition("\n")
        lines.extend([f"## {title}", "", body.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def embed_thai_notes(prs):
    if len(prs.slides) != len(THAI_NOTES):
        raise ValueError(f"Expected {len(THAI_NOTES)} slides, found {len(prs.slides)}")
    for slide, note in zip(prs.slides, THAI_NOTES):
        slide.notes_slide.notes_text_frame.text = note


if __name__ == "__main__":
    path = build_deck()
    presentation = Presentation(path)
    embed_thai_notes(presentation)
    presentation.save(path)
    NOTES.write_text(NOTES_TEXT, encoding="utf-8")
    NOTES_TH.write_text(thai_notes_markdown(), encoding="utf-8")
    print(path)
    print(NOTES)
    print(NOTES_TH)
