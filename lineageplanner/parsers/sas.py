"""SAS parser: libnames, DATA steps, PROC SQL, includes, exports."""
from __future__ import annotations

import re
from pathlib import Path

from lineageplanner.columns import column_edges
from lineageplanner.models import DATASET, FILE, INCLUDES, PARAM, PROGRAM, READS, WRITES, dataset_id, file_id, node_id
from lineageplanner.parsers.base import Parsed, Parser

_RE_LIBNAME = re.compile(r"libname\s+(\w+)\s+(?:'([^']*)'|\"([^\"]*)\"|(\w+))", re.I)
_RE_LET = re.compile(r"%let\s+(\w+)\s*=\s*([^;]+);", re.I)
_RE_INCLUDE = re.compile(r"%include\s+['\"]([^'\"]+)['\"]", re.I)
_RE_FILENAME = re.compile(r"filename\s+(\w+)\s+['\"]([^'\"]+)['\"]", re.I)
_RE_DATA = re.compile(r"\bdata\s+([\w.]+)\s*;(.*?)\brun\s*;", re.I | re.S)
_RE_SET = re.compile(r"\bset\s+([^;]+);", re.I)
_RE_CREATE = re.compile(r"create\s+table\s+([\w.]+)\s+as", re.I)
_RE_FROM = re.compile(r"\bfrom\s+([^;]+?)(?:\bwhere\b|\bgroup\b|\border\b|\bjoin\b|;|$)", re.I)
_RE_JOIN = re.compile(r"\bjoin\s+([\w.]+)", re.I)
_RE_SORT = re.compile(r"proc\s+sort\s+data\s*=\s*([\w.]+)\s+out\s*=\s*([\w.]+)", re.I)
_RE_EXPORT = re.compile(r"proc\s+export\s+data\s*=\s*([\w.]+)\s+outfile\s*=\s*['\"]([^'\"]+)['\"]", re.I)


def _tables(csv: str) -> list[str]:
    out = []
    for part in csv.split(","):
        name = part.strip().split()[0] if part.strip() else ""
        name = name.strip()
        if name and not name.startswith("(") and re.match(r"^[\w.]+$", name):
            out.append(name)
    return out


class SasParser(Parser):
    name = "sas"
    extensions = (".sas", ".pgm")

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        prog = p.node(node_id(PROGRAM, path.stem), path.stem, PROGRAM, "sas", relpath)

        for m in _RE_LIBNAME.finditer(text):
            p.node(node_id("lib", m.group(1)), m.group(1), "lib", "sas", relpath)
        for m in _RE_LET.finditer(text):
            p.node(node_id(PARAM, m.group(1)), m.group(1), PARAM, "sas", relpath,
                   {"value": m.group(2).strip()})
        for m in _RE_INCLUDE.finditer(text):
            target = file_id(m.group(1))
            p.node(target, m.group(1), FILE, "sas", relpath)
            p.edge(prog.id, target, INCLUDES, "sas %include")
        for m in _RE_FILENAME.finditer(text):
            target = file_id(m.group(2))
            p.node(target, m.group(2), FILE, "sas", relpath)
            p.edge(prog.id, target, "uses", "sas filename")

        # DATA step: data OUT; set IN...;
        for m in _RE_DATA.finditer(text):
            out = m.group(1)
            body = m.group(2)
            p.node(dataset_id(out), out.upper(), DATASET, "sas", relpath)
            p.edge(prog.id, dataset_id(out), WRITES, "data step")
            for sm in _RE_SET.finditer(body):
                for src in _tables(sm.group(1)):
                    p.node(dataset_id(src), src.upper(), DATASET, "sas", relpath)
                    p.edge(dataset_id(src), dataset_id(out), READS, "set")

        # PROC SQL: create table OUT as ... from IN
        for m in _RE_CREATE.finditer(text):
            out = m.group(1)
            p.node(dataset_id(out), out.upper(), DATASET, "sas", relpath)
            p.edge(prog.id, dataset_id(out), WRITES, "proc sql create")
            semi = text.find(";", m.end())
            stmt = text[m.start(): semi if semi != -1 else len(text)]
            sources = []
            for fm in _RE_FROM.finditer(stmt):
                sources += _tables(fm.group(1))
            for jm in _RE_JOIN.finditer(stmt):
                sources.append(jm.group(1))
            for src in sources:
                p.node(dataset_id(src), src.upper(), DATASET, "sas", relpath)
                p.edge(dataset_id(src), dataset_id(out), READS, "proc sql from/join")
            if getattr(self, "columns", False):
                cnodes, cedges = column_edges(out, sources, stmt)
                p.nodes.extend(cnodes)
                for s, d, k, det in cedges:
                    p.edge(s, d, k, det)

        for m in _RE_SORT.finditer(text):
            p.node(dataset_id(m.group(1)), m.group(1).upper(), DATASET, "sas", relpath)
            p.node(dataset_id(m.group(2)), m.group(2).upper(), DATASET, "sas", relpath)
            p.edge(dataset_id(m.group(1)), dataset_id(m.group(2)), READS, "proc sort")
        for m in _RE_EXPORT.finditer(text):
            p.node(dataset_id(m.group(1)), m.group(1).upper(), DATASET, "sas", relpath)
            p.node(file_id(m.group(2)), m.group(2), FILE, "sas", relpath)
            p.edge(dataset_id(m.group(1)), file_id(m.group(2)), WRITES, "proc export")

        p.node(node_id(PROGRAM, path.stem), path.stem, PROGRAM, "sas", relpath,
               {"lines": len(text.splitlines())})
        return p
