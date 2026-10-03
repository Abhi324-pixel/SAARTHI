"""Builds updated.pdf — SAARTHI Complete Product Report v2.0 (revised edition)."""
import os

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String, Circle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "updated.pdf")
FONT_DIR = r"C:\Windows\Fonts"

# ---------------------------------------------------------------- fonts
pdfmetrics.registerFont(TTFont("Body", os.path.join(FONT_DIR, "DejaVuSansCondensed.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", os.path.join(FONT_DIR, "DejaVuSansCondensed-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", os.path.join(FONT_DIR, "DejaVuSansCondensed-Oblique.ttf")))
pdfmetrics.registerFont(TTFont("Body-BoldItalic", os.path.join(FONT_DIR, "DejaVuSansCondensed-BoldOblique.ttf")))
pdfmetrics.registerFont(TTFont("Mono", os.path.join(FONT_DIR, "DejaVuSansMono.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic",
                              boldItalic="Body-BoldItalic")

# ---------------------------------------------------------------- palette
NAVY = colors.HexColor("#16324F")
SAFFRON = colors.HexColor("#E07A1F")
TEAL = colors.HexColor("#1F7A7A")
TEXT = colors.HexColor("#1E2530")
MUTED = colors.HexColor("#5B6675")
LIGHT = colors.HexColor("#F3F6FA")
GRID = colors.HexColor("#C9D3DF")
CALLOUT_BG = colors.HexColor("#FDF3E9")
CLIENT_BG = colors.HexColor("#E3EDF7")
VOICE_BG = colors.HexColor("#FCE9D6")
ENGINE_BG = colors.HexColor("#DDF0EE")
STORE_BG = colors.HexColor("#ECEFF3")
C_MASTERED = colors.HexColor("#2E7D32")
C_DEVELOPING = colors.HexColor("#E0A100")
C_UNKNOWN = colors.HexColor("#C62828")
C_NOTASSESSED = colors.HexColor("#B0BEC5")
C_MISCONCEPTION = colors.HexColor("#7B1FA2")

PAGE_W, PAGE_H = A4
MARGIN_X = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X

# ---------------------------------------------------------------- styles
ST = {
    "body": ParagraphStyle("body", fontName="Body", fontSize=9.6, leading=13.6, textColor=TEXT,
                           spaceAfter=6),
    "bullet": ParagraphStyle("bullet", fontName="Body", fontSize=9.6, leading=13.4, textColor=TEXT,
                             leftIndent=14, bulletIndent=3, spaceAfter=2.5, bulletFontName="Body"),
    "part": ParagraphStyle("part", fontName="Body-Bold", fontSize=19, leading=24, textColor=NAVY,
                           spaceBefore=4, spaceAfter=10, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=13.2, leading=17, textColor=NAVY,
                         spaceBefore=12, spaceAfter=6, keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName="Body-Bold", fontSize=10.4, leading=14, textColor=TEAL,
                         spaceBefore=7, spaceAfter=3, keepWithNext=1),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=8.6, leading=11.3, textColor=TEXT),
    "cellhead": ParagraphStyle("cellhead", fontName="Body-Bold", fontSize=8.6, leading=11.3,
                               textColor=colors.white),
    "callout": ParagraphStyle("callout", fontName="Body", fontSize=9.4, leading=13.2, textColor=TEXT),
    "quote": ParagraphStyle("quote", fontName="Body-Bold", fontSize=11.5, leading=16, textColor=NAVY,
                            alignment=TA_CENTER),
    "caption": ParagraphStyle("caption", fontName="Body-Italic", fontSize=8.2, leading=11,
                              textColor=MUTED, alignment=TA_CENTER, spaceBefore=3, spaceAfter=8),
    "tochead": ParagraphStyle("tochead", fontName="Body-Bold", fontSize=19, leading=24, textColor=NAVY,
                              spaceAfter=10),
}
TOC_L0 = ParagraphStyle("toc0", fontName="Body-Bold", fontSize=10.2, leading=15, textColor=NAVY,
                        spaceBefore=5)
TOC_L1 = ParagraphStyle("toc1", fontName="Body", fontSize=9.2, leading=12.6, textColor=TEXT,
                        leftIndent=14)

TBC = '<font color="#E07A1F"><b>[TO CONFIRM]</b></font>'


# ---------------------------------------------------------------- story helpers
class Builder:
    def __init__(self):
        self.story = []
        self.sec = 0
        self.secnum = {}

    def part(self, title, new_page=True):
        if new_page and self.story:
            self.story.append(PageBreak())
        self.story.append(Paragraph(title, ST["part"]))
        self.rule()

    def rule(self):
        d = Drawing(CONTENT_W, 6)
        d.add(Rect(0, 2, 60, 2.2, fillColor=SAFFRON, strokeColor=None))
        d.add(Rect(60, 2.8, CONTENT_W - 60, 0.6, fillColor=GRID, strokeColor=None))
        self.story.append(d)
        self.story.append(Spacer(1, 4))

    def h2(self, key, title):
        self.sec += 1
        self.secnum[key] = self.sec
        self.story.append(Paragraph(f"{self.sec}. {title}", ST["h2"]))

    def h3(self, title):
        self.story.append(Paragraph(title, ST["h3"]))

    def p(self, text):
        self.story.append(Paragraph(text, ST["body"]))

    def bullets(self, items):
        for it in items:
            self.story.append(Paragraph(it, ST["bullet"], bulletText="•"))
        self.story.append(Spacer(1, 4))

    def numbered(self, items):
        for i, it in enumerate(items, 1):
            self.story.append(Paragraph(it, ST["bullet"], bulletText=f"{i}."))
        self.story.append(Spacer(1, 4))

    def table(self, head, rows, widths):
        self.story.append(make_table(head, rows, widths))
        self.story.append(Spacer(1, 8))

    def callout(self, text):
        self.story.append(make_callout(text))
        self.story.append(Spacer(1, 8))

    def flow(self, f):
        self.story.append(f)

    def ref(self, key):
        return f"§{self.secnum[key]}"


def make_table(head, rows, widths):
    data = [[Paragraph(h, ST["cellhead"]) for h in head]]
    for r in rows:
        data.append([Paragraph(c, ST["cell"]) for c in r])
    t = Table(data, colWidths=[w * CONTENT_W for w in widths], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(style))
    return t


def make_callout(text):
    t = Table([[Paragraph(text, ST["callout"])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CALLOUT_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 3, SAFFRON),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


# ---------------------------------------------------------------- diagrams
def box(d, x, y, w, h, lines, fill, fg=TEXT, size=7.6, bold=False, stroke=GRID, dash=None):
    r = Rect(x, y, w, h, rx=4, ry=4, fillColor=fill, strokeColor=stroke, strokeWidth=0.8)
    if dash:
        r.strokeDashArray = dash
    d.add(r)
    font = "Body-Bold" if bold else "Body"
    lh = size + 2
    top = y + h / 2 + (len(lines) - 1) * lh / 2 - size / 3
    for i, ln in enumerate(lines):
        d.add(String(x + w / 2, top - i * lh, ln, fontName=font, fontSize=size, fillColor=fg,
                     textAnchor="middle"))


def arrow(d, x1, y1, x2, y2, color=MUTED, width=1.0, head=4.5):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width))
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    p1 = (x2 - head * math.cos(ang - 0.45), y2 - head * math.sin(ang - 0.45))
    p2 = (x2 - head * math.cos(ang + 0.45), y2 - head * math.sin(ang + 0.45))
    d.add(Polygon([x2, y2, p1[0], p1[1], p2[0], p2[1]], fillColor=color, strokeColor=color,
                  strokeWidth=0.5))


def core_loop_drawing():
    W, H = CONTENT_W, 100
    d = Drawing(W, H)
    steps = ["Understand", "Diagnose", "Teach", "Listen", "Assess", "Adapt"]
    bw, bh, y = 68, 38, 48
    gap = (W - len(steps) * bw) / (len(steps) - 1)
    xs = [i * (bw + gap) for i in range(len(steps))]
    for i, (x, s) in enumerate(zip(xs, steps)):
        box(d, x, y, bw, bh, [s], NAVY if i % 2 == 0 else TEAL, fg=colors.white, size=9, bold=True,
            stroke=None)
        if i < len(steps) - 1:
            arrow(d, x + bw + 1, y + bh / 2, x + bw + gap - 1, y + bh / 2, color=SAFFRON, width=1.4)
    # repeat path
    ly = 26
    d.add(Line(xs[-1] + bw / 2, y, xs[-1] + bw / 2, ly, strokeColor=SAFFRON, strokeWidth=1.4))
    d.add(Line(xs[-1] + bw / 2, ly, xs[0] + bw / 2, ly, strokeColor=SAFFRON, strokeWidth=1.4))
    arrow(d, xs[0] + bw / 2, ly, xs[0] + bw / 2, y - 1, color=SAFFRON, width=1.4)
    d.add(String(W / 2, 10, "Repeat — every interaction writes evidence to the Learner Twin",
                 fontName="Body-Italic", fontSize=8.4, fillColor=MUTED, textAnchor="middle"))
    return d


def architecture_drawing():
    W, H = CONTENT_W, 300
    d = Drawing(W, H)
    # row 1: clients
    box(d, 0, 262, 240, 32, ["Student app — Web / Mobile PWA", "text · voice · visual panel"], CLIENT_BG,
        fg=NAVY, bold=False, size=7.8)
    box(d, 246, 262, 121, 32, ["Mentor console", "(Chhatrachhaya)"], CLIENT_BG, fg=NAVY, size=7.8)
    box(d, 373, 262, W - 373, 32, ["Institution / teacher", "dashboard"], CLIENT_BG, fg=NAVY, size=7.8)
    # row 2: channels
    box(d, 0, 208, 160, 32, ["ElevenLabs Agent", "speech in/out · turn-taking"], VOICE_BG, fg=TEXT,
        size=7.8)
    box(d, 166, 208, 74, 32, ["Text chat", "channel"], VOICE_BG, size=7.8)
    arrow(d, 80, 262, 80, 241)
    arrow(d, 203, 262, 203, 241)
    # row 3: API
    box(d, 0, 158, W, 30, ["SAARTHI API — orchestration · auth & roles · tool endpoints · policy guardrails"],
        NAVY, fg=colors.white, size=8.6, bold=True, stroke=None)
    arrow(d, 80, 208, 80, 189)
    arrow(d, 203, 208, 203, 189)
    arrow(d, 306, 262, 306, 189)
    arrow(d, 433, 262, 433, 189)
    # row 4: engines
    engines = [["Diagnostic", "Engine"], ["Teaching", "Strategy Engine"], ["Learning", "Engine"],
               ["Assessment", "Engine"], ["Adaptation", "Engine"], ["Mentor", "Service"]]
    ew = (W - 5 * 5) / 6
    for i, e in enumerate(engines):
        x = i * (ew + 5)
        box(d, x, 98, ew, 36, e, ENGINE_BG, fg=TEXT, size=7.6)
        arrow(d, x + ew / 2, 158, x + ew / 2, 135)
        d.add(Line(x + ew / 2, 98, x + ew / 2, 86, strokeColor=MUTED, strokeWidth=1))
    d.add(Line(ew / 2, 86, W - ew / 2, 86, strokeColor=MUTED, strokeWidth=1))
    # row 5: data + LLM
    stores = [["Learner Twin", "Service"], ["Skill Graph", "Service"], ["Evidence Log", "(append-only)"],
              ["Content &", "Misconception Library"], ["LLM Gateway", "(provider-agnostic)"]]
    sw = (W - 4 * 6) / 5
    for i, s in enumerate(stores):
        x = i * (sw + 6)
        box(d, x, 36, sw, 36, s, STORE_BG, fg=TEXT, size=7.6)
        arrow(d, x + sw / 2, 86, x + sw / 2, 73)
    d.add(String(W / 2, 16, "Clients  →  channels  →  API  →  engines  →  shared state & model gateway",
                 fontName="Body-Italic", fontSize=8.2, fillColor=MUTED, textAnchor="middle"))
    return d


def skill_graph_drawing():
    W, H = CONTENT_W, 185
    d = Drawing(W, H)
    bw, bh = 100, 34
    top, bot = 126, 56
    nodes = {
        "py": (0, top, ["Python basics", "Mastered"], C_MASTERED, colors.white, None),
        "sel": (130, top, ["SQL SELECT & WHERE", "Mastered"], C_MASTERED, colors.white, None),
        "join": (260, top, ["SQL JOINs", "Developing"], C_DEVELOPING, TEXT, None),
        "grp": (W - bw, top, ["GROUP BY & aggregates", "Not assessed"], C_NOTASSESSED, TEXT, None),
        "http": (0, bot, ["HTTP fundamentals", "Unknown · inserted"], C_UNKNOWN, colors.white, None),
        "rest": (131, bot, ["REST APIs", "Blocked by prerequisite"], colors.white, TEXT, [3, 2]),
        "fast": (262, bot, ["FastAPI", "Blocked by prerequisite"], colors.white, TEXT, [3, 2]),
        "dock": (W - bw, bot, ["Docker", "Not assessed"], C_NOTASSESSED, TEXT, None),
    }
    for k, (x, y, lines, fill, fg, dash) in nodes.items():
        box(d, x, y, bw, bh, lines, fill, fg=fg, size=7.6, stroke=MUTED if dash else None, dash=dash)

    def edge(a, b, side="h"):
        ax, ay = nodes[a][0], nodes[a][1]
        bx, by = nodes[b][0], nodes[b][1]
        if side == "h":
            arrow(d, ax + bw + 1, ay + bh / 2, bx - 1, by + bh / 2)
        else:
            arrow(d, ax + bw / 2, ay - 1, bx + bw / 2 + (8 if a == "join" else -18), by + bh + 1)

    edge("sel", "join")
    edge("join", "grp")
    edge("http", "rest")
    edge("rest", "fast")
    edge("fast", "dock")
    edge("py", "fast", side="v")
    edge("join", "fast", side="v")
    # misconception badge on JOINs
    jx, jy = nodes["join"][0], nodes["join"][1]
    d.add(Circle(jx + bw - 2, jy + bh - 2, 6.5, fillColor=C_MISCONCEPTION, strokeColor=colors.white,
                 strokeWidth=1))
    d.add(String(jx + bw - 2, jy + bh - 5, "!", fontName="Body-Bold", fontSize=8.5,
                 fillColor=colors.white, textAnchor="middle"))
    # legend
    items = [("Mastered", C_MASTERED, None), ("Developing", C_DEVELOPING, None),
             ("Unknown", C_UNKNOWN, None), ("Not assessed", C_NOTASSESSED, None),
             ("Blocked (flag)", colors.white, [3, 2]), ("Misconception (flag)", C_MISCONCEPTION, "dot")]
    x = 0
    for label, col, kind in items:
        if kind == "dot":
            d.add(Circle(x + 5, 20, 5, fillColor=col, strokeColor=None))
        else:
            r = Rect(x, 15, 10, 10, fillColor=col, strokeColor=MUTED, strokeWidth=0.6)
            if kind:
                r.strokeDashArray = kind
            d.add(r)
        d.add(String(x + 14, 17, label, fontName="Body", fontSize=7.8, fillColor=TEXT))
        x += 14 + pdfmetrics.stringWidth(label, "Body", 7.8) + 16
    return d


# ---------------------------------------------------------------- document template
class ReportDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                         topMargin=22 * mm, bottomMargin=20 * mm, **kw)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="cover", frames=[frame], onPage=draw_cover),
                               PageTemplate(id="body", frames=[frame])])
        self._heading_seq = 0

    def beforeDocument(self):
        # multiBuild runs several passes; keys must be identical on each pass for the TOC to settle
        self._heading_seq = 0

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        name = flowable.style.name
        if name not in ("part", "h2"):
            return
        level = 0 if name == "part" else 1
        text = flowable.getPlainText()
        self._heading_seq += 1
        key = f"h{self._heading_seq}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=False)
        self.notify("TOCEntry", (level, text, self.page, key))


