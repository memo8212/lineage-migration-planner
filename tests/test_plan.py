"""Tests for the migration planner."""
from pathlib import Path

from lineageplanner import build_plan, parse_estate

ROOT = Path(__file__).resolve().parents[1]
EST = ROOT / "sample_estate"


def test_plan_targets_and_effort():
    plan = build_plan(parse_estate(EST))
    by_name = {c["name"]: c for c in plan["components"]}
    assert "Delta table" in by_name["CARDS_CLEAN"]["target"]
    assert "PySpark notebook" in by_name["extract_cards"]["target"]
    assert "Workflow" in by_name["nightly_orchestrator"]["target"]
    file_comp = next(c for c in plan["components"] if c["name"].endswith("dept_txn.csv"))
    assert "landing" in file_comp["target"].lower() or "volume" in file_comp["target"].lower()
    assert plan["summary"]["total_effort_hours"] > 0
    assert plan["summary"]["waves"] >= 3


def test_plan_is_deterministic():
    p1 = build_plan(parse_estate(EST))
    p2 = build_plan(parse_estate(EST))
    assert p1["summary"]["content_hash"] == p2["summary"]["content_hash"]
    assert [c["id"] for c in p1["components"]] == [c["id"] for c in p2["components"]]


def test_waves_are_ordered():
    plan = build_plan(parse_estate(EST))
    assert plan["waves"][0]["wave"] == 0
    # every component has a wave assigned
    assert all("wave" in c for c in plan["components"])
