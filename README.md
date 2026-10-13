# Lineage & Migration Planner

Point it at a **bunch of legacy files** and it will:

1. **Parse** them (SAS, SQL, COBOL/JCL, Informatica, Elasticsearch, shell, Python).
2. **Link** the components into one **lineage graph** (what reads/writes/calls what).
3. **Render** the graph (Mermaid, Graphviz DOT, PNG) + an assessment.
4. **Plan the migration** — predict each component's Databricks target, complexity,
   effort, and a **dependency-ordered wave plan**.
5. Produce **predictable, reproducible output** (deterministic IDs, sorted
   JSON/DOT/MD, a stable content hash).

```
 files ──▶ parsers ──▶ Graph(nodes, edges) ──▶ lineage.json/dot/md/png
                                          └──▶ migration_plan.json/md  (+ assessment.md)
```

## Quick start

```bash
pip install -r requirements.txt
python -m lineageplanner scan sample_estate --out artifacts
python -m lineageplanner scan sample_estate --columns --out artifacts   # + column lineage
python -m lineageplanner impact sample_estate CARDS_CLEAN --out artifacts  # what breaks
```

Output:

```
Scanned sample_estate (12 files parsed)
  components: 52  links: 61
  migration waves: 7  effort: 232h ({'LOW': 50, 'MEDIUM': 2})
  cycles: 0
  content hash: 8ff5850a4a4a3515
```

Then read `artifacts/migration_plan.md` (target mapping + waves) and
`artifacts/lineage.md` (Mermaid graph + edge table).

## Interactive viewer (Streamlit)

```bash
pip install -r requirements-streamlit.txt      # streamlit + pyvis
streamlit run app.py
```

The app lets you:

- **Explore the graph** — draggable/zoomable (pyvis), colored by component kind,
  with a kind/tech/name filter in the sidebar.
- **See the migration plan** — dependency-ordered **waves** and a sortable table
  of each component's target / complexity / effort.
- **Inspect a component** — pick any node to see its **upstream inputs** and
  **downstream consumers**, plus a neighborhood subgraph at a chosen depth
  (a quick impact analysis).
- **Read the assessment** — inventory, hubs, entry points, cycles.

Falls back to a static Graphviz view if `pyvis` isn't installed.

## Column-level lineage

`scan --columns` (or the sidebar toggle in the app) parses `SELECT` lists and
adds **column nodes + `derives` edges**:

```
CREATE TABLE out AS SELECT t.account_no, t.amount + 1 AS bumped FROM t
  →  T.account_no --copy--> OUT.account_no
     T.amount     --expr--> OUT.bumped
```

It's heuristic: qualified columns (`t.col`) resolve to their table; unqualified
columns are attributed to every source table in the statement (marked
`ambiguous`). Covers SQL, SAS `proc sql`, and PySpark `spark.sql`.

## Impact analysis — "what breaks if X changes"

```bash
python -m lineageplanner impact sample_estate CARDS_CLEAN
```

```
If CARDS_CLEAN changes…
- 8 downstream components are affected (≈32h of migrated code to review).
- It depends on 4 upstream components.
```

`impact_report()` computes the **downstream closure** (all transitive consumers),
grouped by kind/tech with a review-effort estimate, plus the **upstream closure**
(what it depends on). In the app, the **Inspector** tab shows the same numbers and
offers a **downloadable Markdown report**.

## What it extracts

