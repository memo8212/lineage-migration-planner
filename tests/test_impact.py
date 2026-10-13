"""Tests for impact analysis."""
from pathlib import Path

from lineageplanner import build_plan, downstream_closure, impact_md, impact_report, parse_estate, upstream_closure

ROOT = Path(__file__).resolve().parents[1]
EST = ROOT / "sample_estate"


def _graph():
    return parse_estate(EST)


def test_closures():
    g = _graph()
    down = downstream_closure(g, "ds:CARDS_CLEAN")
    assert "ds:GOLD_SEGMENT" in down           # consumer
    assert "ds:CARDS_STG" not in down          # that's upstream
    up = upstream_closure(g, "ds:CARDS_CLEAN")
    assert "ds:CARDS_STG" in up


def test_impact_report():
    g = _graph()
    plan = build_plan(g)
    rep = impact_report(g, plan, "ds:CARDS_CLEAN")
    assert rep["name"] == "CARDS_CLEAN"
    assert rep["affected_summary"]["count"] >= 4
    assert rep["affected_summary"]["effort_hours"] > 0
    md = impact_md(g, plan, "ds:CARDS_CLEAN")
    assert "Impact Analysis" in md and "downstream" in md.lower()


def test_impact_is_deterministic():
    g = _graph()
    plan = build_plan(g)
    a = impact_report(g, plan, "ds:GOLD_SEGMENT")
    b = impact_report(g, plan, "ds:GOLD_SEGMENT")
    assert a["affected"] == b["affected"]
