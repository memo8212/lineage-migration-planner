@echo off
REM Windows batch: land the cards feed and load the warehouse
set BATCH_ID=20260115
set BASE_CCY=CAD

call prepare_dirs.bat
sas sas\extract_cards.sas
python python\transform.py
sqlcmd -S bank01 -i sql\ddl.sql
bteq < load_fact.bteq
copy \\partner\drop\dept_txn.csv C:\landing\dept_txn.csv
