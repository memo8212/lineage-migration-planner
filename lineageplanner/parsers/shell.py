"""Unix shell parser: orchestration calls, sqlplus/bteq/sas/python, file moves, env vars."""
from __future__ import annotations

import re
from pathlib import Path

from lineageplanner.models import CALLS, FILE, JOB, PARAM, PROGRAM, file_id, node_id
from lineageplanner.parsers.base import Parsed, Parser, stem

_RE_SAS = re.compile(r"\bsas\s+[^\n]*?-sysin\s+(\S+)", re.I)
_RE_PY = re.compile(r"\bpython3?\s+(\S+\.py)", re.I)
_RE_SH = re.compile(r"\b(?:bash|sh|ksh|csh|zsh|source|\.)\s+(\S+\.(?:sh|bash|ksh|csh|zsh))", re.I)
_RE_PMCMD = re.compile(r"pmcmd\s+startworkflow[^\n]*?\b(\w+)\s*$", re.I | re.M)
_RE_SQLPLUS = re.compile(r"\bsqlplus\b[^\n]*?@\s*(\S+\.sql)", re.I)
_RE_BTEQ = re.compile(r"\bbteq\b[^\n]*?<\s*(\S+)", re.I)
_RE_PERL = re.compile(r"\bperl\s+(\S+\.pl)", re.I)
_RE_MOVE = re.compile(r"\b(?:cp|mv|scp|sftp|rsync|aws\s+s3\s+cp)\s+[^\n]*?(\S+\.(?:csv|json|parquet|txt|ndjson|dat|xml))", re.I)
_RE_EXPORT = re.compile(r"^\s*export\s+(\w+)=([^\n]*)", re.I | re.M)


class ShellParser(Parser):
    name = "shell"
    extensions = (".sh", ".bash", ".ksh", ".csh", ".zsh")

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        job = p.node(node_id(JOB, path.stem), path.stem, JOB, "shell", relpath)
        for m in _RE_SAS.finditer(text):
            p.edge(job.id, node_id(PROGRAM, stem(m.group(1))), CALLS, "sas -sysin")
        for m in _RE_PY.finditer(text):
            p.edge(job.id, node_id(PROGRAM, stem(m.group(1))), CALLS, "python")
        for m in _RE_SH.finditer(text):
            p.edge(job.id, node_id(JOB, stem(m.group(1))), CALLS, "shell")
        for m in _RE_PMCMD.finditer(text):
            p.edge(job.id, node_id(JOB, m.group(1)), CALLS, "pmcmd")
        for m in _RE_SQLPLUS.finditer(text):
            p.edge(job.id, node_id(PROGRAM, stem(m.group(1))), CALLS, "sqlplus")
        for m in _RE_BTEQ.finditer(text):
            p.edge(job.id, node_id(PROGRAM, stem(m.group(1))), CALLS, "bteq")
        for m in _RE_PERL.finditer(text):
            p.edge(job.id, node_id(PROGRAM, stem(m.group(1))), CALLS, "perl")
        for m in _RE_MOVE.finditer(text):
            f = m.group(1)
            p.node(file_id(f), f, FILE, "shell", relpath)
            p.edge(job.id, file_id(f), "lands", "file move")
        for m in _RE_EXPORT.finditer(text):
            p.node(node_id(PARAM, m.group(1)), m.group(1).upper(), PARAM, "shell", relpath,
                   {"value": m.group(2).strip()})
        return p
