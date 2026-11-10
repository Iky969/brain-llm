# 🧠 Brain

> English Documentation · [中文文档](README.zh.md) · [Architecture](doc/architecture.md)

**CLI-first Obsidian for LLMs**: Build your second brain with Markdown notes, bi-directional wikilinks, and high-performance full-text search.
Implemented with zero external dependencies using the Python standard library.

---

## 🏛️ Vault Architecture: Core, Brain & Daily

The vault directory (defaults to `~/.brain` or `$BRAIN_VAULT`) organizes memory into distinct tiers:

```
~/.brain/
├── core/                # Core directives, identity & soul [inti brain][soul]
│   ├── soul.md          # Agent identity, persona & foundational guidelines
│   └── memory.md        # Persistent facts & long-term user profile
├── brain/               # Knowledge notes [judul][isi]
│   ├── Concept A.md     # [Title].md holding title and Markdown content
│   └── Concept B.md     # Interconnected with [[wikilinks]] and #tags
├── daily/               # Episodic logs & journal entries
│   └── 2026-11-10.md    # Daily notes auto-created by date
└── README.md            # Vault overview and quick reference
```

- **`core/` [Core Brain / Soul]**: Fundamental directives, persona, and core rules. Managed via `brain core` and MCP tools `brain_get_core` / `brain_save_core`.
- **`brain/` [Title / Content]**: Specific domain knowledge, ideas, documentation, and conceptual notes. Managed via `brain new`, `brain search`, etc.
- **`daily/` [Episodic Journal]**: Daily logs and task lists managed via `brain daily`.

---

## ✨ Features

- 📝 **Markdown Notes**: Clean files with simple frontmatter (`tags` / `aliases`) and standard Markdown formatting.
- 🔗 **Obsidian-Style Wikilinks**: Supports `[[Note]]`, `[[Note|alias]]`, and `[[Note#section]]` with bi-directional backlink tracking.
- 🏷️ **Tagging System**: `#ai`, `#notes/ml`, with support for nested and international tags.
- 🔍 **Full-Text Search Engine**: Fast word-token search with built-in unigram + bigram support for CJK languages (no external tokenizer required). Weighted by title (3x), tags (2x), and content.
- 🕸️ **Interactive & Exportable Graph**: ASCII adjacency view, Graphviz DOT, and JSON exports.
- 📅 **Daily Notes**: Automatic template creation for daily planning and episodic logs.
- 🧊 **Integrity Tools**: Orphan note detection, vault statistics, and rename with automatic global wikilink rewriting.
- 💻 **Interactive REPL**: Run `brain repl` for an interactive shell session.
- 🤖 **MCP Server (Model Context Protocol)**: Seamless long-term memory for Claude Code, Cursor, Codex, and any MCP-compatible AI client.

---

## 🚀 Installation

### One-line Install (Recommended)

Install or update Brain with a single command via `curl | bash`:

```bash
curl -fsSL https://raw.githubusercontent.com/Iky969/brain-llm/main/install.sh | bash
```

### Manual Install via Git

```bash
git clone https://github.com/Iky969/brain-llm.git
cd brain-llm
pip install -e .
```

---

## ⚡ Quick Start

```bash
# 1. Initialize the vault (~/.brain)
brain init

# 2. View or edit core identity [inti brain][soul]
brain core
brain core -e

# 3. Create domain knowledge notes in brain/ [judul][isi]
brain new "Machine Learning" -t ai ml
brain new "Deep Learning" -t ai ml -c "# Deep Learning\n\nBranch of [[Machine Learning]]."

# 4. Search and browse
brain search "learning"     # Full-text search
brain list                  # List notes with folder/category indicator
brain links "Deep Learning" # Inspect forward links and backlinks
brain tags                  # View all tags
brain graph                 # Render ASCII graph (-f dot / -f json also available)
brain stats                 # View vault statistics
brain daily                 # Open or view today's daily log
brain repl                  # Enter interactive shell
```

### Global Options
- `--vault <dir>`: Custom vault directory (defaults to `~/.brain`, or environment variable `BRAIN_VAULT`).
- `EDITOR`: Editor used by `brain open` and `-e` flags (e.g. `export EDITOR=nano`).

---

## 📖 CLI Command Reference

| Command | Aliases | Description |
| --- | --- | --- |
| `init` | `initialize`, `初始化` | Initialize or verify vault structure (`core/`, `brain/`, `daily/`) |
| `core [name]` | `soul`, `inti` | View, edit (`-e`), set (`-s`), or list (`-l`) core soul memory |
| `new <title>` | `create`, `add`, `新建` | Create note in `brain/` (`-c` content, `-t` tags, `-e` edit, `--folder`) |
| `open <title>` | `edit`, `打开` | Open note in `$EDITOR` |
| `show <title>` | `view`, `cat`, `read`, `查看` | Display note content (`--raw` for unhighlighted output) |
| `list` | `ls`, `列表` | List notes with folder and tag columns (`-n` limit, `--folder`) |
| `search <query>` | `find`, `grep`, `搜索` | Full-text search across all notes (`-n` limit) |
| `delete <title>` | `rm`, `remove`, `删除` | Delete note (`-f` to skip confirmation) |
| `rename <old> <new>` | `mv`, `重命名` | Rename note and rewrite all `[[wikilinks]]` in the vault |
| `links <title>` | `backlinks`, `链接` | Inspect outlinks and incoming backlinks |
| `tags [tag]` | `tag`, `标签` | List all tags or filter notes by a tag |
| `daily` | `today`, `journal`, `日记` | View or create today's daily log (`-e` to edit) |
| `graph` | `图谱` | Export link graph (`-f ascii\|dot\|json`, `-o <file>`) |
| `orphans` | `孤立` | List orphan notes (notes with no inlinks or outlinks) |
| `stats` | `status`, `info`, `统计` | Vault statistics (notes, links, tags, orphans) |
| `repl` | `shell`, `interactive`, `交互` | Enter interactive REPL shell |
| `mcp` | `serve` | Launch MCP stdio server for LLM integration |

---

## 🤖 LLM & MCP Integration

Brain provides a built-in MCP (Model Context Protocol) server exposing tools for LLM agents:

- `brain_get_core`: Retrieve core directives and soul identity.
- `brain_save_core`: Update core persona and persistent directives.
- `brain_search`: Full-text search across all notes with relevance scoring and snippets.
- `brain_get`: Fetch the full Markdown content of a note.
- `brain_save`: Create or update a note in the knowledge base.
- `brain_delete`: Delete a note.
- `brain_list`: List notes with category and tag filtering.
- `brain_daily`: Retrieve or append to today's daily log.
- `brain_links`: Inspect forward links and backlinks.
- `brain_graph`: Export link graph for contextual graph navigation.
- `brain_tags`: View tags index.
- `brain_stats`: Overview of vault health and stats.

### Claude Code Setup

```bash
claude mcp add brain -- brain --vault ~/.brain mcp
```

### Cursor Setup (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "brain": {
      "command": "brain",
      "args": ["--vault", "/home/your_user/.brain", "mcp"]
    }
  }
}
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) © 2026 Iky969.
