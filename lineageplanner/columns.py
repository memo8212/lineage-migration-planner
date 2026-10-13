"""Column-level lineage: parse SELECT lists into column nodes + `derives` edges.

Static and heuristic: for `CREATE TABLE out AS SELECT t.a, t.b+1 AS c FROM t` we
emit `t.a -> out.a`, `t.b -> out.c` (expression) edges. Unqualified columns are
attributed to every source table in the statement (marked ambiguous).
"""
from __future__ import annotations

import re

from lineageplanner.models import COLUMN, Node

KEYWORDS = {
    "select", "from", "where", "group", "by", "order", "having", "join", "inner",
    "left", "right", "full", "outer", "on", "as", "and", "or", "not", "in", "is",
    "null", "case", "when", "then", "else", "end", "distinct", "count", "sum",
    "avg", "min", "max", "round", "cast", "coalesce", "concat", "upper", "lower",
    "date", "to_date", "to_char", "abs", "substr", "substring", "length", "trim",
    "current_date", "current_timestamp", "sha2", "greatest", "least", "like",
    "union", "all", "asc", "desc", "with", "partition", "over", "row_number",
}


def col_id(table: str, column: str) -> str:
    t = re.sub(r"[^a-z0-9_]+", "_", table.strip().lower()).strip("_")
    c = re.sub(r"[^a-z0-9_]+", "_", column.strip().lower()).strip("_")
    return f"col:{t}.{c}"


def column_node(table: str, column: str) -> Node:
    return Node(id=col_id(table, column), name=f"{table}.{column}", kind=COLUMN,
                tech="", meta={"table": table, "column": column})


def _split_top(s: str) -> list[str]:
    out, depth, buf = [], 0, []
    in_str = None
    for ch in s:
        if in_str:
            buf.append(ch)
            if ch == in_str:
                in_str = None
            continue
        if ch in "'\"":
            in_str = ch
            buf.append(ch)
        elif ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


def select_list(sql: str) -> str | None:
    """Return the text between the first SELECT and its matching FROM (depth 0)."""
    m = re.search(r"\bselect\b(.*?)\bfrom\b", sql, re.I | re.S)
    if not m:
        return None
    return m.group(1)


def _alias(item: str) -> tuple[str, str]:
    """Return (expression, output-column-name)."""
    m = re.search(r"\bas\s+([\w.]+)\s*$", item, re.I)
    if m:
        return item[:m.start()].strip(), m.group(1).split(".")[-1]
    # bare `expr alias` (last word if the expression isn't a simple qualified name)
    stripped = item.strip()
    parts = stripped.split()
    if len(parts) >= 2 and re.match(r"^[\w.]+$", parts[-1]) and not re.match(r"^[\w.]+$", stripped):
        return " ".join(parts[:-1]), parts[-1]
    return stripped, stripped.split(".")[-1]


def _identifiers(expr: str) -> set[str]:
    """Column identifiers referenced by an expression (excluding functions/keywords)."""
    expr = re.sub(r"'[^']*'", " ", expr)
    idents = set()
    for m in re.finditer(r"[A-Za-z_][\w.]*", expr):
        word = m.group(0)
        after = expr[m.end():].lstrip()
        if after.startswith("("):
            continue  # function name
        base = word.split(".")[-1]
        if base.lower() in KEYWORDS or word.lower() in KEYWORDS:
            continue
        idents.add(word)
    return idents


def _resolve(table_ref: str, sources: list[str]) -> str | None:
    ref = table_ref.lower()
    for s in sources:
        if s.lower() == ref or s.lower().endswith("." + ref) or ref.endswith("." + s.lower()):
            return s
    return None


def column_edges(out_table: str, sources: list[str], select_sql: str) -> tuple[list, list]:
    """Return (column_nodes, edges) for one SELECT ... FROM statement."""
    nodes: dict[str, Node] = {}
    edges: list = []
    block = select_list(select_sql)
    if not block:
        return [], []
    for item in _split_top(block):
        if not item.strip():
            continue
        expr, out_col = _alias(item)
        if out_col.lower() in KEYWORDS:
            continue
        nodes[col_id(out_table, out_col)] = column_node(out_table, out_col)
        dst = col_id(out_table, out_col)
        is_expr = not re.fullmatch(r"[\w.]+", expr.strip())
        for ident in _identifiers(expr):
            if "." in ident:
                tbl = _resolve(ident.split(".")[0], sources)
                src_col = ident.split(".")[-1]
                if tbl:
                    nodes[col_id(tbl, src_col)] = column_node(tbl, src_col)
                    edges.append((col_id(tbl, src_col), dst,
                                  "derives", "expr" if is_expr else "copy"))
            else:
                for s in sources:  # ambiguous: attribute to every source
                    nodes[col_id(s, ident)] = column_node(s, ident)
                    edges.append((col_id(s, ident), dst, "derives",
                                  "ambiguous" if len(sources) > 1 else ("expr" if is_expr else "copy")))
    return list(nodes.values()), edges
