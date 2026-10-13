"""Parser registry + estate scanner."""
from __future__ import annotations

from pathlib import Path

from lineageplanner.models import Graph
from lineageplanner.parsers.batch import WindowsParser
from lineageplanner.parsers.cobol_jcl import CobolJclParser
from lineageplanner.parsers.elasticsearch import ElasticsearchParser
from lineageplanner.parsers.informatica import InformaticaParser
from lineageplanner.parsers.python_src import PythonParser
from lineageplanner.parsers.sas import SasParser
from lineageplanner.parsers.scheduler import AutosysParser, CronParser, MakefileParser
from lineageplanner.parsers.shell import ShellParser
from lineageplanner.parsers.sql import SqlParser

PARSERS = [
    InformaticaParser(),   # specific XML first
    SasParser(),
    SqlParser(),
    CobolJclParser(),
    WindowsParser(),       # .bat / .cmd / .ps1
    ShellParser(),         # .sh / .bash / .ksh / .csh / .zsh
    CronParser(),          # crontab / .cron
    AutosysParser(),       # .jil
    MakefileParser(),      # Makefile
    ElasticsearchParser(),  # JSON (after XML check)
    PythonParser(),
]

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "artifacts", "graphify-out"}
SKIP_EXT = {".png", ".jpg", ".mp4", ".pdf", ".zip", ".gz", ".parquet", ".whl", ".csv"}


def pick_parser(path: Path):
    for parser in PARSERS:
        if parser.matches(path):
            return parser
    return None


def parse_estate(root: str | Path, columns: bool = False) -> Graph:
    """Scan a directory tree and build one deterministic lineage graph.

    Set `columns=True` to also extract column-level lineage.
    """
    root = Path(root)
    for parser in PARSERS:
        parser.columns = columns
    graph = Graph()
    files = sorted(p for p in root.rglob("*")
                   if p.is_file()
                   and not any(part in SKIP_DIRS for part in p.parts)
                   and p.suffix.lower() not in SKIP_EXT)
    parsed_files = 0
    for path in files:
        parser = pick_parser(path)
        if parser is None:
            continue
        relpath = str(path.relative_to(root))
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        try:
            parsed = parser.parse(path, relpath, text)
        except Exception:  # noqa: BLE001 - never let one file break the scan
            continue
        parsed_files += 1
        for n in parsed.nodes:
            graph.add_node(n)
        for e in parsed.edges:
            graph.add_edge(e.src, e.dst, e.kind, e.detail)
    graph.parsed_files = parsed_files  # type: ignore[attr-defined]
    return graph
