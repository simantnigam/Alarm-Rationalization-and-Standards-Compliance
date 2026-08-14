"""Render rag/documents/_source/ALM-STD-002.md to rag/documents/ALM-STD-002.pdf via
reportlab -- pure Python, no system dependencies; weasyprint needs GTK and would break a
Windows dev box (07-rag-corpus.md §5, 02-phases.md Phase 6 step 5b).

The front matter and every body line are each rendered as their own literal-text
paragraph -- including the `---` delimiters and the `##`/`###` heading markers -- so
rag.ingestion.loader.extract_pdf()'s pypdf-based text extraction can parse the front
matter and detect clause boundaries with the exact same logic used for markdown
sources, just recovered from page text instead of a file read.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

SOURCE = Path(__file__).parent.parent / "rag" / "documents" / "_source" / "ALM-STD-002.md"
OUTPUT = Path(__file__).parent.parent / "rag" / "documents" / "ALM-STD-002.pdf"

_META_STYLE = ParagraphStyle(name="Meta", fontName="Courier", fontSize=9, leading=12)
_TITLE_STYLE = ParagraphStyle(name="Title", fontName="Helvetica-Bold", fontSize=16, spaceAfter=14)
_H2_STYLE = ParagraphStyle(
    name="H2", fontName="Helvetica-Bold", fontSize=13, spaceBefore=14, spaceAfter=8
)
_H3_STYLE = ParagraphStyle(
    name="H3", fontName="Helvetica-Bold", fontSize=11, spaceBefore=10, spaceAfter=6
)
_BODY_STYLE = ParagraphStyle(
    name="Body", fontName="Helvetica", fontSize=10, leading=14, spaceAfter=8
)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(source_path: Path = SOURCE, output_path: Path = OUTPUT) -> None:
    text = source_path.read_text(encoding="utf-8")
    _, front_matter, body = text.split("---", 2)
    body = body.lstrip("\n")

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
    )
    story: list = [Paragraph("---", _META_STYLE)]
    for line in front_matter.strip("\n").splitlines():
        story.append(Paragraph(_escape(line) if line.strip() else "&nbsp;", _META_STYLE))
    story.append(Paragraph("---", _META_STYLE))
    story.append(Spacer(1, 16))

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 4))
        elif line.startswith("# "):
            story.append(Paragraph(_escape(line[2:]), _TITLE_STYLE))
        elif line.startswith("## "):
            story.append(Paragraph(_escape(line), _H2_STYLE))
        elif line.startswith("### "):
            story.append(Paragraph(_escape(line), _H3_STYLE))
        else:
            story.append(Paragraph(_escape(line), _BODY_STYLE))

    doc.build(story)


def main() -> None:  # pragma: no cover -- thin CLI wrapper
    build_pdf()
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":  # pragma: no cover
    main()
