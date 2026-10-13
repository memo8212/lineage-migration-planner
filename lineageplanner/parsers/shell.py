"""Shell parser: orchestration calls, sas/python/pmcmd, file moves."""
from __future__ import annotations

import re
from pathlib import Path

from lineageplanner.models import CALLS, FILE, JOB, PROGRAM, file_id, node_id
from lineageplanner.parsers.base import Parsed, Parser

_RE_SAS = re.compile(r"\bsas\s+[^\n]*?-sysin\s+(\S+)", re.I)
_RE_PY = re.compile(r"\bpython3?\s+(\S+\.py)", re.I)
_RE_SH = re.compile(r"(?:bash|sh|\./)\s*(\S+\.sh)", re.I)
_RE_PMCMD = re.compile(r"pmcmd\s+startworkflow[^\n]*?\b(\w+)\s*$", re.I | re.M)
_RE_MOVE = re.compile(r"\b(?:cp|mv|scp|sftp|rsync|aws\s+s3\s+cp)\s+[^\n]*?(\S+\.(?:csv|json|parquet|txt|ndjson))", re.I)


class ShellParser(Parser):
    name = "shell"
    extensions = (".sh", ".bash")

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        job = p.node(node_id(JOB, path.stem), path.stem, JOB, "shell", relpath)
        for m in _RE_SAS.finditer(text):
            p.edge(job.id, node_id(PROGRAM, Path(m.group(1)).stem), CALLS, "sas -sysin")
        for m in _RE_PY.finditer(text):
            p.edge(job.id, node_id(PROGRAM, Path(m.group(1)).stem), CALLS, "python")
        for m in _RE_SH.finditer(text):
            p.edge(job.id, node_id(JOB, Path(m.group(1)).stem), CALLS, "shell")
        for m in _RE_PMCMD.finditer(text):
            p.edge(job.id, node_id(JOB, m.group(1)), CALLS, "pmcmd")
        for m in _RE_MOVE.finditer(text):
            f = m.group(1)
            p.node(file_id(f), f, FILE, "shell", relpath)
            p.edge(job.id, file_id(f), "lands", "file move")
        return p
