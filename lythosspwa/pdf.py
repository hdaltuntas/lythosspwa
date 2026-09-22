"""
PDF output for the calculation report.

`report.build_html()` assembles the report once; this module turns that same
HTML into a PDF with reportlab, so the PDF, the HTML file and the DOCX all say
exactly the same thing and there is one place where report content is decided.

The walker deliberately understands only the markup `report.build_html()`
produces — headings, paragraphs, tables, list items and figures. It is not a
general HTML engine, and does not pretend to be one: anything else is reduced
to its text.

Fonts: the standard PDF fonts are Latin-1, which cannot spell Turkish (ı, ş,
ğ) or the symbols an engineering report is full of (φ, γ, kₛ, √). A Unicode
TrueType font is registered instead — the DejaVu that comes with Matplotlib,
which is a required dependency, so it is always there.
"""

from __future__ import annotations

import html
import io
import os
import re
from typing import Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

#: Report colors, the same family as the HTML stylesheet in report.py
NAVY = colors.HexColor("#1F4E79")
INK = colors.HexColor("#222222")
GREY = colors.HexColor("#555555")
HEAD_BG = colors.HexColor("#E8EEF6")
LINE = colors.HexColor("#B8C4D6")
OK = colors.HexColor("#1E8449")
BAD = colors.HexColor("#C0392B")

MARGIN = 15 * mm
PAGE = A4


# --------------------------------------------------------------------------- #
#  Fonts
# --------------------------------------------------------------------------- #

