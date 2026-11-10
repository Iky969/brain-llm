"""MCP (Model Context Protocol) stdio server for Brain.

Exposes the knowledge base as tools for MCP-compliant LLM clients (Claude Code, Cursor, etc.).
Protocol: JSON-RPC 2.0 over standard I/O (newline-delimited JSON).
"""
from __future__ import annotations

import datetime
import json
import sys

from . import __version__
from .vault import Vault, daily_template, soul_template, CORE_DIR, BRAIN_DIR, DAILY_DIR
from .search import search, snippet
from .graph import build_graph, to_dot, to_json, to_ascii

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "brain_list",
        "description": "List notes in the knowledge base (sorted by modification time descending), showing title, category/folder, updated time, and tags.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of notes to return (default 50)"},
                "folder": {
                    "type": "string",
                    "enum": ["brain", "core", "daily"],
                    "description": "Optional folder filter ('brain', 'core', or 'daily')",
                },
            },
            "required": [],
        },
    },
    {
        "name": "brain_search",
        "description": "Full-text search in the knowledge base (unigram + bigram for multilingual recall). Returns matching notes with scores and content snippets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or phrase"},
                "limit": {"type": "integer", "description": "Maximum results to return (default 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "brain_get",
        "description": "Read the full Markdown content and metadata of a note.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title or path (without .md)"}
            },
            "required": ["title"],
        },
    },
    {
        "name": "brain_save",
        "description": "Create or update a note in the knowledge base (write to long-term memory).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title"},
                "content": {"type": "string", "description": "Markdown body content"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of tags",
                },
                "folder": {
                    "type": "string",
                    "enum": ["brain", "core", "daily"],
                    "description": "Target folder (default 'brain')",
                },
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "brain_delete",
        "description": "Delete a note from the knowledge base.",
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Note title to delete"}},
            "required": ["title"],
        },
    },
    {
        "name": "brain_get_core",
        "description": "Read a core soul/directives note (default: 'soul'). Contains the agent's core identity, directives, and fundamental memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Core note name (default 'soul')"}
            },
            "required": [],
        },
    },
    {
        "name": "brain_save_core",
        "description": "Create or update a core soul/directives note in the core/ folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Core note name (default 'soul')"},
                "content": {"type": "string", "description": "Markdown content for core soul memory"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "brain_tags",
        "description": "List all tags and the count of notes under each tag.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "brain_links",
        "description": "View outlinks and backlinks for a note to explore knowledge connections.",
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Note title"}},
            "required": ["title"],
        },
    },
    {
        "name": "brain_graph",
        "description": "Export the knowledge link graph to visualize the second brain.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["ascii", "dot", "json"],
                    "description": "Export format (default 'ascii')",
                }
            },
            "required": [],
        },
    },
    {
        "name": "brain_orphans",
        "description": "List orphan notes (notes with no incoming or outgoing links).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "brain_stats",
        "description": "Retrieve knowledge base statistics (notes count, core notes, links, tags).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "brain_daily",
        "description": "View or initialize today's daily log note for episodic memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Optional content to append or set"}
            },
            "required": [],
        },
    },
]