class NumberedCanvas(rl_canvas.Canvas):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self._decorate(total)
            super().showPage()
        super().save()

    def _decorate(self, total):
        self.saveState()
        self.setFillColor(NAVY)
        self.rect(0, PAGE_H - 9 * mm, PAGE_W, 9 * mm, fill=1, stroke=0)
        self.setFillColor(SAFFRON)
        self.rect(0, PAGE_H - 9.8 * mm, PAGE_W, 0.8 * mm, fill=1, stroke=0)
        self.setFillColor(colors.white)
        self.setFont("Body-Bold", 8.5)
        self.drawString(MARGIN_X, PAGE_H - 6 * mm, "SAARTHI")
        self.setFont("Body", 8.5)
        self.drawString(MARGIN_X + 44, PAGE_H - 6 * mm, "Adaptive AI Mentor & Learner Intelligence Platform")
        self.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 6 * mm, "Product Report · v2.0")
        self.setStrokeColor(GRID)
        self.setLineWidth(0.5)
        self.line(MARGIN_X, 13 * mm, PAGE_W - MARGIN_X, 13 * mm)
        self.setFillColor(MUTED)
        self.setFont("Body", 8)
        self.drawString(MARGIN_X, 9 * mm, "SAARTHI — Complete Product Report · Revised edition · 29 September 2026")
        self.drawRightString(PAGE_W - MARGIN_X, 9 * mm, f"Page {self._pageNumber} of {total}")
        self.restoreState()


def draw_cover(c, doc):
    c.saveState()
    band_h = 355
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - band_h, PAGE_W, band_h, fill=1, stroke=0)
    c.setFillColor(SAFFRON)
    c.rect(0, PAGE_H - band_h - 5, PAGE_W, 5, fill=1, stroke=0)
    x = MARGIN_X + 6
    c.setFillColor(SAFFRON)
    c.setFont("Body-Bold", 10)
    c.drawString(x, PAGE_H - 70, "COMPLETE PRODUCT CONCEPT & TECHNICAL REPORT  ·  VERSION 2.0")
    c.setFillColor(colors.white)
    c.setFont("Body-Bold", 50)
    c.drawString(x, PAGE_H - 140, "SAARTHI")
    c.setFont("Body", 17)
    c.drawString(x, PAGE_H - 172, "Adaptive AI Mentor & Learner Intelligence Platform")
    c.setFillColor(colors.HexColor("#F6C08A"))
    c.setFont("Body-Italic", 14)
    c.drawString(x, PAGE_H - 205, "“An AI mentor that learns how to teach you.”")
    c.setFillColor(colors.HexColor("#C9D6E6"))
    c.setFont("Body", 10)
    c.drawString(x, PAGE_H - 250, "Core loop:  Understand → Diagnose → Teach → Listen → Assess → Adapt → Repeat")
    c.drawString(x, PAGE_H - 300, "Revised edition · 29 September 2026 · supersedes v1.0 (21 September 2026)")
    c.drawString(x, PAGE_H - 316, "Prepared by the SAARTHI Product Team")

    rows = [
        ("Product category", "Adaptive learning + career intelligence + AI mentorship"),
        ("Core differentiator", "Learner Twin + conversational diagnosis + adaptive teaching"),
        ("First release focus", "SQL and prerequisites for aspiring Backend Developers; voice and text"),
        ("Voice technology", "ElevenLabs conversational voice layer (text parity guaranteed)"),
        ("Human layer", "Chhatrachhaya — SAARTHI’s human mentor network for escalated cases"),
        ("Primary audience", "Students and self-learners, mentors, educational institutions"),
        ("Document status", "Revised draft for review — items marked [TO CONFIRM] need team input"),
    ]
    data = [[Paragraph(f"<b>{k}</b>", ST["cell"]), Paragraph(v, ST["cell"])] for k, v in rows]
    t = Table(data, colWidths=[0.28 * CONTENT_W, 0.72 * CONTENT_W])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    _, th = t.wrapOn(c, CONTENT_W, 400)
    t.drawOn(c, MARGIN_X, PAGE_H - band_h - 40 - th)
    c.setFillColor(MUTED)
    c.setFont("Body-Italic", 9)
    c.drawString(MARGIN_X, 60, "Prepared as a product, innovation and implementation blueprint.")
    c.restoreState()


