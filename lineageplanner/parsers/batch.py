"""Windows batch / PowerShell parser: calls, SQL steps, file moves, variables."""
from __future__ import annotations

import re
from pathlib import Path

from lineageplanner.models import (
    CALLS, FILE, JOB, PARAM, PROGRAM, file_id, node_id,
)
from lineageplanner.parsers.base import Parsed, Parser, stem

_RE_CALL_BAT = re.compile(r"\bcall\s+(\S+\.(?:bat|cmd))", re.I)
_RE_PY = re.compile(r"\bpython3?\s+(\S+\.py)", re.I)
_RE_SAS = re.compile(r"\bsas\s+[^\n]*?(\S+\.sas)", re.I)
_RE_SQLCMD = re.compile(r"\bsqlcmd\b[^\n]*?(?:-i|/i)\s+(\S+\.sql)", re.I)
_RE_BTEQ = re.compile(r"\bbteq\b[^\n]*?<\s*(\S+)", re.I)
_RE_PERL = re.compile(r"\bperl\s+(\S+\.pl)", re.I)
_RE_PS_FILE = re.compile(r"powershell[^\n]*?-file\s+(\S+\.ps1)", re.I)
_RE_PS_CALL = re.compile(r"&\s*\.?/?(\S+\.ps1)", re.I)
_RE_SQLPLUS = re.compile(r"\bsqlplus\b[^\n]*?@\s*(\S+\.sql)", re.I)
_RE_COPY = re.compile(r"\b(?:copy|xcopy|move|robocopy|cp)\b[^\n]*?(\S+\.(?:csv|json|parquet|txt|ndjson|dat|xml))\b", re.I)
_RE_SET = re.compile(r"^\s*set\s+(\w+)=([^\r\n]*)", re.I | re.M)
_RE_INVOKE_SQL = re.compile(r"Invoke-Sqlcmd[^\n]*?-InputFile\s+(\S+\.sql)", re.I)
_RE_COPY_ITEM = re.compile(r"\b(?:Copy-Item|Move-Item)\b[^\n]*?(\S+\.(?:csv|json|parquet|txt|ndjson|dat|xml))\b", re.I)


class WindowsParser(Parser):
    """Handles .bat/.cmd (batch) and .ps1 (PowerShell)."""

    name = "batch"
    extensions = (".bat", ".cmd", ".ps1")

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        tech = "powershell" if path.suffix.lower() == ".ps1" else "batch"
        job = p.node(node_id(JOB, path.stem), path.stem, JOB, tech, relpath)

        for m in _RE_CALL_BAT.finditer(text):
            p.edge(job.id, node_id(JOB, stem(m.group(1))), CALLS, "call batch")
        for m in _RE_PS_CALL.finditer(text):
            p.edge(job.id, node_id(JOB, stem(m.group(1))), CALLS, "powershell script")
        for m in _RE_PY.finditer(text):
            p.edge(job.id, node_id(PROGRAM, stem(m.group(1))), CALLS, "python")
        for m in _RE_SAS.finditer(text):
            p.edge(job.id, node_id(PROGRAM, stem(m.group(1))), CALLS, "sas")
        for m in _RE_PERL.finditer(text):
            p.edge(job.id, node_id(PROGRAM, stem(m.group(1))), CALLS, "perl")
        for rx in (_RE_SQLCMD, _RE_SQLPLUS, _RE_INVOKE_SQL):
            for m in rx.finditer(text):
                p.edge(job.id, node_id(PROGRAM, stem(m.group(1))), CALLS, "sql script")
        for m in _RE_BTEQ.finditer(text):
            p.edge(job.id, node_id(PROGRAM, stem(m.group(1))), CALLS, "bteq")
        for m in _RE_PS_FILE.finditer(text):
            p.edge(job.id, node_id(JOB, stem(m.group(1))), CALLS, "powershell -file")
        for rx in (_RE_COPY, _RE_COPY_ITEM):
            for m in rx.finditer(text):
                f = m.group(1)
                p.node(file_id(f), f, FILE, tech, relpath)
                p.edge(job.id, file_id(f), "lands", "file move")
        for m in _RE_SET.finditer(text):
            p.node(node_id(PARAM, m.group(1)), m.group(1).upper(), PARAM, tech, relpath,
                   {"value": m.group(2).strip()})
        return p
