"""Migration planner: predict the Databricks target, complexity, effort and order."""
from __future__ import annotations

import json
from pathlib import Path

from lineageplanner.models import Graph, Node

TARGET = {
    ("dataset", ""): "Delta table (Silver/Gold)",
    ("index", ""): "Delta table (from search index)",
    ("file", ""): "UC Volume + Auto Loader (landing)",
    ("job", "shell"): "Databricks Workflow (job)",
    ("job", "jcl"): "Databricks Workflow (job)",
    ("job", "informatica"): "Workflow task (session)",
    ("program", "sas"): "PySpark notebook (SAS→PySpark)",
    ("program", "cobol"): "PySpark notebook (COBOL→PySpark)",
    ("program", "python"): "PySpark notebook / wheel",
    ("program", "sql"): "Databricks SQL",
    ("mapping", "informatica"): "PySpark notebook (mapping)",
    ("pipeline", "elasticsearch"): "Lakeflow Declarative Pipeline / ingest",
    ("param", ""): "Job parameter / bundle variable",
    ("lib", ""): "UC connection / external location",
    ("search", "elasticsearch"): "Databricks SQL / Vector Search",
    ("field", ""): "column (schema)",
    ("fd", ""): "schema (StructType)",
    ("copybook", ""): "schema (StructType)",
}

_FALLBACK = {"dataset": "Delta table", "index": "Delta table", "file": "UC Volume",
             "job": "Databricks Workflow", "program": "PySpark notebook",
             "mapping": "PySpark notebook", "pipeline": "Lakeflow pipeline",
             "param": "Job parameter", "lib": "UC connection", "search": "Databricks SQL",
             "field": "column", "fd": "schema", "copybook": "schema"}

EFFORT = {"LOW": 4, "MEDIUM": 16, "HIGH": 48}


def target_for(node: Node) -> str:
    return TARGET.get((node.kind, node.tech)) or TARGET.get((node.kind, "")) \
        or _FALLBACK.get(node.kind, "review")


def complexity(node: Node) -> str:
    lines = int(node.meta.get("lines", 0) or 0)
    if node.kind in ("program", "mapping", "pipeline"):
        if lines > 120 or int(node.meta.get("processors", 0) or 0) > 8:
            return "HIGH"
        if lines > 40 or node.kind in ("mapping", "pipeline"):
            return "MEDIUM"
        return "LOW"
    return "LOW"


def build_plan(graph: Graph) -> dict:
    deg = graph.degrees()
    waves = graph.waves()
    wave_of: dict[str, int] = {}
    for i, w in enumerate(waves):
        for nid in w:
            wave_of[nid] = i

    components = []
    for n in graph.sorted_nodes():
        cx = complexity(n)
        fi, fo = deg.get(n.id, (0, 0))
        components.append({
            "id": n.id, "name": n.name, "kind": n.kind, "tech": n.tech,
            "target": target_for(n), "complexity": cx,
            "effort_hours": EFFORT[cx], "wave": wave_of.get(n.id, 0),
            "fan_in": fi, "fan_out": fo, "path": n.path,
        })

    by_cx: dict[str, int] = {}
    for c in components:
        by_cx[c["complexity"]] = by_cx.get(c["complexity"], 0) + 1

    return {
        "summary": {
            "components": len(components),
            "waves": len(waves),
            "total_effort_hours": sum(c["effort_hours"] for c in components),
            "by_complexity": dict(sorted(by_cx.items())),
            "content_hash": graph.content_hash(),
        },
        "waves": [{"wave": i, "components": [graph.nodes[n].name for n in w]}
                  for i, w in enumerate(waves)],
        "components": components,
    }


def plan_md(plan: dict) -> str:
    s = plan["summary"]
    lines = [
        "# Migration Plan",
        "",
        f"- Components: **{s['components']}**",
        f"- Migration waves: **{s['waves']}** (dependency-ordered)",
        f"- Estimated effort: **{s['total_effort_hours']} hours** "
        f"({', '.join(f'{k}={v}' for k, v in s['by_complexity'].items())})",
        f"- Content hash: `{s['content_hash']}`",
        "",
        "## Migration order (waves)",
        "",
    ]
    for w in plan["waves"]:
        lines.append(f"**Wave {w['wave']}** ({len(w['components'])}): "
                     + ", ".join(w["components"]))
        lines.append("")

    lines += ["## Components → Databricks target", "",
              "| Component | Kind | Tech | Target | Complexity | Hours | Wave |",
              "|---|---|---|---|---|---|---|"]
    for c in plan["components"]:
        lines.append(f"| {c['name']} | {c['kind']} | {c['tech']} | {c['target']} | "
                     f"{c['complexity']} | {c['effort_hours']} | {c['wave']} |")
    return "\n".join(lines)


def write_plan(graph: Graph, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    plan = build_plan(graph)
    (out / "migration_plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    (out / "migration_plan.md").write_text(plan_md(plan), encoding="utf-8")
    return plan["summary"]
