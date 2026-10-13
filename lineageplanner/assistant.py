"""The assistant: interview the user about gaps, then apply answers end-to-end."""
from __future__ import annotations

from pathlib import Path

from lineageplanner.ai import suggest, tech_for_ext
from lineageplanner.gaps import detect_gaps
from lineageplanner.overrides import apply_overrides, blank_overrides
from lineageplanner.parsers import parse_estate
from lineageplanner.plan import build_plan


def answer_to_override(q, answer: str, ov: dict) -> None:
    """Translate one (question, answer) into an overrides patch."""
    answer = (answer or "").strip()
    if not answer:
        return
    if q.kind == "placeholder":
        if answer == "external":
            ov["node_kinds"][q.target] = {"kind": "dataset", "tech": "external"}
            ov["external_sources"].append(q.target)
        elif answer == "workflow":
            ov["node_kinds"][q.target] = {"kind": "job", "tech": "workflow"}
        elif answer == "file":
            ov["node_kinds"][q.target] = {"kind": "file", "tech": ""}
        elif answer == "program":
            ov["node_kinds"][q.target] = {"kind": "program", "tech": ""}
        elif answer == "ignore":
            ov["ignored"].append(q.target)
    elif q.kind == "orphan_source":
        if answer == "external":
            ov["external_sources"].append(q.target)
        elif answer == "ignore":
            ov["ignored"].append(q.target)
    elif q.kind == "orphan_sink":
        if answer == "terminal":
            ov["terminal_sinks"].append(q.target)
        elif answer == "ignore":
            ov["ignored"].append(q.target)
    elif q.kind == "unknown_file":
        if answer == "ignore":
            return
        tech = tech_for_ext(q.context.get("ext", ""))
        ov["unknown_files"][q.target] = {"kind": answer, "tech": tech}
    elif q.kind == "ambiguous_column":
        ov["column_resolution"][q.target] = answer


def build_overrides(questions: list, answers: dict) -> dict:
    ov = blank_overrides()
    by_id = {q.id: q for q in questions}
    for qid, ans in answers.items():
        q = by_id.get(qid)
        if q:
            answer_to_override(q, ans, ov)
    # de-duplicate list fields, keep deterministic order
    for key in ("external_sources", "terminal_sinks", "ignored"):
        ov[key] = sorted(set(ov[key]))
    return ov


def assist(root: str | Path, columns: bool = False, answers: dict | None = None,
           suggest_missing: bool = False) -> dict:
    """Detect gaps, collect answers (optionally AI-suggested), apply, re-scan."""
    graph_before = parse_estate(root, columns=columns)
    questions = detect_gaps(graph_before)
    answers = dict(answers or {})
    suggestions: dict[str, dict] = {}
    hint = f"{graph_before.stats()['nodes']} components, {graph_before.stats()['edges']} links"
    for q in questions:
        if q.id not in answers:
            s = suggest(q, hint)
            suggestions[q.id] = s
            if suggest_missing:
                answers[q.id] = s["answer"]

    ov = build_overrides(questions, answers)
    graph_after = apply_overrides(parse_estate(root, columns=columns), ov)
    plan = build_plan(graph_after)
    remaining = detect_gaps(graph_after)

    return {"graph_before": graph_before, "graph": graph_after, "plan": plan,
            "questions": questions, "answers": answers, "suggestions": suggestions,
            "overrides": ov, "remaining": remaining}


def assist_report(result: dict) -> str:
    before = result["graph_before"].stats()
    after = result["graph"].stats()
    answered = result["answers"]
    qs = result["questions"]
    remaining = result["remaining"]
    src = {result["suggestions"].get(q.id, {}).get("source") for q in qs} - {None}
    end_to_end = len(remaining) == 0

    lines = [
        "# Assistant Report — completing the end-to-end mapping",
        "",
        f"- Gaps detected: **{len(qs)}**  (answered: {len(answered)})",
        f"- Suggestion source(s): {', '.join(sorted(src)) or 'none'}",
        f"- Remaining gaps after applying answers: **{len(remaining)}**",
        f"- Result: {'✅ end-to-end (no open gaps)' if end_to_end else '⚠️ still open'}",
        f"- Components: {before['nodes']} → **{after['nodes']}**  |  "
        f"Links: {before['edges']} → **{after['edges']}**",
        "",
        "## Interview (question → answer)",
        "",
        "| Gap | Question | Answer | Suggested by |",
        "|---|---|---|---|",
    ]
    for q in qs:
        ans = answered.get(q.id, "—")
        sugg = result["suggestions"].get(q.id, {})
        by = f"{sugg.get('source', '')} ({sugg.get('answer', '')})" if sugg else "user"
        lines.append(f"| {q.kind} | {q.prompt} | **{ans}** | {by} |")

    if remaining:
        lines += ["", "## Still open", "",
                  "| Kind | Question |", "|---|---|"]
        lines += [f"| {q.kind} | {q.prompt} |" for q in remaining]
    return "\n".join(lines)
