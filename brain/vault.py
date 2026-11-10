"""🧠 大脑 —— 知识库核心。

笔记以 Markdown 文件存储在 vault(仓库)目录中,支持:
- Obsidian 风格 ``[[双向链接]]``(含 ``|别名`` 与 ``#小节``)
- ``#标签``(支持中文标签)
- 简易 YAML frontmatter(``tags`` / ``aliases``)
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
    "CJK",
    "LINK_RE",
]

CJK = "㐀-䶿一-鿿豈-﫿"
LINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")
TAG_RE = re.compile(r"(?<![\w#/])#([A-Za-z0-9_/" + CJK + r"-]+)")
FRONT_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.S)
FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
MD_SUFFIXES = (".md", ".markdown")
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

README_TEMPLATE = """# 🧠 大脑知识库

这是「大脑」的默认仓库。所有笔记均为 Markdown 文件,支持 `[[双向链接]]` 与「标签」系统。

## 常用命令

- `brain 新建 "标题"` 创建笔记
- `brain 搜索 "关键词"` 中文全文搜索
- `brain 列表` 浏览全部笔记
- `brain 链接 "标题"` 查看反向链接
- `brain 图谱` 导出链接图谱
- `brain 交互` 进入交互式 shell
- `brain mcp` 启动 MCP 服务(供 LLM 客户端使用)
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

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def title(self) -> str:
        return self.path.stem

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
    """去掉围栏代码块与行内代码,避免把示例中的 [[链接]] / #标签 当作真内容。"""
    return INLINE_CODE_RE.sub(" ", FENCE_RE.sub(" ", text))


def parse_note(path) -> Note:
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
    )


def note_template(title: str, tags=None) -> str:
    today = datetime.date.today().isoformat()
    tagline = " ".join("#" + t for t in (tags or []))
    return (
        f"# {title}\n\n"
        f"<!-- 创建:{today} -->\n\n"
        f"{tagline}\n\n"
        f"## 概要\n\n## 笔记\n\n## 相关链接\n"
    )


def daily_template(date=None) -> str:
    d = date or datetime.date.today()
    return (
        f"# {d.isoformat()} {WEEKDAYS[d.weekday()]}\n\n"
        "## 今日计划\n\n## 记录\n\n## 灵感\n\n## 链接\n"
    )


class Vault:
    """知识库仓库:一组 Markdown 笔记的集合。"""

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
        self.path.mkdir(parents=True, exist_ok=True)
        readme = self.path / "README.md"
        if not readme.exists():
            readme.write_text(README_TEMPLATE, encoding="utf-8")
        self.invalidate_cache()

    @staticmethod
    def safe_filename(title: str) -> str:
        name = re.sub(r'[\\/:*?"<>|]', "_", str(title)).strip().strip(". ")
        return (name or "未命名") + ".md"

    def notes(self) -> list:
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
            out.append(parse_note(p))
        return out

    def find(self, name):
        if name is None:
            return None
        n = str(name).strip()
        if n.lower().endswith(".md"):
            n = n[:-3]
        if not n:
            return None
        direct = self.path / self.safe_filename(n)
        if direct.is_file():
            return parse_note(direct)
        notes = self.notes()
        for note in notes:
            if note.path.stem == n:
                return note
        low = n.lower()
        for note in notes:
            if note.path.stem.lower() == low:
                return note
        return None

    def create(self, title, content=None, tags=None):
        title = str(title).strip()
        if not title:
            raise ValueError("笔记标题不能为空")
        path = self.path / self.safe_filename(title)
        if path.exists():
            raise FileExistsError(str(path))
        if content is None:
            content = note_template(title, tags)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.invalidate_cache()
        return parse_note(path)

    def save(self, note, content):
        note.path.parent.mkdir(parents=True, exist_ok=True)
        note.path.write_text(content, encoding="utf-8")
        self.invalidate_cache()
        return parse_note(note.path)

    def delete(self, note):
        note.path.unlink()
        self.invalidate_cache()

    def rename(self, old_title, new_title):
        note = self.find(old_title)
        if note is None:
            raise FileNotFoundError(old_title)
        new_title = str(new_title).strip()
        if not new_title:
            raise ValueError("新标题不能为空")
        new_path = self.path / self.safe_filename(new_title)
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
        return parse_note(new_path), changed

    def resolve_map(self):
        return {n.path.stem.lower(): n.path.stem for n in self.notes()}

    def _rmap(self):
        if self._rmap_cache is None:
            self._rmap_cache = self.resolve_map()
        return self._rmap_cache

    def resolve_link(self, target):
        target = str(target).split("|", 1)[0].split("#", 1)[0].strip()
        if not target:
            return None
        return self._rmap().get(target.lower())

    def outlinks(self, note):
        out = []
        seen = set()
        for raw in note.links:
            resolved = self.resolve_link(raw)
            key = (raw, resolved)
            if key not in seen:
                seen.add(key)
                out.append((raw, resolved))
        return out

    def backlinks(self, title):
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

    def tags_index(self):
        idx = {}
        for n in self.notes():
            for t in n.tags:
                idx.setdefault(t, []).append(n)
        return idx

    def daily_path(self, date=None):
        d = date or datetime.date.today()
        return self.path / f"{d.isoformat()}.md"

    def stats(self):
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
            if not inn.get(n.path.stem) and not outn.get(n.path.stem)
        ]
        return {
            "笔记总数": len(notes),
            "总字数": sum(len(n.content) for n in notes),
            "链接总数": resolved + broken,
            "有效链接": resolved,
            "失效链接": broken,
            "标签总数": len(self.tags_index()),
            "孤立笔记": len(orphans),
            "仓库路径": str(self.path),
        }
