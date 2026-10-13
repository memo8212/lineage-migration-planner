"""Tests for column-level lineage."""
from pathlib import Path

from lineageplanner import parse_estate
from lineageplanner.columns import column_edges, col_id

ROOT = Path(__file__).resolve().parents[1]
EST = ROOT / "sample_estate"


def test_column_edges_from_select():
    sql = "select t.account_no, t.amount, t.amount + 1 as bumped from t"
    nodes, edges = column_edges("OUT", ["T"], sql)
    ids = {n.id for n in nodes}
    assert col_id("OUT", "account_no") in ids
    assert col_id("OUT", "bumped") in ids
    triples = {(s, d) for s, d, _, _ in edges}
    assert (col_id("T", "account_no"), col_id("OUT", "account_no")) in triples
    assert (col_id("T", "amount"), col_id("OUT", "bumped")) in triples


def test_ambiguous_column_links_all_sources():
    sql = "select a, b from t1 join t2"
    _, edges = column_edges("OUT", ["T1", "T2"], sql)
    triples = {(s, d) for s, d, _, _ in edges}
    assert (col_id("T1", "a"), col_id("OUT", "a")) in triples
    assert (col_id("T2", "a"), col_id("OUT", "a")) in triples


def test_scan_with_columns_adds_column_nodes():
    plain = parse_estate(EST, columns=False)
    cols = parse_estate(EST, columns=True)
    assert "column" not in plain.stats()["node_kinds"]
    assert cols.stats()["node_kinds"].get("column", 0) > 5
    # column lineage is deterministic too
    assert cols.content_hash() == parse_estate(EST, columns=True).content_hash()
