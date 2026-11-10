"""🧠 大脑 —— 命令行界面(全中文交互)。"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys

from . import __version__
from .vault import Vault, daily_template, LINK_RE
from .search import search, snippet, tokenize
from .graph import build_graph, to_dot, to_json, to_ascii

TTY = sys.stdout.isatty()


def c(code, s):
    return f"\033[{code}m{s}\033[0m" if TTY else str(s)


def bold(s):
    return c("1", s)


def yellow(s):
    return c("33", s)


def green(s):
    return c("32", s)


def cyan(s):
    return c("36", s)


def dim(s):
    return c("2", s)


def dwidth(s):
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in str(s))


def pad(s, w):
    s = str(s)
    return s + " " * max(0, w - dwidth(s))


def highlight(text, terms, code="33"):
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


def query_terms(query):
    return {query.strip().lower()} | {
        t.lower() for t in tokenize(query) if len(t) > 1
    }


def render_note(note):
    if not TTY:
        return note.content
    return LINK_RE.sub(lambda m: cyan(m.group(0)), note.content)


def open_editor(vault, path):
    editor = os.environ.get("EDITOR", "vi")
    try:
        subprocess.call(shlex.split(editor) + [str(path)])
    except FileNotFoundError:
        print(yellow(f"⚠️  找不到编辑器「{editor}」,请设置 EDITOR 环境变量"))
    finally:
        vault.invalidate_cache()


# ─────────────────────────── 命令处理 ───────────────────────────


def cmd_init(vault, args):
    vault.ensure()
    print(green(f"🧠 知识库已就绪:{vault.path}"))
    print(dim("提示:用 `brain 新建 \"标题\"` 开始记录,或 `brain 交互` 进入交互模式。"))


def cmd_new(vault, args):
    vault.ensure()
    note = vault.create(args.title.strip(), content=args.content, tags=args.tags)
    print(green(f"✅ 已创建《{note.path.stem}》"))
    print(dim(f"   {note.path}"))
    if args.edit:
        open_editor(vault, note.path)


def cmd_open(vault, args):
    note = vault.find(args.title)
    if note is None:
        print(yellow(f"⚠️  找不到笔记《{args.title}》"))
        return
    open_editor(vault, note.path)


def cmd_show(vault, args):
    note = vault.find(args.title)
    if note is None:
        print(yellow(f"⚠️  找不到笔记《{args.title}》"))
        return
    meta = (
        f"《{note.path.stem}》 {note.updated}  "
        f"标签:{(' '.join('#' + t for t in note.tags)) or '无'}  "
        f"链接:{len(note.links)}"
    )
    print(dim(meta))
    print(dim("─" * 48))
    print(note.content if args.raw else render_note(note))


def cmd_list(vault, args):
    notes = vault.notes()
    if not notes:
        print(dim("(知识库为空)"))
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
    print(bold(f"📚 共 {len(notes)} 篇笔记") + dim(f"(仓库:{vault.path})"))
    print(dim(pad("标题", 26) + pad("更新时间", 17) + pad("反链", 5) + "标签"))
    print(dim("─" * 64))
    for n in notes[: args.limit or len(notes)]:
        tags = " ".join("#" + t for t in n.tags)
        print(
            pad(n.path.stem, 26)
            + pad(n.updated, 17)
            + pad(str(inlink.get(n.path.stem, 0)), 5)
            + dim(tags)
        )


def cmd_search(vault, args):
    q = args.query.strip()
    if not q:
        print(yellow("⚠️  请输入关键词"))
        return
    results = search(vault.notes(), q, args.limit)
    if not results:
        print(dim(f"🔍「{q}」没有匹配的笔记。"))
        return
    terms = query_terms(q)
    print(bold(f"🔍 搜索「{q}」") + dim(f" 共 {len(results)} 条结果"))
    print()
    for i, (score, hits, n) in enumerate(results, 1):
        title = highlight(n.path.stem, [q]) if TTY else n.path.stem
        print(
            f"{bold(str(i) + '.')} 《{title}》 "
            + dim(f"匹配 {hits} 项 · {n.updated}")
        )
        print("   " + highlight(snippet(n.content, q), terms))
        print()


def cmd_delete(vault, args):
    note = vault.find(args.title)
    if note is None:
        print(yellow(f"⚠️  找不到笔记《{args.title}》"))
        return
    if not args.force:
        ans = input(f"确认删除《{note.path.stem}》?[y/N] ").strip().lower()
        if ans not in ("y", "yes", "是"):
            print(dim("已取消"))
            return
    affected = [n.path.stem for n in vault.backlinks(note.path.stem)]
    vault.delete(note)
    print(green(f"🗑️  已删除《{note.path.stem}》"))
    if affected:
        print(dim(f"   注意:{len(affected)} 篇笔记曾链接到它:" + "、".join(affected)))


def cmd_rename(vault, args):
    new_note, changed = vault.rename(args.old, args.new)
    print(green(f"✏️  已重命名:《{args.old}》→《{new_note.path.stem}》"))
    if changed:
        print(dim(f"   已同步更新 {changed} 篇笔记中的链接"))


def cmd_links(vault, args):
    note = vault.find(args.title)
    if note is None:
        print(yellow(f"⚠️  找不到笔记《{args.title}》"))
        return
    out = vault.outlinks(note)
    inn = vault.backlinks(note.path.stem)
    print(bold(f"🔗 《{note.path.stem}》"))
    print(dim("出链:"))
    if out:
        for raw, r in out:
            mark = green("✓") if r else yellow("✗")
            tail = "" if r else dim("(未找到对应笔记)")
            print(f"  {mark} {raw}{tail}")
    else:
        print(dim("  (无)"))
    print(dim("反向链接:"))
    if inn:
        for n in inn:
            print(f"  ← {n.path.stem}")
    else:
        print(dim("  (无)"))


def cmd_tags(vault, args):
    idx = vault.tags_index()
    if args.tag:
        t = args.tag.lstrip("#").strip().lower()
        notes = idx.get(t, [])
        print(bold(f"🏷️  #{t}  共 {len(notes)} 篇"))
        for n in sorted(notes, key=lambda x: -x.mtime):
            print(f"  - {n.path.stem} {dim(n.updated)}")
        return
    if not idx:
        print(dim("(暂无标签)"))
        return
    print(bold(f"🏷️  共 {len(idx)} 个标签"))
    for t, ns in sorted(idx.items(), key=lambda x: (-len(x[1]), x[0])):
        print(f"  #{t} {dim(f'({len(ns)})')}")


def cmd_daily(vault, args):
    vault.ensure()
    path = vault.daily_path()
    if not path.exists():
        vault.create(path.stem, content=daily_template())
        print(green(f"✅ 已创建今日笔记:{path}"))
    note = vault.find(path.stem)
    if args.edit:
        open_editor(vault, path)
    else:
        print(note.content)


def cmd_graph(vault, args):
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
        print(green(f"✅ 图谱已导出:{args.out}(共 {len(g)} 个节点)"))
    else:
        print(text)


def cmd_orphans(vault, args):
    g = build_graph(vault)
    orphans = sorted(
        t
        for t, n in g.items()
        if not n["inn"] and not [r for r in n["out"] if r]
    )
    if not orphans:
        print(green("🎉 没有孤立笔记,知识网络很健康。"))
        return
    print(bold(f"🧊 孤立笔记(无出链、无反向链接)共 {len(orphans)} 篇:"))
    for t in orphans:
        print(f"  - {t}")


def cmd_stats(vault, args):
    print(bold("📊 知识库统计"))
    for k, v in vault.stats().items():
        print(f"  {k}:{v}")


def cmd_mcp(vault, args):
    from .mcp import main as mcp_main

    print(dim(f"🧠 大脑 MCP 服务启动中(仓库:{vault.path})…"), file=sys.stderr)
    mcp_main(vault.path)


# ─────────────────────────── 交互模式 ───────────────────────────

REPL_HELP = """可用命令:
  新建 <标题> [-t 标签...] [-e]     创建笔记(-e 用编辑器打开)
  打开 <标题>                       用 $EDITOR 打开笔记
  查看 <标题>                       显示笔记内容
  列表 [-n 数量]                    列出全部笔记
  搜索 <关键词> [-n 数量]           中文全文搜索
  删除 <标题> [-f]                  删除笔记
  重命名 <旧> <新>                  重命名并同步链接
  链接 <标题>                       查看出链与反向链接
  标签 [标签名]                     列出标签 / 按标签筛选
  日记 [-e]                         查看或创建今日笔记
  图谱 [-f ascii|dot|json] [-o 文件] 导出链接图谱
  孤立                              列出孤立笔记
  统计                              知识库统计
  mcp                               启动 MCP 服务(供 LLM 使用)
  帮助 / 退出"""


def cmd_repl(vault, args):
    repl(vault)


def repl(vault):
    vault.ensure()
    print(bold("🧠 大脑 · 交互模式"))
    print(dim("输入「帮助」查看命令,「退出」离开。"))
    parser = build_parser()
    while True:
        try:
            line = input(cyan("🧠 大脑> ")).strip()
        except EOFError:
            print()
            break
        if not line:
            continue
        if line in ("退出", "quit", "exit", "q"):
            print(dim("再见 👋"))
            break
        if line in ("帮助", "help", "?"):
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
            print(dim("(输入「帮助」查看用法)"))
        except (KeyboardInterrupt, EOFError):
            print()
            continue
        except Exception as e:  # noqa: BLE001
            print(yellow(f"⚠️  {e}"))


# ─────────────────────────── 参数解析 ───────────────────────────


def build_parser():
    p = argparse.ArgumentParser(
        prog="brain",
        description=(
            "🧠 大脑 —— 面向 LLM 的 CLI 知识库(类 Obsidian):"
            "Markdown 笔记、双向链接、中文全文搜索。"
        ),
        epilog=(
            "提示:`brain 交互` 进入交互式 shell;"
            "`brain mcp` 启动 MCP 服务供 LLM 客户端使用。"
        ),
    )
    p.add_argument(
        "--vault",
        metavar="目录",
        help="知识库目录(默认:~/.brain,或环境变量 BRAIN_VAULT)",
    )
    p.add_argument(
        "-V", "--version", action="version", version=f"🧠 大脑 v{__version__}"
    )
    sub = p.add_subparsers(dest="cmd", metavar="命令")

    def add(name, aliases, help_, func):
        sp = sub.add_parser(name, aliases=aliases, help=help_)
        sp.set_defaults(func=func)
        return sp

    add("初始化", ["init"], "初始化知识库目录", cmd_init)

    sp = add("新建", ["new", "create"], "新建笔记", cmd_new)
    sp.add_argument("title", help="笔记标题")
    sp.add_argument("-c", "--content", help="初始内容(默认使用模板)")
    sp.add_argument("-t", "--tags", nargs="*", default=None, help="标签列表")
    sp.add_argument("-e", "--edit", action="store_true", help="创建后用 $EDITOR 打开")

    sp = add("打开", ["open", "edit"], "用编辑器打开笔记", cmd_open)
    sp.add_argument("title")

    sp = add("查看", ["show", "cat", "read"], "查看笔记内容", cmd_show)
    sp.add_argument("title")
    sp.add_argument("--raw", action="store_true", help="原样输出(不高亮链接)")

    sp = add("列表", ["list", "ls"], "列出全部笔记", cmd_list)
    sp.add_argument("-n", "--limit", type=int, help="最多显示多少条")

    sp = add("搜索", ["search", "find", "grep"], "中文全文搜索", cmd_search)
    sp.add_argument("query", help="关键词(支持中文)")
    sp.add_argument("-n", "--limit", type=int, default=15, help="最多显示多少条(默认 15)")

    sp = add("删除", ["delete", "rm", "remove"], "删除笔记", cmd_delete)
    sp.add_argument("title")
    sp.add_argument("-f", "--force", action="store_true", help="跳过确认")

    sp = add("重命名", ["rename", "mv"], "重命名笔记并同步链接", cmd_rename)
    sp.add_argument("old")
    sp.add_argument("new")

    sp = add("链接", ["links", "backlinks"], "查看出链与反向链接", cmd_links)
    sp.add_argument("title")

    sp = add("标签", ["tags", "tag"], "列出标签或按标签筛选", cmd_tags)
    sp.add_argument("tag", nargs="?")

    sp = add("日记", ["daily", "today"], "查看/创建今日笔记", cmd_daily)
    sp.add_argument("-e", "--edit", action="store_true", help="用编辑器打开")

    sp = add("图谱", ["graph"], "导出链接图谱", cmd_graph)
    sp.add_argument(
        "-f",
        "--format",
        choices=["ascii", "dot", "json"],
        default="ascii",
        help="输出格式(默认 ascii)",
    )
    sp.add_argument("-o", "--out", metavar="文件", help="写入文件而非屏幕")

    add("孤立", ["orphans"], "列出孤立笔记", cmd_orphans)
    add("统计", ["stats"], "知识库统计", cmd_stats)
    add("交互", ["repl", "shell"], "进入交互式 shell", cmd_repl)
    add("mcp", ["serve"], "启动 MCP 服务(供 LLM 客户端使用)", cmd_mcp)
    return p


def main(argv=None):
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
        print(yellow(f"⚠️  笔记已存在:{e}"))
        return 1
    except FileNotFoundError as e:
        print(yellow(f"⚠️  找不到笔记:{e}"))
        return 1
    except ValueError as e:
        print(yellow(f"⚠️  {e}"))
        return 1
    except KeyboardInterrupt:
        print(dim("\n已中断"))
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
