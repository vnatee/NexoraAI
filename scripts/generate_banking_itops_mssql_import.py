#!/usr/bin/env python3
"""Generate a credential-free Azure SQL INSERT script from the synthetic CSV."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"docs"/"demo"/"banking_it_operations"/"banking_it_operations_tickets_2024_2026.csv"
OUTPUT=ROOT/"docs"/"demo"/"banking_it_operations"/"azure_sql"/"02_import_data.sql"
BATCH_SIZE=500

TEXT_FIELDS={
    "ticket_number","ticket_type","status","priority","severity","impact","urgency","channel",
    "requester_department","business_service","application_service","environment","category","subcategory",
    "ci_type","configuration_item","assignment_group","support_tier","vendor","site","short_description",
    "request_item","sla_breached","related_change_id","caused_by_change","problem_id","root_cause_category",
    "resolution_code","knowledge_used","data_month",
}
UNICODE_FIELDS={
    "status","channel","requester_department","business_service","application_service","category","subcategory",
    "ci_type","configuration_item","assignment_group","vendor","site","short_description","request_item",
    "root_cause_category","resolution_code",
}
DATETIME_FIELDS={"opened_at","assigned_at","first_response_at","resolved_at","closed_at","last_updated_at"}


def literal(field,value):
    if value=="": return "NULL"
    if field in DATETIME_FIELDS:
        return "CONVERT(datetime2(0),'"+value.replace(" ","T")+"',126)"
    if field in TEXT_FIELDS:
        escaped=value.replace("'","''")
        return ("N" if field in UNICODE_FIELDS else "")+"'"+escaped+"'"
    return value


def main():
    with SOURCE.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f); fields=reader.fieldnames; rows=list(reader)
    if len(rows)!=4500: raise RuntimeError(f"Expected 4500 rows, got {len(rows)}")
    columns=", ".join(f"[{f}]" for f in fields)
    out=[
        "/* Connect directly to the existing Azure SQL database [itopers].",
        "   This file contains synthetic demo data only and no credentials.",
        "   Run 01_create_table.sql first. The script refuses to load a non-empty table. */",
        "", "SET NOCOUNT ON;", "SET XACT_ABORT ON;", "",
        "IF OBJECT_ID(N'[dbo].[it_operations_tickets]', N'U') IS NULL",
        "    THROW 51010, 'Run 01_create_table.sql before importing data.', 1;", "",
        "IF EXISTS (SELECT 1 FROM [dbo].[it_operations_tickets])",
        "    THROW 51011, 'Import stopped because dbo.it_operations_tickets is not empty.', 1;", "",
        "BEGIN TRANSACTION;", "",
    ]
    for start in range(0,len(rows),BATCH_SIZE):
        batch=rows[start:start+BATCH_SIZE]
        out.append(f"-- Records {start+1:,} through {start+len(batch):,}")
        out.append(f"INSERT INTO [dbo].[it_operations_tickets] ({columns})")
        out.append("VALUES")
        values=[]
        for row in batch:
            values.append("    ("+", ".join(literal(f,row[f]) for f in fields)+")")
        out.append(",\n".join(values)+";")
        out.append("")
    out.extend([
        "IF (SELECT COUNT(*) FROM [dbo].[it_operations_tickets]) <> 4500", "BEGIN",
        "    ROLLBACK TRANSACTION;",
        "    THROW 51012, 'Import validation failed: expected exactly 4500 rows.', 1;",
        "END;", "", "COMMIT TRANSACTION;", "",
        "SELECT", "    COUNT(*) AS [total_rows],",
        "    SUM(CASE WHEN [ticket_type]='Incident' THEN 1 ELSE 0 END) AS [incidents],",
        "    SUM(CASE WHEN [ticket_type]='Service Request' THEN 1 ELSE 0 END) AS [service_requests],",
        "    MIN([opened_at]) AS [first_opened_at], MAX([opened_at]) AS [last_opened_at]",
        "FROM [dbo].[it_operations_tickets];", "",
    ])
    OUTPUT.write_text("\n".join(out),encoding="utf-8")
    print(OUTPUT); print(f"rows={len(rows)} batches={(len(rows)+BATCH_SIZE-1)//BATCH_SIZE}")


if __name__=="__main__": main()
