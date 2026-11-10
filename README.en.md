# 🧠 Brain

> [中文文档](README.md) · English README · [Architecture](doc/architecture.md)

The **CLI version of Obsidian for LLMs**: build your second brain with Markdown
notes, wikilinks, and Chinese full-text search.
Pure Python standard library, zero third-party dependencies.

## Features

- 📝 **Markdown notes**: filename is the title, simple frontmatter (`tags` / `aliases`) supported
- 🔗 **Obsidian-style wikilinks**: `[[Note]]`, `[[Note|alias]]`, `[[Note#section]]`, with backlinks
- 🏷️ **Tags**: `#人工智能`, `#笔记/ML`, Chinese tags supported
- 🔍 **Chinese full-text search**: unigram + bigram tokenization, no jieba needed; titles/tags weighted
- 🕸️ **Link graph**: ASCII adjacency list / Graphviz DOT / JSON
- 📅 **Daily notes**, auto-created
- 🧊 **Orphan detection**, 📊 stats, ✏️ rename with automatic link rewrites
- 💻 **Interactive shell**: `brain 交互` (Chinese) / `brain repl`
- 🤖 **MCP server**: 11 Chinese tools for any MCP-capable LLM client
  (Claude Code, Cursor, ...) to use Brain as long-term memory

## Installation

```bash
cd brain-llm
python3 -m venv .venv
.venv/bin/pip install -e .
# now the brain command is available (.venv/bin/brain)
```

## Quick Start

```bash
brain --vault ~/.brain 初始化

brain 新建 "机器学习基础" -t 人工智能 笔记
brain 新建 "深度学习" -t 人工智能
# edit the notes, add [[机器学习基础]] and #人工智能

brain 搜索 "人工智能"        # Chinese full-text search
brain 列表                   # all notes (by modification time)
brain 链接 "机器学习基础"     # outlinks and backlinks
brain 标签                   # all tags
brain 图谱                   # ASCII graph (-f dot / -f json)
brain 孤立                   # orphan notes
brain 统计                   # statistics
brain 日记                   # today's note
brain 交互                   # interactive shell
```

Global options:

- `--vault <dir>`: vault location (default `~/.brain`, or env `BRAIN_VAULT`)
- `EDITOR` env var: editor used by `brain 打开` / `-e`

## Commands

| Command | Aliases | Description |
| --- | --- | --- |
| `初始化` | `init` | Initialize the vault directory |
| `新建 <标题>` | `new` | Create a note (`-c` content, `-t` tags, `-e` edit) |
| `打开 <标题>` | `open` | Open in `$EDITOR` |
| `查看 <标题>` | `show` | Show note content (`--raw` for plain output) |
| `列表` | `list`, `ls` | List all notes (`-n` limit) |
| `搜索 <关键词>` | `search` | Chinese full-text search (`-n` limit) |
| `删除 <标题>` | `delete`, `rm` | Delete (`-f` to skip confirmation) |
| `重命名 <旧> <新>` | `rename` | Rename and rewrite every link across the vault |
| `链接 <标题>` | `links` | Outlinks and backlinks |
| `标签 [标签名]` | `tags` | List tags / filter by tag |
| `日记` | `daily` | Show or create today's note |
| `图谱` | `graph` | Export graph (`-f ascii\|dot\|json`, `-o` file) |
| `孤立` | `orphans` | List orphan notes |
| `统计` | `stats` | Vault statistics |
| `交互` | `repl` | Interactive shell |
| `mcp` | `serve` | Run the MCP server (for LLM clients) |

## How the Chinese search works

The query `人工智能` is tokenized into **unigrams** (人/工/智/能) and
**bigrams** (人工/工智/智能), then matched against the same tokenization of
note bodies, titles and tags. More hits = higher score; titles weigh ×3 and
tags ×2. Because unigrams are indexed too, searching `人工智慧` can still
recall a note about `人工智能` (tolerance for variant forms).

## LLM integration (MCP)

Brain ships an MCP server exposing 11 Chinese tools:
`brain_search` / `brain_get` / `brain_save` / `brain_delete` / `brain_list` /
`brain_tags` / `brain_links` / `brain_graph` / `brain_orphans` / `brain_stats` /
`brain_daily`.

**Claude Code:**

```bash
claude mcp add brain -- brain --vault ~/.brain mcp
```

**Cursor (~/.cursor/mcp.json) or any MCP-capable client:**

```json
{
  "mcpServers": {
    "brain": {
      "command": "brain",
      "args": ["--vault", "/home/YOUR_USER/.brain", "mcp"]
    }
  }
}
```

## Vault layout

```
~/.brain/
├── README.md
├── 机器学习基础.md
├── 深度学习.md
└── 2026-11-10.md      # daily note
```

Notes are plain files: edit them with any editor. Links and tags are rebuilt
automatically on the next command.

## Development

```bash
python -m unittest discover -s tests -v   # run tests
python -m brain --vault ~/.brain 搜索 人工智能   # run without installing
```

Architecture design: [doc/architecture.md](doc/architecture.md)