# ================================================================= CONTENT
def build_body(b):
    # ---------------------------------------------------------- PART A
    b.part("Part A — Product", new_page=False)

    b.h2("exec", "Executive Summary")
    b.p("SAARTHI is an adaptive AI learning and career-mentorship platform designed to move beyond "
        "conventional AI tutors. Rather than only answering questions, summarising documents or recommending "
        "courses, SAARTHI builds a continuously evolving <b>Learner Twin</b>: a structured, evidence-backed model "
        "of what a student knows, what they misunderstand, which teaching strategies work for them, and what "
        "they want to achieve.")
    b.p("Conversation — typed or spoken through an ElevenLabs-powered voice layer — is used as an "
        "<b>assessment instrument</b>, not just an interface. SAARTHI probes understanding with follow-up "
        "questions, separates knowledge gaps from misconceptions, asks the learner to teach concepts back, and "
        "regenerates the learner’s roadmap from the resulting evidence. When AI interventions are not enough, "
        "it escalates to a human mentor in the <b>Chhatrachhaya</b> network with a structured case report of the "
        "problem and everything already tried.")
    b.flow(core_loop_drawing())
    b.flow(Paragraph("Figure 1 — The SAARTHI core loop", ST["caption"]))
    b.table(["Loop step", "What happens", "Output"], [
        ["Understand", "Capture goal, context, time budget and the learner’s own claims", "Goal and initial Learner Twin"],
        ["Diagnose", "Short adaptive probe with follow-up questions", "Evidence events; candidate gaps and misconceptions"],
        ["Teach", "Select a strategy and deliver an explanation, example or practice task", "Intervention record"],
        ["Listen", "Learner explains the concept back in their own words (voice or text)", "Transcript for rubric scoring"],
        ["Assess", "Rubric-based scoring with a confidence estimate", "Updated mastery probability and flags"],
        ["Adapt", "Update roadmap, schedule reviews, escalate if triggered", "Next action with a “Why this?” reason"],
    ], [0.16, 0.52, 0.32])
    b.callout("<b>First release in one line:</b> one domain (SQL and its prerequisites), one target role "
              "(Backend Developer), voice and text, and a generated human-mentor handoff report — everything "
              "else is staged in the MVP scope and roadmap sections.")

    b.h2("vision", "Vision, Mission & Design Principles")
    b.p("<b>Vision:</b> every learner should have a learning journey that continuously adapts to what they know, "
        "what they misunderstand, how they learn and where they want to go.")
    b.p("<b>Mission:</b> build an AI mentor that does not merely deliver content, but continuously models the "
        "learner and makes the next learning decision — transparently and with the learner in control.")
    b.h3("Design principles")
    b.bullets([
        "<b>Evidence over assumption</b> — every change to the learner model is traceable to recorded evidence.",
        "<b>Explainable adaptation</b> — every roadmap change carries a plain-language “Why this?” reason.",
        "<b>Learner in control</b> — learners can view, dispute and correct what SAARTHI believes about them.",
        "<b>Human in the loop</b> — persistent or high-impact problems go to people, not only to the model.",
        "<b>Voice with a purpose</b> — voice is used where it produces learning evidence, with full text parity.",
        "<b>Measure learning, not just engagement</b> — adaptive features must prove they improve outcomes.",
    ])

    b.h2("problem", "Problem Statement")
    b.p("Most digital learning follows a largely fixed sequence: course → content → quiz → score → next topic. "
        "A score does not explain <i>why</i> a learner is struggling, so the system’s response is usually the same "
        "regardless of the cause.")
    b.table(["Student situation", "Typical system response", "SAARTHI response"], [
        ["Does not know the concept", "Recommend revision", "Identify the missing concept and teach it"],
        ["Missing prerequisite", "Continue or repeat the topic", "Insert prerequisite remediation"],
        ["Has a misconception", "Mark the answer wrong", "Identify the misconception and correct it"],
        ["Knows the concept but cannot apply it", "Show the solution", "Application practice and explain-back"],
        ["Teaching style is not working", "Repeat the same content", "Try a different teaching strategy"],
    ], [0.3, 0.3, 0.4])
    b.p("Mature adaptive systems such as ALEKS already remediate prerequisites over structured item banks, and "
        "general AI assistants now converse well — but they typically forget the learner between sessions and "
        "do not turn open-ended explanations into a persistent model. The gap SAARTHI targets is "
        "<b>conversation-driven diagnosis that persists into a learner model and drives the roadmap</b>, in the "
        "languages many Indian learners actually use: English, Hindi and Hinglish.")

    b.h2("twin", "Product Concept — the Learner Twin")
    b.p("SAARTHI is built around one central concept: the Learner Twin. Instead of storing only profile "
        "information and scores, SAARTHI maintains an evolving, evidence-linked representation of the learner.")
    b.table(["Dimension", "What SAARTHI models"], [
        ["Knowledge", "Mastery level and probability for every concept on the goal path (unified model, see "
                      "Skill-State Model section)"],
        ["Misconceptions", "Active and resolved misconception instances, each with the evidence that raised it"],
        ["Strategy effectiveness", "Which teaching strategies produced measurable gains, per concept cluster — "
                                   "not a fixed “learning style”"],
        ["Pace and memory", "Time-to-mastery and forgetting estimates, used to schedule reviews"],
        ["Goals", "Target role, target date and weekly time budget"],
        ["History", "Append-only evidence log: assessments, interventions, mentor feedback"],
        ["Learner corrections", "Estimates the learner has disputed, and how each dispute was resolved"],
    ], [0.25, 0.75])
    b.callout("<b>Naming:</b> the <b>Learner Twin</b> is the internal structured model. The <b>Learning Genome</b> "
              "is the student-facing, plain-language view of the Twin. “Learner model” is used only as the generic "
              "research term. All three names in v1 now have one defined meaning (see Glossary).")

    b.h2("innovation", "Core Innovation & Positioning Against Prior Art")
    b.bullets([
        "<b>Innovation 1 — Learner Twin:</b> a continuously updated, evidence-linked model of the learner.",
        "<b>Innovation 2 — Conversational Diagnosis:</b> dialogue and follow-up questions gather evidence about "
        "understanding instead of relying only on fixed tests.",
        "<b>Innovation 3 — Adaptive Teaching:</b> SAARTHI learns which strategies work for an individual and "
        "adjusts future instruction.",
        "<b>Innovation 4 — Dynamic Skill Graph:</b> learning is a dependency graph, enabling prerequisite-aware "
        "roadmap changes.",
        "<b>Innovation 5 — AI-to-Human Escalation:</b> persistent problems are packaged with context for a mentor.",
    ])
    b.h3("What makes the combination innovative")
    b.bullets([
        "The core asset is the learner model, not a content library (curated content is still required — "
        "see the Skill Graph section).",
        "Conversation becomes an assessment instrument rather than just a user interface.",
        "The system distinguishes knowledge gaps from misconceptions.",
        "Teaching strategies are selected and adapted based on learner evidence.",
        "The roadmap is a dynamic output of the learner model.",
        "Human mentorship is an escalation layer rather than a separate, disconnected feature.",
        "Voice has a functional role in the learning loop rather than a decorative one.",
    ])
    b.callout("<b>Honest positioning:</b> learner modelling, knowledge tracing and prerequisite graphs are "
              "established in intelligent-tutoring research and products such as ALEKS; Socratic LLM tutoring "
              "exists in Khanmigo, ChatGPT Study Mode and Gemini Guided Learning. SAARTHI’s claim is the "
              "<b>integration</b>: open-ended spoken or written explanations → structured evidence → persistent "
              "learner model → roadmap and human escalation.")

    b.h2("states", "Unified Skill-State Model")
    b.p("Each learner × concept pair has exactly <b>one mastery level</b> plus <b>zero or more independent "
        "flags</b>. This replaces the three different vocabularies used in v1. The level is derived from "
        "<i>P(known)</i>, the model’s estimated probability that the learner knows the concept (see AI "
        "Architecture section).")
    b.table(["Mastery level", "Definition", "Typical action"], [
        ["Not assessed", "No evidence yet", "Include in the placement probe if on the goal path"],
        ["Unknown", "P(known) below 0.40, with at least one piece of evidence", "Teach the concept (prerequisites first)"],
        ["Developing", "P(known) 0.40 – 0.80", "Practise and reinforce"],
        ["Proficient", "P(known) 0.80 – 0.95", "Application practice and explain-back"],
        ["Mastered", "P(known) ≥ 0.95 with evidence from at least two item types, including one application "
                     "task or explain-back", "Compress to a single check; schedule spaced review"],
    ], [0.18, 0.47, 0.35])
    b.table(["Flag", "Meaning", "Action"], [
        ["Misconception", "An incorrect mental model detected and confirmed (see Misconception Detection)",
         "Targeted correction cycle"],
        ["Blocked by prerequisite", "A prerequisite concept is below Proficient", "Insert the prerequisite into the roadmap"],
        ["Due for review", "Predicted recall has decayed below target", "Schedule a spaced-review item"],
        ["Disputed", "The learner has contested the current estimate", "Offer a quick re-check; never hide the dispute"],
        ["Low confidence", "Too little or conflicting evidence", "Ask one more probe before acting"],
    ], [0.22, 0.46, 0.32])
    b.p("Thresholds are initial defaults to be calibrated on pilot data. Mapping from v1 terms: "
        "<i>Understood</i> → Proficient/Mastered; <i>Weak</i> and <i>Knowledge gap</i> → Unknown; "
        "<i>Missing prerequisite</i> → Blocked flag on the dependent concept; <i>Misconception</i> → a flag, "
        "because a concept can be Developing <i>and</i> carry a misconception at the same time.")
    b.callout("<b>Example state:</b> SQL JOINs — <b>Developing</b> (P = 0.55) · flag <b>Misconception</b>: "
              "“LEFT JOIN returns only matching rows” · not blocked · last evidence: explain-back, today.")

    b.h2("diagnosis", "Conversational Skill Diagnosis")
    b.p("Instead of asking only “What is the answer?”, SAARTHI asks the learner to explain a concept and uses "
        "follow-up questions to test depth. Example: a learner explains binary search; SAARTHI then asks why the "
        "data must be sorted, what happens when the target is larger than the midpoint, and how many steps are "
        "needed for 1,024 items. The responses are combined into a sub-skill assessment:")
    b.table(["Sub-skill", "Level", "Evidence"], [
        ["Core concept (halving a sorted search space)", "Proficient",
         "Correct explanation; correctly said why sorting is required"],
        ["Algorithm mechanics (midpoint, bound updates)", "Proficient", "Correctly traced the target > midpoint case"],
        ["Complexity reasoning (O(log n))", "Developing · Blocked",
         "Said “it is faster” but could not estimate the number of halvings for n = 1,024"],
        ["Prerequisite: logarithms", "Developing", "Could not answer “2 to the power of what is 1,024?”"],
        ["Practical application", "Unknown", "Did not recognise binary search in a “first bad version” problem"],
    ], [0.36, 0.2, 0.44])
    b.p("<b>Detected gaps, in the order they will be addressed:</b>")
    b.numbered([
        "Prerequisite gap — logarithms: a five-minute refresher is inserted first, because it blocks complexity reasoning.",
        "Complexity reasoning: a “count the halvings” exercise, then explain-back.",
        "Practical application (weakest sub-skill): two problem-recognition tasks in the practice sandbox.",
    ])
    b.h3("Diagnosis design rules")
    b.bullets([
        "Probes are short — typically 3 to 5 turns per concept — and stop early once confidence is reached.",
        "Self-reports such as “I understand SQL joins” are treated as a prior, never as evidence of mastery.",
        "Every conclusion is stored as an evidence event, so the learner can see why SAARTHI believes it.",
    ])

    b.h2("misconception", "Misconception Detection")
    b.p("A major product distinction is separating “does not know” from “knows incorrectly”. For example, if a "
        "learner describes LEFT JOIN as returning only matching records, SAARTHI flags a likely confusion with "
        "INNER JOIN and starts a correction cycle:")
    b.numbered([
        "<b>Detect</b> — the learner’s statement matches a known misconception pattern above a confidence threshold.",
        "<b>Confirm</b> — one discriminating question (and, in voice, a read-back of what was heard) rules out "
        "a slip of the tongue or a transcription error before the flag is raised.",
        "<b>Counter-example</b> — show a query where LEFT JOIN keeps unmatched rows with NULLs.",
        "<b>Re-explain</b> — the learner explains again in their own words.",
        "<b>Verify later</b> — a delayed check in a later session is required before the flag is marked resolved.",
    ])
    b.h3("Misconception library")
    b.p("Each domain has a curated library. Every entry holds an identifier, description, example learner "
        "statements, a discriminating question, a counter-example and a remediation sequence. The first release "
        "covers 10–15 common SQL misconceptions, for example: LEFT versus INNER JOIN; WHERE versus HAVING; "
        "comparing with <font name='Mono'>= NULL</font> instead of <font name='Mono'>IS NULL</font>; "
        "<font name='Mono'>COUNT(*)</font> versus <font name='Mono'>COUNT(column)</font>; selecting "
        "non-aggregated columns with GROUP BY. New misconceptions proposed by the LLM enter as "
        "<i>candidates</i> and are reviewed by a domain expert before they join the library.")

    b.h2("graph", "Dynamic Skill Graph")
    b.p("SAARTHI represents skills as interconnected concepts rather than a fixed weekly syllabus. Node colours "
        "show mastery levels; flags are drawn on top. This graph powers the adaptive roadmap.")
    b.flow(skill_graph_drawing())
    b.flow(Paragraph("Figure 2 — Part of a Backend Developer skill graph after diagnosis", ST["caption"]))
    b.h3("Where the graph comes from")
    b.bullets([
        "Graphs are curated per domain by domain experts. LLM-assisted drafting is allowed, but every node and "
        "edge is reviewed before release, and each graph is versioned.",
        "Each concept node holds a description, prerequisites, an item bank across item types (multiple choice, "
        "short answer, SQL/code task, explain-back rubric), known misconceptions and an estimated study time.",
        "First release: roughly 30–40 concepts covering Python basics, SQL and HTTP fundamentals for the "
        "Backend Developer path.",
        "Mentors and learners can report a wrong edge or item; reports feed an expert review queue.",
    ])

    b.h2("roadmap", "Adaptive Roadmap")
    b.p("The roadmap is generated and regenerated from the learner state. It is not a static course schedule.")
    b.table(["Initial roadmap", "After diagnosis"], [
        ["Python → SQL → REST APIs → FastAPI → Docker", "Python → SQL → HTTP Fundamentals → REST APIs → FastAPI → Docker"],
        ["Static sequence", "Prerequisite-aware sequence"],
        ["Same path for everyone", "Path changes with learner evidence"],
    ], [0.45, 0.55])
    b.h3("Roadmap rules")
    b.bullets([
        "<b>Ordering:</b> a prerequisite-first ordering of the goal’s sub-graph, weighted by gaps and the "
        "learner’s weekly time budget.",
        "<b>Compress, don’t skip:</b> Mastered concepts are reduced to a single check and a scheduled review, "
        "so a false “mastered” estimate is caught.",
        "<b>“Why this?”</b> on every item, e.g. “HTTP Fundamentals was added because two of your answers about "
        "request methods and status codes suggest REST APIs will be hard without it.”",
        "<b>Learner choice:</b> a learner can decline an insertion and take a quick test instead.",
        "<b>Stability:</b> the roadmap changes only when evidence crosses a threshold — at most one major "
        "re-order per session unless the learner asks. Every change is saved as a versioned roadmap with its reason.",
    ])

    b.h2("strategy", "Adaptive Teaching Strategy Engine")
    b.p("SAARTHI can try different ways of teaching a concept. If an analogy does not improve understanding, it "
        "may try a visual explanation, code tracing, a worked example or practice-first.")
    b.table(["Strategy", "Best suited for", "Delivered as"], [
        ["Analogy", "New abstract concepts", "Voice or text"],
        ["Worked example", "Procedures and multi-step methods", "Visual panel with narration"],
        ["Visual explanation", "Structures and flows (e.g. row-level JOIN diagrams)", "Visual panel"],
        ["Code tracing", "Program and query behaviour", "Step-through in the visual panel"],
        ["Practice-first", "Learners with partial knowledge", "Sandbox task, then debrief"],
        ["Contrasting cases", "Misconceptions", "Side-by-side examples (e.g. LEFT vs INNER JOIN output)"],
    ], [0.22, 0.43, 0.35])
    b.h3("How strategies are chosen and credited")
    b.bullets([
        "<b>First release:</b> rule-based choice (e.g. misconception → contrasting cases; application gap → practice-first).",
        "<b>Pilot onwards:</b> a contextual multi-armed bandit (Thompson sampling). Context = concept cluster, "
        "current level and flags; population data provides priors for new learners (cold start).",
        "<b>Fair credit:</b> the reward is the mastery gain on a <i>later</i> item (next session), not the "
        "immediate reply — otherwise whichever strategy happens to be tried second gets undeserved credit.",
        "<b>Bounded exploration:</b> experimentation is capped and is never used on concepts close to a "
        "learner’s deadline.",
        "<b>No “learning styles” labels:</b> research does not support matching instruction to self-reported "
        "learning styles, so effectiveness is recorded per concept cluster and re-evaluated — learners are never "
        "labelled “visual learners”.",
    ])

    b.h2("explainback", "Explain-Back Assessment")
    b.p("A signature interaction: <b>“Don’t answer me. Teach it back to me.”</b> The learner explains the concept "
        "in their own words, by voice or text. This produces a richer signal than a multiple-choice score and "
        "fits naturally into the conversational interface.")
    b.table(["Rubric dimension", "What is checked"], [
        ["Coverage", "Key ideas from the concept’s checklist are present"],
        ["Reasoning", "The explanation of why/how is correct"],
        ["Application", "The learner can give or work through an example"],
        ["Misconceptions", "No statement matches a known misconception"],
        ["Not scored", "Fluency, accent, grammar and choice of language (English, Hindi or Hinglish)"],
    ], [0.25, 0.75])
    b.h3("Scoring pipeline and quality control")
    b.bullets([
        "Transcript → rubric scoring by the LLM against the concept’s rubric and reference explanation → "
        "confidence estimate from agreement between two independent scoring passes.",
        "Low-confidence results trigger a follow-up question instead of a grade.",
        "Every score is stored as an evidence event together with the model and prompt version.",
        "Calibration against human graders on a sample (target agreement: Cohen’s κ ≥ 0.70), repeated whenever "
        "a model or prompt changes. Learners can dispute any score.",
        "Integrity: each explain-back is followed by a live question that cannot be pre-scripted, so reading out "
        "a prepared answer earns little credit.",
    ])

    b.h2("voice", "Voice Layer — ElevenLabs Integration")
    b.p("ElevenLabs is positioned as the conversational voice layer, not the core intelligence. Its value is "
        "in turning speech into a source of learning evidence.")
    b.h3("Key voice interactions")
    b.bullets([
        "Voice-based doubt solving", "Conversational teaching", "Follow-up questioning",
        "Explain-back assessment", "Voice quizzes", "Instant spoken feedback",
        "Hindi, English and Hinglish interaction", "Context-aware conversations",
    ])
    b.h3("Integration design")
    b.p("<b>Recommended:</b> the ElevenLabs agent handles speech-to-text, text-to-speech, turn-taking and "
        "interruptions. The SAARTHI API owns all learning logic and exposes a small set of server tools the "
        "agent calls (see API section). Learner state never lives in the voice layer. Reasoning is routed "
        "through SAARTHI’s own LLM gateway so that voice and text sessions behave identically. A technical "
        "spike must confirm the current ElevenLabs agent capabilities, Hindi/Hinglish quality and pricing "
        "before this is committed.")
    b.table(["Layer", "Responsibility"], [
        ["Student", "Speaks or types naturally and explains concepts"],
        ["ElevenLabs Agent", "Speech in/out, turn-taking, interruptions"],
        ["SAARTHI API", "Routes requests, authorises tool calls, provides learner context"],
        ["Learner Twin Service", "Maintains current learning state"],
        ["Skill Graph Service", "Concept dependencies and per-learner states"],
        ["Diagnostic Engine", "Interprets gaps and misconceptions"],
        ["Teaching Strategy Engine", "Selects or experiments with teaching methods"],
        ["Learning Engine", "Generates grounded explanations, examples and practice"],
        ["Assessment Engine", "Scores evidence of understanding"],
        ["Adaptation Engine", "Updates skill state, roadmap and review schedule; checks escalation"],
        ["Mentor Service", "Creates and tracks human-mentor cases"],
    ], [0.3, 0.7])
    b.h3("Speech-recognition safeguards")
    b.bullets([
        "Vocabulary hints for technical terms (SQL keywords, “O(log n)”) where the platform supports them.",
        "Read-back before any misconception flag: “You said LEFT JOIN returns only matching rows — is that right?”",
        "Transcript confidence is stored; low-confidence segments are never the sole evidence for a change.",
        "A Hinglish technical-speech test set is built to measure recognition errors before launch.",
    ])
    b.h3("Text parity, fallback and cost")
    b.bullets([
        "Every voice interaction has a text equivalent, and learners can switch at any time. Text is essential "
        "for deaf, hard-of-hearing and speech-impaired learners and for noisy, shared or low-bandwidth settings.",
        "If the voice service is unavailable, the session continues in text automatically.",
        "Voice is used where it adds evidence (diagnosis, explain-back, voice quizzes); plans carry minute caps.",
    ])

    b.h2("practice", "Practice, Retention & Learning Content")
    b.bullets([
        "<b>In-browser practice sandbox:</b> SQL runs in an in-browser engine (SQLite compiled to WebAssembly) "
        "with seeded datasets; Python runs in Pyodide. Tasks are auto-graded by comparing results with reference "
        "output. Code runs on the learner’s device, so there is no server-side code-execution risk.",
        "<b>Visual panel:</b> synchronised with voice — diagrams, row-level JOIN visualisations and code "
        "step-through, so “visual explanation” and “code tracing” work during voice sessions.",
        "<b>Spaced review:</b> each Proficient or Mastered concept has a next-review date from its forgetting "
        "estimate. Short mixed reviews appear in Today’s Mission; a failed review lowers mastery and may re-open "
        "the concept.",
        "<b>Grounded content:</b> LLM explanations are grounded in the concept’s curated reference notes. "
        "Factual and career claims show a source or are labelled “AI-generated guidance”. Learners can report "
        "errors, which feed the review queue.",
        "<b>Learner documents (Phase 3):</b> learners and institutions can upload a syllabus or notes. These "
        "align the skill graph and act as reference material — treated as one evidence source, not as ground truth.",
    ])

    b.h2("career", "Career Intelligence")
    b.p("SAARTHI connects learning to career outcomes. A learner defines a target role and receives a "
        "role-to-skill map, a current-versus-required skill analysis, a learning roadmap, project "
        "recommendations, portfolio guidance and a job-readiness view.")
    b.table(["Career stage", "SAARTHI function"], [
        ["Goal", "Choose a target role"], ["Requirements", "Map the role to skills"],
        ["Current state", "Assess existing skills"], ["Gap", "Compare current and required skills"],
        ["Learning", "Generate the adaptive roadmap"], ["Evidence", "Recommend projects and portfolio artefacts"],
        ["Outcome", "Track job-readiness progress"],
    ], [0.3, 0.7])
    b.bullets([
        "<b>Data source:</b> role-to-skill templates are curated from job descriptions, reviewed by practitioners "
        "and refreshed quarterly.",
        "<b>First release:</b> one preset role template (Backend Developer); no live job-market data.",
        "<b>Honest readiness:</b> job readiness is shown as “skills evidenced on your roadmap”, never as a "
        "probability of being hired.",
        "High-impact career decisions (changing track, choosing a course) are routed to a human mentor.",
    ])

    b.h2("mentor", "Human Mentor Layer — Chhatrachhaya")
    b.p("<b>Chhatrachhaya</b> (“protective canopy”) is SAARTHI’s human mentor network: vetted senior students, "
        "industry practitioners and teachers who take escalated cases. SAARTHI does not try to replace mentors; "
        "it makes their time count by handing over full context. " + TBC + " final definition and branding.")
    b.table(["Escalation trigger", "Initial rule (to be tuned in pilot)"], [
        ["Persistent struggle", "Same concept still below Developing after at least 3 assessment attempts using at "
                                "least 2 different strategies"],
        ["Unresolved misconception", "Misconception flag survives 2 complete correction cycles"],
        ["Learner request", "The learner asks for a human at any time"],
        ["High-impact decision", "Career or course choice, or a deadline at risk"],
        ["Wellbeing concern", "Learner explicitly expresses distress → safety protocol (Safety section), not an "
                              "ordinary mentor ticket"],
    ], [0.28, 0.72])
    b.h3("What the mentor receives")
    b.p("The learner’s goal, the concept, current state with evidence, detected misconceptions, strategies tried "
        "and their outcomes, short transcript excerpts (only with consent), a suggested intervention and the "
        "learner’s availability — instead of starting from zero.")
    b.h3("Mentor operations")
    b.bullets([
        "<b>Mentor console:</b> case queue, case report, session scheduling (chat or call), outcome and feedback "
        "form, and a button to flag graph or content errors.",
        "<b>Service level:</b> first response within 24 hours during the pilot " + TBC + ".",
        "<b>No mentor available:</b> the AI continues with a different strategy and tells the learner the "
        "expected wait.",
        "<b>Supply and incentives:</b> volunteer senior students and practitioners in the pilot; paid sessions "
        "through a marketplace in Phase 4. All mentors are vetted and trained.",
        "<b>Privacy:</b> mentors see only case data the learner has agreed to share.",
        "<b>Feedback loop:</b> mentor feedback becomes evidence events and can update strategy priors and the "
        "misconception library.",
    ])

    b.h2("genome", "Learning Genome — the Learner’s View")
    b.p("The Learning Genome is the student-facing view of the Learner Twin: what I know, what is tripping me up, "
        "what has worked for me (with evidence counts, not guesses), my pace and my goals. It is an "
        "evidence-based product model, never a personality diagnosis: no labels such as “slow learner” and no "
        "emotion inference.")
    b.h3("“Correct me” controls")
    b.bullets([
        "Dispute an estimate → SAARTHI offers a quick re-check and records the outcome.",
        "“I already know this” → a short placement probe instead of the lesson.",
        "Hide or delete a transcript; reset strategy preferences.",
        "See the evidence behind any level, flag or roadmap change.",
    ])

    b.h2("dashboards", "Dashboards")
    b.h3("Student dashboard")
    b.table(["Component", "Purpose"], [
        ["Overall mastery", "High-level progress on the goal path"],
        ["Skill graph", "See strengths, gaps and flags"],
        ["Active misconception", "See the current conceptual bottleneck"],
        ["Today’s mission", "The next actionable tasks, including due reviews"],
        ["Career goal", "Connect learning to the target role"],
        ["Voice mentor", "Start a voice or text learning / assessment session"],
        ["Roadmap", "The dynamically generated path, with “Why this?” on every item"],
        ["Mentor case", "Status of any open Chhatrachhaya case"],
    ], [0.3, 0.7])
    b.h3("Other audiences")
    b.table(["Dashboard", "Main contents", "Phase"], [
        ["Mentor console", "Case queue, case reports, scheduling, feedback", "Pilot"],
        ["Teacher / institution", "Cohort mastery heat-map, most common misconceptions, learners who may need "
                                  "help — aggregated and privacy-preserving", "Phase 5"],
        ["Parent / guardian (minors)", "Consent management and a progress summary; no transcripts by default", "Pilot"],
    ], [0.25, 0.6, 0.15])

    b.h2("onboarding", "Onboarding & Placement")
    b.numbered([
        "Account creation with an age check; guardian consent flow for learners under 18.",
        "Goal, target date and weekly time budget.",
        "Language (English, Hindi or Hinglish) and mode (voice or text) preferences.",
        "Adaptive placement probe of about 10–15 minutes that stops early once confident.",
        "First roadmap, with a “Why this?” explanation on each item.",
    ])
    b.p("<b>Cold start:</b> until a learner has their own evidence, population-level priors are used for mastery "
        "and teaching-strategy estimates.")

    b.h2("motivation", "Motivation & Engagement")
    b.bullets([
        "Today’s mission sized to the learner’s time budget (for example 20–30 minutes, adjustable).",
        "Streaks with forgiveness (streak freezes), weekly progress recap and opt-in reminders with quiet hours.",
        "Milestone badges tied to <b>verified mastery</b>, not time spent.",
        "Project checkpoints that connect progress to the career goal.",
        "No dark patterns: engagement is never optimised at the expense of learning outcomes.",
    ])

    b.h2("journey", "End-to-End Student Journey")
    b.p("Scenario: a student wants to become a Backend Developer. Each step maps to a step of the core loop.")
    b.table(["#", "Step", "Loop step", "SAARTHI action"], [
        ["1", "Onboard", "Understand", "Goal Backend Developer; consent, language and time budget captured"],
        ["2", "Placement", "Diagnose", "Adaptive probe across Python, SQL and HTTP; stops early"],
        ["3", "Learner Twin", "Understand", "Initial mastery levels with confidence"],
        ["4", "Skill graph", "Adapt", "Goal sub-graph with levels and flags"],
        ["5", "Roadmap", "Adapt", "Prerequisite-aware sequence with “Why this?”"],
        ["6", "Lesson", "Teach", "Strategy selected by the Teaching Strategy Engine"],
        ["7", "Explain-back", "Listen", "Learner teaches the concept back by voice or text"],
        ["8", "Scoring", "Assess", "Rubric score with confidence; misconception check"],
        ["9", "Update", "Adapt", "Mastery, flags, roadmap and review schedule updated"],
        ["10", "Escalate (if triggered)", "Adapt", "Chhatrachhaya case opened with a full report"],
        ["11", "Review", "Repeat", "Spaced reviews in later sessions keep the Twin accurate"],
    ], [0.05, 0.2, 0.15, 0.6])

    # ---------------------------------------------------------- PART B
    b.part("Part B — Technical Design")

    b.h2("arch", "Technical Architecture")
    b.flow(architecture_drawing())
    b.flow(Paragraph("Figure 3 — SAARTHI component architecture", ST["caption"]))
    b.p("This is the single canonical component list; every other section uses the same names.")
    b.table(["Component", "Role"], [
        ["Student app (Web / Mobile PWA)", "Learning sessions, visual panel, sandbox, dashboard"],
        ["Mentor console & institution dashboard", "Case handling; cohort analytics (Phase 5)"],
        ["ElevenLabs Agent", "Voice channel: speech in/out and turn-taking"],
        ["SAARTHI API", "Orchestration, authentication, role-based access, tool endpoints, policy guardrails"],
        ["Learner Twin Service", "Persistent learner state (levels, flags, strategy outcomes)"],
        ["Skill Graph Service", "Concepts, prerequisites, graph versions"],
        ["Diagnostic Engine", "Gap and misconception analysis"],
        ["Teaching Strategy Engine", "Strategy selection and experimentation"],
        ["Learning Engine", "Grounded explanations, examples and practice tasks"],
        ["Assessment Engine", "Quizzes, explain-back scoring, confidence and calibration"],
        ["Adaptation Engine", "Roadmap, next action, review scheduling, escalation checks"],
        ["Mentor Service", "Human escalation cases and feedback"],
        ["LLM Gateway", "Provider-agnostic model access, prompt versions, logging and cost limits"],
        ["Data stores", "PostgreSQL (state and evidence log), object storage for short-lived audio"],
    ], [0.35, 0.65])

    b.h2("ai", "AI Architecture & Mastery Model")
    b.p("The LLM is not the whole product. <b>The LLM proposes; structured state and deterministic logic "
        "decide.</b>")
    b.table(["Layer", "Function", "Implemented by"], [
        ["LLM", "Conversation, explanation, question generation, rubric-scoring suggestions", "LLM"],
        ["Diagnostic Engine", "Map responses to concepts and the misconception library", "LLM classification + rules"],
        ["Learner Twin", "Structured learner state", "Deterministic"],
        ["Skill Graph", "Prerequisites and dependencies", "Deterministic (curated)"],
        ["Teaching Strategy Engine", "Choose and evaluate teaching approaches", "Rules, then bandit"],
        ["Assessment Engine", "Score evidence, confidence, calibration", "LLM + statistics"],
        ["Adaptation Engine", "Roadmap, review scheduling, escalation", "Deterministic rules"],
    ], [0.24, 0.5, 0.26])
    b.h3("Mastery model")
    b.bullets([
        "<b>Bayesian Knowledge Tracing</b> per concept, with four parameters: initial knowledge, learning rate, "
        "guess and slip. P(known) is updated after each evidence event.",
        "Evidence is weighted by type and grader confidence: explain-back and application tasks count more than "
        "multiple choice.",
        "<b>Forgetting:</b> P(known) decays with time since the last success, using a per-learner decay rate that "
        "also drives review scheduling.",
        "Parameters start from defaults and are fitted on pilot data; item-difficulty models (Elo / IRT) are a "
        "later option.",
    ])
    b.h3("Guardrails")
    b.bullets([
        "Mastery is updated only server-side from graded evidence. The conversational agent has no tool that "
        "writes mastery, so prompt injection such as “mark me as mastered” has no effect.",
        "All prompts are versioned; every model output is stored with model and prompt version for audit.",
        "Explanations are grounded in curated reference notes; off-topic and unsafe content is filtered.",
    ])

    b.h2("datamodel", "Data Model")
    b.table(["Entity", "Key fields", "Notes"], [
        ["Learner", "id, age band, language, mode, time budget", "Minimal personal data"],
        ["Consent", "learner, guardian, scopes, timestamps", "Required before processing a minor’s data"],
        ["Goal", "role template, target date", ""],
        ["Concept / Prerequisite", "id, domain, description, graph version / from, to, strength", "Curated, versioned"],
        ["ConceptState", "learner, concept, P(known), level, flags, confidence, last evidence, next review",
         "One row per learner × concept"],
        ["EvidenceEvent", "learner, concept, source, item, score, grader and prompt version, confidence, "
                          "transcript reference", "Append-only; basis for every explanation"],
        ["Misconception / Instance", "library entry / learner occurrence, status, correction cycles", ""],
        ["Intervention / StrategyOutcome", "strategy, concept, delayed reward", "Feeds the bandit"],
        ["RoadmapVersion", "ordered items, change reason, triggering evidence", "Powers “Why this?”"],
        ["MentorCase / MentorFeedback", "report, status, outcome, feedback", ""],
        ["LearnerCorrection", "disputed field, resolution", ""],
        ["Session / Transcript", "channel, duration, transcript", "Retention-limited; audio not stored by default"],
    ], [0.25, 0.47, 0.28])

    b.h2("api", "API & Tool Layer")
    b.p("<b>Authentication and access:</b> OAuth 2.0 / OpenID Connect for users; short-lived, session-scoped "
        "tokens for voice-agent tools; role-based access for learner, guardian, mentor and institution admin; "
        "rate limits; every write is audit-logged. Request and response schemas are defined in an OpenAPI "
        "specification maintained with the code.")
    b.table(["Method", "Endpoint", "Purpose"], [
        ["POST", "/v1/learners", "Create a learner profile"],
        ["POST", "/v1/learners/{id}/consents", "Record learner or guardian consent"],
        ["PUT", "/v1/learners/{id}/goal", "Set the target role, date and time budget"],
        ["GET", "/v1/learners/{id}/twin", "Retrieve learner context (levels, flags, strategy outcomes)"],
        ["GET", "/v1/learners/{id}/skill-graph", "Goal sub-graph with per-learner states"],
        ["GET", "/v1/learners/{id}/gaps", "Current gaps and active misconceptions"],
        ["GET", "/v1/learners/{id}/roadmap", "Current roadmap with “Why this?” reasons"],
        ["POST", "/v1/learners/{id}/roadmap/adapt", "Regenerate next steps from new evidence"],
        ["GET", "/v1/learners/{id}/today", "Today’s mission, including due reviews"],
        ["POST", "/v1/sessions", "Start a voice or text session"],
        ["POST", "/v1/assessments", "Begin an adaptive assessment or explain-back"],
        ["POST", "/v1/assessments/{id}/responses", "Submit a text answer or voice transcript segment"],
        ["POST", "/v1/strategy-outcomes", "Record a delayed strategy outcome (internal)"],
        ["POST", "/v1/learners/{id}/corrections", "Learner disputes an estimate"],
        ["POST", "/v1/mentor-cases", "Open a human-mentor case"],
        ["POST", "/v1/mentor-cases/{id}/feedback", "Mentor feedback and outcome"],
        ["GET", "/v1/learners/{id}/export", "Export all of the learner’s data"],
        ["DELETE", "/v1/learners/{id}", "Erase the learner’s data"],
    ], [0.1, 0.4, 0.5])
    b.h3("Voice-agent tools (exposed to the ElevenLabs agent)")
    b.table(["Tool", "Purpose"], [
        ["get_learner_context", "Minimal context: goal, current concept, level, flags, language"],
        ["get_next_action", "What to do next in this session"],
        ["explain_topic", "Grounded explanation using the selected strategy"],
        ["record_response", "Submit a transcript segment for scoring; returns a follow-up question"],
        ["request_mentor", "Open a mentor case when a trigger fires or the learner asks"],
    ], [0.3, 0.7])
    b.p("No tool can set mastery directly — mastery changes only through graded evidence on the server.")

    b.h2("dataflow", "Data Flow")
    b.numbered([
        "The learner speaks or types.",
        "Voice: the ElevenLabs agent transcribes and manages turn-taking. Text goes straight to the API.",
        "The SAARTHI API authenticates the request and loads context from the Learner Twin and Skill Graph.",
        "The Diagnostic Engine interprets the response against the concept and the misconception library.",
        "The Teaching Strategy Engine picks the next intervention; the Learning Engine generates grounded content.",
        "The Assessment Engine scores evidence with a confidence estimate and writes an evidence event.",
        "The Adaptation Engine updates concept state, roadmap and review schedule, and checks escalation triggers.",
        "The response returns to the learner — spoken through ElevenLabs or shown as text and visuals — with the next action.",
        "If triggered, the Mentor Service opens a case; mentor feedback flows back as evidence.",
    ])

    b.h2("stack", "Proposed Technology Stack")
    b.table(["Layer", "Proposed choice", "Reason"], [
        ["Frontend", "Next.js (React) progressive web app", "Web and mobile from one codebase; installable"],
        ["Backend", "Python with FastAPI", "Strong ML ecosystem; async I/O for voice tools"],
        ["Database", "PostgreSQL", "Relational state plus JSON; graph stored as adjacency tables at MVP scale"],
        ["Cache / jobs", "Redis", "Session state and background jobs"],
        ["Voice", "ElevenLabs Agents", "Speech in/out, turn-taking, Hindi support (to verify in spike)"],
        ["LLM", "Provider-agnostic gateway; e.g. Claude Sonnet 5.5 for tutoring and diagnosis, Claude Haiku 4.5 "
                "for high-volume rubric scoring", "Quality where it matters, lower cost at volume"],
        ["Sandbox", "SQLite (WebAssembly) and Pyodide in the browser", "No server-side code execution"],
        ["Hosting", "Managed cloud, India region", "Latency and data-localisation preferences"],
        ["Observability", "OpenTelemetry, error tracking, LLM trace logging", "Debugging, cost and quality monitoring"],
    ], [0.15, 0.47, 0.38])
    b.p("Final choices " + TBC + " after the technical spike.")

    b.h2("nfr", "Non-Functional Requirements")
    b.table(["Area", "Initial target (to validate in pilot)"], [
        ["Voice turn latency", "Median under 1.0 s and 95th percentile under 2.0 s from end of speech to start of reply"],
        ["Context-tool latency", "95th percentile under 300 ms"],
        ["Dashboard load", "Under 3 s on a mid-range phone over 4G"],
        ["Availability", "99.5% monthly during the pilot"],
        ["Scale", "Pilot: 500 concurrent learners; stateless services scale horizontally"],
        ["Security", "TLS everywhere, encryption at rest, role-based access, audit log, secrets manager, "
                     "dependency scanning"],
        ["Cost", "Per-learner monthly model and voice budget enforced by the LLM gateway"],
        ["Accessibility", "WCAG 2.1 AA for the web UI; full text parity for all voice features"],
        ["Localisation", "UI in English and Hindi; conversation in English, Hindi and Hinglish"],
    ], [0.25, 0.75])

    b.h2("safety", "Safety, Privacy & Compliance")
    b.h3("Principles")
    b.bullets([
        "Avoid claiming that voice alone can reliably infer emotion, intelligence or psychological state.",
        "Keep learner-state updates evidence-based and explainable.",
        "Provide a way for students to correct inaccurate learner-model assumptions.",
        "Protect student data and minimise unnecessary storage of sensitive conversation content.",
        "Clearly distinguish AI-generated guidance from verified academic or career information.",
        "Keep human mentors in the loop for persistent or high-impact decisions.",
        "Measure whether adaptive interventions actually improve learning rather than assuming personalisation works.",
    ])
    b.h3("Children’s data — India’s DPDP Act, 2023")
    b.p("Many learners will be under 18. Under the Digital Personal Data Protection Act, 2023, processing a "
        "child’s data requires verifiable consent from a parent or guardian, and the Act restricts tracking or "
        "behavioural monitoring of children and targeted advertising at them; the DPDP Rules set out consent "
        "mechanics and certain exemptions (for example, for educational institutions). Because the Learner Twin "
        "models learning behaviour, <b>legal review is required before launching to minors</b>. Until then, run "
        "the pilot with learners aged 18+ or through partner institutions under appropriate agreements.")
    b.h3("Data minimisation and retention")
    b.bullets([
        "Audio is not stored by default — only transcripts. Transcripts are kept for a limited period (e.g. 90 "
        "days " + TBC + ") unless the learner opts in; after that, evidence keeps scores, not raw text.",
        "Self-service export and erasure (see API section).",
        "Voice, LLM and cloud providers act as data processors under data-processing agreements; zero-retention "
        "options and cross-border transfer are reviewed before launch.",
    ])
    b.h3("Wellbeing and safeguarding")
    b.p("SAARTHI does not infer emotion from voice. If a learner <i>explicitly</i> mentions distress, self-harm "
        "or abuse, it follows a scripted safe response, shares helpline information (in India, the Tele-MANAS "
        "mental-health helpline, 14416) and, for institution learners, alerts the designated safeguarding contact "
        "according to that institution’s policy.")
    b.h3("Integrity, misuse and fairness")
    b.bullets([
        "Explain-backs include live follow-ups; sandbox tasks use randomised data.",
        "For graded external homework, SAARTHI offers guided help rather than finished answers.",
        "Prompt-injection resistance: the agent cannot change mastery (see AI Architecture).",
        "Scores are independent of accent, fluency and language choice. Recognition and grading are tested across "
        "accents and English/Hindi/Hinglish, and score gaps between language groups are monitored.",
    ])

    # ---------------------------------------------------------- PART C
    b.part("Part C — Delivery & Business")

    b.h2("mvp", "MVP Scope")
    b.p("The hackathon build and the first pilot have different requirements, so they are scoped separately. "
        "Every step of the recommended demo uses only P0 features.")
    b.table(["Priority", "Feature", "Stage"], [
        ["P0", "Onboarding with goal (preset Backend Developer template)", "Hackathon MVP"],
        ["P0", "Skill graph: SQL and prerequisites (about 30–40 concepts)", "Hackathon MVP"],
        ["P0", "Voice and text mentor (ElevenLabs + text channel)", "Hackathon MVP"],
        ["P0", "Placement probe and conversational diagnosis", "Hackathon MVP"],
        ["P0", "Explain-back assessment with rubric", "Hackathon MVP"],
        ["P0", "Knowledge-gap <b>and</b> misconception detection (curated SQL library, 10–15 entries)", "Hackathon MVP"],
        ["P0", "Unified skill-state model with Bayesian Knowledge Tracing", "Hackathon MVP"],
        ["P0", "Rule-based strategy choice and a basic visual panel (pre-built JOIN diagrams)", "Hackathon MVP"],
        ["P0", "Adaptive roadmap with “Why this?”", "Hackathon MVP"],
        ["P0", "Student dashboard", "Hackathon MVP"],
        ["P0", "Mentor handoff report (generated case report; no live mentor matching)", "Hackathon MVP"],
        ["P1", "Teaching-strategy bandit", "Pilot"],
        ["P1", "SQL / Python practice sandbox and spaced review", "Pilot"],
        ["P1", "Learning Genome with “correct me” controls", "Pilot"],
        ["P1", "Mentor console with pilot Chhatrachhaya mentors", "Pilot"],
        ["P1", "Guardian consent flow; data export and erasure", "Pilot"],
        ["P1", "Hinglish recognition test set and tuning; evaluation instrumentation", "Pilot"],
        ["P2", "Full career intelligence (multiple roles, portfolio mapping)", "Later"],
        ["P2", "Document ingestion; more domains", "Later"],
        ["P2", "Institutional dashboards; mentor marketplace", "Later"],
    ], [0.11, 0.66, 0.23])

    b.h2("demo", "Recommended Hackathon Demo")
    b.p("The strongest demo tells one complete story rather than showing dozens of disconnected features. The "
        "visual “wow” moment is <b>the roadmap changing live</b> after the conversational assessment.")
    b.table(["Time", "Demo step", "P0 feature shown"], [
        ["0:00", "Student chooses “Backend Developer” as the target", "Onboarding"],
        ["0:20", "SAARTHI displays the initial skill graph", "Skill graph"],
        ["0:40", "Student says: “I understand SQL joins.”", "Voice mentor"],
        ["0:50", "SAARTHI starts a short voice diagnosis", "Conversational diagnosis"],
        ["1:30", "Student reveals a LEFT JOIN vs INNER JOIN misconception; SAARTHI reads it back to confirm",
         "Misconception detection"],
        ["1:50", "SAARTHI explains using contrasting cases and a row-level JOIN diagram", "Strategy + visual panel"],
        ["2:40", "Student teaches the concept back through voice", "Explain-back"],
        ["3:20", "SAARTHI evaluates the explanation", "Rubric scoring"],
        ["3:40", "The mastery state changes", "Unified state model"],
        ["3:50", "The roadmap inserts targeted practice — live, with “Why this?”", "Adaptive roadmap"],
        ["4:30", "Simulated persistent failure: SAARTHI prepares a human-mentor handoff report", "Mentor handoff report"],
    ], [0.09, 0.62, 0.29])
    b.h3("Demo risk plan")
    b.bullets([
        "Pre-recorded backup video of the full flow.",
        "Switch to text mode if the venue network or microphone fails.",
        "Seeded demo learner account; real API calls rather than mock-ups, and a clear statement of what is live "
        "and what is pre-seeded.",
    ])

    b.h2("competition", "Differentiation & Competitive Landscape")
    b.table(["Category", "Typical focus", "SAARTHI focus"], [
        ["Document AI", "Understand source material", "Use material as one evidence source (Phase 3)"],
        ["Generic AI tutor", "Answer questions", "Model learner state"],
        ["Course platform", "Deliver a fixed curriculum", "Continuously adapt the curriculum"],
        ["Voice AI", "Natural conversation", "Use conversation for diagnosis and assessment"],
        ["Quiz systems", "Measure answers", "Infer gaps and misconceptions"],
        ["Human mentoring", "Experience and guidance", "AI prepares a contextual escalation"],
    ], [0.22, 0.33, 0.45])
    b.table(["Product", "Primary focus", "Where SAARTHI differs"], [
        ["Khanmigo (Khan Academy)", "Socratic AI tutor over Khan content; teacher tools",
         "Career-oriented self-learners; voice-first Hinglish; persistent, learner-visible skill model"],
        ["ChatGPT Study Mode, Gemini Guided Learning", "Step-by-step guided learning inside general assistants",
         "Structured skill graph and roadmap owned by the learner; explain-back assessment"],
        ["ALEKS (McGraw Hill)", "Adaptive assessment using knowledge space theory",
         "Conversational, open-ended evidence instead of item-only assessment"],
        ["Duolingo Max", "AI conversation for language learning", "Technical and career skills"],
        ["Indian ed-tech apps with AI doubt-solving", "Exam preparation and doubt solving at scale",
         "Learner-model-centred rather than answer-centred"],
    ], [0.27, 0.33, 0.4])
    b.p("<i>Competitor capabilities change quickly; verify before external use.</i>")

    b.h2("business", "Business Model & Unit Economics")
    b.table(["Model", "Customer", "Notes"], [
        ["B2C freemium", "Self-learners", "Text mode free with limits; paid plan adds voice minutes and mentor sessions"],
        ["Institutional licence (B2B2C)", "Colleges, bootcamps, coaching institutes",
         "Per-seat annual licence; cohort dashboards (Phase 5)"],
        ["Mentor sessions", "Learners", "Commission on paid Chhatrachhaya sessions (Phase 4)"],
    ], [0.25, 0.27, 0.48])
    b.h3("Cost model")
    b.p("<b>Cost per active learner per month</b> = voice minutes × voice price per minute + LLM tokens × token "
        "price + infrastructure share + mentor minutes × mentor cost.")
    b.table(["Input", "Starting assumption (to validate)"], [
        ["Voice minutes per active learner per month", "About 60, used for diagnosis and explain-back only"],
        ["LLM tokens per session", "Measured during the pilot"],
        ["Voice and LLM unit prices", "Vendor pricing at the time of launch"],
        ["Mentor escalation rate", "Under 5% of active learners per month"],
        ["Pricing and target gross margin", TBC + " after willingness-to-pay interviews in the pilot"],
    ], [0.45, 0.55])
    b.p("<b>Cost levers:</b> text as the default mode; voice for high-value moments; a smaller model for scoring; "
        "caching explanations per concept; per-plan minute caps.")

    b.h2("metrics", "Success Metrics & Evaluation Plan")
    b.p("<b>North Star metric:</b> verified mastery gains per active learner per week — concepts that reach "
        "Mastered and are still answered correctly at a 7-day review.")
    b.table(["Metric", "Definition", "Pilot target (proposed)"], [
        ["Learning gain", "Pre/post test improvement versus a control group", "Significantly above control"],
        ["Misconception resolution", "Share of flagged misconceptions still resolved at a 7-day check", "≥ 60%"],
        ["Misconception precision", "Share of flags confirmed correct by human review", "≥ 90%"],
        ["Grader agreement", "Cohen’s κ between AI rubric scores and human graders", "≥ 0.70"],
        ["Retention", "Accuracy on delayed review items", "≥ 80%"],
        ["Learning efficiency", "Median time to Mastered per concept", "Set baseline, then reduce"],
        ["Adaptation quality", "Share of roadmap changes followed by a better result at the next check", "≥ 60%"],
        ["Roadmap stability", "Major re-orders per learner per week", "≤ 1"],
        ["Mentor handoff usefulness", "Mentor rating of the case report (1–5)", "≥ 4.0"],
        ["Engagement", "Weekly active learners; 30-day retention", "Tracked, never optimised alone"],
        ["Voice quality", "Recognition error rate on the Hinglish test set; voice latency", "Baseline first; p95 under 2 s"],
        ["Cost", "Cost per active learner per month", "Within plan budget"],
    ], [0.23, 0.5, 0.27])
    b.h3("Evaluation design")
    b.bullets([
        "Pilot with one or two partner institutions " + TBC + ".",
        "Randomised comparison: adaptive SAARTHI versus the same content in a fixed order (both with AI chat), "
        "so the effect of adaptation — not just of having an AI — is measured.",
        "Pre-test, post-test and a 2-week delayed test; metrics defined before the pilot starts.",
        "Target sample: 100+ learners per group if feasible " + TBC + ".",
        "A human-graded sample of about 200 explain-backs for calibration.",
    ])

    b.h2("risks", "Risks & Mitigations")
    b.table(["Risk", "Impact", "Mitigation"], [
        ["Wrong misconception flags", "Loss of trust", "Confirmation question, confidence threshold, precision metric, dispute button"],
        ["Speech-recognition errors on Hinglish and technical terms", "False evidence",
         "Read-back, confidence gating, text fallback, dedicated test set"],
        ["LLM explains something incorrectly", "Learner learns wrong content",
         "Grounding in curated notes, error reporting, expert review"],
        ["Skill-graph quality", "Poor roadmaps", "Expert curation, versioning, mentor and learner flags"],
        ["Voice costs higher than planned", "Weak margins", "Minute caps, text default, model tiering"],
        ["Dependence on voice or LLM vendor", "Outage or price change", "Provider-agnostic gateway, text fallback"],
        ["Children’s-data compliance", "Legal and regulatory exposure",
         "Legal review, 18+ pilot, guardian consent, data minimisation"],
        ["Too few mentors", "Escalations go unanswered", "Pilot volunteers, response targets, AI fallback, marketplace later"],
        ["Personalisation benefits not proven", "Credibility", "Controlled evaluation before making claims"],
        ["Gaming or cheating", "Invalid mastery", "Live follow-ups, randomised tasks, server-side mastery"],
    ], [0.3, 0.2, 0.5])

    b.h2("future", "Future Roadmap")
    b.table(["Phase", "Capabilities", "Priority tier"], [
        ["Phase 1 — Hackathon MVP", "Learner Twin, SQL skill graph, voice and text diagnosis, gap and misconception "
                                    "detection, explain-back, adaptive roadmap, mentor handoff report", "P0"],
        ["Phase 2 — Pilot", "Strategy bandit, practice sandbox, spaced review, Learning Genome controls, mentor "
                            "console with pilot mentors, consent flow", "P1"],
        ["Phase 3 — Career & content", "Career intelligence across roles, project and portfolio mapping, document "
                                       "ingestion", "P2"],
        ["Phase 4 — Chhatrachhaya at scale", "Mentor marketplace, paid sessions, mentor quality ratings", "P2"],
        ["Phase 5 — Institutions", "Teacher and institution dashboards, aggregate skill intelligence, curriculum "
                                   "alignment", "P2"],
        ["Phase 6 — Cross-domain", "More domains and Indian languages; long-term learning memory across goals", "Later"],
    ], [0.26, 0.6, 0.14])

    b.h2("team", "Team, Milestones & Open Questions")
    b.table(["Role", "Owner"], [
        ["Product lead", TBC], ["AI / ML engineer", TBC], ["Backend engineer", TBC],
        ["Frontend engineer", TBC], ["Domain expert (SQL / backend)", TBC], ["Design", TBC],
    ], [0.45, 0.55])
    b.table(["Milestone", "Definition of done", "Date"], [
        ["M1 — Content ready", "SQL skill graph, item bank, rubrics and misconception library reviewed", TBC],
        ["M2 — Core loop in text", "Diagnosis → teach → explain-back → assess → adapt works end to end in text", TBC],
        ["M3 — Voice integrated", "ElevenLabs agent calling SAARTHI tools; read-back safeguards working", TBC],
        ["M4 — Demo-ready MVP", "Full demo script runs live, with backup plan rehearsed", TBC],
        ["M5 — Pilot launch", "Consent flow, mentor console and evaluation instrumentation live", TBC],
    ], [0.24, 0.56, 0.2])
    b.h3("Open questions")
    b.bullets([
        "First user segment: college students or working professionals switching careers?",
        "Age policy for the pilot (18+ only, or minors through institutions)?",
        "Voice integration mode: ElevenLabs-hosted LLM with tools, or SAARTHI’s own LLM endpoint?",
        "Pilot institution partners and mentor recruitment sources.",
        "Pricing and plan structure.",
    ])

    b.h2("positioning", "Product Positioning & Final Statement")
    b.p("SAARTHI should not be positioned as “another AI tutor”, “a voice-enabled study assistant” or “an AI PDF "
        "reader”. Those descriptions reduce the product to individual features.")
    b.callout("<b>Recommended positioning:</b> SAARTHI is an Adaptive AI Mentor that builds a living model of the "
              "learner and continuously decides what the learner should learn, why they are struggling, how to "
              "teach the concept, and when human guidance is needed.")
    b.p("SAARTHI transforms learning from a static content-delivery process into a continuous learner-modelling "
        "loop. It does not simply ask “What should I teach?” It asks: <b>“What does this learner understand, what is "
        "preventing progress, what teaching approach is working, and what should happen next?”</b>")
    b.flow(Spacer(1, 10))
    b.flow(Paragraph("SAARTHI — The AI Mentor That Learns How to Teach You.", ST["quote"]))
    b.flow(Paragraph("Understand → Diagnose → Teach → Listen → Assess → Adapt → Repeat", ST["caption"]))

    # ---------------------------------------------------------- Appendix
    b.part("Appendix — Glossary")
    b.table(["Term", "Meaning in this report"], [
        ["Learner Twin", "SAARTHI’s internal, structured, evidence-linked model of one learner"],
        ["Learning Genome", "The learner-facing, plain-language view of the Learner Twin"],
        ["Skill graph", "Concepts (nodes) and prerequisite relationships (edges) for a domain"],
        ["Mastery level", "Not assessed, Unknown, Developing, Proficient or Mastered — derived from P(known)"],
        ["Flag", "Independent marker on a concept: Misconception, Blocked by prerequisite, Due for review, "
                 "Disputed, Low confidence"],
        ["Misconception", "An incorrect mental model, as opposed to missing knowledge"],
        ["Evidence event", "One recorded, scored observation of the learner; the basis for every state change"],
        ["Explain-back", "Assessment in which the learner teaches the concept back in their own words"],
        ["Teaching strategy", "A way of teaching a concept, e.g. analogy, worked example, contrasting cases"],
        ["Chhatrachhaya", "SAARTHI’s human mentor network for escalated cases"],
        ["Mentor case", "A structured handoff containing goal, evidence, strategies tried and suggested next step"],
        ["BKT", "Bayesian Knowledge Tracing — the probabilistic model used to estimate P(known)"],
        ["P0 / P1 / P2", "Priority tiers: hackathon MVP / pilot / later"],
    ], [0.22, 0.78])


