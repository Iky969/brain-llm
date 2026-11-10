"""🧠 Brain — Command-line interface and interactive shell."""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys

from . import __version__
from .vault import (
    Vault,
    daily_template,
    soul_template,
    LINK_RE,
    CORE_DIR,
    BRAIN_DIR,
    DAILY_DIR,
)
from .search import search, snippet, tokenize
from .graph import build_graph, to_dot, to_json, to_ascii

TTY = sys.stdout.isatty()


def c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if TTY else str(s)


def bold(s: str) -> str:
    return c("1", s)


def yellow(s: str) -> str:
    return c("33", s)


def green(s: str) -> str:
    return c("32", s)


def cyan(s: str) -> str:
    return c("36", s)


def dim(s: str) -> str:
    return c("2", s)


def dwidth(s: str) -> int:
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in str(s))


def pad(s: str, w: int) -> str:
    s = str(s)
    return s + " " * max(0, w - dwidth(s))


def highlight(text: str, terms, code: str = "33") -> str:
    terms = sorted({str(t).lower() for t in terms if t}, key=len, reverse=True)
    if not terms or not TTY:
        return text
    low = text.lower()
    spans = []
    for t in terms:
        start = 0
        while True:
            i = low.find(t, start)
            if i < 0:
                break
            spans.append((i, i + len(t)))
            start = i + len(t)
    if not spans:
        return text
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    out = []
    pos = 0
    for s, e in merged:
        out.append(text[pos:s])
        out.append(f"\033[{code}m{text[s:e]}\033[0m")
        pos = e
    out.append(text[pos:])
    return "".join(out)


def query_terms(query: str):
    return {query.strip().lower()} | {
        t.lower() for t in tokenize(query) if len(t) > 1
    }


def render_note(note) -> str:
    if not TTY:
        return note.content
    return LINK_RE.sub(lambda m: cyan(m.group(0)), note.content)


def open_editor(vault: Vault, path) -> None:
    editor = os.environ.get("EDITOR", "vi")
    try:
        subprocess.call(shlex.split(editor) + [str(path)])
    except FileNotFoundError:
        print(yellow(f'⚠️  Editor "{editor}" not found. Set EDITOR environment variable.'))
    finally:
        vault.invalidate_cache()


# ─────────────────────────── Command Handlers ───────────────────────────


def cmd_init(vault: Vault, args) -> None:
    vault.ensure()
    print(green(f"🧠 Brain vault ready at: {vault.path}"))
    print(dim("   Structure: core/ [soul & directives] · brain/ [notes] · daily/ [journal]"))
    print(dim('   Tip: Use `brain new "Title"` to create a note, or `brain repl` for interactive shell.'))


def cmd_core(vault: Vault, args) -> None:
    vault.ensure()
    name = getattr(args, "name", "soul") or "soul"
    if getattr(args, "list", False):
        cores = vault.core_notes()
        print(bold(f"🧠 Core Memory ({len(cores)} notes in core/):"))
        for c_note in cores:
            print(f"  - {c_note.path.stem} ({c_note.updated})")
        return

    content_to_set = getattr(args, "set", None)
    if content_to_set is not None:
        content_to_set = content_to_set.replace("\\n", "\n")
        note = vault.save_core(name, content=content_to_set)
        print(green(f'✅ Core note "{note.path.stem}" updated in core/'))
        return

    note = vault.get_core(name)
    if note is None:
        if name.lower() == "soul":
            note = vault.save_core("soul")
        else:
            print(yellow(f'⚠️  Core note "{name}" not found in core/'))
            return

    if getattr(args, "edit", False):
        open_editor(vault, note.path)
    else:
        print(bold(f"🧠 Core Soul [core/{note.path.name}] — {note.updated}"))
        print(dim("─" * 52))
        print(note.content)


def cmd_new(vault: Vault, args) -> None:
    vault.ensure()
    folder = getattr(args, "folder", BRAIN_DIR) or BRAIN_DIR
    content = args.content
    if content:
        content = content.replace("\\n", "\n")
    note = vault.create(
        args.title.strip(),
        content=content,
        tags=args.tags,
        folder=folder,
    )
    print(green(f'✅ Created note: 《{note.path.stem}》 in [{note.category}]'))
    print(dim(f"   {note.path}"))
    if args.edit:
        open_editor(vault, note.path)


def cmd_open(vault: Vault, args) -> None:
    note = vault.find(args.title)
    if note is None:
        print(yellow(f'⚠️  Note "{args.title}" not found'))
        return
    open_editor(vault, note.path)


