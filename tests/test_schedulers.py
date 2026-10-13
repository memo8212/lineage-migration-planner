"""Tests for batch / PowerShell / Unix shell / scheduler / makefile parsers."""
from pathlib import Path

from lineageplanner import parse_estate
from lineageplanner.parsers import pick_parser

ROOT = Path(__file__).resolve().parents[1]
EST = ROOT / "sample_estate"


def _parse(rel):
    path = EST / rel
    parser = pick_parser(path)
    return parser.parse(path, rel, path.read_text())


def test_windows_batch():
    parsed = _parse("batch/load_cards.bat")
    edges = {(e.src, e.dst, e.kind) for e in parsed.edges}
    assert ("job:load_cards", "job:prepare_dirs", "calls") in edges          # call
    assert ("job:load_cards", "program:transform", "calls") in edges         # python
    assert ("job:load_cards", "program:ddl", "calls") in edges               # sqlcmd -i
    assert ("job:load_cards", "program:load_fact", "calls") in edges         # bteq
    assert any(e.kind == "lands" for e in parsed.edges)                      # copy
    assert any(n.kind == "param" and n.name == "BATCH_ID" for n in parsed.nodes)


def test_powershell():
    parsed = _parse("powershell/publish.ps1")
    edges = {(e.src, e.dst, e.kind) for e in parsed.edges}
    assert ("job:publish", "program:ddl", "calls") in edges          # Invoke-Sqlcmd
    assert ("job:publish", "program:transform", "calls") in edges
    assert ("job:publish", "job:publish_report", "calls") in edges   # & script
    assert any(e.kind == "lands" for e in parsed.edges)              # Copy-Item


def test_korn_shell():
    parsed = _parse("shell/etl_nightly.ksh")
    edges = {(e.src, e.dst, e.kind) for e in parsed.edges}
    assert ("job:etl_nightly", "program:ddl", "calls") in edges
    assert ("job:etl_nightly", "program:build_mart", "calls") in edges
    assert ("job:etl_nightly", "job:wf_gold_summary", "calls") in edges


def test_cron():
    parsed = _parse("scheduler/crontab")
    dsts = {e.dst for e in parsed.edges}
    assert "job:nightly_orchestrator" in dsts
    assert "job:etl_nightly" in dsts
    assert "program:transform" in dsts
    assert "job:load_cards" in dsts


def test_autosys_jil():
    parsed = _parse("scheduler/bank_jobs.jil")
    edges = {(e.src, e.dst, e.kind) for e in parsed.edges}
    assert ("job:job_extract_cards", "job:etl_nightly", "calls") in edges
    assert ("job:job_extract_cards", "job:job_build_mart", "triggers") in edges  # condition
    assert ("job:box_nightly", "job:job_publish", "triggers") in edges           # box
    assert ("job:job_publish", "job:load_cards", "calls") in edges               # command


def test_makefile():
    parsed = _parse("Makefile")
    edges = {(e.src, e.dst, e.kind) for e in parsed.edges}
    assert ("job:extract", "job:mart", "triggers") in edges     # mart depends on extract
    assert ("job:mart", "job:publish", "triggers") in edges
    assert not any(e.dst == "job:.phony" for e in parsed.edges)  # special targets skipped


def test_estate_includes_new_technologies():
    g = parse_estate(EST)
    techs = {n.tech for n in g.nodes.values()}
    assert {"batch", "powershell", "cron", "autosys", "make", "shell"} <= techs