def build_front(b, secnum):
    s = lambda k: f"§{secnum[k]}"
    front = [Paragraph("About this Revision (v2.0)", ST["part"])]
    rb = Builder()
    rb.rule()
    front += rb.story
    front.append(Paragraph(
        "This edition fixes the issues found in the review of v1.0 (21 September 2026). The table maps each "
        "issue to its fix. Items marked " + TBC + " need a decision or input from the team.", ST["body"]))
    rows = [
        ["Page 2 held 32 bullets with no headings; §11, §23, §25 and §26 of v1 had headings but no content",
         "Every bullet restored under its correct section; headings kept with their content",
         f"{s('innovation')}, {s('voice')}, {s('safety')}, {s('demo')}"],
        ["Headings stranded at the bottom of pages", "Keep-with-next on all headings; table headers repeat",
         "Throughout"],
        ["No contents page, version, date or diagrams", "Contents, PDF bookmarks, version block, three diagrams",
         f"Front matter, {s('exec')}, {s('graph')}, {s('arch')}"],
        ["Three different skill-state vocabularies", "One model: a mastery level plus independent flags",
         s("states")],
        ["Demo relied on P1/P2 features", "Misconception detection and mentor handoff report moved to P0; "
                                          "demo uses P0 only", f"{s('mvp')}, {s('demo')}"],
        ["MVP priorities and phase roadmap disagreed", "Phases mapped one-to-one to priority tiers", s("future")],
        ["Component lists differed between sections", "One canonical component list used everywhere",
         f"{s('voice')}, {s('arch')}, {s('ai')}"],
        ["Diagnosis example contradicted itself", "Rewritten; prerequisite gap found, gaps ordered and tied to "
                                                  "the weakest sub-skills", s("diagnosis")],
        ["Document ingestion mentioned but never described", "Defined and scheduled for Phase 3",
         f"{s('practice')}, {s('future')}"],
        ["“Chhatrachhaya” never defined", "Defined, with escalation rules and operations", s("mentor")],
        ["Learner Twin / Learning Genome / learner model", "One meaning each; glossary added",
         f"{s('twin')}, Appendix"],
        ["No mastery algorithm; grading, speech-recognition and strategy-credit risks",
         "BKT with forgetting; rubric calibration; read-back; delayed-reward bandit",
         f"{s('strategy')}, {s('explainback')}, {s('voice')}, {s('ai')}"],
        ["API was function names only", "REST API with auth, consent, correction, export/erasure, mentor "
                                        "feedback; restricted voice tools", s("api")],
        ["No data model, tech stack or non-functional requirements", "Added",
         f"{s('datamodel')}, {s('stack')}, {s('nfr')}"],
        ["Missing features", "Spaced review, sandbox, visual panel, “Why this?”, correct-me controls, "
                             "mentor/institution/guardian views, placement, motivation, text parity, safeguarding",
         f"{s('roadmap')}, {s('practice')}, {s('genome')}–{s('motivation')}, {s('safety')}"],
        ["No privacy law, competitors, business model, metric targets, team or timeline",
         "Added (DPDP Act, named competitors, cost model, targets and evaluation design, milestones)",
         f"{s('safety')}, {s('competition')}–{s('metrics')}, {s('team')}"],
    ]
    front.append(make_table(["Issue in v1.0", "Fix in v2.0", "Where"], rows, [0.4, 0.43, 0.17]))
    front.append(PageBreak())
    front.append(Paragraph("Contents", ST["tochead"]))
    toc = TableOfContents()
    toc.levelStyles = [TOC_L0, TOC_L1]
    toc.dotsMinLevel = 1
    front.append(toc)
    front.append(PageBreak())
    return front


def main():
    b = Builder()
    build_body(b)
    front = build_front(b, b.secnum)
    story = [Spacer(1, 1), NextPageTemplate("body"), PageBreak()] + front + b.story
    doc = ReportDoc(OUT, title="SAARTHI — Complete Product Report v2.0", author="SAARTHI Product Team",
                    subject="Adaptive AI Mentor & Learner Intelligence Platform — revised product and technical report",
                    keywords="SAARTHI, adaptive learning, learner twin, AI mentor, ElevenLabs, Chhatrachhaya",
                    creator="build_updated_report.py")
    doc.multiBuild(story, canvasmaker=NumberedCanvas)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