def cmd_show(vault: Vault, args) -> None:
    note = vault.find(args.title)
    if note is None:
        print(yellow(f'⚠️  Note "{args.title}" not found'))
        return
    meta = (
        f"《{note.path.stem}》 [{note.category}] {note.updated}  "
        f"Tags: {(' '.join('#' + t for t in note.tags)) or 'none'}  "
        f"Links: {len(note.links)}"
    )
    print(dim(meta))
    print(dim("─" * 52))
    print(note.content if args.raw else render_note(note))


def cmd_list(vault: Vault, args) -> None:
    folder = getattr(args, "folder", None)
    notes = vault.notes(folder=folder)
    if not notes:
        print(dim("(Vault is empty)"))
        return
    notes.sort(key=lambda n: -n.mtime)
    rmap = vault.resolve_map()
    inlink = {}
    for n in notes:
        for raw in n.links:
            t = raw.split("|", 1)[0].split("#", 1)[0].strip()
            r = rmap.get(t.lower())
            if r:
                inlink[r] = inlink.get(r, 0) + 1
    folder_str = f" in [{folder}]" if folder else ""
    print(bold(f"📚 {len(notes)} note(s){folder_str}") + dim(f" (vault: {vault.path})"))
    print(dim(pad("Title", 26) + pad("Folder", 10) + pad("Updated", 17) + pad("Inlinks", 9) + "Tags"))
    print(dim("─" * 74))
    for n in notes[: args.limit or len(notes)]:
        tags = " ".join("#" + t for t in n.tags)
        print(
            pad(n.path.stem, 26)
            + pad(f"[{n.category}]", 10)
            + pad(n.updated, 17)
            + pad(str(inlink.get(n.path.stem, 0)), 9)
            + dim(tags)
        )


def cmd_search(vault: Vault, args) -> None:
    q = args.query.strip()
    if not q:
        print(yellow("⚠️  Please provide a search query"))
        return
    results = search(vault.notes(), q, args.limit)
    if not results:
        print(dim(f'🔍 No notes matching "{q}".'))
        return
    terms = query_terms(q)
    print(bold(f'🔍 Search "{q}"') + dim(f" — found {len(results)} result(s)"))
    print()
    for i, (score, hits, n) in enumerate(results, 1):
        title = highlight(n.path.stem, [q]) if TTY else n.path.stem
        category = f"[{n.category}] " if n.category else ""
        print(
            f"{bold(str(i) + '.')} {category}《{title}》 "
            + dim(f"hits: {hits} · score: {score} · {n.updated}")
        )
        print("   " + highlight(snippet(n.content, q), terms))
        print()


def cmd_delete(vault: Vault, args) -> None:
    note = vault.find(args.title)
    if note is None:
        print(yellow(f'⚠️  Note "{args.title}" not found'))
        return
    if not args.force:
        ans = input(f'Are you sure you want to delete "{note.path.stem}"? [y/N] ').strip().lower()
        if ans not in ("y", "yes"):
            print(dim("Cancelled"))
            return
    affected = [n.path.stem for n in vault.backlinks(note.path.stem)]
    vault.delete(note)
    print(green(f'🗑️  Deleted "{note.path.stem}"'))
    if affected:
        print(dim(f"   Note: {len(affected)} note(s) linked to it: " + ", ".join(affected)))


def cmd_rename(vault: Vault, args) -> None:
    new_note, changed = vault.rename(args.old, args.new)
    print(green(f'✏️  Renamed: "{args.old}" → "{new_note.path.stem}"'))
    if changed:
        print(dim(f"   Updated wikilinks in {changed} note(s)"))


def cmd_links(vault: Vault, args) -> None:
    note = vault.find(args.title)
    if note is None:
        print(yellow(f'⚠️  Note "{args.title}" not found'))
        return
    out = vault.outlinks(note)
    inn = vault.backlinks(note.path.stem)
    print(bold(f'🔗 Links for "{note.path.stem}" [{note.category}]'))
    print(dim("Outlinks:"))
    if out:
        for raw, r in out:
            mark = green("✓") if r else yellow("✗")
            tail = "" if r else dim(" (unresolved)")
            print(f"  {mark} {raw}{tail}")
    else:
        print(dim("  (none)"))
    print(dim("Backlinks:"))
    if inn:
        for n in inn:
            print(f"  ← {n.path.stem} [{n.category}]")
    else:
        print(dim("  (none)"))


def cmd_tags(vault: Vault, args) -> None:
    idx = vault.tags_index()
    if args.tag:
        t = args.tag.lstrip("#").strip().lower()
        notes = idx.get(t, [])
        print(bold(f"🏷️  #{t} — {len(notes)} note(s)"))
        for n in sorted(notes, key=lambda x: -x.mtime):
            print(f"  - {n.path.stem} [{n.category}] {dim(n.updated)}")
        return
    if not idx:
        print(dim("(No tags found in vault)"))
        return
    print(bold(f"🏷️  {len(idx)} tag(s) across vault:"))
    for t, ns in sorted(idx.items(), key=lambda x: (-len(x[1]), x[0])):
        print(f"  #{t} {dim(f'({len(ns)})')}")


