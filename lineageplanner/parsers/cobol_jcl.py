"""COBOL + JCL parser: programs, VSAM/DB2 datasets, step dependencies."""
from __future__ import annotations

import re
from pathlib import Path

from lineageplanner.models import (
    CALLS, DATASET, JOB, PROGRAM, READS, WRITES, dataset_id, node_id,
)
from lineageplanner.parsers.base import Parsed, Parser

# JCL
_RE_JOB = re.compile(r"^//(\w+)\s+JOB\b", re.M)
_RE_EXEC = re.compile(r"^//(\w+)\s+EXEC\s+(?:PGM=)?(\w+)", re.M)
_RE_DD_DSN = re.compile(r"^//(\w+)\s+DD\s+.*?DSN=([\w.]+)", re.M)
_RE_SAS_SYSIN = re.compile(r"sas\s+[^\n]*?-sysin\s+(\S+)", re.I)
_RE_PMCMD = re.compile(r"pmcmd\s+startworkflow[^\n]*?(\w+)\s*$", re.I | re.M)

# COBOL
_RE_SELECT = re.compile(r"SELECT\s+([\w-]+)\s+ASSIGN\s+TO\s+([\w-]+)", re.I)
_RE_FD = re.compile(r"FD\s+([\w-]+)", re.I)
_RE_COPY = re.compile(r"COPY\s+([\w-]+)", re.I)
_RE_READ = re.compile(r"\bREAD\s+([\w-]+)", re.I)
_RE_WRITE = re.compile(r"\b(?:WRITE|REWRITE)\s+([\w-]+)", re.I)
_RE_PROGRAM_ID = re.compile(r"PROGRAM-ID\.\s+([\w-]+)", re.I)


class CobolJclParser(Parser):
    name = "cobol_jcl"
    extensions = (".jcl", ".cbl", ".cob", ".cobol")

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        if path.suffix.lower() == ".jcl":
            return self._jcl(path, relpath, text, p)
        return self._cobol(path, relpath, text, p)

    def _jcl(self, path, relpath, text, p: Parsed) -> Parsed:
        job = p.node(node_id(JOB, path.stem), path.stem, JOB, "jcl", relpath)
        prev = None
        for line in text.splitlines():
            m = _RE_EXEC.match(line)
            if m:
                step, pgm = m.group(1), m.group(2)
                prog = p.node(node_id(PROGRAM, pgm), pgm, PROGRAM, "jcl", relpath)
                p.edge(job.id, prog.id, CALLS, f"EXEC {step}")
                if prev:
                    p.edge(prev, prog.id, "after", "step order")
                prev = prog.id
            d = _RE_DD_DSN.match(line)
            if d:
                ds = d.group(2)
                ddname = d.group(1).upper()
                p.node(dataset_id(ds), ds, DATASET, "jcl", relpath)
                is_write = "OUT" in ddname or "DISP=(NEW" in line.upper() or "DISP=(MOD" in line.upper()
                p.edge(job.id, dataset_id(ds), WRITES if is_write else READS, f"DD {ddname}")
        for m in _RE_SAS_SYSIN.finditer(text):
            p.edge(job.id, node_id(PROGRAM, Path(m.group(1)).stem), CALLS, "sas -sysin")
        for m in _RE_PMCMD.finditer(text):
            p.edge(job.id, node_id(JOB, m.group(1)), CALLS, "pmcmd startworkflow")
        return p

    def _cobol(self, path, relpath, text, p: Parsed) -> Parsed:
        pid = _RE_PROGRAM_ID.search(text)
        prog = p.node(node_id(PROGRAM, pid.group(1) if pid else path.stem),
                      pid.group(1) if pid else path.stem, PROGRAM, "cobol", relpath)
        files = {}
        for m in _RE_SELECT.finditer(text):
            files[m.group(1).upper()] = m.group(2)
            p.node(dataset_id(m.group(2)), m.group(2), DATASET, "cobol", relpath)
        for m in _RE_FD.finditer(text):
            p.node(node_id("fd", m.group(1)), m.group(1), "file", "cobol", relpath)
        for m in _RE_COPY.finditer(text):
            p.edge(prog.id, node_id("copybook", m.group(1)), "includes", "copy")
        # READ/WRITE map file name -> dataset via SELECT
        for m in _RE_READ.finditer(text):
            name = m.group(1).upper()
            if name in files:
                p.edge(dataset_id(files[name]), prog.id, READS, "READ")
        for m in _RE_WRITE.finditer(text):
            name = m.group(1).upper()
            if name in files:
                p.edge(prog.id, dataset_id(files[name]), WRITES, "WRITE/REWRITE")
        return p
