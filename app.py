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
from lineageplanner.report import assessment_md, to_dot

st.set_page_config(page_title="Lineage & Migration Planner", layout="wide")
st.title("🧬 Lineage & Migration Planner")
st.caption("Parse a legacy estate → linked lineage graph → dependency-ordered migration plan.")


@st.cache_resource
def load_graph(root: str):
    return parse_estate(root)


# ------------------------------------------------------------------ sidebar
st.sidebar.header("Estate")
root = st.sidebar.text_input("Directory", "sample_estate")
if not Path(root).exists():
    st.error(f"Directory not found: {root}")
    st.stop()

graph = load_graph(root)
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

tabs = st.tabs(["🕸️ Graph", "🗺️ Migration plan", "📊 Assessment", "🔎 Inspector"])

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
    html = view.to_pyvis_html(sub, height=460)
    if html:
        components.html(html, height=480, scrolling=True)
    else:
        st.graphviz_chart(to_dot(sub))
