"""🧠 Brain — Knowledge Base Core Engine.

Notes are stored as Markdown files in the vault directory with:
- Obsidian-style ``[[wikilinks]]`` (including ``|alias`` and ``#section``)
- ``#tags`` (including alphanumeric and international tags)
- Simple YAML frontmatter (``tags`` / ``aliases``)

Vault Directory Structure:
- ``core/``  : Core identity, persona, rules, and soul memory ([inti brain][soul])
- ``brain/`` : Structured knowledge notes ([title][content])
- ``daily/`` : Daily journal and episodic logs (YYYY-MM-DD.md)
"""
from __future__ import annotations

import datetime
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "Note",
    "Vault",
    "parse_note",
    "note_template",
    "daily_template",
    "soul_template",
    "CJK",
    "LINK_RE",
    "CORE_DIR",
    "BRAIN_DIR",
    "DAILY_DIR",
]

CORE_DIR = "core"
BRAIN_DIR = "brain"
DAILY_DIR = "daily"

CJK = "㐀-䶿一-鿿豈-﫿"
LINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")
TAG_RE = re.compile(r"(?<![\w#/])#([A-Za-z0-9_/" + CJK + r"-]+)")
FRONT_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.S)
FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
MD_SUFFIXES = (".md", ".markdown")
WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

DEFAULT_SOUL_TEMPLATE = """# 🧠 Core Soul & Directives

<!-- Created: {today} -->

## Identity
- Name: Brain LLM
- Role: AI Long-Term Memory & Second Brain
- Core Purpose: Retain context, maintain structured knowledge, and preserve continuity across sessions.

## Core Directives
1. Maintain truthfulness, clarity, and concise structure.
2. Interconnect concepts using `[[wikilinks]]`.
3. Categorize topics under `#tags`.
4. Keep identity, persona, and foundational directives in `core/`.
5. Store domain knowledge and general notes (`[Title][Content]`) in `brain/`.
6. Store time-based logs in `daily/`.
"""

README_TEMPLATE = """# 🧠 Brain Vault

This is the default Brain knowledge base repository. All notes are stored as Markdown files with Obsidian-compatible `[[wikilinks]]` and `#tags`.

## Vault Structure
- `core/`  : Core identity, system soul, and persistent directives (`soul.md`, `memory.md`).
- `brain/` : Knowledge notes (`[Title].md`) containing domain concepts and content (`[judul][isi]`).
- `daily/` : Daily journal entries (`YYYY-MM-DD.md`) for episodic memory and logs.

## CLI Commands
- `brain init`               : Initialize or verify vault structure
- `brain core`               : View or edit core soul memory
- `brain new "Title"`        : Create a new note in `brain/`
- `brain search "keyword"`   : Full-text search across all notes
- `brain list`               : Browse all notes with category indicators
- `brain show "Title"`       : View note content
- `brain links "Title"`      : View forward links and backlinks
- `brain graph`              : Export knowledge graph
- `brain daily`              : View or create today's daily log
- `brain repl`               : Interactive shell
- `brain mcp`                : Launch MCP server for LLMs
"""


@dataclass
class Note:
    path: Path
    content: str
    front: dict = field(default_factory=dict)
    body: str = ""
    tags: list = field(default_factory=list)
    links: list = field(default_factory=list)
    mtime: float = 0.0
    folder: str = ""

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def title(self) -> str:
        return self.path.stem

    @property
    def category(self) -> str:
        return self.folder or "root"

    @property
    def updated(self) -> str:
        return datetime.datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M")


def parse_frontmatter(text: str) -> dict:
    front = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key not in ("tags", "aliases"):
            front[key] = val
            continue
        if val.startswith("[") and val.endswith("]"):
            val = val[1:-1]
        items = [x.strip().strip("'\"") for x in val.split(",")]
        front[key] = [x for x in items if x]
    return front


