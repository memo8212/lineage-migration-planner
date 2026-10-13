# TODO / Roadmap

Roadmap for `lineage-migration-planner`. Legend: `[x]` done · `[ ]` planned ·
`[~]` partial. Priorities: **P0** next · **P1** soon · **P2** later.

---

## Done

### Parsers (7 technologies → nodes + edges)
- [x] **SAS** — `libname`, `%let`, `%include`, `data…set`, `proc sql create…from/join`, `proc sort`, `proc export`
- [x] **SQL** — `create table/view as`, `insert…select…from`, joins
- [x] **COBOL / JCL** — `PROGRAM-ID`, `SELECT…ASSIGN`, `FD`, `COPY`, `READ/WRITE/REWRITE`, `// EXEC PGM=`, `// DD DSN=`, `sas -sysin`, `pmcmd`
- [x] **Informatica** — `MAPPING`, `SOURCE`, `TARGET`, `TRANSFORMATION`, `SESSION`, `WORKFLOW`, `WORKFLOWLINK`
- [x] **Elasticsearch** — index mappings, ingest `processors`, saved `searches`
- [x] **Unix shell** — `.sh/.bash/.ksh/.csh/.zsh`: `sas -sysin`, `python`, `sqlplus @f.sql`, `bteq`, `perl`, `pmcmd`, `sh/ksh/csh`, `cp/mv/scp/sftp`, `export`
- [x] **Windows batch / PowerShell** — `.bat/.cmd/.ps1`: `call`, `python`, `sas`, `sqlcmd -i`, `bteq`, `Invoke-Sqlcmd`, `copy/move/xcopy/robocopy`, `Copy-Item`, `set`
- [x] **Schedulers** — cron (`crontab`/`.cron`), Autosys JIL (`.jil`: command/condition/box), `Makefile`
- [x] **Python / PySpark** — `read.table/parquet/csv`, `write.saveAsTable/save`, `spark.sql(...)`

### Engine & features
- [x] Deterministic graph (topo order, **dependency waves**, SCC cycle detection, fan-in/out, content hash)
- [x] **Column-level lineage** (`scan --columns`) for SQL / SAS `proc sql` / PySpark `spark.sql`
- [x] **Impact analysis** (`impact <dir> <node>`): downstream/upstream closures + report
- [x] **Migration plan**: target rules, complexity heuristic, effort estimate, waves
- [x] **Reports**: `lineage.json/dot/md`, `lineage.png`, `assessment.md`, `migration_plan.json/md`
- [x] **Streamlit viewer**: interactive graph, plan table, assessment, node inspector + impact + download
- [x] Tests (26), `ruff`, `pre-commit`, CI

---

## Planned parsers

### Schedulers / orchestration (P0)
- [ ] **Control-M** (job XML / scheduling DB) — jobs, `INCOND`/`OUTCOND` deps, cyclic/timers, calendars, scripts
- [ ] **Tivoli Workload Scheduler (TWS/OPC)**, **CA-7**, **Broadcom ESP** — jobs, predecessors, calendars
- [ ] **Airflow** DAGs, **Oozie** workflows (XML) — tasks, `>>` deps, sensors
- [ ] **Jenkins / GitLab / Azure Pipelines** YAML + `deploy.sh` — build/deploy steps, artifacts
- [ ] **Calendar / `.cal`** files — schedule windows → job schedule

### ETL / data movement (P0)
- [ ] **SSIS** (`.dtsx`) — packages, data-flow tasks, sources/targets, precedence constraints
- [ ] **Azure Data Factory** (JSON) — pipelines, activities, datasets, triggers
- [ ] **IBM DataStage** (`.dsx`/`.isx`) — jobs, stages, links, transforms
- [ ] **Ab Initio** (`.mp`) — components, flows
- [ ] **Talend** (`.item`), **Pentaho/Kettle** (`.ktr`/`.kjb`) — jobs, steps, hops
- [ ] **Oracle ODI**, **SAP BODS**, **Matillion**, **dbt** (SQL + YAML) — mappings/models, deps