def _font_candidates() -> List[Tuple[str, str, str]]:
    """(name, regular, bold) font files to try, best coverage first."""
    candidates = []
    try:                                     # Matplotlib's own DejaVu
        import matplotlib
        ttf = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
        candidates.append(("DejaVuSans", os.path.join(ttf, "DejaVuSans.ttf"),
                           os.path.join(ttf, "DejaVuSans-Bold.ttf")))
    except Exception:                        # pragma: no cover - no Matplotlib data
        pass
    candidates += [
        ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("Arial", r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
        ("Arial", "/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ]
    return candidates


def fonts() -> Tuple[str, str]:
    """Registers and returns (regular, bold) font names for the report."""
    for name, regular, bold in _font_candidates():
        if not os.path.exists(regular):
            continue
        try:
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, regular))
                pdfmetrics.registerFont(
                    TTFont(name + "-Bold", bold if os.path.exists(bold) else regular))
            return name, name + "-Bold"
        except Exception:                    # pragma: no cover - unreadable font file
            continue
    return "Helvetica", "Helvetica-Bold"     # Latin-1 only; last resort


# --------------------------------------------------------------------------- #
#  Inline markup
# --------------------------------------------------------------------------- #

_STATUS = {"ok": OK, "bad": BAD}


def _inline(text: str) -> str:
    """The report's inline markup as the markup reportlab paragraphs take."""
    for cls, color in _STATUS.items():
        text = re.sub(rf'<span class="{cls}">(.*?)</span>',
                      rf'<font color="#{color.hexval()[2:]}"><b>\1</b></font>',
                      text, flags=re.S)
    text = re.sub(r"<br\s*/?>", "<br/>", text)
    text = re.sub(r"</?(?!b>|/b>|i>|/i>|font|br/|super|sub)[a-zA-Z][^>]*>", "", text)
    return text.strip()


def _plain(text: str) -> str:
    """Tag-free text, for headings and captions."""
    return html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", " ", text))).strip()


# --------------------------------------------------------------------------- #
#  Styles
# --------------------------------------------------------------------------- #

def _styles() -> Dict[str, ParagraphStyle]:
    regular, bold = fonts()
    body = ParagraphStyle("body", fontName=regular, fontSize=9, leading=12,
                          textColor=INK, alignment=TA_LEFT)
    return {
        "font": regular, "bold": bold,
        "title": ParagraphStyle("title", parent=body, fontName=bold, fontSize=17,
                                leading=21, textColor=NAVY, spaceAfter=2),
        "meta": ParagraphStyle("meta", parent=body, fontSize=8.5, leading=12,
                               textColor=GREY, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=body, fontName=bold, fontSize=12.5, leading=16,
                             textColor=NAVY, spaceBefore=14, spaceAfter=4,
                             borderWidth=0, borderPadding=0),
        "h3": ParagraphStyle("h3", parent=body, fontName=bold, fontSize=10.5, leading=14,
                             spaceBefore=9, spaceAfter=3),
        "body": body,
        "cell": ParagraphStyle("cell", parent=body, fontSize=8.2, leading=10.5),
        "head": ParagraphStyle("head", parent=body, fontName=bold, fontSize=8.2,
                               leading=10.5),
        "bullet": ParagraphStyle("bullet", parent=body, leftIndent=10, bulletIndent=2,
                                 spaceAfter=2),
        "caption": ParagraphStyle("caption", parent=body, fontSize=8, leading=10,
                                  textColor=GREY, spaceBefore=2, spaceAfter=8),
    }


# --------------------------------------------------------------------------- #
#  Tables and figures
# --------------------------------------------------------------------------- #

def _table_flowable(token: str, st: Dict[str, ParagraphStyle], width: float):
    """One `<table>` of the report as a reportlab table."""
    rows = re.findall(r"<tr>(.*?)</tr>", token, flags=re.S)
    if not rows:
        return None
    parsed, header = [], False
    widths: Optional[List[float]] = None
    for index, row in enumerate(rows):
        cells = re.findall(r"<(t[hd])[^>]*>(.*?)</t[hd]>", row, flags=re.S)
        if not cells:
            continue
        is_head = index == 0 and cells[0][0] == "th"
        header = header or is_head
        style = st["head"] if is_head else st["cell"]
        parsed.append([Paragraph(_inline(body) or "&nbsp;", style) for _, body in cells])
        if is_head:
            percents = [float(m) for m in re.findall(r"width='(\d+)%'", row)]
            if len(percents) == len(cells) and sum(percents) > 0:
                widths = [width * p / sum(percents) for p in percents]
    if not parsed:
        return None
    columns = max(len(row) for row in parsed)
    for row in parsed:                       # square the table off
        row += [Paragraph("&nbsp;", st["cell"])] * (columns - len(row))
    if widths is None or len(widths) != columns:
        widths = [width / columns] * columns

    table = Table(parsed, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
    table.setStyle(TableStyle(commands))
    return table


def _image_flowable(png: bytes, width: float, max_height: float):
    """A figure scaled to the text width, and to the page if it is tall."""
    from reportlab.lib.utils import ImageReader
    reader = ImageReader(io.BytesIO(png))
    natural_width, natural_height = reader.getSize()
    scale = min(width / natural_width, max_height / natural_height)
    return Image(io.BytesIO(png), width=natural_width * scale,
                 height=natural_height * scale)


# --------------------------------------------------------------------------- #
#  The walker
# --------------------------------------------------------------------------- #

_TOKENS = re.compile(
    r"(<h1>.*?</h1>|<h2[^>]*>.*?</h2>|<h3>.*?</h3>|<table[^>]*>.*?</table>|"
    r"<p[^>]*>.*?</p>|<li>.*?</li>)", flags=re.S)


def flowables(html_text: str, figures: Dict[str, bytes], st: Dict[str, ParagraphStyle],
              width: float, height: float) -> list:
    """The report HTML as a list of reportlab flowables."""
    story: list = []
    for token in _TOKENS.split(html_text):
        if token.startswith("<h1>"):
            story.append(Paragraph(_plain(token), st["title"]))
        elif token.startswith("<h2"):
            if "page-break-before" in token and story:
                story.append(PageBreak())
            story.append(Paragraph(_plain(token), st["h2"]))
        elif token.startswith("<h3>"):
            story.append(Paragraph(_plain(token), st["h3"]))
        elif token.startswith("<li>"):
            story.append(Paragraph(_inline(token), st["bullet"], bulletText="•"))
        elif token.startswith("<table"):
            table = _table_flowable(token, st, width)
            if table is not None:
                story += [table, Spacer(1, 6)]
        elif token.startswith("<p"):
            figure = re.search(r"src='fig://([a-z_]+)'", token)
            if figure and figure.group(1) in figures:
                story.append(KeepTogether(
                    _image_flowable(figures[figure.group(1)], width, height * 0.82)))
                story.append(Spacer(1, 8))
            else:
                style = st["meta"] if "class='meta'" in token else st["body"]
                text = _inline(token)
                if text:
                    story.append(Paragraph(text, style))
    return story


def _page_furniture(canvas, doc, footer: str, font: str) -> None:
    """Page number and a one-line footer on every page."""
    canvas.saveState()
    canvas.setFont(font, 7.5)
    canvas.setFillColor(GREY)
    canvas.drawString(MARGIN, 10 * mm, footer)
    canvas.drawRightString(PAGE[0] - MARGIN, 10 * mm, str(canvas.getPageNumber()))
    canvas.setStrokeColor(LINE)
    canvas.line(MARGIN, 13 * mm, PAGE[0] - MARGIN, 13 * mm)
    canvas.restoreState()


def html_to_pdf(path: str, html_text: str, figures: Dict[str, bytes],
                title: str = "", author: str = "", footer: str = "") -> str:
    """Writes the report PDF and returns the path it wrote."""
    st = _styles()
    doc = SimpleDocTemplate(path, pagesize=PAGE, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=18 * mm,
                            title=title or None, author=author or None)
    story = flowables(html_text, figures, st, doc.width, doc.height)
    doc.build(story, onFirstPage=lambda c, d: _page_furniture(c, d, footer, st["font"]),
              onLaterPages=lambda c, d: _page_furniture(c, d, footer, st["font"]))
    return path
