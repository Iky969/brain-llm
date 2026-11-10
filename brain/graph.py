"""链接图谱:把双向链接构建成图,导出为 ASCII / Graphviz DOT / JSON。"""
from __future__ import annotations

import json


def build_graph(vault):
    notes = vault.notes()
    rmap = vault.resolve_map()
    g = {}
    for n in notes:
        raw_out = list(n.links)
        out = []
        for raw in raw_out:
            t = raw.split("|", 1)[0].split("#", 1)[0].strip()
            out.append(rmap.get(t.lower()))
        g[n.path.stem] = {"note": n, "out": out, "raw_out": raw_out, "inn": []}
    for t, node in g.items():
        for r in node["out"]:
            if r and r != t and r in g:
                g[r]["inn"].append(t)
    return g


def to_dot(g) -> str:
    lines = [
        "digraph 大脑 {",
        "  rankdir=LR;",
        '  node [shape=note, style="rounded,filled", fillcolor="#f5f5f4"];',
        '  edge [color="#a8a29e"];',
    ]
    for t in sorted(g):
        lines.append(f'  "{t}";')
    for t, node in sorted(g.items()):
        seen = set()
        for r in node["out"]:
            if r and r != t and r not in seen:
                seen.add(r)
                lines.append(f'  "{t}" -> "{r}";')
        for raw, r in zip(node["raw_out"], node["out"]):
            if not r and raw not in seen:
                seen.add(raw)
                lines.append(
                    f'  "{raw}(未找到)" [shape=ellipse, dashed, fillcolor="#fee2e2"];'
                )
                lines.append(f'  "{t}" -> "{raw}(未找到)" [dashed, color="#ef4444"];'
                )
    lines.append("}")
    return "\n".join(lines)


def to_json(g) -> str:
    data = {
        t: {
            "出链": [r for r in node["out"] if r],
            "未解析": [raw for raw, r in zip(node["raw_out"], node["out"]) if not r],
            "反向链接": node["inn"],
            "更新时间": node["note"].updated,
            "标签": node["note"].tags,
        }
        for t, node in g.items()
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def to_ascii(g) -> str:
    lines = [f"🕸️  知识图谱(共 {len(g)} 个节点)", ""]
    for t in sorted(g):
        node = g[t]
        out = [r for r in node["out"] if r]
        bad = [
            raw for raw, r in zip(node["raw_out"], node["out"]) if not r
        ]
        lines.append(f"📄 {t}")
        lines.append("   ├─ 出链 → " + ("、".join(dict.fromkeys(out)) or "无"))
        if bad:
            lines.append("   ├─ 失效 → " + "、".join(dict.fromkeys(bad)))
        lines.append("   └─ 反向 ← " + ("、".join(node["inn"]) or "无"))
    return "\n".join(lines)
