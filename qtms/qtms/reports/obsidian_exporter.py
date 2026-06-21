"""Obsidian 'second brain' exporter — writes Markdown notes to QTMS_BRAIN/.

Each note is a plain Markdown file with front-matter-style headers and
wiki-link tags so it drops cleanly into an Obsidian vault.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..app.config import get_config


def _brain() -> Path:
    p = Path(get_config().brain_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_note(title: str, body: str, tags: list[str] | None = None, subfolder: str = "") -> str:
    folder = _brain() / subfolder if subfolder else _brain()
    folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip().replace(" ", "_")
    path = folder / f"{ts}_{safe}.md"
    tag_line = " ".join(f"#{t}" for t in (tags or []))
    header = (
        f"# {title}\n\n"
        f"- created: {datetime.now(timezone.utc).isoformat()}\n"
        f"- tags: {tag_line}\n\n"
        f"> ⚠️ Research artifact. No profit is promised. Live trading disabled by default.\n\n"
        f"---\n\n"
    )
    path.write_text(header + body)
    return str(path)


def md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)
