"""Parser base types + registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lineageplanner.models import Edge, Node


@dataclass
class Parsed:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def node(self, *args, **kwargs) -> Node:
        n = Node(*args, **kwargs)
        self.nodes.append(n)
        return n

    def edge(self, src: str, dst: str, kind: str, detail: str = "") -> None:
        self.edges.append(Edge(src, dst, kind, detail))


class Parser:
    """Subclasses implement `matches` and `parse`."""

    name: str = "base"
    extensions: tuple = ()
    columns: bool = False

    def matches(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:  # pragma: no cover
        raise NotImplementedError


def stem(path: str) -> str:
    """Basename without extension, handling both / and \\ separators."""
    name = path.replace("\\", "/").rstrip("/").split("/")[-1]
    return name.rsplit(".", 1)[0] if "." in name else name
