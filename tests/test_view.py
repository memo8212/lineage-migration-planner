"""Tests for the viewer helpers."""
from pathlib import Path

from lineageplanner import build_plan, parse_estate
from lineageplanner import view

ROOT = Path(__file__).resolve().parents[1]
EST = ROOT / "sample_estate"


def _graph():
    return parse_estate(EST)


def test_filter_by_kind_and_query():
    g = _graph()
    only_ds = view.filter_graph(g, kinds={"dataset"})
    assert all(n.kind == "dataset" for n in only_ds.nodes.values())
    assert only_ds.stats()["nodes"] < g.stats()["nodes"]

    q = view.filter_graph(g, query="cards")
    assert q.nodes and all("card" in n.name.lower() for n in q.nodes.values())


def test_neighborhood_and_subgraph():
    g = _graph()
    nbrs = view.neighborhood(g, "ds:CARDS_CLEAN", direction="upstream", depth=1)
    assert "ds:CARDS_CLEAN" in nbrs
    assert "ds:CARDS_STG" in nbrs  # direct input
    sub = view.subgraph(g, nbrs)
    assert set(sub.nodes) == nbrs
    assert sub.stats()["nodes"] == len(nbrs)


def test_plan_rows_and_node_details():
    g = _graph()
    plan = build_plan(g)
    rows = view.plan_rows(plan)
    assert len(rows) == plan["summary"]["components"]
    assert {"name", "target", "wave", "hours"} <= set(rows[0])

    det = view.node_details(g, plan, "ds:CARDS_CLEAN")
    assert det["name"] == "CARDS_CLEAN"
    assert "CARDS_STG" in det["upstream"]
    assert det["component"]["target"].startswith("Delta table")


def test_pyvis_html_is_optional():
    g = _graph()
    html = view.to_pyvis_html(g, height=200)
    assert html is None or "<html" in html.lower()
