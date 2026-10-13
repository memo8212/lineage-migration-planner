#!/usr/bin/env bash
# Nightly orchestrator: land files, run SAS, call Informatica, publish.
set -euo pipefail

# land the department feeds
scp partner:/drop/dept_txn.csv /landing/dept_txn.csv
cp /staging/statements_20260115.ndjson /landing/statements.ndjson

# run the SAS extract + mart
sas -sysin sas/extract_cards.sas
sas -sysin sas/build_mart.sas

# run the python transformer
python3 python/transform.py

# trigger Informatica
pmcmd startworkflow WF_DAILY_BANK_FEED

# archive the report
cp /out/gold_segment.csv /archive/gold_segment.csv
