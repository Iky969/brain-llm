"""Full-text search engine for Brain.

Supports English words, numbers, and identifiers, plus unigram & bigram tokenization
for CJK characters without external dependencies:
- English & alphanumeric: whole lowercase words/tokens
- CJK characters: unigrams + adjacent bigrams
- Weighted scoring: title (3x), tags (2x), body (1x), plus whole-term bonuses.
"""
from __future__ import annotations

import re

from .vault import CJK

WORD_RE = re.compile(r"[A-Za-z0-9_]+")
CJK_RUN_RE = re.compile("[" + CJK + "]+")


def tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase words and CJK unigrams/bigrams."""
    toks: set[str] = set()
    for m in WORD_RE.finditer(text):
        toks.add(m.group(0).lower())
    for run in CJK_RUN_RE.finditer(text):
        s = run.group(0)
        for i in range(len(s)):
            toks.add(s[i])
        for i in range(len(s) - 1):
            toks.add(s[i : i + 2])
    return toks


def build_index(note) -> dict[str, int]:
    idx: dict[str, int] = {}

    def add(text: str, weight: int):
        for t in tokenize(text):
            w = weight * (2 if len(t) > 1 else 1)
            idx[t] = idx.get(t, 0) + w

    add(note.path.stem, 3)
    add(" ".join(note.tags), 2)
    add(note.body, 1)
    return idx


def search(notes, query: str, limit: int = 20):
    q = query.strip()
    if not q:
        return []
    qtoks = tokenize(q)
    raw = q.lower()
    results = []
    for note in notes:
        idx = build_index(note)
        hits = [t for t in qtoks if t in idx]
        if not hits:
            continue
        score = sum(idx[t] for t in hits)
        if raw in note.path.stem.lower():
            score += 12
        if raw in note.content.lower():
            score += 6
        results.append((score, len(hits), note))
    results.sort(key=lambda x: (-x[0], -x[1], x[2].path.stem))
    return results[:limit]


def snippet(text: str, query: str, width: int = 90) -> str:
    raw = query.strip().lower()
    pos = text.lower().find(raw)
    if pos < 0:
        for t in sorted(tokenize(query), key=len, reverse=True):
            p = text.lower().find(t.lower())
            if p >= 0:
                pos = p
                break
    if pos < 0:
        pos = 0
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    s = " ".join(text[start:end].split())
    if start > 0:
        s = "…" + s
    if end < len(text):
        s = s + "…"
    return s
