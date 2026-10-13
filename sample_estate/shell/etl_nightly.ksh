#!/usr/bin/ksh
# Korn shell nightly ETL
export BASE_CCY=CAD
export MIN_AMOUNT=100

sqlplus bank/pw@orcl @sql/ddl.sql
sas -sysin sas/build_mart.sas
python3 python/transform.py
scp partner:/drop/statements_20260115.ndjson /landing/statements.ndjson
pmcmd startworkflow WF_GOLD_SUMMARY