### Database scripts & utilities (P0/P1)
- [ ] **Teradata** BTEQ / FastLoad / MultiLoad / Tpump (`.bteq`, `.ctl`) — SQL steps, load targets, `BEGIN/END LOAD`
- [ ] **Oracle SQL\*Plus / SQL\*Loader** (`.sql`, `.ctl`) — control files, load targets
- [ ] **Stored procedures** (PL/SQL, T-SQL, Teradata SP) — cursors, temp tables, `MERGE`, dynamic SQL, **column lineage**
- [ ] **DB2** (DDL, SQL PL, `LOAD` cards), **Sybase**, **Informix** — tables, procs, loads

### Mainframe extras (P1)
- [ ] **JCL PROC / cataloged procedures** (`.prc`) — proc steps, symbolic params, expansions
- [ ] **CICS** (CSD, BMS maps), **IMS** (DBD/PSB) — transactions, screens, DB segments
- [ ] **Easytrieve** reports, **CA-7** — report jobs, deps
- [ ] **DFSORT / Syncsort** control cards — sort/join/merge steps

### Messaging / streaming (P1)
- [ ] **IBM MQ** (MQSC), **Kafka** (topics/connectors), **Solace**, **Tibco** — queues/topics, producers/consumers

### BI / reporting (P1)
- [ ] **Cognos** (report/model XML), **MicroStrategy**, **OBIEE RPD** — reports, sources, joins
- [ ] **Tableau** (`.twb`/`.twbx`), **Power BI** (`.pbix`/`.bim`) — datasources, measures
- [ ] **SAS EG** (`.egp`), SAS stored processes — process flows, datasets

### Config / control files → PARAM / connection nodes (P1)
- [ ] `sqlldr`/Teradata **`.ctl`**, **`tnsnames.ora`**, **`odbc.ini`**, **`jdbc.properties`**
- [ ] `.env`, `.ini`, `.properties`, `.yaml` config
- [ ] trigger / manifest / control files (`.ok`, `.done`, `.trigger`) → file + trigger edges

### Notebooks / ML (P2)
- [ ] **Jupyter** (`.ipynb`), **Zeppelin** (`.zep`), Databricks notebooks (`.py` with `# MAGIC`)

---

## Cross-cutting enhancements

- [ ] **Schema / data types** — parse DDL + copybooks to attach types to column nodes
- [ ] **Column lineage for more engines** — COBOL `MOVE`, Informatica expression ports, stored procs, SSIS/ADF
- [ ] **Unknown / review bucket** — emit a node per unrecognized file so nothing is silently dropped
- [ ] **Per-dialect SQL** — Teradata/Oracle/DB2/Snowflake (`MERGE`, `QUALIFY`, `CONNECT BY`, temp tables, `#`/`##`)
- [ ] **Target rules** for new kinds (BI → SQL dashboard, MQ/Kafka → streaming, `.ctl` → Auto Loader)
- [ ] **Migration readiness score** per component (complexity + fan-in + tech risk)
- [ ] **Diff two scans** — "what changed since last scan" (new/dropped components, new edges)
- [ ] **Export plan → Databricks Asset Bundle skeleton** (`databricks.yml` + job stubs)
- [ ] **Column-level impact** — impact analysis over column edges, not just components
- [ ] **Configurable target map** (YAML) instead of hardcoded rules
- [ ] **Incremental scanning** (cache parse results by file hash)

---

## Priority summary

**P0 (next):** Control-M · SSIS · Azure Data Factory · Teradata BTEQ/FastLoad · stored procedures
**P1:** TWS/CA-7 · DataStage/Ab Initio · Oracle SQL\*Loader `.ctl` · BI lineage · messaging · config/control files
**P2:** notebooks · per-dialect SQL · readiness score · scan diff · DAB export

---

## Adding a parser (checklist)

1. Create `lineageplanner/parsers/<name>.py` subclassing `Parser`
   (`name`, `extensions`, `matches()`, `parse(path, relpath, text) -> Parsed`).
2. Emit nodes/edges with `p.node(...)` / `p.edge(...)`; use `node_id(kind, name)`,
   `dataset_id(name)`, `file_id(path)` and the shared `stem()` helper.
3. Register it in `lineageplanner/parsers/__init__.py` (`PARSERS`, correct order).
4. Add target rules for any new kinds/techs in `lineageplanner/plan.py`.
5. Add a sample file under `sample_estate/` and a test in `tests/`.
6. Run `pytest -q tests/` and `ruff check .`, then `scan sample_estate`.
