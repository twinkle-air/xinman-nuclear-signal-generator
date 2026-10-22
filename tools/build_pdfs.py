from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
FONT_REGULAR = Path(r"C:\Windows\Fonts\Deng.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\Dengb.ttf")

pdfmetrics.registerFont(TTFont("Deng", str(FONT_REGULAR)))
pdfmetrics.registerFont(TTFont("Deng-Bold", str(FONT_BOLD)))


class NumberedCanvasMixin:
    pass


def inline_markup(text: str) -> str:
    text = html.escape(text.strip())
    text = re.sub(r"`([^`]+)`", r'<font name="Deng-Bold" color="#175a75">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r'<font name="Deng-Bold">\1</font>', text)
    url_re = re.compile(r"(https?://[^\s<]+)")
    text = url_re.sub(r'<link href="\1" color="#0b6a88">\1</link>', text)
    return text


def make_styles(accent: colors.Color):
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontName="Deng-Bold", fontSize=28,
            leading=38, alignment=TA_CENTER, textColor=accent, spaceAfter=12 * mm,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], fontName="Deng", fontSize=13,
            leading=22, alignment=TA_CENTER, textColor=colors.HexColor("#44515a"),
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Deng-Bold", fontSize=17,
            leading=22, textColor=accent, spaceBefore=6 * mm, spaceAfter=2.5 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Deng-Bold", fontSize=13,
            leading=17, textColor=colors.HexColor("#243b48"), spaceBefore=3 * mm,
            spaceAfter=1.5 * mm, keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName="Deng-Bold", fontSize=11,
            leading=16, textColor=colors.HexColor("#355565"), spaceBefore=3 * mm,
            spaceAfter=1.5 * mm, keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName="Deng", fontSize=9.0,
            leading=14.2, alignment=TA_JUSTIFY, textColor=colors.HexColor("#1f2529"),
            spaceAfter=1.8 * mm, wordWrap="CJK",
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["BodyText"], fontName="Deng", fontSize=9.0,
            leading=13.8, leftIndent=5 * mm, firstLineIndent=-3.5 * mm,
            bulletIndent=1.2 * mm, spaceAfter=1.0 * mm, wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "table", parent=base["BodyText"], fontName="Deng", fontSize=6.7,
            leading=9.2, alignment=TA_LEFT, wordWrap="CJK", textColor=colors.HexColor("#182126"),
        ),
        "table_head": ParagraphStyle(
            "table_head", parent=base["BodyText"], fontName="Deng-Bold", fontSize=6.8,
            leading=9.4, alignment=TA_CENTER, wordWrap="CJK", textColor=colors.white,
        ),
        "code": ParagraphStyle(
            "code", parent=base["Code"], fontName="Deng", fontSize=7.2,
            leading=10, leftIndent=3 * mm, rightIndent=3 * mm,
            textColor=colors.HexColor("#17313d"), backColor=colors.HexColor("#eef5f7"),
            borderPadding=5, spaceBefore=1.5 * mm, spaceAfter=3 * mm,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base["Normal"], fontName="Deng", fontSize=8,
            leading=13, textColor=colors.HexColor("#5b6870"),
        ),
    }


def column_widths(rows: list[list[str]], total: float) -> list[float]:
    count = max(len(r) for r in rows)
    scores = []
    for c in range(count):
        values = [r[c] if c < len(r) else "" for r in rows]
        max_len = max((sum(2 if ord(ch) > 127 else 1 for ch in v) for v in values), default=1)
        scores.append(min(34, max(7, max_len)))
    s = sum(scores)
    widths = [total * score / s for score in scores]
    min_w = 16 * mm
    for i, w in enumerate(widths):
        if w < min_w:
            deficit = min_w - w
            widths[i] = min_w
            biggest = max(range(count), key=lambda j: widths[j] if j != i else -1)
            widths[biggest] = max(min_w, widths[biggest] - deficit)
    scale = total / sum(widths)
    return [w * scale for w in widths]


