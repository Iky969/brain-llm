"""MCP(stdio)服务器:让 LLM 客户端把「大脑」当作记忆插件。

协议:JSON-RPC 2.0,消息按行分隔(每行一个 JSON 对象,不得包含内嵌换行)。
工具列表全部使用中文描述,方便 LLM 理解。
"""
from __future__ import annotations

import datetime
import json
import sys

from . import __version__
from .vault import Vault, daily_template
from .search import search, snippet
from .graph import build_graph, to_dot, to_json, to_ascii

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "brain_list",
        "description": "列出知识库中的全部笔记(按修改时间倒序),返回标题、更新时间与标签。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "最多返回条数,默认 50"}
            },
            "required": [],
        },
    },
    {
        "name": "brain_search",
        "description": "在知识库中做中文全文搜索(单字+二元组分词),返回匹配笔记与内容摘要。这是回忆知识的首选工具。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词,支持中文"},
                "limit": {"type": "integer", "description": "最多返回条数,默认 10"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "brain_get",
        "description": "读取一篇笔记的完整 Markdown 内容。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "笔记标题(不带 .md)"}
            },
            "required": ["title"],
        },
    },
    {
        "name": "brain_save",
        "description": "新建或更新一篇笔记(把重要信息写入长期记忆)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "笔记标题"},
                "content": {"type": "string", "description": "Markdown 正文"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表(可选)",
                },
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "brain_delete",
        "description": "删除一篇笔记。",
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    },
    {
        "name": "brain_tags",
        "description": "列出全部标签及每个标签下的笔记数量。",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "brain_links",
        "description": "查看某篇笔记的出链与反向链接(双向链接),用于发现知识之间的联系。",
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    },
    {
        "name": "brain_graph",
        "description": "导出知识库链接图谱,可观察整个知识结构。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["ascii", "dot", "json"],
                    "description": "输出格式,默认 ascii",
                }
            },
            "required": [],
        },
    },
    {
        "name": "brain_orphans",
        "description": "列出孤立笔记(既无出链也无反向链接),便于补全知识网络。",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "brain_stats",
        "description": "知识库统计信息(笔记数、链接数、标签数等)。",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "brain_daily",
        "description": "获取今日笔记(不存在则自动创建),用于每日记录与复盘。",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


def dispatch(name, args, vault):
    args = args or {}
    if name == "brain_list":
        notes = vault.notes()
        notes.sort(key=lambda n: -n.mtime)
        limit = int(args.get("limit", 50))
        lines = [f"共 {len(notes)} 篇笔记:"]
        for n in notes[:limit]:
            tags = "、".join("#" + t for t in n.tags) or "无"
            lines.append(f"- {n.path.stem}({n.updated})标签:{tags}")
        return "\n".join(lines)

    if name == "brain_search":
        q = str(args.get("query", "")).strip()
        if not q:
            return "❌ 缺少 query 参数"
        limit = int(args.get("limit", 10))
        results = search(vault.notes(), q, limit)
        if not results:
            return f"🔍「{q}」没有匹配的笔记。"
        lines = [f"🔍「{q}」共 {len(results)} 条结果:"]
        for i, (score, hits, n) in enumerate(results, 1):
            lines.append(
                f"{i}. {n.path.stem}(匹配 {hits} 项,得分 {score},{n.updated})"
            )
            lines.append(f"   {snippet(n.content, q)}")
        return "\n".join(lines)

    if name == "brain_get":
        title = str(args.get("title", "")).strip()
        n = vault.find(title)
        if not n:
            return f"❌ 找不到笔记《{title}》"
        return n.content

    if name == "brain_save":
        title = str(args.get("title", "")).strip()
        content = str(args.get("content", ""))
        if not title:
            return "❌ 缺少 title 参数"
        n = vault.find(title)
        if n:
            vault.save(n, content)
            return f"✅ 已更新《{title}》({len(content)} 字符)"
        vault.create(title, content=content)
        return f"✅ 已创建《{title}》({len(content)} 字符)"

    if name == "brain_delete":
        title = str(args.get("title", "")).strip()
        n = vault.find(title)
        if not n:
            return f"❌ 找不到笔记《{title}》"
        vault.delete(n)
        return f"🗑️ 已删除《{title}》"

    if name == "brain_tags":
        idx = vault.tags_index()
        if not idx:
            return "(知识库中暂无标签)"
        lines = [f"共 {len(idx)} 个标签:"]
        for t, ns in sorted(idx.items(), key=lambda x: (-len(x[1]), x[0])):
            lines.append(f"- #{t}({len(ns)} 篇)")
        return "\n".join(lines)

    if name == "brain_links":
        title = str(args.get("title", "")).strip()
        n = vault.find(title)
        if not n:
            return f"❌ 找不到笔记《{title}》"
        out = vault.outlinks(n)
        inn = vault.backlinks(n.path.stem)
        lines = [f"《{n.path.stem}》的链接关系:"]
        out_txt = "、".join(
            raw if r else f"{raw}(未找到笔记)" for raw, r in out
        )
        lines.append("出链:" + (out_txt or "无"))
        lines.append("反向链接:" + ("、".join(x.path.stem for x in inn) or "无"))
        return "\n".join(lines)

    if name == "brain_graph":
        fmt = str(args.get("format", "ascii"))
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
            if not n["inn"] and not [r for r in n["out"] if r]
        )
        if not orphans:
            return "🎉 没有孤立笔记,知识网络很健康。"
        lines = [f"孤立笔记(无出链也无反向链接)共 {len(orphans)} 篇:"]
        lines += [f"- {t}" for t in orphans]
        return "\n".join(lines)

    if name == "brain_stats":
        s = vault.stats()
        return "\n".join(f"{k}:{v}" for k, v in s.items())

    if name == "brain_daily":
        p = vault.daily_path()
        if not p.exists():
            vault.create(p.stem, content=daily_template())
            return f"✅ 已创建今日笔记:{p}"
        return p.read_text(encoding="utf-8")

    return f"❌ 未知工具:{name}"


def handle(req, vault):
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
                    "🧠 大脑:面向 LLM 的 CLI 知识库(类 Obsidian)。"
                    "用 brain_search 回忆知识、brain_save 写入记忆、"
                    "brain_links / brain_graph 探索知识联系。"
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
            text = f"❌ 工具执行失败:{e}"
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
        return None  # 通知(notification)无需响应

    return {
        "jsonrpc": "2.0",
        "id": rid,
        "error": {"code": -32601, "message": f"未知方法:{method}"},
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
