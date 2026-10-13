"""CLI: scan a legacy estate -> lineage graph + migration plan.

    python -m lineageplanner scan sample_estate --out artifacts
    python -m lineageplanner scan sample_estate --json      # print plan summary
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lineageplanner.impact import impact_md
from lineageplanner.parsers import parse_estate
from lineageplanner.plan import build_plan, write_plan
from lineageplanner.report import write_lineage


def cmd_scan(args) -> int:
    root = Path(args.dir)
    if not root.exists():
        print(f"error: {root} not found", file=sys.stderr)
        return 2
    out = Path(args.out)
    graph = parse_estate(root, columns=args.columns)
    info = write_lineage(graph, out)
    summary = write_plan(graph, out)

    print(f"Scanned {root} ({getattr(graph, 'parsed_files', '?')} files parsed)"
          + (" [column-level]" if args.columns else ""))
    print(f"  components: {summary['components']}  links: {graph.stats()['edges']}")
    print(f"  node kinds: {graph.stats()['node_kinds']}")
    print(f"  migration waves: {summary['waves']}  effort: {summary['total_effort_hours']}h "
          f"({summary['by_complexity']})")
    print(f"  cycles: {len(graph.cycles())}")
    print(f"  content hash: {info['hash']}")
    print(f"  outputs -> {out}/ (lineage.json, lineage.dot, lineage.md, "
          f"assessment.md, migration_plan.json, migration_plan.md"
          + (", lineage.png" if info["png"] else "") + ")")
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_impact(args) -> int:
    root = Path(args.dir)
    if not root.exists():
        print(f"error: {root} not found", file=sys.stderr)
        return 2
    graph = parse_estate(root, columns=args.columns)
    plan = build_plan(graph)
    # resolve node by id or name (case-insensitive, partial)
    node_id = args.node
    if node_id not in graph.nodes:
        matches = [n for n in graph.nodes
                   if graph.nodes[n].name.lower() == node_id.lower()
                   or node_id.lower() in graph.nodes[n].name.lower()]
        if not matches:
            print(f"error: no component matching '{args.node}'", file=sys.stderr)
            return 2
        node_id = sorted(matches)[0]
    md = impact_md(graph, plan, node_id)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    safe = node_id.replace(":", "_").replace(".", "_")
    (out / f"impact_{safe}.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"\n-> {out / f'impact_{safe}.md'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lineageplanner",
                                 description="Lineage graph + migration planner for legacy estates")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="scan a directory and produce lineage + plan")
    s.add_argument("dir", help="root directory of the legacy estate")
    s.add_argument("--out", default="artifacts")
    s.add_argument("--columns", action="store_true", help="also extract column-level lineage")
    s.add_argument("--json", action="store_true", help="also print the plan summary as JSON")
    s.set_defaults(func=cmd_scan)

    im = sub.add_parser("impact", help="what breaks if a component changes")
    im.add_argument("dir", help="root directory of the legacy estate")
    im.add_argument("node", help="component id or name (partial match ok)")
    im.add_argument("--out", default="artifacts")
    im.add_argument("--columns", action="store_true")
    im.set_defaults(func=cmd_impact)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
