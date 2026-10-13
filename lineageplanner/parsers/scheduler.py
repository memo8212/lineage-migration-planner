"""Scheduler parsers: cron (crontab), Autosys JIL, and Makefiles."""
from __future__ import annotations

import re
from pathlib import Path

from lineageplanner.models import CALLS, JOB, PROGRAM, TRIGGERS, node_id
from lineageplanner.parsers.base import Parsed, Parser, stem

# --- extract the artifact a command line invokes -------------------------------
_RE_PMCMD = re.compile(r"pmcmd\s+startworkflow[^\n]*?\b(\w+)", re.I)
_RE_BTEQ = re.compile(r"\bbteq\b[^\n]*?<\s*(\S+)", re.I)
# extension-based: works whether invoked directly or via an interpreter
_EXT_PATTERNS = [
    (re.compile(r"(\S+\.sas)\b", re.I), PROGRAM, "sas"),
    (re.compile(r"(\S+\.py)\b", re.I), PROGRAM, "python"),
    (re.compile(r"(\S+\.pl)\b", re.I), PROGRAM, "perl"),
    (re.compile(r"(\S+\.sql)\b", re.I), PROGRAM, "sql"),
    (re.compile(r"(\S+\.(?:sh|bash|ksh|csh|zsh))\b", re.I), JOB, "shell"),
    (re.compile(r"(\S+\.(?:bat|cmd))\b", re.I), JOB, "batch"),
    (re.compile(r"(\S+\.ps1)\b", re.I), JOB, "powershell"),
]


def _invoked(cmd: str) -> list[tuple[str, str, str]]:
    """Return (node_kind, name, detail) invoked by a command string."""
    out = []
    for m in _RE_PMCMD.finditer(cmd):
        out.append((JOB, m.group(1), "pmcmd"))
    for m in _RE_BTEQ.finditer(cmd):
        out.append((PROGRAM, stem(m.group(1)), "bteq"))
    for rx, kind, det in _EXT_PATTERNS:
        for m in rx.finditer(cmd):
            out.append((kind, stem(m.group(1)), det))
    # de-duplicate while preserving order
    seen, uniq = set(), []
    for item in out:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


class CronParser(Parser):
    name = "cron"
    extensions = (".cron",)

    def matches(self, path: Path) -> bool:
        return path.suffix.lower() == ".cron" or "crontab" in path.name.lower()

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        cron = p.node(node_id(JOB, "crontab"), "crontab", JOB, "cron", relpath)
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line and not line[0].isdigit() and not line.startswith("@"):
                continue  # env assignment
            m = re.match(r"^(@\w+|(?:\S+\s+){4}\S+)\s+(.*)$", line)
            if not m:
                continue
            schedule, cmd = m.group(1), m.group(2)
            for kind, name, det in _invoked(cmd):
                p.edge(cron.id, node_id(kind, name), CALLS, f"cron {schedule}")
        return p


class AutosysParser(Parser):
    name = "autosys"
    extensions = (".jil",)

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        blocks = re.split(r"(?=insert_job:)", text, flags=re.I)
        for block in blocks:
            m = re.search(r"insert_job:\s*(\S+)", block, re.I)
            if not m:
                continue
            name = m.group(1)
            job = p.node(node_id(JOB, name), name, JOB, "autosys", relpath)
            cmd = re.search(r"command:\s*(.+)", block, re.I)
            if cmd:
                for kind, iname, det in _invoked(cmd.group(1)):
                    p.edge(job.id, node_id(kind, iname), CALLS, f"autosys {det}")
            cond = re.search(r"condition:\s*(.+)", block, re.I)
            if cond:
                for dep in re.findall(r"[a-z]*\(([\w.]+)\)", cond.group(1), re.I):
                    p.edge(node_id(JOB, dep), job.id, TRIGGERS, "autosys condition")
            box = re.search(r"box_name:\s*(\S+)", block, re.I)
            if box:
                p.edge(node_id(JOB, box.group(1)), job.id, TRIGGERS, "autosys box")
        return p


class MakefileParser(Parser):
    name = "makefile"
    extensions = ()

    def matches(self, path: Path) -> bool:
        return path.name.lower() in ("makefile", "gnumakefile")

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        job = p.node(node_id(JOB, "make"), "make", JOB, "make", relpath)
        for m in re.finditer(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*)\s*:\s*([A-Za-z0-9_. -]*)$", text, re.M):
            target, deps = m.group(1), m.group(2).split()
            t = p.node(node_id(JOB, target), target, JOB, "make", relpath)
            p.edge(job.id, t.id, CALLS, "make target")
            for d in deps:
                p.edge(node_id(JOB, d), t.id, TRIGGERS, "make dependency")
        return p
