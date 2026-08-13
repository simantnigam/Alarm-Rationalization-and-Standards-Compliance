"""Loads a document's YAML front matter and body. Markdown only for now; Phase 6 adds
a format-dispatching extract() for the PDF-sourced document (2.3.x)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml


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


def _split_front_matter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        raise ValueError("document is missing YAML front matter")
    _, front_matter, body = text.split("---", 2)
    return front_matter, body.lstrip("\n")


def load_markdown(path: Path) -> LoadedDocument:
    text = path.read_text(encoding="utf-8")
    front_matter_text, body = _split_front_matter(text)
    raw = yaml.safe_load(front_matter_text)

    metadata = DocumentMetadata(
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
    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return LoadedDocument(metadata=metadata, body=body, sha256=sha256)
