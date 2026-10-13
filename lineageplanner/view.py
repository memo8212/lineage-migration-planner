"""View helpers for the Streamlit app (and reusable programmatically).

Kept free of Streamlit imports so they can be unit-tested.
"""
from __future__ import annotations

from collections import deque

from lineageplanner.models import Graph

KIND_COLOR = {
    "dataset": "#8be9fd", "index": "#8be9fd", "file": "#f1fa8c",
    "job": "#ffb86c", "program": "#ff79c6", "mapping": "#bd93f9",
    "pipeline": "#50fa7b", "param": "#6272a4", "lib": "#8f8f8f",
    "search": "#ffb86c", "field": "#cccccc", "fd": "#cccccc", "copybook": "#cccccc",
}

KIND_SHAPE = {
    "dataset": "cylinder", "index": "cylinder", "file": "note", "job": "box",
    "program": "box", "mapping": "box", "pipeline": "box", "param": "text",
    "lib": "folder", "search": "ellipse",
}


def filter_graph(graph: Graph, kinds=None, techs=None, query=None) -> Graph:
    """Return a subgraph keeping nodes that match the filters (edges need both ends)."""
    out = Graph()
    keep = set()
    q = (query or "").lower()
    for n in graph.sorted_nodes():
        if kinds and n.kind not in kinds:
            continue
        if techs and n.tech and n.tech not in techs:
            continue
        if q and q not in n.name.lower():
            continue
        keep.add(n.id)
        out.add_node(n)
    for e in graph.sorted_edges():
        if e.src in keep and e.dst in keep:
            out.add_edge(e.src, e.dst, e.kind, e.detail)
    out.parsed_files = getattr(graph, "parsed_files", None)  # type: ignore[attr-defined]
    return out


def _adjacency(graph: Graph) -> tuple[dict, dict]:
    out: dict[str, set] = {n: set() for n in graph.nodes}
    inn: dict[str, set] = {n: set() for n in graph.nodes}
    for e in graph.edges:
        if e.src in out and e.dst in inn:
            out[e.src].add(e.dst)
            inn[e.dst].add(e.src)
    return out, inn


def neighborhood(graph: Graph, node_id: str, direction: str = "both", depth: int = 2) -> set:
    """BFS neighbours of a node (direction: upstream | downstream | both)."""
    out, inn = _adjacency(graph)
    seen = {node_id}
    frontier = deque([(node_id, 0)])
    while frontier:
        cur, d = frontier.popleft()
        if d >= depth:
            continue
        nbrs = set()
        if direction in ("downstream", "both"):
            nbrs |= out.get(cur, set())
        if direction in ("upstream", "both"):
            nbrs |= inn.get(cur, set())
        for m in nbrs:
            if m not in seen:
                seen.add(m)
                frontier.append((m, d + 1))
    return seen


def subgraph(graph: Graph, node_ids: set) -> Graph:
    out = Graph()
    for nid in sorted(node_ids):
        if nid in graph.nodes:
            out.add_node(graph.nodes[nid])
    for e in graph.sorted_edges():
        if e.src in node_ids and e.dst in node_ids:
            out.add_edge(e.src, e.dst, e.kind, e.detail)
    return out


def plan_rows(plan: dict) -> list[dict]:
    """Flatten plan components into rows for a table."""
    return [
        {"name": c["name"], "kind": c["kind"], "tech": c["tech"], "target": c["target"],
         "complexity": c["complexity"], "hours": c["effort_hours"], "wave": c["wave"],
         "fan_in": c["fan_in"], "fan_out": c["fan_out"]}
        for c in plan["components"]
    ]


def to_pyvis_html(graph: Graph, height: int = 640, physics: bool = True) -> str | None:
    """Interactive draggable graph as HTML (requires pyvis). None if unavailable."""
    try:
        from pyvis.network import Network
    except ImportError:
        return None
    net = Network(height=f"{height}px", width="100%", directed=True, bgcolor="#1e1e2e",
                  font_color="#f8f8f2", cdn_resources="in_line")
    net.barnes_hut() if physics else net.toggle_physics(False)
    for n in graph.sorted_nodes():
        net.add_node(n.id, label=n.name, title=f"{n.name}\n({n.kind} / {n.tech})\n{n.path}",
                     color=KIND_COLOR.get(n.kind, "#cccccc"),
                     shape=KIND_SHAPE.get(n.kind, "dot"))
    for e in graph.sorted_edges():
        net.add_edge(e.src, e.dst, label=e.kind, title=e.kind)
    return net.generate_html(notebook=False)


def node_details(graph: Graph, plan: dict, node_id: str) -> dict:
    """Everything the inspector panel needs for one component."""
    out, inn = _adjacency(graph)
    comp = next((c for c in plan["components"] if c["id"] == node_id), None)
    name = graph.nodes[node_id].name if node_id in graph.nodes else node_id
    return {
        "name": name,
        "component": comp,
        "upstream": sorted(graph.nodes[m].name for m in inn.get(node_id, set()) if m in graph.nodes),
        "downstream": sorted(graph.nodes[m].name for m in out.get(node_id, set()) if m in graph.nodes),
    }


def edge_rows(graph: Graph) -> list[dict]:
    return [
        {"from": graph.nodes[e.src].name if e.src in graph.nodes else e.src,
         "kind": e.kind,
         "to": graph.nodes[e.dst].name if e.dst in graph.nodes else e.dst,
         "detail": e.detail}
        for e in graph.sorted_edges()
    ]


__all__ = ["KIND_COLOR", "KIND_SHAPE", "filter_graph", "neighborhood", "subgraph",
           "plan_rows", "to_pyvis_html", "node_details", "edge_rows"]
