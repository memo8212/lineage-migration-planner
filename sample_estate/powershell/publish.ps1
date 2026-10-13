# PowerShell: publish the gold output
$ErrorActionPreference = "Stop"

Invoke-Sqlcmd -ServerInstance bank01 -InputFile sql\ddl.sql
python python\transform.py
Copy-Item C:\out\gold_segment.csv \\archive\gold_segment.csv
& .\publish_report.ps1
