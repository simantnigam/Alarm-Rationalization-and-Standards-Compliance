"""Loads a document's YAML front matter and body. `extract()` (07-rag-corpus.md §5,
2.3.x traceability) format-dispatches on suffix: `.pdf` sources go through pypdf
page-by-page text extraction (front matter and clause headings round-trip as literal
text -- see scripts/build_pdf_corpus.py), everything else through load_markdown().
Page numbers matter only for PDF sources, so `clause_pages` stays None for markdown.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pypdf import PdfReader

from rag.ingestion.chunker import CLAUSE_RE


@dataclass(frozen=True)
class DocumentMetadata:
    doc_id: str
    title: str
    doc_type: str
    version: str
    effective_date: date
    approval_status: str
    site_scope: str
    unit_scope: str
    owner: str
    source_note: str
    supersedes: str | None = None
    superseded_by: str | None = None


@dataclass(frozen=True)
class LoadedDocument:
    metadata: DocumentMetadata
    body: str
    sha256: str
    # clause_id -> 1-indexed page number. Only populated for PDF sources; a citation
    # into a markdown document never carries a page.
    clause_pages: dict[str, int] | None = None


def _split_front_matter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        raise ValueError("document is missing YAML front matter")
    _, front_matter, body = text.split("---", 2)
    return front_matter, body.lstrip("\n")


def _metadata_from_raw(raw: dict[str, Any]) -> DocumentMetadata:
    return DocumentMetadata(
        doc_id=raw["doc_id"],
        title=raw["title"],
        doc_type=raw["doc_type"],
        version=str(raw["version"]),
        effective_date=raw["effective_date"],
        approval_status=raw["approval_status"],
        site_scope=raw["site_scope"],
        unit_scope=raw["unit_scope"],
        owner=raw["owner"],
        source_note=raw["source_note"],
        supersedes=raw.get("supersedes"),
        superseded_by=raw.get("superseded_by"),
    )


def load_markdown(path: Path) -> LoadedDocument:
    text = path.read_text(encoding="utf-8")
    front_matter_text, body = _split_front_matter(text)
    raw = yaml.safe_load(front_matter_text)

    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return LoadedDocument(metadata=_metadata_from_raw(raw), body=body, sha256=sha256)


def extract_pdf(path: Path) -> LoadedDocument:
    reader = PdfReader(path)
    pages_text = [page.extract_text() for page in reader.pages]

    front_matter_text, body = _split_front_matter("\n".join(pages_text))
    raw = yaml.safe_load(front_matter_text)

    clause_pages: dict[str, int] = {}
    for page_number, page_text in enumerate(pages_text, start=1):
        for line in page_text.splitlines():
            match = CLAUSE_RE.match(line)
            if match:
                clause_pages.setdefault(match.group(1), page_number)

    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return LoadedDocument(
        metadata=_metadata_from_raw(raw), body=body, sha256=sha256, clause_pages=clause_pages
    )


def extract(path: Path) -> LoadedDocument:
    if path.suffix.lower() == ".pdf":
        return extract_pdf(path)
    return load_markdown(path)
