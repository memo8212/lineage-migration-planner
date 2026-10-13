"""Impact analysis: what depends on a component, and what breaks if it changes."""
from __future__ import annotations

from collections import deque

from lineageplanner.models import Graph


def _adj(graph: Graph):
    out: dict[str, set] = {n: set() for n in graph.nodes}
    inn: dict[str, set] = {n: set() for n in graph.nodes}
    for e in graph.edges:
        if e.src in out and e.dst in inn:
            out[e.src].add(e.dst)
            inn[e.dst].add(e.src)
    return out, inn


def _closure(adj: dict, start: str) -> set:
    seen, q = set(), deque([start])
    while q:
        cur = q.popleft()
        for m in adj.get(cur, ()):  # noqa: B007
            if m not in seen and m != start:
                seen.add(m)
                q.append(m)
    return seen


def downstream_closure(graph: Graph, node_id: str) -> set:
    """Components affected if `node_id` changes (its consumers, transitively)."""
    return _closure(_adj(graph)[0], node_id)


def upstream_closure(graph: Graph, node_id: str) -> set:
    """Everything `node_id` depends on (its inputs, transitively)."""
    return _closure(_adj(graph)[1], node_id)


def impact_report(graph: Graph, plan: dict, node_id: str) -> dict:
    affected = downstream_closure(graph, node_id)
    depends = upstream_closure(graph, node_id)
    comps = {c["id"]: c for c in plan["components"]}
    name = graph.nodes[node_id].name if node_id in graph.nodes else node_id

    def summarize(ids: set) -> dict:
        by_kind: dict[str, int] = {}
        by_tech: dict[str, int] = {}
        hours = 0
        for i in ids:
            c = comps.get(i)
            if not c:
                continue
            by_kind[c["kind"]] = by_kind.get(c["kind"], 0) + 1
            by_tech[c["tech"]] = by_tech.get(c["tech"], 0) + 1
            hours += c["effort_hours"]
        return {"count": len(ids), "by_kind": dict(sorted(by_kind.items())),
                "by_tech": dict(sorted(by_tech.items())), "effort_hours": hours}

    return {
        "node": node_id, "name": name,
        "affected": sorted(affected, key=lambda i: (comps.get(i, {}).get("wave", 99),
                                                     graph.nodes[i].name if i in graph.nodes else i)),
        "depends_on": sorted(depends),
        "affected_summary": summarize(affected),
        "depends_summary": summarize(depends),
    }


def impact_md(graph: Graph, plan: dict, node_id: str) -> str:
    rep = impact_report(graph, plan, node_id)
    comps = {c["id"]: c for c in plan["components"]}
    a, d = rep["affected_summary"], rep["depends_summary"]

    def label(i):
        c = comps.get(i)
        return f"{graph.nodes[i].name} ({c['kind']}/{c['tech']})" if c else \
            (graph.nodes[i].name if i in graph.nodes else i)

    lines = [
        f"# Impact Analysis — {rep['name']}",
        "",
        f"If **{rep['name']}** changes…",
        "",
        f"- **{a['count']}** downstream components are affected "
        f"(≈{a['effort_hours']}h of migrated code to review).",
        f"- It **depends on** {d['count']} upstream components.",
        f"- Affected kinds: {a['by_kind'] or '—'}",
        f"- Affected technologies: {a['by_tech'] or '—'}",
        "",
        "## Affected (downstream, in migration order)",
        "",
        "| Component | Kind | Tech | Wave |",
        "|---|---|---|---|",
    ]
    for i in rep["affected"]:
        c = comps.get(i, {})
        lines.append(f"| {label(i)} | {c.get('kind', '?')} | {c.get('tech', '?')} | {c.get('wave', '?')} |")

    lines += ["", "## Depends on (upstream)", ""]
    lines += [f"- {label(i)}" for i in rep["depends_on"]] or ["- —"]
    return "\n".join(lines)