def cmd_daily(vault: Vault, args) -> None:
    vault.ensure()
    path = vault.daily_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(daily_template(), encoding="utf-8")
        print(green(f"✅ Created today's daily log: {path}"))
    note = vault.find(path.stem)
    if args.edit:
        open_editor(vault, path)
    else:
        print(note.content if note else path.read_text(encoding="utf-8"))


def cmd_graph(vault: Vault, args) -> None:
    g = build_graph(vault)
    fmt = args.format
    if fmt == "dot":
        text = to_dot(g)
    elif fmt == "json":
        text = to_json(g)
    else:
        text = to_ascii(g)
    if args.out:
        from pathlib import Path

        Path(args.out).write_text(text, encoding="utf-8")
        print(green(f"✅ Graph exported to: {args.out} ({len(g)} nodes)"))
    else:
        print(text)


def cmd_orphans(vault: Vault, args) -> None:
    g = build_graph(vault)
    orphans = sorted(
        t
        for t, n in g.items()
        if not n["inn"]
        and not [r for r in n["out"] if r]
        and t.lower() != "readme"
    )
    if not orphans:
        print(green("🎉 No orphan notes! Knowledge graph is fully connected."))
        return
    print(bold(f"🧊 {len(orphans)} orphan note(s) (no inlinks, no outlinks):"))
    for t in orphans:
        cat = f"[{g[t]['note'].category}] " if g[t]["note"].category else ""
        print(f"  - {cat}{t}")


def cmd_stats(vault: Vault, args) -> None:
    print(bold("📊 Knowledge Base Statistics"))
    for k, v in vault.stats().items():
        label = k.replace("_", " ").title()
        print(f"  {label}: {v}")


def cmd_mcp(vault: Vault, args) -> None:
    from .mcp import main as mcp_main

    print(dim(f"🧠 Brain MCP server running (vault: {vault.path})…"), file=sys.stderr)
    mcp_main(vault.path)


# ─────────────────────────── Interactive Shell (REPL) ───────────────────────────

REPL_HELP = """Available Commands:
  core [-e] [-s <text>] [--name <n>]   View, edit, or set core soul memory
  new <title> [-c <txt>] [-t <tags>]   Create a note in brain/ (-e opens editor)
  open <title>                         Open note in $EDITOR
  show <title> [--raw]                 Display note content
  list [-n <count>] [--folder <f>]     List notes in vault
  search <query> [-n <count>]          Full-text search
  delete <title> [-f]                  Delete note
  rename <old> <new>                   Rename note and update wikilinks
  links <title>                        View outlinks and backlinks
  tags [name]                          List tags or filter by tag
  daily [-e]                           View or edit today's daily log
  graph [-f ascii|dot|json] [-o file]  Export link graph
  orphans                              List orphan notes
  stats                                Knowledge base statistics
  mcp                                  Launch MCP server for LLMs
  help / quit / exit"""


def cmd_repl(vault: Vault, args) -> None:
    repl(vault)


def repl(vault: Vault) -> None:
    vault.ensure()
    print(bold("🧠 Brain · Interactive Shell"))
    print(dim("Type 'help' for commands, 'exit' or 'quit' to leave."))
    parser = build_parser()
    while True:
        try:
            line = input(cyan("🧠 brain> ")).strip()
        except EOFError:
            print()
            break
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q", "退出"):
            print(dim("Goodbye 👋"))
            break
        if line.lower() in ("help", "?", "帮助"):
            print(REPL_HELP)
            continue
        try:
            ns = parser.parse_args(shlex.split(line))
            if getattr(ns, "func", None) is None:
                parser.print_help()
            else:
                ns.func(vault, ns)
        except SystemExit:
            if not TTY:
                continue
            print(dim("(Type 'help' for usage)"))
        except (KeyboardInterrupt, EOFError):
            print()
            continue
        except Exception as e:  # noqa: BLE001
            print(yellow(f"⚠️  {e}"))


