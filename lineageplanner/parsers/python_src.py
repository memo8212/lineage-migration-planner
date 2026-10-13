"""Python/PySpark parser: read/write tables + files, spark.sql lineage."""
from __future__ import annotations

import re
from pathlib import Path

from lineageplanner.columns import column_edges
from lineageplanner.models import DATASET, FILE, PROGRAM, READS, WRITES, dataset_id, file_id, node_id
from lineageplanner.parsers.base import Parsed, Parser

_RE_READ_TABLE = re.compile(r"\.read(?:\.\w+)?\(\s*['\"]([\w.]+)['\"]|\.table\(\s*['\"]([\w.]+)['\"]|read\.parquet\(\s*['\"]([^'\"]+)['\"]", re.I)
_RE_READ_PATH = re.compile(r"\.read\.\w+\(\s*['\"]([^'\"]+\.(?:csv|json|parquet|ndjson))['\"]", re.I)
_RE_WRITE_TABLE = re.compile(r"\.saveAsTable\(\s*['\"]([\w.]+)['\"]|\.saveAsTable\(f?['\"]([\w.]+)['\"]", re.I)
_RE_WRITE_PATH = re.compile(r"\.(?:save|parquet|csv|writeStream)\w*\(\s*['\"]([^'\"]+)['\"]", re.I)
_RE_SQL = re.compile(r"(?:spark\.)?sql\(\s*(?:f?['\"]{1,3})(.*?)(?:['\"]{1,3})", re.I | re.S)
_RE_FROM = re.compile(r"\bfrom\s+([\w.]+)", re.I)
_RE_INTO = re.compile(r"\b(?:insert\s+into|create\s+(?:or\s+replace\s+)?table|merge\s+into)\s+([\w.]+)", re.I)


class PythonParser(Parser):
    name = "python"
    extensions = (".py",)

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        prog = p.node(node_id(PROGRAM, path.stem), path.stem, PROGRAM, "python", relpath,
                      {"lines": len(text.splitlines())})

        for m in _RE_READ_TABLE.finditer(text):
            name = m.group(1) or m.group(2)
            if name:
                p.node(dataset_id(name), name.upper(), DATASET, "python", relpath)
                p.edge(dataset_id(name), prog.id, READS, "read.table")
        for m in _RE_READ_PATH.finditer(text):
            f = m.group(1)
            p.node(file_id(f), f, FILE, "python", relpath)
            p.edge(file_id(f), prog.id, READS, "read path")

        for m in _RE_WRITE_TABLE.finditer(text):
            name = m.group(1) or m.group(2)
            if name:
                p.node(dataset_id(name), name.upper(), DATASET, "python", relpath)
                p.edge(prog.id, dataset_id(name), WRITES, "saveAsTable")
        for m in _RE_WRITE_PATH.finditer(text):
            f = m.group(1)
            if "." in f or "/" in f:
                p.node(file_id(f), f, FILE, "python", relpath)
                p.edge(prog.id, file_id(f), WRITES, "write path")

        for m in _RE_SQL.finditer(text):
            sql = m.group(1)
            outs = [x.group(1) for x in _RE_INTO.finditer(sql)]
            srcs = [x.group(1) for x in _RE_FROM.finditer(sql)]
            for o in outs:
                p.node(dataset_id(o), o.upper(), DATASET, "python", relpath)
                p.edge(prog.id, dataset_id(o), WRITES, "spark.sql")
                if getattr(self, "columns", False):
                    cnodes, cedges = column_edges(o, srcs, sql)
                    p.nodes.extend(cnodes)
                    for s, d, k, det in cedges:
                        p.edge(s, d, k, det)
            for s in srcs:
                p.node(dataset_id(s), s.upper(), DATASET, "python", relpath)
                for o in outs:
                    p.edge(dataset_id(s), dataset_id(o), READS, "spark.sql")
                if not outs:
                    p.edge(dataset_id(s), prog.id, READS, "spark.sql")
        return p