def _strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans to avoid false wikilinks/tags."""
    return INLINE_CODE_RE.sub(" ", FENCE_RE.sub(" ", text))


def parse_note(path, folder: str = "") -> Note:
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    front: dict = {}
    body = content
    m = FRONT_RE.match(content)
    if m:
        front = parse_frontmatter(m.group(1))
        body = content[m.end():]
    tags = []
    seen = set()
    scan = _strip_code(body)
    for t in list(front.get("tags", [])) + TAG_RE.findall(scan):
        t = t.lower()
        if t and t not in seen:
            seen.add(t)
            tags.append(t)
    links = []
    for raw in LINK_RE.findall(scan):
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if target and target not in links:
            links.append(target)
    return Note(
        path=path,
        content=content,
        front=front,
        body=body,
        tags=tags,
        links=links,
        mtime=path.stat().st_mtime,
        folder=folder,
    )


def soul_template() -> str:
    today = datetime.date.today().isoformat()
    return DEFAULT_SOUL_TEMPLATE.format(today=today)


def note_template(title: str, tags=None) -> str:
    today = datetime.date.today().isoformat()
    tagline = " ".join("#" + t for t in (tags or []))
    tag_block = f"{tagline}\n\n" if tagline else ""
    return (
        f"# {title}\n\n"
        f"<!-- Created: {today} -->\n\n"
        f"{tag_block}"
        f"## Overview\n\n## Content\n\n## Related Links\n"
    )


def daily_template(date=None) -> str:
    d = date or datetime.date.today()
    return (
        f"# {d.isoformat()} {WEEKDAYS[d.weekday()]}\n\n"
        "## Today's Plan\n\n## Notes & Logs\n\n## Ideas\n\n## Links\n"
    )


class Vault:
    """Knowledge base vault: organized collection of Markdown notes."""

    def __init__(self, path=None):
        if path is None:
            path = os.environ.get("BRAIN_VAULT", "~/.brain")
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path.cwd() / p
        self.path = p
        self._rmap_cache = None

    def __repr__(self):
        return f"Vault({str(self.path)!r})"

    @property
    def exists(self) -> bool:
        return self.path.is_dir()

    def invalidate_cache(self) -> None:
        self._rmap_cache = None

    def ensure(self) -> None:
        """Create vault root and standard directories: core/, brain/, daily/."""
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / CORE_DIR).mkdir(parents=True, exist_ok=True)
        (self.path / BRAIN_DIR).mkdir(parents=True, exist_ok=True)
        (self.path / DAILY_DIR).mkdir(parents=True, exist_ok=True)

        readme = self.path / "README.md"
        if not readme.exists():
            readme.write_text(README_TEMPLATE, encoding="utf-8")

        soul = self.path / CORE_DIR / "soul.md"
        if not soul.exists():
            soul.write_text(soul_template(), encoding="utf-8")

        self.invalidate_cache()

    @staticmethod
    def safe_filename(title: str) -> str:
        name = re.sub(r'[\\/:*?"<>|]', "_", str(title)).strip().strip(". ")
        return (name or "Untitled") + ".md"

    def notes(self, folder: str | None = None) -> list[Note]:
        """Scan all markdown notes. Can filter by subfolder ('core', 'brain', 'daily')."""
        if not self.path.is_dir():
            return []
        out = []
        for p in sorted(self.path.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix.lower() not in MD_SUFFIXES:
                continue
            rel = p.relative_to(self.path)
            if any(part.startswith(".") for part in rel.parts):
                continue
            note_folder = rel.parts[0] if len(rel.parts) > 1 else ""
            if folder is not None and note_folder != folder:
                continue
            out.append(parse_note(p, folder=note_folder))
        return out

    def find(self, name: str | None) -> Note | None:
        """Find note by stem, relative path, or case-insensitive title."""
        if name is None:
            return None
        n = str(name).strip()
        if n.lower().endswith(".md"):
            n = n[:-3]
        if not n:
            return None

        # Direct check in subfolders or root
        safe_name = self.safe_filename(n)
        for check in (
            self.path / BRAIN_DIR / safe_name,
            self.path / CORE_DIR / safe_name,
            self.path / DAILY_DIR / safe_name,
            self.path / safe_name,
            self.path / (n + ".md"),
        ):
            if check.is_file():
                rel = check.relative_to(self.path)
                folder = rel.parts[0] if len(rel.parts) > 1 else ""
                return parse_note(check, folder=folder)

        notes = self.notes()
        for note in notes:
            if note.path.stem == n:
                return note
        low = n.lower()
        for note in notes:
            if note.path.stem.lower() == low:
                return note
        # Check relative path match e.g. core/soul
        for note in notes:
            rel_stem = str(note.path.relative_to(self.path).with_suffix(""))
            if rel_stem.lower() == low:
                return note
        return None

    def create(self, title: str, content: str | None = None, tags=None, folder: str = BRAIN_DIR) -> Note:
        """Create a new note. Defaults to the brain/ knowledge folder."""
        title = str(title).strip()
        if not title:
            raise ValueError("Note title cannot be empty")

        # Allow prefixing folder in title e.g. "core/custom" or "daily/2026-11-10"
        if "/" in title or "\\" in title:
            parts = re.split(r"[/\\]", title, maxsplit=1)
            if parts[0].lower() in (CORE_DIR, BRAIN_DIR, DAILY_DIR):
                folder = parts[0].lower()
                title = parts[1]

        target_dir = self.path / folder
        path = target_dir / self.safe_filename(title)
        if path.exists():
            raise FileExistsError(str(path))

        if content is None:
            if folder == CORE_DIR and title.lower() == "soul":
                content = soul_template()
            else:
                content = note_template(title, tags)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.invalidate_cache()
        return parse_note(path, folder=folder)

    def get_core(self, name: str = "soul") -> Note | None:
        """Retrieve a note from the core/ [inti brain][soul] folder."""
        safe_name = self.safe_filename(name)
        target = self.path / CORE_DIR / safe_name
        if target.is_file():
            return parse_note(target, folder=CORE_DIR)
        for n in self.notes(folder=CORE_DIR):
            if n.stem.lower() == name.lower():
                return n
        return None

    def save_core(self, name: str = "soul", content: str | None = None) -> Note:
        """Create or update a core soul/directive note."""
        (self.path / CORE_DIR).mkdir(parents=True, exist_ok=True)
        target = self.path / CORE_DIR / self.safe_filename(name)
        if content is None:
            content = soul_template()
        target.write_text(content, encoding="utf-8")
        self.invalidate_cache()
        return parse_note(target, folder=CORE_DIR)

    def core_notes(self) -> list[Note]:
        """Return all notes in the core/ folder."""
        return self.notes(folder=CORE_DIR)

    def brain_notes(self) -> list[Note]:
        """Return all knowledge notes in brain/ (and root non-core/daily notes except README)."""
        all_notes = self.notes()
        return [
            n for n in all_notes
            if n.folder == BRAIN_DIR or (not n.folder and n.stem.lower() != "readme")
        ]

    def daily_notes(self) -> list[Note]:
        """Return all notes in daily/."""
        return self.notes(folder=DAILY_DIR)

    def save(self, note: Note, content: str) -> Note:
        note.path.parent.mkdir(parents=True, exist_ok=True)
        note.path.write_text(content, encoding="utf-8")
        self.invalidate_cache()
        return parse_note(note.path, folder=note.folder)

    def delete(self, note: Note) -> None:
        note.path.unlink()
        self.invalidate_cache()

    def rename(self, old_title: str, new_title: str):
        note = self.find(old_title)
        if note is None:
            raise FileNotFoundError(old_title)
        new_title = str(new_title).strip()
        if not new_title:
            raise ValueError("New title cannot be empty")
        new_path = note.path.parent / self.safe_filename(new_title)
        if new_path.exists() and new_path.resolve() != note.path.resolve():
            raise FileExistsError(str(new_path))
        old = note.path.stem
        if new_path != note.path:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            note.path.rename(new_path)
        changed = 0
        for n in self.notes():
            if n.path == new_path:
                continue

            def fix(m):
                raw = m.group(1)
                parts = re.split(r"([|#])", raw)
                base = parts[0].strip()
                if base == old or base.lower() == old.lower():
                    return "[[" + new_title + "".join(parts[1:]) + "]]"
                return m.group(0)

            new_content = LINK_RE.sub(fix, n.content)
            if new_content != n.content:
                self.save(n, new_content)
                changed += 1
        self.invalidate_cache()
        return parse_note(new_path, folder=note.folder), changed

    def resolve_map(self) -> dict[str, str]:
        return {n.path.stem.lower(): n.path.stem for n in self.notes()}

    def _rmap(self):
        if self._rmap_cache is None:
            self._rmap_cache = self.resolve_map()
        return self._rmap_cache

    def resolve_link(self, target: str) -> str | None:
        target = str(target).split("|", 1)[0].split("#", 1)[0].strip()
        if not target:
            return None
        return self._rmap().get(target.lower())

    def outlinks(self, note: Note) -> list[tuple[str, str | None]]:
        out = []
        seen = set()
        for raw in note.links:
            resolved = self.resolve_link(raw)
            key = (raw, resolved)
            if key not in seen:
                seen.add(key)
                out.append((raw, resolved))
        return out

    def backlinks(self, title: str) -> list[Note]:
        res = []
        rmap = self._rmap()
        for n in self.notes():
            for raw in n.links:
                target = raw.split("|", 1)[0].split("#", 1)[0].strip()
                resolved = rmap.get(target.lower())
                if resolved == title:
                    res.append(n)
                    break
        return res

    def tags_index(self) -> dict[str, list[Note]]:
        idx = {}
        for n in self.notes():
            for t in n.tags:
                idx.setdefault(t, []).append(n)
        return idx

    def daily_path(self, date=None) -> Path:
        d = date or datetime.date.today()
        (self.path / DAILY_DIR).mkdir(parents=True, exist_ok=True)
        return self.path / DAILY_DIR / f"{d.isoformat()}.md"

    def stats(self) -> dict:
        notes = self.notes()
        rmap = self.resolve_map()
        resolved = broken = 0
        inn = {}
        outn = {}
        for n in notes:
            for raw in n.links:
                t = raw.split("|", 1)[0].split("#", 1)[0].strip()
                r = rmap.get(t.lower())
                if r:
                    resolved += 1
                    if r != n.path.stem:
                        inn[r] = inn.get(r, 0) + 1
                        outn[n.path.stem] = outn.get(n.path.stem, 0) + 1
                else:
                    broken += 1
        orphans = [
            n.path.stem
            for n in notes
            if not inn.get(n.path.stem)
            and not outn.get(n.path.stem)
            and n.path.stem.lower() != "readme"
        ]
        return {
            "total_notes": len(notes),
            "core_notes": len(self.core_notes()),
            "brain_notes": len(self.brain_notes()),
            "daily_notes": len(self.daily_notes()),
            "total_chars": sum(len(n.content) for n in notes),
            "total_links": resolved + broken,
            "valid_links": resolved,
            "broken_links": broken,
            "total_tags": len(self.tags_index()),
            "orphan_notes": len(orphans),
            "vault_path": str(self.path),
        }