# ─────────────────────────── CLI Parser Builder ───────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="brain",
        description=(
            "🧠 Brain — CLI-first knowledge base & second brain for LLMs:\n"
            "Markdown notes, Obsidian-style [[wikilinks]], full-text search, and MCP server."
        ),
        epilog=(
            "Tips: Run `brain repl` for interactive shell;\n"
            "`brain mcp` to run MCP server for LLM clients (Claude Code, Cursor, etc.)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--vault",
        metavar="DIR",
        help="Vault directory (default: ~/.brain, or env BRAIN_VAULT)",
    )
    p.add_argument(
        "-V", "--version", action="version", version=f"🧠 Brain v{__version__}"
    )
    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    def add(name: str, aliases: list[str], help_: str, func):
        sp = sub.add_parser(name, aliases=aliases, help=help_)
        sp.set_defaults(func=func)
        return sp

    add("init", ["initialize", "初始化"], "Initialize or verify vault directory structure", cmd_init)

    sp = add("core", ["soul", "inti"], "View, edit, or configure core soul memory [inti brain][soul]", cmd_core)
    sp.add_argument("name", nargs="?", default="soul", help="Core note name (default 'soul')")
    sp.add_argument("-e", "--edit", action="store_true", help="Open core note in $EDITOR")
    sp.add_argument("-s", "--set", help="Set core note content directly")
    sp.add_argument("-l", "--list", action="store_true", help="List all core notes")

    sp = add("new", ["create", "add", "新建"], "Create a new note in brain/", cmd_new)
    sp.add_argument("title", help="Note title")
    sp.add_argument("-c", "--content", help="Initial content (default: template)")
    sp.add_argument("-t", "--tags", nargs="*", default=None, help="List of tags")
    sp.add_argument("-e", "--edit", action="store_true", help="Open in $EDITOR after creating")
    sp.add_argument("--folder", default=BRAIN_DIR, choices=[BRAIN_DIR, CORE_DIR, DAILY_DIR], help=f"Folder to store in (default '{BRAIN_DIR}')")

    sp = add("open", ["edit", "打开"], "Open note in $EDITOR", cmd_open)
    sp.add_argument("title", help="Note title")

    sp = add("show", ["view", "cat", "read", "查看"], "Display note content", cmd_show)
    sp.add_argument("title", help="Note title")
    sp.add_argument("--raw", action="store_true", help="Print raw content without link highlights")

    sp = add("list", ["ls", "列表"], "List notes in the vault", cmd_list)
    sp.add_argument("-n", "--limit", type=int, help="Maximum number of notes to display")
    sp.add_argument("--folder", choices=[BRAIN_DIR, CORE_DIR, DAILY_DIR], help="Filter notes by folder")

    sp = add("search", ["find", "grep", "搜索"], "Full-text search across all notes", cmd_search)
    sp.add_argument("query", help="Search keyword or phrase")
    sp.add_argument("-n", "--limit", type=int, default=15, help="Maximum results (default: 15)")

    sp = add("delete", ["rm", "remove", "删除"], "Delete a note", cmd_delete)
    sp.add_argument("title", help="Note title to delete")
    sp.add_argument("-f", "--force", action="store_true", help="Skip confirmation prompt")

    sp = add("rename", ["mv", "重命名"], "Rename a note and update all wikilinks", cmd_rename)
    sp.add_argument("old", help="Current note title")
    sp.add_argument("new", help="New note title")

    sp = add("links", ["backlinks", "链接"], "View forward links and backlinks", cmd_links)
    sp.add_argument("title", help="Note title")

    sp = add("tags", ["tag", "标签"], "List all tags or filter notes by tag", cmd_tags)
    sp.add_argument("tag", nargs="?", help="Optional tag to filter by")

    sp = add("daily", ["today", "journal", "日记"], "View or create today's daily log", cmd_daily)
    sp.add_argument("-e", "--edit", action="store_true", help="Open daily note in $EDITOR")

    sp = add("graph", ["图谱"], "Export link graph", cmd_graph)
    sp.add_argument(
        "-f",
        "--format",
        choices=["ascii", "dot", "json"],
        default="ascii",
        help="Output format (default: ascii)",
    )
    sp.add_argument("-o", "--out", metavar="FILE", help="Write graph to file instead of stdout")

    add("orphans", ["孤立"], "List orphan notes (notes with no inlinks or outlinks)", cmd_orphans)
    add("stats", ["status", "info", "统计"], "Knowledge base statistics", cmd_stats)
    add("repl", ["shell", "interactive", "交互"], "Start interactive REPL shell", cmd_repl)
    add("mcp", ["serve"], "Start MCP stdio server for LLM clients", cmd_mcp)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    vault = Vault(args.vault)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 0
    try:
        func(vault, args)
    except FileExistsError as e:
        print(yellow(f"⚠️  Note already exists: {e}"))
        return 1
    except FileNotFoundError as e:
        print(yellow(f"⚠️  Note not found: {e}"))
        return 1
    except ValueError as e:
        print(yellow(f"⚠️  {e}"))
        return 1
    except KeyboardInterrupt:
        print(dim("\nAborted."))
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