def parse_markdown(md: str, styles, accent) -> list:
    lines = md.splitlines()
    story = []
    i = 0
    first_h1_skipped = False
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i].rstrip())
                i += 1
            i += 1
            story.append(Preformatted("\n".join(code), styles["code"], maxLineLength=105))
            continue
        if stripped.startswith("# "):
            if not first_h1_skipped:
                first_h1_skipped = True
            else:
                story.append(Paragraph(inline_markup(stripped[2:]), styles["h1"]))
            i += 1
            continue
        if stripped.startswith("## "):
            story.append(Paragraph(inline_markup(stripped[3:]), styles["h1"]))
            i += 1
            continue
        if stripped.startswith("### "):
            story.append(Paragraph(inline_markup(stripped[4:]), styles["h2"]))
            i += 1
            continue
        if stripped.startswith("#### "):
            story.append(Paragraph(inline_markup(stripped[5:]), styles["h3"]))
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-+", lines[i + 1]):
            table_rows = []
            header = [x.strip() for x in stripped.strip("|").split("|")]
            table_rows.append(header)
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_rows.append([x.strip() for x in lines[i].strip().strip("|").split("|")])
                i += 1
            col_count = max(len(r) for r in table_rows)
            table_rows = [r + [""] * (col_count - len(r)) for r in table_rows]
            data = []
            for ri, row in enumerate(table_rows):
                sty = styles["table_head"] if ri == 0 else styles["table"]
                data.append([Paragraph(inline_markup(cell), sty) for cell in row])
            widths = column_widths(table_rows, 176 * mm)
            t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), accent),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#aab8be")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f7f8")]),
            ]))
            story.extend([t, Spacer(1, 3 * mm)])
            continue
        if re.match(r"^[-*]\s+", stripped):
            text = re.sub(r"^[-*]\s+", "", stripped)
            story.append(Paragraph("•  " + inline_markup(text), styles["bullet"]))
            i += 1
            continue
        if re.match(r"^\d+\.\s+", stripped):
            m = re.match(r"^(\d+)\.\s+(.*)", stripped)
            story.append(Paragraph(f"{m.group(1)}.  {inline_markup(m.group(2))}", styles["bullet"]))
            i += 1
            continue
        para = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or nxt.startswith(("#", "|", "```", "- ", "* ")) or re.match(r"^\d+\.\s+", nxt):
                break
            para.append(nxt)
            i += 1
        text = " ".join(para)
        style = styles["meta"] if text.startswith(("版本：", "日期：", "预算口径：", "定位：")) else styles["body"]
        story.append(Paragraph(inline_markup(text), style))
    return story


def footer(canvas, doc, accent):
    canvas.saveState()
    w, _ = A4
    canvas.setStrokeColor(colors.HexColor("#c9d3d7"))
    canvas.setLineWidth(0.35)
    canvas.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)
    canvas.setFont("Deng", 7.5)
    canvas.setFillColor(colors.HexColor("#65747b"))
    canvas.drawString(18 * mm, 9 * mm, "智能仿核信号发生器实现方案 · 2026-07-23")
    canvas.drawRightString(w - 18 * mm, 9 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def build(md_path: Path, pdf_path: Path, title: str, subtitle: str, accent_hex: str):
    accent = colors.HexColor(accent_hex)
    styles = make_styles(accent)
    doc = BaseDocTemplate(
        str(pdf_path), pagesize=A4, rightMargin=17 * mm, leftMargin=17 * mm,
        topMargin=17 * mm, bottomMargin=18 * mm, title=title, author="Codex",
        subject="新漫杯智能仿核信号发生器实现路径",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([PageTemplate(id="main", frames=frame, onPage=lambda c, d: footer(c, d, accent))])

    story = [
        Spacer(1, 38 * mm),
        Paragraph(title, styles["cover_title"]),
        Paragraph(subtitle, styles["cover_sub"]),
        Spacer(1, 25 * mm),
        Table(
            [[Paragraph("依据文档", styles["table_head"]), Paragraph("主办方《智能仿核信号发生器》竞赛题目及评分标准", styles["table"])],
             [Paragraph("预算目标", styles["table_head"]), Paragraph("设备本体约 1000 元人民币", styles["table"])],
             [Paragraph("方案版本", styles["table_head"]), Paragraph("评分标准修订版 · 2026-07-23", styles["table"])]],
            colWidths=[35 * mm, 95 * mm], hAlign="CENTER",
            style=TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), accent),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#aab8be")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]),
        ),
        Spacer(1, 28 * mm),
        Paragraph("工程实现、采购预算与验证路径", styles["cover_sub"]),
        PageBreak(),
    ]
    story.extend(parse_markdown(md_path.read_text(encoding="utf-8"), styles, accent))
    doc.build(story)


if __name__ == "__main__":
    build(
        ROOT / "docs" / "hardware" / "硬件实现方案.md",
        ROOT / "新漫杯_智能反馈信号发生器_硬件实现方案.pdf",
        "智能仿核信号发生器",
        "硬件实现方案",
        "#176b5b",
    )
    build(
        ROOT / "docs" / "software" / "软件实现方案.md",
        ROOT / "新漫杯_智能反馈信号发生器_软件实现方案.pdf",
        "智能仿核信号发生器",
        "软件实现方案",
        "#245a86",
    )
    build(
        ROOT / "智能反馈信号发生器_综合分析报告.md",
        ROOT / "新漫杯_智能反馈信号发生器_综合分析报告.pdf",
        "智能仿核信号发生器",
        "综合分析报告（评分标准修订版）",
        "#6f4a8e",
    )
    print("PDFs generated")
