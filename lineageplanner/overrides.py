"""Overrides: user answers that patch the lineage graph to be end-to-end.

File format (YAML if PyYAML is available, else JSON):

    external_sources: ["ds:RAW_CARDS"]          # no producer -> external/landing
    terminal_sinks:   ["ds:GOLD_SEGMENT"]        # no consumer -> final output
    ignored:          ["job:wf_unknown"]         # drop from the graph
    node_kinds:       {"job:x": {kind: job, tech: cron}}
    unknown_files:    {"scripts/run.bteq": {kind: program, tech: teradata}}
    column_resolution: {"col:out.c": "T"}         # pick the correct source table
    extra_edges:      [{src: "ds:A", dst: "ds:B", kind: reads, detail: manual}]
"""
from __future__ import annotations

import json
from pathlib import Path

from lineageplanner.models import DATASET, Edge, Graph, Node, file_id


def _yaml():
    try:
        import yaml
        return yaml
    except ImportError:
        return None


def load_overrides(path: str | Path) -> dict:
    text = Path(path).read_text()
    y = _yaml()
    if y is not None:
        return y.safe_load(text) or {}
    return json.loads(text)


def save_overrides(overrides: dict, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(dump_overrides(overrides), encoding="utf-8")
    return path


def dump_overrides(overrides: dict) -> str:
    y = _yaml()
    return y.safe_dump(overrides, sort_keys=True) if y else json.dumps(overrides, indent=2, sort_keys=True)


def _drop_nodes(graph: Graph, ids: set) -> None:
    for nid in ids:
        graph.nodes.pop(nid, None)
    graph.edges = [e for e in graph.edges if e.src not in ids and e.dst not in ids]
    graph._edge_keys = {e.key() for e in graph.edges}


def apply_overrides(graph: Graph, overrides: dict) -> Graph:
    """Patch a graph in place with user answers; returns the same graph."""
    if not overrides:
        return graph

    for nid, spec in (overrides.get("node_kinds") or {}).items():
        if nid in graph.nodes and isinstance(spec, dict):
            if spec.get("kind"):
                graph.nodes[nid].kind = spec["kind"]
            if spec.get("tech"):
                graph.nodes[nid].tech = spec["tech"]
            graph.nodes[nid].meta["placeholder"] = False
            graph.nodes[nid].meta["resolved"] = True

    for nid in overrides.get("external_sources") or []:
        if nid in graph.nodes:
            graph.nodes[nid].meta["external"] = True
            graph.nodes[nid].meta["placeholder"] = False
            graph.nodes[nid].meta["resolved"] = True
    for nid in overrides.get("terminal_sinks") or []:
        if nid in graph.nodes:
            graph.nodes[nid].meta["terminal"] = True
            graph.nodes[nid].meta["resolved"] = True

    for relpath, spec in (overrides.get("unknown_files") or {}).items():
        spec = spec or {}
        fid = file_id(relpath)
        graph.add_node(Node(id=fid, name=relpath, kind=spec.get("kind", "file"),
                            tech=spec.get("tech", ""), meta={"from_override": True}))

    # column resolution: keep only the chosen source table for an ambiguous column
    for dst, choice in (overrides.get("column_resolution") or {}).items():
        choice = str(choice)
        kept = []
        for e in graph.edges:
            if e.dst == dst and e.detail == "ambiguous":
                src_table = e.src.split(":", 1)[-1].rsplit(".", 1)[0]
                if src_table == choice or e.src == choice:
                    kept.append(e)
            else:
                kept.append(e)
        graph.edges = kept
    graph._edge_keys = {e.key() for e in graph.edges}

    _drop_nodes(graph, set(overrides.get("ignored") or []))

    for e in overrides.get("extra_edges") or []:
        graph.add_edge(e["src"], e["dst"], e.get("kind", "reads"), e.get("detail", "manual"))

    return graph


def blank_overrides() -> dict:
    return {"external_sources": [], "terminal_sinks": [], "ignored": [],
            "node_kinds": {}, "unknown_files": {}, "column_resolution": {},
            "extra_edges": []}


__all__ = ["load_overrides", "save_overrides", "apply_overrides", "blank_overrides",
           "Edge", "DATASET"]
