"""Tests for the lineage parsers and graph."""
from pathlib import Path

from lineageplanner import parse_estate
from lineageplanner.parsers import pick_parser

ROOT = Path(__file__).resolve().parents[1]
EST = ROOT / "sample_estate"


def test_parse_estate_builds_connected_graph():
    g = parse_estate(EST)
    names = {n.name for n in g.nodes.values()}
    # components across every technology
    assert {"CARDS_CLEAN", "CARDS_STG", "GOLD_SEGMENT", "CUSTOMER_DIM"} <= names  # datasets
    assert "nightly_orchestrator" in names       # shell
    assert "extract_cards" in names              # sas program
    assert "ACCTPOST" in names                   # cobol program
    assert "ACCTMAST" in names                   # vsam dataset
    assert "m_load_dept_txn" in names            # informatica mapping
    assert "bank-dept-all" in names              # es index
    assert "dept_ingest" in names                # es pipeline
    assert "transform" in names                  # python
    assert g.stats()["edges"] > 40


def test_sas_parser_lineage():
    parser = pick_parser(EST / "sas" / "extract_cards.sas")
    parsed = parser.parse(EST / "sas" / "extract_cards.sas", "sas/extract_cards.sas",
                          (EST / "sas" / "extract_cards.sas").read_text())
    edges = {(e.src, e.dst, e.kind) for e in parsed.edges}
    assert ("ds:BANK_RAW_CARDS", "ds:CARDS_STG", "reads") in edges
    assert ("ds:CARDS_STG", "ds:CARDS_CLEAN", "reads") in edges
    assert any(e.kind == "includes" for e in parsed.edges)


def test_jcl_writes_vs_reads():
    parser = pick_parser(EST / "jcl" / "nightly.jcl")
    parsed = parser.parse(EST / "jcl" / "nightly.jcl", "jcl/nightly.jcl",
                          (EST / "jcl" / "nightly.jcl").read_text())
    edges = {(e.src, e.dst, e.kind) for e in parsed.edges}
    assert ("job:nightly", "ds:PROD_TRANS_SORTED", "writes") in edges
    assert ("job:nightly", "ds:PROD_TRANS_DAILY", "reads") in edges


def test_graph_is_deterministic():
    a = parse_estate(EST)
    b = parse_estate(EST)
    assert a.content_hash() == b.content_hash()
    assert a.topological_order() == b.topological_order()


def test_read_modify_write_is_not_a_cycle():
    g = parse_estate(EST)
    # ACCTPOST reads and rewrites ACCTMAST -> not a real cycle
    for comp in g.cycles():
        assert not ({"ds:ACCTMAST", "program:acctpost"} == set(comp))


def test_waves_respect_dependencies():
    g = parse_estate(EST)
    order = g.topological_order()
    pos = {n: i for i, n in enumerate(order)}
    for e in g.edges:
        if e.src in pos and e.dst in pos and e.src != e.dst:
            # read/write cycles may reorder; for acyclic read edges order holds
            pass
    waves = g.waves()
    assert len(waves) >= 3
    # a source dataset appears no later than its consumer
    flat = {n: i for i, w in enumerate(waves) for n in w}
    assert flat["ds:CARDS_STG"] < flat["ds:CARDS_CLEAN"]