| Technology | Parses | Produces |
|---|---|---|
| **SAS** | `libname`, `%let`, `%include`, `data … set …`, `proc sql create … from/join`, `proc sort`, `proc export` | program, datasets (read/write), files, params |
| **SQL** | `create table/view as`, `insert … select … from`, joins | datasets + derives edges |
| **COBOL/JCL** | `PROGRAM-ID`, `SELECT … ASSIGN`, `FD`, `COPY`, `READ/WRITE/REWRITE`, `// EXEC PGM=`, `// DD DSN=`, `sas -sysin`, `pmcmd` | programs, datasets, job steps |
| **Informatica** | `MAPPING`, `SOURCE`, `TARGET`, `TRANSFORMATION`, `SESSION`, `WORKFLOW`, `WORKFLOWLINK` | mappings, datasets, sessions, workflow DAG |
| **Elasticsearch** | index mappings (`index_patterns`), ingest `processors`, saved `searches` | indices, pipelines, searches |
| **Unix shell** | `.sh/.bash/.ksh/.csh/.zsh`: `sas -sysin`, `python`, `sqlplus @f.sql`, `bteq`, `pmcmd`, `sh/ksh/csh`, `cp/mv/scp/sftp`, `export` | job calls, SQL steps, file landings, params |
| **Windows batch / PowerShell** | `.bat/.cmd/.ps1`: `call`, `python`, `sas`, `sqlcmd -i`, `bteq`, `Invoke-Sqlcmd`, `copy/move/xcopy/robocopy`, `Copy-Item`, `set` | job calls, SQL steps, file moves, params |
| **Schedulers** | cron (`crontab`/`.cron`), Autosys JIL (`.jil`), `Makefile` | scheduled jobs + `calls`/`triggers` (conditions, boxes, make deps) |
| **Python/PySpark** | `read.table/parquet/csv`, `write.saveAsTable/save`, `spark.sql(...)` | program, datasets, files |

## Migration prediction

Each component is mapped to a Databricks target by a rule table
(`lineageplanner/plan.py`):

| Kind | Target |
|---|---|
| dataset / index | Delta table (Silver/Gold) |
| file | UC Volume + Auto Loader (landing) |
| job (shell/jcl) | Databricks Workflow (job) |
| program (sas/cobol) | PySpark notebook |
| program (sql) | Databricks SQL |
| mapping (informatica) | PySpark notebook |
| pipeline (es) | Lakeflow Declarative Pipeline |
| param | Job parameter / bundle variable |
| lib | UC connection / external location |

**Complexity** is a heuristic (lines / processors / kind) → `LOW | MEDIUM | HIGH`,
mapped to **effort hours** (4 / 16 / 48). **Waves** are computed from the graph:
level = longest path from a root, so dependencies migrate before dependents.

## Outputs

| File | Contents |
|---|---|
| `lineage.json` | nodes + edges + stats (sorted, deterministic) |
| `lineage.dot` / `lineage.png` | Graphviz render |
| `lineage.md` | Mermaid diagram + edge table |
| `assessment.md` | inventory, kinds, hubs, entry points, outputs, cycles |
| `migration_plan.json` / `.md` | per-component target/complexity/effort/wave + wave order |

## Determinism

- Node/edge IDs are slugified; serialization is **sorted**.
- Same input → same `content_hash` (asserted in tests).
- No timestamps in the graph/plan (only in nothing) — outputs are stable for diffing.

## Layout

```
lineageplanner/
  models.py          Graph + Node/Edge + topo/waves/cycles/degrees
  parsers/           sas, sql, cobol_jcl, informatica, elasticsearch, shell,
                     batch (win/powershell), scheduler (cron/autosys/make), python
  columns.py         SELECT-list -> column lineage
  impact.py          downstream/upstream closures + impact report
  plan.py            target rules + complexity + effort + waves
  report.py          Mermaid/DOT/PNG + assessment
  cli.py             `scan` (+ --columns), `impact`
sample_estate/       a mixed, interlinked legacy estate (SAS, SQL, COBOL/JCL,
                     Informatica, ES, shell, batch, PowerShell, cron, Autosys,
                     Makefile, Python) — the demo input
tests/               parser + graph + plan + column + impact + scheduler tests
```

## Extend it

Add a parser in `lineageplanner/parsers/` (subclass `Parser`, implement `matches`
+ `parse`) and register it in `parsers/__init__.py`. Add target rules in
`plan.py`. Everything else (graph, waves, report, plan) works automatically.

See **`TODO.md`** for the full roadmap (planned parsers: Control-M, SSIS, ADF,
Teradata, stored procedures, BI tools, messaging, config files, …).

## Notes / scope

- It's a **static analyzer** (regex/XML based), not a compiler: it extracts the
  common constructs and flags what it can't; treat the graph as a strong first
  draft, not a certified lineage.
- File nodes are linked by **basename** so the same logical file joins across
  technologies (paths are kept in metadata).

## License

MIT — see `LICENSE`.
