"""Interactive lineage & migration-plan viewer.

    pip install streamlit pyvis
    streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from lineageplanner import build_plan, parse_estate
from lineageplanner import view
from lineageplanner.ai import suggest
from lineageplanner.assistant import build_overrides
from lineageplanner.gaps import detect_gaps
from lineageplanner.impact import impact_md, impact_report
from lineageplanner.overrides import dump_overrides
from lineageplanner.report import assessment_md, to_dot

st.set_page_config(page_title="Lineage & Migration Planner", layout="wide")
st.title("🧬 Lineage & Migration Planner")
st.caption("Parse a legacy estate → linked lineage graph → dependency-ordered migration plan.")


# ------------------------------------------------------------------ sidebar
st.sidebar.header("Estate")
root = st.sidebar.text_input("Directory", "sample_estate")
columns = st.sidebar.checkbox("Column-level lineage", value=False,
                              help="Also extract column → column edges (SQL/SAS/PySpark).")
if not Path(root).exists():
    st.error(f"Directory not found: {root}")
    st.stop()

overrides = st.session_state.get("overrides")
graph = parse_estate(root, columns=columns, overrides=overrides)
if overrides:
    st.sidebar.success("Assistant overrides applied")
    if st.sidebar.button("Reset overrides"):
        st.session_state.pop("overrides", None)
        st.rerun()
plan = build_plan(graph)
stats = graph.stats()

all_kinds = sorted(stats["node_kinds"])
all_techs = sorted({n.tech for n in graph.nodes.values() if n.tech})
kinds = st.sidebar.multiselect("Component kinds", all_kinds, default=all_kinds)
techs = st.sidebar.multiselect("Technologies", all_techs, default=all_techs)
query = st.sidebar.text_input("Name contains", "")

filtered = view.filter_graph(graph, kinds=kinds, techs=techs, query=query)

st.sidebar.header("Legend")
for kind in all_kinds:
    st.sidebar.markdown(
        f"<span style='color:{view.KIND_COLOR.get(kind, '#ccc')}'>■</span> {kind}",
        unsafe_allow_html=True)

# ------------------------------------------------------------------ metrics
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Components", stats["nodes"])
c2.metric("Links", stats["edges"])
c3.metric("Waves", plan["summary"]["waves"])
c4.metric("Effort (h)", plan["summary"]["total_effort_hours"])
c5.metric("Cycles", len(graph.cycles()))

tabs = st.tabs(["🕸️ Graph", "🗺️ Migration plan", "📊 Assessment", "🔎 Inspector", "🤖 Assistant"])

# ------------------------------------------------------------------ graph
with tabs[0]:
    st.caption(f"Showing {len(filtered.nodes)} components / {len(filtered.edges)} links "
               "(drag, zoom; hover for details)")
    html = view.to_pyvis_html(filtered, height=680)
    if html:
        components.html(html, height=700, scrolling=True)
    else:
        st.info("Install `pyvis` for the interactive graph; showing a static Graphviz view.")
        st.graphviz_chart(to_dot(filtered))

# ------------------------------------------------------------------ plan
with tabs[1]:
    st.subheader("Dependency-ordered waves")
    for w in plan["waves"]:
        with st.expander(f"Wave {w['wave']} — {len(w['components'])} components", expanded=(w["wave"] == 0)):
            st.write(", ".join(w["components"]))
    st.subheader("Components → target")
    rows = view.plan_rows(plan)
    st.dataframe(rows, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ assessment
with tabs[2]:
    st.markdown(assessment_md(graph))

# ------------------------------------------------------------------ inspector
with tabs[3]:
    names = {graph.nodes[n].name: n for n in graph.nodes}
    picked = st.selectbox("Component", sorted(names))
    nid = names[picked]
    det = view.node_details(graph, plan, nid)
    comp = det["component"] or {}
    a, b, c = st.columns(3)
    a.metric("Kind / Tech", f"{comp.get('kind', '?')} / {comp.get('tech', '?')}")
    b.metric("Target", comp.get("target", "?"))
    c.metric("Complexity / Hours", f"{comp.get('complexity', '?')} / {comp.get('effort_hours', '?')}")
    st.write(f"**Wave**: {comp.get('wave', '?')}  |  **Path**: `{comp.get('path', '')}`")

    depth = st.slider("Lineage depth", 1, 4, 2)
    direction = st.radio("Direction", ["both", "upstream", "downstream"], horizontal=True)
    keep = view.neighborhood(graph, nid, direction=direction, depth=depth)
    sub = view.subgraph(graph, keep)
    st.markdown("**Upstream** (inputs): " + (", ".join(det["upstream"]) or "—"))
    st.markdown("**Downstream** (consumers): " + (", ".join(det["downstream"]) or "—"))

    # ---- impact analysis: what breaks if this component changes ----
    imp = impact_report(graph, plan, nid)
    st.divider()
    st.subheader("💥 Impact")
    i1, i2, i3 = st.columns(3)
    i1.metric("Downstream affected", imp["affected_summary"]["count"])
    i2.metric("Review effort (h)", imp["affected_summary"]["effort_hours"])
    i3.metric("Depends on", imp["depends_summary"]["count"])
    st.caption("Affected kinds: " + str(imp["affected_summary"]["by_kind"] or "—"))
    st.download_button("⬇️ Download impact report (Markdown)",
                       impact_md(graph, plan, nid),
                       file_name=f"impact_{nid.replace(':', '_').replace('.', '_')}.md")

    html = view.to_pyvis_html(sub, height=460)
    if html:
        components.html(html, height=480, scrolling=True)
    else:
        st.graphviz_chart(to_dot(sub))

# ------------------------------------------------------------------ assistant
with tabs[4]:
    st.subheader("🤖 Assistant — complete the end-to-end mapping")
    st.caption("When the mapping isn't fully resolved, answer a few questions. "
               "Suggestions come from heuristics, or an LLM if configured "
               "(`OPENAI_API_KEY` / Databricks). You confirm every answer.")
    qs = detect_gaps(graph)
    if not qs:
        st.success("No open gaps — the lineage is end-to-end. ✅")
    else:
        st.info(f"{len(qs)} gap(s) detected. Review the suggestions and apply.")
        answers = {}
        for q in qs:
            s = suggest(q)
            idx = q.options.index(s["answer"]) if s["answer"] in q.options else 0
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**[{q.kind}]** {q.prompt}")
            c2.caption(f"🤖 {s['source']}: **{s['answer']}**")
            answers[q.id] = st.selectbox(q.id, q.options, index=idx, key=f"q_{q.id}",
                                         label_visibility="collapsed")
        if st.button("✅ Apply answers & rescan", type="primary"):
            st.session_state["overrides"] = build_overrides(qs, answers)
            st.rerun()
        if overrides:
            st.download_button("⬇️ Download overrides.yaml", dump_overrides(overrides),
                               file_name="overrides.yaml")
