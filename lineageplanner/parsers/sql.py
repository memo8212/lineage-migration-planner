"""SQL parser: DDL/DML -> dataset lineage (create/insert/view/select)."""
from __future__ import annotations

import re
from pathlib import Path

from lineageplanner.models import DATASET, DERIVES, READS, WRITES, dataset_id, node_id
from lineageplanner.parsers.base import Parsed, Parser

_RE_CREATE_TABLE = re.compile(r"create\s+(?:or\s+replace\s+)?table\s+([\w.]+)", re.I)
_RE_CREATE_VIEW = re.compile(r"create\s+(?:or\s+replace\s+)?view\s+([\w.]+)\s+as\s+(.*?);", re.I | re.S)
_RE_INSERT = re.compile(r"insert\s+(?:overwrite\s+|into\s+)?(?:table\s+)?([\w.]+)(?:\s+.*?select\s+(.*?);)?", re.I | re.S)
_RE_FROM = re.compile(r"\bfrom\s+([\w.]+)", re.I)
_RE_JOIN = re.compile(r"\bjoin\s+([\w.]+)", re.I)
_RE_CTAS = re.compile(r"create\s+(?:or\s+replace\s+)?table\s+([\w.]+)\s+(?:using\s+\w+\s+)?as\s+(.*?);", re.I | re.S)


class SqlParser(Parser):
    name = "sql"
    extensions = (".sql",)

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        prog = p.node(node_id("program", path.stem), path.stem, "program", "sql", relpath)

        def refs(block: str) -> list[str]:
            out = []
            for rx in (_RE_FROM, _RE_JOIN):
                for m in rx.finditer(block):
                    out.append(m.group(1))
            return out

        # CTAS: create table X as select ... from Y
        for m in _RE_CTAS.finditer(text):
            out, body = m.group(1), m.group(2)
            p.node(dataset_id(out), out.upper(), DATASET, "sql", relpath)
            p.edge(prog.id, dataset_id(out), WRITES, "ctas")
            for src in refs(body):
                p.node(dataset_id(src), src.upper(), DATASET, "sql", relpath)
                p.edge(dataset_id(src), dataset_id(out), READS, "ctas from")

        for m in _RE_CREATE_VIEW.finditer(text):
            out, body = m.group(1), m.group(2)
            p.node(dataset_id(out), out.upper(), DATASET, "sql", relpath, {"object": "view"})
            p.edge(prog.id, dataset_id(out), DERIVES, "create view")
            for src in refs(body):
                p.node(dataset_id(src), src.upper(), DATASET, "sql", relpath)
                p.edge(dataset_id(src), dataset_id(out), READS, "view from")

        for m in _RE_CREATE_TABLE.finditer(text):
            out = m.group(1)
            p.node(dataset_id(out), out.upper(), DATASET, "sql", relpath)

        for m in _RE_INSERT.finditer(text):
            out = m.group(1)
            p.node(dataset_id(out), out.upper(), DATASET, "sql", relpath)
            p.edge(prog.id, dataset_id(out), WRITES, "insert")
            for src in refs(m.group(0)):
                p.node(dataset_id(src), src.upper(), DATASET, "sql", relpath)
                p.edge(dataset_id(src), dataset_id(out), READS, "insert from")

        p.node(node_id("program", path.stem), path.stem, "program", "sql", relpath,
               {"lines": len(text.splitlines())})
        return p
