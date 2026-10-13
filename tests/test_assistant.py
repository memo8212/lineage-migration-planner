"""Tests for the gap detector, overrides, and the AI assistant."""
from pathlib import Path

from lineageplanner import assist, build_overrides, detect_gaps, parse_estate
from lineageplanner.ai import heuristic, suggest

ROOT = Path(__file__).resolve().parents[1]
EST = ROOT / "sample_estate"


def test_detect_gaps_finds_placeholders_and_orphans():
    qs = detect_gaps(parse_estate(EST))
    kinds = {q.kind for q in qs}
    assert "placeholder" in kinds
    assert "orphan_source" in kinds
    assert all(q.options for q in qs)


def test_unknown_file_gap(tmp_path):
    (tmp_path / "mystery.xyz").write_text("data")
    g = parse_estate(tmp_path)
    assert "mystery.xyz" in g.unknown_files
    qs = detect_gaps(g)
    assert any(q.kind == "unknown_file" and q.target == "mystery.xyz" for q in qs)


def test_heuristic_suggestions():
    g = parse_estate(EST)
    qs = {q.id: q for q in detect_gaps(g)}
    wf = next(q for q in qs.values() if "wf_gold_summary" in q.target)
    assert heuristic(wf)[0] == "workflow"
    assert suggest(wf)["source"] in ("heuristic", "openai", "databricks")


def test_build_overrides_from_answers():
    g = parse_estate(EST)
    qs = detect_gaps(g)
    answers = {q.id: q.default for q in qs}
    ov = build_overrides(qs, answers)
    assert set(ov) >= {"external_sources", "terminal_sinks", "node_kinds",
                       "unknown_files", "column_resolution", "extra_edges"}
    assert ov["external_sources"] or ov["node_kinds"]


def test_assist_closes_gaps_with_suggestions():
    result = assist(EST, suggest_missing=True)
    assert len(result["questions"]) > 0
    assert len(result["remaining"]) == 0          # end-to-end after applying suggestions
    assert result["answers"]


def test_apply_overrides_marks_external():
    g = parse_estate(EST)
    qs = detect_gaps(g)
    answers = {}
    for q in qs:
        if q.kind == "placeholder":
            answers[q.id] = "external"
        elif q.kind == "orphan_source":
            answers[q.id] = "external"
        elif q.kind == "orphan_sink":
            answers[q.id] = "terminal"
        else:
            answers[q.id] = q.default
    ov = build_overrides(qs, answers)
    g2 = parse_estate(EST, overrides=ov)
    assert len(detect_gaps(g2)) == 0
    assert any(n.meta.get("external") for n in g2.nodes.values())
