"""Structure-aware chunking: one chunk per table, metric, issue or glossary doc.

Chunks follow the shape of the source instead of fixed-size windows, so a
retrieved chunk is always a complete, citable unit.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Chunk:
    chunk_id: str
    source_type: str
    source_path: str
    title: str
    content: str
    table_names: list[str]
    metadata: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def chunk_tables(path: Path, root: Path) -> list[Chunk]:
    doc = yaml.safe_load(path.read_text())
    chunks = []
    for model in doc["models"]:
        table = f"analytics.{model['name']}"
        meta = model.get("meta", {})
        lines = [f"Table {table}", model["description"].strip()]
        if meta.get("deprecated"):
            lines.insert(1, "STATUS: DEPRECATED - do not use.")
        lines.append("Columns:")
        lines += [f"- {c['name']}: {c['description']}" for c in model.get("columns", [])]
        chunks.append(Chunk(
            chunk_id=f"table:{table}",
            source_type="table",
            source_path=_rel(path, root),
            title=table,
            content="\n".join(lines),
            table_names=[table],
            metadata=meta,
        ))
    return chunks


def chunk_metrics(path: Path, root: Path) -> list[Chunk]:
    doc = yaml.safe_load(path.read_text())
    chunks = []
    for m in doc["metrics"]:
        lines = [
            f"Metric {m['name']} ({m['label']})",
            f"Synonyms: {', '.join(m.get('synonyms', []))}",
            m["description"].strip(),
            f"SQL: {' '.join(m['sql'].split())}",
            f"Tables: {', '.join(m['tables'])}",
        ]
        chunks.append(Chunk(
            chunk_id=f"metric:{m['name']}",
            source_type="metric",
            source_path=_rel(path, root),
            title=m["label"],
            content="\n".join(lines),
            table_names=list(m["tables"]),
            metadata={"owner": m.get("owner"), "updated_at": m.get("updated_at")},
        ))
    return chunks


def _front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body.strip()


def chunk_markdown(path: Path, root: Path, source_type: str) -> list[Chunk]:
    fm, body = _front_matter(path.read_text())
    doc_id = fm.get("id", path.stem)
    prefix = "OUTDATED DOCUMENT. " if fm.get("outdated") else ""
    return [Chunk(
        chunk_id=f"{source_type}:{doc_id}",
        source_type=source_type,
        source_path=_rel(path, root),
        title=fm.get("title", path.stem),
        content=f"{prefix}{fm.get('title', path.stem)}\n{body}",
        table_names=list(fm.get("tables", [])),
        metadata={k: v for k, v in fm.items() if k not in ("id", "title", "tables")},
    )]


def build_chunks(docs_dir: Path, root: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for p in sorted((docs_dir / "tables").glob("*.yml")):
        chunks += chunk_tables(p, root)
    for p in sorted((docs_dir / "metrics").glob("*.yml")):
        chunks += chunk_metrics(p, root)
    for p in sorted((docs_dir / "issues").glob("*.md")):
        chunks += chunk_markdown(p, root, "issue")
    for p in sorted((docs_dir / "glossary").glob("*.md")):
        chunks += chunk_markdown(p, root, "glossary")
    return chunks
