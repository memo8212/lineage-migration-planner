"""Render the lineage graph (Mermaid, DOT, PNG) and an assessment report."""
from __future__ import annotations

import json
from pathlib import Path

from lineageplanner.models import Graph

_SHAPE = {"dataset": "cylinder", "index": "cylinder", "file": "note", "job": "box",
          "program": "component", "mapping": "component", "pipeline": "component",
          "param": "plaintext", "lib": "folder", "search": "ellipse"}

_MERMAID_SHAPE = {"dataset": "[( )]", "index": "[( )]", "file": "[/ /]", "job": "[ ]",
                  "program": "[ ]", "mapping": "[ ]", "pipeline": "[ ]", "param": "( )",
                  "lib": "[ ]", "search": "( )"}


def _mid(node_id: str) -> str:
    return "n_" + node_id.replace(":", "_").replace(".", "_").replace("/", "_").replace("-", "_")


def to_mermaid(graph: Graph) -> str:
    lines = ["flowchart LR"]
    for n in graph.sorted_nodes():
        lines.append(f'  {_mid(n.id)}["{n.name}<br/><i>{n.kind}</i>"]')
    for e in graph.sorted_edges():
        if e.src in graph.nodes and e.dst in graph.nodes:
            lines.append(f"  {_mid(e.src)} -->|{e.kind}| {_mid(e.dst)}")
    return "\n".join(lines)


def to_dot(graph: Graph) -> str:
    lines = ["digraph lineage {", "  rankdir=LR;", '  node [style=filled, fontname="Helvetica"];']
    for n in graph.sorted_nodes():
        color = {"dataset": "#8be9fd", "index": "#8be9fd", "file": "#f1fa8c",
                 "job": "#ffb86c", "program": "#ff79c6", "mapping": "#bd93f9",
                 "pipeline": "#50fa7b"}.get(n.kind, "#cccccc")
        lines.append(f'  "{n.id}" [label="{n.name}\\n({n.kind})", shape={_SHAPE.get(n.kind, "box")}, fillcolor="{color}"];')
    for e in graph.sorted_edges():
        lines.append(f'  "{e.src}" -> "{e.dst}" [label="{e.kind}"];')
    lines.append("}")
    return "\n".join(lines)


def render_png(graph: Graph, path: Path) -> bool:
    try:
        import pygraphviz  # noqa: F401
        from networkx.drawing.nx_agraph import to_agraph
        import networkx as nx
    except ImportError:
        return False
    g = nx.DiGraph()
    for n in graph.sorted_nodes():
        g.add_node(n.id, label=f"{n.name}\n({n.kind})", shape=_SHAPE.get(n.kind, "box"))
    for e in graph.sorted_edges():
        g.add_edge(e.src, e.dst, label=e.kind)
    A = to_agraph(g)
    A.layout(prog="dot")
    A.draw(str(path))
    return True


def assessment_md(graph: Graph) -> str:
    stats = graph.stats()
    deg = graph.degrees()
    roots = sorted(n for n, (i, _) in deg.items() if i == 0)
    leaves = sorted(n for n, (_, o) in deg.items() if o == 0)
    hubs = sorted(deg, key=lambda n: (deg[n][0] + deg[n][1]), reverse=True)[:10]
    cycles = graph.cycles()

    def label(nid):
        n = graph.nodes.get(nid)
        return f"{n.name} ({n.kind})" if n else nid

    lines = [
        "# Migration Assessment",
        "",
        f"- Files parsed: **{getattr(graph, 'parsed_files', '?')}**",
        f"- Components (nodes): **{stats['nodes']}**",
        f"- Links (edges): **{stats['edges']}**",
        f"- Content hash: `{graph.content_hash()}`",
        "",
        "## Node kinds",
        "",
        "| Kind | Count |", "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in stats["node_kinds"].items()]
    lines += ["", "## Edge kinds", "", "| Kind | Count |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in stats["edge_kinds"].items()]
    lines += ["", "## Most connected components", "", "| Component | in | out |", "|---|---|---|"]
    lines += [f"| {label(n)} | {deg[n][0]} | {deg[n][1]} |" for n in hubs]
    lines += ["", f"## Entry points (no inputs): {len(roots)}", ""]
    lines += [f"- {label(n)}" for n in roots[:15]]
    lines += ["", f"## Outputs (no consumers): {len(leaves)}", ""]
    lines += [f"- {label(n)}" for n in leaves[:15]]
    if cycles:
        lines += ["", f"## ⚠️ Cycles detected: {len(cycles)}", ""]
        for c in cycles:
            lines += [f"- {' -> '.join(label(x) for x in c)}"]
    else:
        lines += ["", "## Cycles detected: none ✅"]
    return "\n".join(lines)


def write_lineage(graph: Graph, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "lineage.json").write_text(json.dumps(graph.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    (out / "lineage.dot").write_text(to_dot(graph), encoding="utf-8")
    md = ["# Data & Job Lineage", "", "```mermaid", to_mermaid(graph), "```", "",
          "## Edges", "", "| From | Kind | To | Detail |", "|---|---|---|---|"]
    for e in graph.sorted_edges():
        src = graph.nodes[e.src].name if e.src in graph.nodes else e.src
        dst = graph.nodes[e.dst].name if e.dst in graph.nodes else e.dst
        md.append(f"| {src} | {e.kind} | {dst} | {e.detail} |")
    (out / "lineage.md").write_text("\n".join(md), encoding="utf-8")
    png = render_png(graph, out / "lineage.png")
    (out / "assessment.md").write_text(assessment_md(graph), encoding="utf-8")
    return {"png": png, "hash": graph.content_hash()}
