"""Gap detection: find where the lineage is incomplete and ask the user.

Gaps are places the static analysis can't resolve end-to-end:
  * placeholders      - a component referenced but never defined
  * orphan_source     - a dataset with no producer (external source?)
  * orphan_sink       - a dataset with no consumer (final output?)
  * unknown_file      - a file no parser recognized
  * ambiguous_column  - a column attributed to several source tables
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lineageplanner.models import Graph


@dataclass
class Question:
    id: str
    kind: str
    prompt: str
    target: str
    options: list = field(default_factory=list)
    default: str = ""
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "prompt": self.prompt,
                "target": self.target, "options": self.options,
                "default": self.default, "context": self.context}


def _col_table(col_id: str) -> str:
    # col:<table>.<column>  ->  <table>
    body = col_id.split(":", 1)[-1]
    return body.rsplit(".", 1)[0]


def detect_gaps(graph: Graph) -> list[Question]:
    qs: list[Question] = []
    deg = graph.degrees()

    # 1. placeholders (referenced but not defined)
    for n in graph.sorted_nodes():
        if n.meta.get("placeholder") and not n.meta.get("resolved"):
            qs.append(Question(
                id=f"placeholder:{n.id}", kind="placeholder",
                prompt=f"'{n.name}' is referenced but never defined. What is it?",
                target=n.id,
                options=["external", "workflow", "file", "program", "ignore"],
                default="external",
                context={"name": n.name, "kind": n.kind}))

    # 2. orphan sources / sinks (datasets only, skip placeholders/resolved)
    for n in graph.sorted_nodes():
        if n.kind not in ("dataset", "index") or n.meta.get("placeholder"):
            continue
        if n.meta.get("external") or n.meta.get("terminal") or n.meta.get("resolved"):
            continue  # already classified as a boundary
        fan_in, fan_out = deg.get(n.id, (0, 0))
        if fan_in == 0:
            qs.append(Question(
                id=f"orphan_source:{n.id}", kind="orphan_source",
                prompt=f"'{n.name}' has no producer in the estate. Is it an external/landing source?",
                target=n.id, options=["external", "missing_producer", "ignore"],
                default="external", context={"name": n.name}))
        if fan_out == 0:
            qs.append(Question(
                id=f"orphan_sink:{n.id}", kind="orphan_sink",
                prompt=f"'{n.name}' has no consumer. Is it a final output?",
                target=n.id, options=["terminal", "missing_consumer", "ignore"],
                default="terminal", context={"name": n.name}))

    # 3. unknown files (nothing recognized them)
    for relpath in getattr(graph, "unknown_files", []):
        ext = relpath.rsplit(".", 1)[-1].lower() if "." in relpath else ""
        qs.append(Question(
            id=f"unknown_file:{relpath}", kind="unknown_file",
            prompt=f"File '{relpath}' wasn't recognized. What is it?",
            target=relpath,
            options=["file", "program", "job", "config", "data", "ignore"],
            default="file",
            context={"ext": ext, "name": relpath}))

    # 4. ambiguous columns
    amb: dict[str, set] = {}
    for e in graph.edges:
        if e.detail == "ambiguous":
            amb.setdefault(e.dst, set()).add(_col_table(e.src))
    for dst, tables in sorted(amb.items()):
        qs.append(Question(
            id=f"ambiguous_column:{dst}", kind="ambiguous_column",
            prompt=f"Column '{dst}' is attributed to multiple tables. Which source table is correct?",
            target=dst, options=sorted(tables),
            default=sorted(tables)[0], context={"candidates": sorted(tables)}))

    return qs
