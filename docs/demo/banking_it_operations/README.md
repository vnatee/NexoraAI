# Synthetic Banking IT Operations dataset

This package contains **synthetic demonstration data only**. It contains no real bank, employee, customer, credential, account or production-system data.

## Files

- `banking_it_operations_tickets_2024_2026.csv` — 4,500 UTF-8 ticket records.
- `banking_it_operations_demo.sqlite` — ready-to-query SQLite database.
- `data_dictionary.md` — field definitions and interpretation notes.
- `azure_sql/01_create_table.sql` — creates the typed table in the existing `itopers` database.
- `azure_sql/02_import_data.sql` — imports all 4,500 rows without Blob Storage or credentials.

## Coverage

- As-of date: 12 November 2026, 17:00.
- Incident records: 2,910.
- Service Request records: 1,590.
- Records by year: 2024 = 1,555; 2025 = 1,558; 2026 YTD = 1,387.
- SLA-breached records: 1,259.
- Domains include hardware, software, network, database, security, batch/integration, storage/backup and cloud.

`severity` is included because it is useful operationally, but ITIL does not prescribe one universal severity taxonomy. `priority` is derived from impact and urgency in this synthetic model. Service Requests use their own lifecycle while sharing reporting dimensions.

## SQLite objects

- Table: `tickets`
- Views: `v_incidents`, `v_service_requests`, `v_monthly_ticket_summary`, `v_incident_service_performance`, `v_open_backlog`, `v_problem_candidates`

Configure the InsightSphere SQLite database connection as read-only and allow only the table/views required for the demonstration.

## Suggested demonstration prompts

1. Summarize Incident and Service Request volume by month for 2024–2026 YTD.
2. Create a stacked chart of Incidents by severity and month.
3. Which business services have the highest SLA breach rate? Show ticket count as context.
4. Compare average Incident resolution time for P1–P4 by business service.
5. Show the current open backlog by age band, assignment group and priority.
6. Which categories contribute the most outage minutes, and which CIs recur most often?
7. Compare hardware and software Incidents by volume, MTTR and SLA performance.
8. Identify recurring Incident patterns that should become Problem records.
9. What percentage of Incidents were related to Changes, and how did their MTTR compare?
10. Analyze Service Request fulfillment time and SLA by request category.
11. Does Knowledge usage correlate with lower resolution time? State that this dataset shows association, not causation.
12. Draft a weekly IT Operations report with executive summary, KPIs, risks and recommended actions.

## Important interpretation boundaries

- Do not present synthetic patterns as evidence about a real bank.
- SLA calculations use elapsed clock minutes for a simple demonstration, not business calendars or pause rules.
- Open-ticket SLA breach is calculated as of the fixed dataset date.
- Root-cause values are populated only for completed Incidents and remain synthetic.
- Demonstration analytics must distinguish correlation from causation.
