"""Core graph model for the lineage / migration planner."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

# node kinds
DATASET = "dataset"      # a table/file-like data entity
FILE = "file"            # a source/landing file
JOB = "job"              # an orchestrator (workflow/jcl/shell)
PROGRAM = "program"      # a program (cobol/sas program/python module)
MAPPING = "mapping"      # an ETL mapping (informatica)
PIPELINE = "pipeline"    # an ingest pipeline (es/ldp)
PARAM = "param"          # a parameter/variable
LIB = "lib"              # a library/connection
INDEX = "index"          # a search index
COLUMN = "column"        # a column (column-level lineage)

# edge kinds
READS = "reads"
WRITES = "writes"
DERIVES = "derives"
CALLS = "calls"
TRIGGERS = "triggers"
INCLUDES = "includes"
LOOKUP = "lookup"
ROUTES = "routes"
LANDING = "lands"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", s.strip().lower()).strip("_")


@dataclass
class Node:
    id: str
    name: str
    kind: str
    tech: str = ""
    path: str = ""
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind,
                "tech": self.tech, "path": self.path, "meta": self.meta}


@dataclass
class Edge:
    src: str
    dst: str
    kind: str
    detail: str = ""

    def key(self) -> tuple:
        return (self.src, self.dst, self.kind, self.detail)

    def to_dict(self) -> dict:
        return {"src": self.src, "dst": self.dst, "kind": self.kind, "detail": self.detail}


def dataset_id(name: str) -> str:
    return f"ds:{_slug(name).upper()}"


def node_id(kind: str, name: str) -> str:
    return f"{kind}:{_slug(name)}"


def file_id(relpath: str) -> str:
    # normalize by basename so the same logical file links across technologies
    name = relpath.replace("\\", "/").rstrip("/").split("/")[-1]
    return f"file:{_slug(name)}"


class Graph:
    """A deterministic directed multigraph of components and links."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._edge_keys: set = set()

    def add_node(self, node: Node) -> Node:
        existing = self.nodes.get(node.id)
        if existing:
            # a real node replaces an auto-created placeholder (keep its real name)
            if existing.meta.get("placeholder") and not node.meta.get("placeholder"):
                self.nodes[node.id] = node
                return node
            # otherwise keep first-seen display info, merge meta
            for k, v in node.meta.items():
                existing.meta.setdefault(k, v)
            if not existing.path and node.path:
                existing.path = node.path
            return existing
        self.nodes[node.id] = node
        return node

    def add_edge(self, src: str, dst: str, kind: str, detail: str = "") -> None:
        if src == dst:
            return
        # ensure both endpoints exist (parsers may reference a node by id only)
        for end in (src, dst):
            if end not in self.nodes:
                prefix, _, name = end.partition(":")
                self.nodes[end] = Node(id=end, name=name or end,
                                       kind={"ds": DATASET}.get(prefix, prefix),
                                       meta={"placeholder": True})
        e = Edge(src, dst, kind, detail)
        if e.key() in self._edge_keys:
            return
        self._edge_keys.add(e.key())
        self.edges.append(e)

    # ---- deterministic serialization ----
    def sorted_nodes(self) -> list[Node]:
        return sorted(self.nodes.values(), key=lambda n: (n.kind, n.name.lower(), n.id))

    def sorted_edges(self) -> list[Edge]:
        return sorted(self.edges, key=lambda e: (e.src, e.dst, e.kind, e.detail))

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.sorted_nodes()],
            "edges": [e.to_dict() for e in self.sorted_edges()],
            "stats": self.stats(),
        }

    def content_hash(self) -> str:
        blob = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def stats(self) -> dict:
        kinds: dict[str, int] = {}
        for n in self.nodes.values():
            kinds[n.kind] = kinds.get(n.kind, 0) + 1
        ekind: dict[str, int] = {}
        for e in self.edges:
            ekind[e.kind] = ekind.get(e.kind, 0) + 1
        return {"nodes": len(self.nodes), "edges": len(self.edges),
                "node_kinds": dict(sorted(kinds.items())),
                "edge_kinds": dict(sorted(ekind.items()))}

    # ---- graph algorithms ----
    def _adj(self) -> dict[str, set]:
        adj: dict[str, set] = {n: set() for n in self.nodes}
        for e in self.edges:
            if e.src in adj and e.dst in adj:
                adj[e.src].add(e.dst)
        return adj

    def topological_order(self) -> list[str]:
        adj = self._adj()
        indeg = {n: 0 for n in self.nodes}
        for src, dsts in adj.items():
            for d in dsts:
                indeg[d] += 1
        ready = sorted([n for n, d in indeg.items() if d == 0])
        order: list[str] = []
        while ready:
            n = ready.pop(0)
            order.append(n)
            for m in sorted(adj[n]):
                indeg[m] -= 1
                if indeg[m] == 0:
                    ready.append(m)
            ready.sort()
        # any remaining nodes are in cycles -> append deterministically
        order += sorted(n for n in self.nodes if n not in set(order))
        return order

    def cycles(self) -> list[list[str]]:
        """Return strongly-connected components with >1 node (deterministic)."""
        adj = self._adj()
        index: dict[str, int] = {}
        low: dict[str, int] = {}
        on_stack: dict[str, bool] = {}
        stack: list[str] = []
        sccs: list[list[str]] = []
        counter = [0]

        def strongconnect(v: str) -> None:
            index[v] = low[v] = counter[0]
            counter[0] += 1
            stack.append(v)
            on_stack[v] = True
            for w in sorted(adj[v]):
                if w not in index:
                    strongconnect(w)
                    low[v] = min(low[v], low[w])
                elif on_stack.get(w):
                    low[v] = min(low[v], index[w])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    sccs.append(sorted(comp))

        for v in sorted(self.nodes):
            if v not in index:
                strongconnect(v)

        # A 2-node SCC that is a read-modify-write pair (a program reads AND
        # writes the same dataset) is not a real dependency cycle.
        filtered = []
        for comp in sorted(sccs):
            if len(comp) == 2:
                a, b = comp
                kinds = {e.kind for e in self.edges if {e.src, e.dst} == {a, b}}
                if "reads" in kinds and kinds & {"writes", "derives"}:
                    continue
            filtered.append(comp)
        return filtered

    def waves(self) -> list[list[str]]:
        """Dependency waves: level = longest path from a root (deterministic)."""
        adj = self._adj()
        indeg = {n: 0 for n in self.nodes}
        for src, dsts in adj.items():
            for d in dsts:
                indeg[d] += 1
        level = {n: 0 for n in self.nodes}
        order = self.topological_order()
        for n in order:
            for m in adj.get(n, ()):  # noqa: B007
                level[m] = max(level[m], level[n] + 1)
        buckets: dict[int, list[str]] = {}
        for n, lv in level.items():
            buckets.setdefault(lv, []).append(n)
        return [sorted(buckets[k]) for k in sorted(buckets)]

    def degrees(self) -> dict[str, tuple[int, int]]:
        fan_in = {n: 0 for n in self.nodes}
        fan_out = {n: 0 for n in self.nodes}
        for e in self.edges:
            if e.dst in fan_in:
                fan_in[e.dst] += 1
            if e.src in fan_out:
                fan_out[e.src] += 1
        return {n: (fan_in[n], fan_out[n]) for n in self.nodes}
