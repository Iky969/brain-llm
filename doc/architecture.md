# 🧠 Architecture Documentation

Brain is a three-tiered CLI knowledge base designed as a persistent "second brain" for LLMs:
- **Presentation Layer**: CLI interface and interactive REPL (`brain/cli.py`).
- **Domain Layer**: Core vault engine, notes parser, full-text search, and link graph (`brain/vault.py`, `brain/search.py`, `brain/graph.py`).
- **Protocol Layer**: Model Context Protocol (MCP) server exposing tools to LLMs (`brain/mcp.py`).

The domain layer is completely decoupled from presentation and protocols: the same markdown note engine drives both local command-line operations and automated LLM agent tool calls.

---

## 1. Vault Directory Topology

The vault is divided into three functional memory tiers:

```
~/.brain/
├── core/                # Core directives, identity & soul [inti brain][soul]
│   ├── soul.md          # AI personality, directives & foundational rules
│   └── memory.md        # Persistent facts & long-term user profile
├── brain/               # Knowledge notes [judul][isi]
│   ├── NoteA.md         # [Title].md holding title and Markdown content
│   └── NoteB.md         # Connected via [[wikilinks]] and #tags
├── daily/               # Episodic logs & journal entries
│   └── YYYY-MM-DD.md    # Daily notes auto-created by date
└── README.md            # Vault overview and quick reference
```

- **`core/` [Core Brain / Soul]**: Foundational identity and instructions. Managed directly via `brain core` and MCP tools `brain_get_core` / `brain_save_core`.
- **`brain/` [Title / Content]**: Specific concepts, domain documentation, and interconnected ideas. Managed via `brain new`, `brain search`, `brain list`, etc.
- **`daily/` [Episodic Memory]**: Time-stamped daily logs for tracking tasks and reflections. Managed via `brain daily`.

---

## 2. Module Layering

```
brain/
├── cli.py      Presentation: Argument parsing, terminal styling, interactive REPL
├── vault.py    Domain Core: Note parsing, wikilinks, tags, CRUD operations
├── search.py   Domain: Full-text indexing, tokenization, ranking, snippets
├── graph.py    Domain: Bi-directional link graph (ASCII / DOT / JSON)
└── mcp.py      Protocol: MCP stdio JSON-RPC server exposing tools to LLMs
```

Dependencies flow strictly inward:

```
cli.py ──→ vault.py ←── mcp.py
   │           ↑
   └──→ search.py / graph.py
```

`vault` has no dependency on `cli` or `mcp`. This allows the memory engine to be integrated into any frontend, background daemon, or custom agent loop.

---

## 3. Data Models (`brain/vault.py`)

### `Note` (Data Class)
- `path`: `pathlib.Path` pointing to the markdown file on disk.
- `content`: Raw content of the markdown file.
- `body`: Content stripped of YAML frontmatter.
- `front`: Parsed dictionary of frontmatter keys (`tags`, `aliases`).
- `tags`: Extracted unique lowercase tags (from frontmatter and `#tag` occurrences).
- `links`: Target note stems extracted from `[[wikilinks]]` (ignoring section anchors and aliases).
- `folder`: Subfolder name relative to vault root (`core`, `brain`, `daily`, or root).
- `category`: Category string (`folder` or `"root"`).
- `mtime`: File modification timestamp.

### `Vault` (Knowledge Base Repository)
- `ensure()`: Creates directory structure (`core/`, `brain/`, `daily/`) and default `core/soul.md`.
- `notes(folder=None)`: Recursively scans `.md` files, ignoring hidden directories.
- `find(name)`: Searches note by stem, relative path, or case-insensitive name.
- `create(title, content, tags, folder)`: Creates note inside designated folder (default `brain/`).
- `get_core(name)` / `save_core(name, content)`: Dedicated helpers for core soul memory.
- `resolve_map()`: Case-insensitive map of lowercase title to canonical stem.
- `outlinks(note)` / `backlinks(title)`: Bi-directional link relationships.
- `rename(old, new)`: Renames file and updates every `[[old]]` wikilink in all vault notes.
- `stats()`: Returns total notes, core notes, brain notes, daily notes, link counts, and tags.

The file system is the database: no external SQL or key-value store is required. Any text editor can modify files directly.

---

## 4. End-to-End Command Flow: `brain search "machine learning"`

1. `cli.py` uses `argparse` to parse the command and flags.
2. `Vault(path)` locates the repository directory.
3. `cmd_search` queries `vault.notes()`, scanning the directory. Each note is parsed:
   - Strips YAML frontmatter.
   - Strips code blocks and inline code (preventing code examples from registering as real wikilinks).
   - Regex-extracts `#tags` and `[[wikilinks]]`.
4. `search()` dynamically indexes notes:
   - English words are tokenized by `[A-Za-z0-9_]+`.
   - CJK text is tokenized into unigrams and bigrams.
   - Weights: Title (3x), Tags (2x), Content (1x). Bigrams receive a multiplier over unigrams.
5. Exact matches in titles (+12) and bodies (+6) receive bonus scores.
6. `snippet()` extracts relevant context around matches.
7. `cli.py` highlights terms and outputs formatted results.

---

## 5. Wikilink Engine

Obsidian-compatible wikilinks follow standard syntax:
- `[[Title]]`: Direct link to another note.
- `[[Title|Alias]]`: Custom display alias.
- `[[Title#Section]]`: Anchor link to a specific header.

### Link Resolution & Backlinks
- `resolve_map()` dynamically builds a lowercase lookup table across all notes in `core/`, `brain/`, and `daily/`.
- When note `A` links to `[[B]]`, `outlinks(A)` maps `B` to its canonical note.
- `backlinks(B)` scans all notes in the vault whose `links` point to `B`.

### Global Renaming with Link Rewrite
When `vault.rename("Old", "New")` is invoked:
1. The physical file is moved to the new filename.
2. All notes across all folders (`core/`, `brain/`, `daily/`) are inspected.
3. Regular expression matches on `[[Old]]`, `[[Old|Alias]]`, and `[[Old#Section]]` are updated to `[[New]]`, preserving aliases and anchors.
4. Changed notes are saved back to disk.

---

## 6. Full-Text Search Engine (`brain/search.py`)

Brain implements a zero-dependency inverted index built on demand:
- **English**: Tokenized by whole words and numbers in lowercase.
- **CJK**: Tokenized by unigrams (individual characters) and bigrams (two-character pairs).
- **No external tokenizers**: Avoids dependencies on heavy NLP packages (e.g., `jieba`, `nltk`) while maintaining fast performance and multilingual tolerance.

---

## 7. Model Context Protocol (MCP) Protocol Layer (`brain/mcp.py`)

The built-in MCP server adheres to the Model Context Protocol (JSON-RPC 2.0 over standard I/O):
- Transport: `stdin` / `stdout`, newline-delimited JSON.
- Handlers:
  - `initialize`: Returns capabilities, protocol version, and server instructions.
  - `tools/list`: Exposes tools for LLM use (`brain_get_core`, `brain_save_core`, `brain_search`, `brain_get`, `brain_save`, `brain_delete`, `brain_list`, `brain_daily`, `brain_links`, `brain_graph`, `brain_orphans`, `brain_stats`, `brain_tags`).
  - `tools/call`: Dispatches function calls directly into `Vault` methods.
