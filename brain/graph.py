"""Link graph: construct directional graphs from wikilinks, export to ASCII / DOT / JSON."""
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
        "digraph Brain {",
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
                    f'  "{raw} (missing)" [shape=ellipse, dashed, fillcolor="#fee2e2"];'
                )
                lines.append(f'  "{t}" -> "{raw} (missing)" [dashed, color="#ef4444"];')
    lines.append("}")
    return "\n".join(lines)


def to_json(g) -> str:
    data = {
        t: {
            "folder": node["note"].category,
            "outlinks": [r for r in node["out"] if r],
            "unresolved": [raw for raw, r in zip(node["raw_out"], node["out"]) if not r],
            "backlinks": node["inn"],
            "updated": node["note"].updated,
            "tags": node["note"].tags,
        }
        for t, node in g.items()
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def to_ascii(g) -> str:
    lines = [f"🕸️  Knowledge Graph ({len(g)} nodes)", ""]
    for t in sorted(g):
        node = g[t]
        out = [r for r in node["out"] if r]
        bad = [raw for raw, r in zip(node["raw_out"], node["out"]) if not r]
        folder_tag = f" [{node['note'].category}]" if node["note"].category else ""
        lines.append(f"📄 {t}{folder_tag}")
        lines.append("   ├─ Outlinks   → " + (", ".join(dict.fromkeys(out)) or "none"))
        if bad:
            lines.append("   ├─ Unresolved → " + ", ".join(dict.fromkeys(bad)))
        lines.append("   └─ Backlinks  ← " + (", ".join(node["inn"]) or "none"))
    return "\n".join(lines)