def dispatch(name: str, args: dict, vault: Vault) -> str:
    args = args or {}
    if name == "brain_list":
        folder = args.get("folder")
        notes = vault.notes(folder=folder)
        notes.sort(key=lambda n: -n.mtime)
        limit = int(args.get("limit", 50))
        lines = [f"Found {len(notes)} note(s):"]
        for n in notes[:limit]:
            tags = " ".join("#" + t for t in n.tags) or "none"
            category = f"[{n.category}]" if n.category else ""
            lines.append(f"- {n.path.stem} {category} ({n.updated}) tags: {tags}")
        return "\n".join(lines)

    if name == "brain_search":
        q = str(args.get("query", "")).strip()
        if not q:
            return "❌ Missing query parameter"
        limit = int(args.get("limit", 10))
        results = search(vault.notes(), q, limit)
        if not results:
            return f'🔍 No notes matching "{q}".'
        lines = [f'🔍 Search "{q}" found {len(results)} result(s):']
        for i, (score, hits, n) in enumerate(results, 1):
            category = f"[{n.category}]" if n.category else ""
            lines.append(
                f"{i}. {n.path.stem} {category} (hits: {hits}, score: {score}, {n.updated})"
            )
            lines.append(f"   {snippet(n.content, q)}")
        return "\n".join(lines)

    if name == "brain_get":
        title = str(args.get("title", "")).strip()
        n = vault.find(title)
        if not n:
            return f'❌ Note "{title}" not found'
        return n.content

    if name == "brain_save":
        title = str(args.get("title", "")).strip()
        content = str(args.get("content", ""))
        folder = str(args.get("folder", BRAIN_DIR)).strip().lower()
        if folder not in (CORE_DIR, BRAIN_DIR, DAILY_DIR):
            folder = BRAIN_DIR
        if not title:
            return "❌ Missing title parameter"
        n = vault.find(title)
        if n:
            vault.save(n, content)
            return f'✅ Updated "{title}" ({len(content)} chars)'
        vault.create(title, content=content, folder=folder)
        return f'✅ Created "{title}" in [{folder}] ({len(content)} chars)'

    if name == "brain_get_core":
        core_name = str(args.get("name", "soul")).strip()
        n = vault.get_core(core_name)
        if not n:
            return f'❌ Core note "{core_name}" not found in core/'
        return n.content

    if name == "brain_save_core":
        core_name = str(args.get("name", "soul")).strip()
        content = str(args.get("content", ""))
        if not content:
            return "❌ Missing content parameter"
        n = vault.save_core(core_name, content=content)
        return f'✅ Saved core note "{core_name}" in core/ ({len(content)} chars)'

    if name == "brain_delete":
        title = str(args.get("title", "")).strip()
        n = vault.find(title)
        if not n:
            return f'❌ Note "{title}" not found'
        vault.delete(n)
        return f'🗑️ Deleted "{title}"'

    if name == "brain_tags":
        idx = vault.tags_index()
        if not idx:
            return "No tags found in vault."
        lines = [f"Found {len(idx)} tag(s):"]
        for t, ns in sorted(idx.items(), key=lambda x: (-len(x[1]), x[0])):
            lines.append(f"- #{t} ({len(ns)} notes)")
        return "\n".join(lines)

    if name == "brain_links":
        title = str(args.get("title", "")).strip()
        n = vault.find(title)
        if not n:
            return f'❌ Note "{title}" not found'
        out = vault.outlinks(n)
        inn = vault.backlinks(n.path.stem)
        lines = [f'Links for "{n.path.stem}":']
        out_txt = ", ".join(
            raw if r else f"{raw} (unresolved)" for raw, r in out
        )
        lines.append("Outlinks: " + (out_txt or "none"))
        lines.append("Backlinks: " + (", ".join(x.path.stem for x in inn) or "none"))
        return "\n".join(lines)

    if name == "brain_graph":
        fmt = str(args.get("format", "ascii")).lower()
        g = build_graph(vault)
        if fmt == "dot":
            return to_dot(g)
        if fmt == "json":
            return to_json(g)
        return to_ascii(g)

    if name == "brain_orphans":
        g = build_graph(vault)
        orphans = sorted(
            t
            for t, n in g.items()
            if not n["inn"]
            and not [r for r in n["out"] if r]
            and t.lower() != "readme"
        )
        if not orphans:
            return "🎉 No orphan notes found. Knowledge graph is well connected."
        lines = [f"Found {len(orphans)} orphan note(s):"]
        lines += [f"- {t}" for t in orphans]
        return "\n".join(lines)

    if name == "brain_stats":
        s = vault.stats()
        return "\n".join(f"{k}: {v}" for k, v in s.items())

    if name == "brain_daily":
        p = vault.daily_path()
        extra_content = args.get("content")
        if not p.exists():
            vault.ensure()
            init_content = daily_template()
            if extra_content:
                init_content += f"\n{extra_content}\n"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(init_content, encoding="utf-8")
            return f"✅ Created today's daily log: {p}"
        if extra_content:
            existing = p.read_text(encoding="utf-8")
            new_content = existing + f"\n{extra_content}\n"
            p.write_text(new_content, encoding="utf-8")
            return f"✅ Appended to today's daily log: {p}"
        return p.read_text(encoding="utf-8")

    return f"❌ Unknown tool: {name}"


def handle(req: dict, vault: Vault):
    method = req.get("method")
    rid = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "brain", "version": __version__},
                "instructions": (
                    "🧠 Brain: CLI-first knowledge base and second brain for LLMs. "
                    "Use brain_get_core/brain_save_core for core identity and soul directives, "
                    "brain_search to recall notes, brain_save to record knowledge, "
                    "and brain_links / brain_graph to navigate relationships."
                ),
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            text = dispatch(name, args, vault)
            is_error = text.startswith("❌")
        except Exception as e:  # noqa: BLE001
            text = f"❌ Tool execution failed: {e}"
            is_error = True
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "content": [{"type": "text", "text": text}],
                "isError": is_error,
            },
        }

    if rid is None:
        return None  # Notifications do not require response

    return {
        "jsonrpc": "2.0",
        "id": rid,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main(vault_path=None):
    vault = Vault(vault_path)
    vault.ensure()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req, vault)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
