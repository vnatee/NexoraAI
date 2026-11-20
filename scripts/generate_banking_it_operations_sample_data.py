#!/usr/bin/env python3
"""Generate deterministic synthetic banking ITSM Incident and Service Request data."""

from __future__ import annotations

import csv
import random
import sqlite3
import zlib
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo" / "banking_it_operations"
CSV_PATH = OUT / "banking_it_operations_tickets_2024_2026.csv"
DB_PATH = OUT / "banking_it_operations_demo.sqlite"
AS_OF = datetime(2026, 11, 12, 17, 0, 0)
START = datetime(2024, 1, 1, 0, 0, 0)
RECORD_COUNT = 4500
SEED = 20261112


SERVICES = {
    "Core Banking": ("Core Banking Platform", "Production", ["CBS-APP-01", "CBS-APP-02", "CBS-DB-CLUSTER", "CBS-MQ-01"]),
    "Mobile Banking": ("Mobile Banking API", "Production", ["MB-API-01", "MB-API-02", "MB-AUTH-01", "MB-REDIS-01"]),
    "Internet Banking": ("Internet Banking Portal", "Production", ["IB-WEB-01", "IB-APP-01", "IB-WAF-01", "IB-DB-01"]),
    "ATM & Card Services": ("ATM Switching Service", "Production", ["ATM-SWITCH-01", "ATM-HSM-01", "ATM-NET-GW", "CARD-DB-01"]),
    "Payments": ("Payment Gateway", "Production", ["PAY-API-01", "PAY-MQ-01", "PAY-DB-01", "PAY-LB-01"]),
    "SWIFT": ("SWIFT Messaging", "Production", ["SWIFT-APP-01", "SWIFT-GW-01", "SWIFT-HSM-01"]),
    "Fraud & AML": ("Fraud Detection Platform", "Production", ["FRAUD-STREAM-01", "AML-APP-01", "AML-DB-01"]),
    "Treasury": ("Treasury Management", "Production", ["TRS-APP-01", "TRS-DB-01", "MARKET-FEED-GW"]),
    "Loan Services": ("Loan Origination", "Production", ["LOS-APP-01", "LOS-WORKFLOW-01", "LOS-DB-01"]),
    "Customer Service": ("CRM & Contact Center", "Production", ["CRM-APP-01", "CRM-DB-01", "CTI-GW-01"]),
    "Data & Reporting": ("Enterprise Data Platform", "Production", ["DWH-ETL-01", "DWH-DB-01", "BI-GW-01", "REG-REPORT-01"]),
    "Identity Services": ("Enterprise Identity", "Production", ["AD-DC-01", "AD-DC-02", "IAM-APP-01", "MFA-GW-01"]),
    "Collaboration": ("Email & Collaboration", "Production", ["MAIL-GW-01", "M365-TENANT", "VC-ROOM-SVC"]),
    "End User Computing": ("Workplace Services", "Corporate", ["VDI-POOL-A", "PRINT-SVC-01", "ENDPOINT-FLEET"]),
}

SERVICE_WEIGHTS = {
    "Core Banking": 12, "Mobile Banking": 12, "Internet Banking": 8,
    "ATM & Card Services": 10, "Payments": 10, "SWIFT": 4,
    "Fraud & AML": 6, "Treasury": 4, "Loan Services": 5,
    "Customer Service": 6, "Data & Reporting": 7, "Identity Services": 7,
    "Collaboration": 4, "End User Computing": 5,
}

INCIDENT_CATEGORIES = {
    "Hardware": [("Server component failure", "Physical Server"), ("Disk degradation", "Storage"), ("Power supply alert", "Physical Server"), ("Edge appliance offline", "Appliance")],
    "Software": [("Application error", "Application"), ("Service process stopped", "Application"), ("Memory leak", "Application"), ("Configuration defect", "Application")],
    "Network": [("Packet loss", "Network Device"), ("Interface error", "Network Device"), ("High latency", "Network Path"), ("DNS resolution failure", "Network Service")],
    "Database": [("Slow query", "Database"), ("Connection pool exhausted", "Database"), ("Blocking session", "Database"), ("Replication lag", "Database")],
    "Security": [("Authentication failure", "Identity Service"), ("Suspicious access alert", "Security Control"), ("Certificate expired", "Certificate"), ("Endpoint protection alert", "Endpoint")],
    "Batch & Integration": [("Batch job failed", "Batch Job"), ("Message queue backlog", "Middleware"), ("File transfer delayed", "Integration"), ("API dependency unavailable", "API")],
    "Storage & Backup": [("Filesystem capacity critical", "Storage"), ("Backup job failed", "Backup Service"), ("Snapshot delayed", "Storage"), ("Object storage unavailable", "Storage")],
    "Cloud Platform": [("Cloud service degradation", "Cloud Service"), ("Container restart loop", "Container"), ("Autoscaling limit reached", "Cloud Service"), ("IAM policy error", "Cloud Identity")],
}

INCIDENT_CATEGORY_WEIGHTS = {"Hardware": 12, "Software": 30, "Network": 15, "Database": 12, "Security": 8, "Batch & Integration": 12, "Storage & Backup": 6, "Cloud Platform": 5}

REQUEST_CATEGORIES = {
    "Access Management": [("New application access", "Access"), ("Modify role access", "Access"), ("Password or MFA reset", "Identity"), ("Privileged access request", "Access")],
    "Software Service": [("Install approved software", "Software"), ("Software license assignment", "Software"), ("Application configuration request", "Application")],
    "Hardware Service": [("New laptop or workstation", "Endpoint"), ("Hardware replacement", "Endpoint"), ("Peripheral request", "Hardware")],
    "Data & Report": [("Standard report request", "Report"), ("Data extract request", "Data"), ("Dashboard access", "Analytics")],
    "Cloud Service": [("Cloud resource request", "Cloud Resource"), ("Storage capacity request", "Storage"), ("Non-production environment request", "Environment")],
    "Security Service": [("Certificate request", "Certificate"), ("Firewall rule request", "Security Control"), ("Security review request", "Assessment")],
    "User Service": [("Mailbox or distribution list", "Collaboration"), ("VPN access request", "Remote Access"), ("Shared folder request", "File Service")],
}

REQUEST_CATEGORY_WEIGHTS = {"Access Management": 28, "Software Service": 18, "Hardware Service": 14, "Data & Report": 12, "Cloud Service": 8, "Security Service": 8, "User Service": 12}

DEPARTMENTS = ["Retail Banking", "Corporate Banking", "Operations", "Finance", "Risk", "Compliance", "Treasury", "Customer Service", "Digital Banking", "Technology", "Internal Audit", "Human Resources"]
CHANNELS = ["Self-Service Portal", "Service Desk", "Monitoring Event", "Email", "Phone", "API Integration"]
SITES = ["Primary Data Center", "Secondary Data Center", "Head Office", "Branch Network", "AWS ap-southeast-1"]
VENDORS = ["Internal", "Network Vendor", "Hardware Vendor", "Application Vendor", "Database Vendor", "Cloud Provider"]
ASSIGNMENT_GROUPS = ["Service Desk L1", "Application Support", "Infrastructure Operations", "Network Operations", "Database Operations", "Security Operations", "Cloud Platform", "End User Support"]

FIELDS = [
    "record_id", "ticket_number", "ticket_type", "opened_at", "assigned_at",
    "first_response_at", "resolved_at", "closed_at", "last_updated_at", "status",
    "priority", "severity", "impact", "urgency", "channel", "requester_department",
    "business_service", "application_service", "environment", "category", "subcategory",
    "ci_type", "configuration_item", "assignment_group", "support_tier", "vendor", "site",
    "short_description", "request_item", "affected_users", "outage_minutes",
    "response_minutes", "resolution_minutes", "fulfillment_minutes", "sla_target_minutes",
    "sla_breached", "sla_breach_minutes", "reopen_count", "related_change_id",
    "caused_by_change", "problem_id", "root_cause_category", "resolution_code",
    "knowledge_used", "customer_satisfaction", "data_year", "data_month",
]


def weighted_choice(rng, mapping):
    return rng.choices(list(mapping), weights=list(mapping.values()), k=1)[0]


def random_opened(rng, ticket_type):
    total_days = (AS_OF - START).days
    day = rng.randrange(total_days + 1)
    base = START + timedelta(days=day)
    if ticket_type == "Service Request":
        while base.weekday() >= 5:
            base += timedelta(days=1)
        hour = rng.choices(range(8, 18), weights=[2, 5, 8, 9, 9, 8, 7, 6, 4, 2], k=1)[0]
    else:
        hour = rng.choices(range(24), weights=[2, 2, 2, 2, 2, 3, 4, 6, 9, 10, 10, 9, 8, 8, 8, 8, 9, 10, 9, 7, 5, 4, 3, 2], k=1)[0]
    return base.replace(hour=hour, minute=rng.randrange(60), second=rng.randrange(60))


def priority_profile(rng, ticket_type, service):
    critical_service = service in {"Core Banking", "Mobile Banking", "ATM & Card Services", "Payments", "SWIFT"}
    if ticket_type == "Incident":
        weights = [2.2 if critical_service else 0.7, 15 if critical_service else 10, 55, 28]
    else:
        weights = [0, 2, 34, 64]
    priority = rng.choices(["P1", "P2", "P3", "P4"], weights=weights, k=1)[0]
    profiles = {
        "P1": ("Critical", "High", "High", 240),
        "P2": ("High", rng.choice(["High", "Medium"]), rng.choice(["High", "Medium"]), 480 if ticket_type == "Incident" else 1440),
        "P3": ("Medium", "Medium", rng.choice(["Medium", "Low"]), 1440 if ticket_type == "Incident" else 2880),
        "P4": ("Low", "Low", "Low", 4320 if ticket_type == "Incident" else 7200),
    }
    return priority, *profiles[priority]


def duration_minutes(rng, ticket_type, priority, category):
    if ticket_type == "Incident":
        medians = {"P1": 145, "P2": 330, "P3": 900, "P4": 2100}
        factor = {"Hardware": 1.35, "Software": 1.0, "Network": 1.05, "Database": 1.2, "Security": 1.15, "Batch & Integration": .9, "Storage & Backup": 1.1, "Cloud Platform": .85}[category]
    else:
        medians = {"P1": 300, "P2": 900, "P3": 1900, "P4": 4200}
        factor = 1.0
    return max(5, int(rng.lognormvariate(0, .72) * medians[priority] * factor))


def status_for(rng, opened, ticket_type, completed):
    age_days = (AS_OF - opened).total_seconds() / 86400
    if completed:
        if ticket_type == "Incident": return rng.choices(["Closed", "Resolved"], [95, 5], k=1)[0]
        return rng.choices(["Closed", "Fulfilled"], [92, 8], k=1)[0]
    if ticket_type == "Incident":
        return rng.choices(["New", "Assigned", "In Progress", "Pending User", "Pending Vendor"], [5, 10, 45, 18, 22], k=1)[0]
    return rng.choices(["Submitted", "Approved", "Assigned", "In Fulfillment", "Pending User"], [4, 8, 10, 58, 20], k=1)[0]


def root_cause(category, rng):
    options = {
        "Hardware": ["Hardware failure", "Firmware defect", "Power or environmental"],
        "Software": ["Software defect", "Configuration error", "Resource exhaustion"],
        "Network": ["Network configuration", "Carrier degradation", "Device failure"],
        "Database": ["Query or index design", "Capacity or contention", "Database configuration"],
        "Security": ["Identity configuration", "Certificate lifecycle", "Security policy"],
        "Batch & Integration": ["Upstream dependency", "Data quality", "Scheduling or orchestration"],
        "Storage & Backup": ["Capacity management", "Backup configuration", "Storage component failure"],
        "Cloud Platform": ["Cloud configuration", "Service quota", "Provider degradation"],
    }
    return rng.choice(options[category])


def description(ticket_type, service, subcategory, ci, rng):
    if ticket_type == "Incident":
        patterns = [
            f"{service}: {subcategory} detected on {ci}",
            f"Service degradation associated with {subcategory.lower()} on {ci}",
            f"User impact reported for {service} due to {subcategory.lower()}",
            f"Monitoring alert: {subcategory} affecting {service}",
        ]
    else:
        patterns = [
            f"Request to fulfil {subcategory.lower()} for {service}",
            f"Standard service request: {subcategory} — {service}",
            f"User request for {subcategory.lower()} in {service}",
        ]
    return rng.choice(patterns)


def iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""


def generate_record(rng, idx, counters):
    ticket_type = rng.choices(["Incident", "Service Request"], weights=[65, 35], k=1)[0]
    opened = random_opened(rng, ticket_type)
    service = weighted_choice(rng, SERVICE_WEIGHTS)
    app, default_env, cis = SERVICES[service]
    environment = rng.choices([default_env, "UAT", "Development", "DR"], weights=[82, 8, 6, 4], k=1)[0]
    ci = rng.choice(cis)
    if ticket_type == "Incident":
        category = weighted_choice(rng, INCIDENT_CATEGORY_WEIGHTS)
        subcategory, ci_type = rng.choice(INCIDENT_CATEGORIES[category])
        request_item = ""
    else:
        category = weighted_choice(rng, REQUEST_CATEGORY_WEIGHTS)
        subcategory, ci_type = rng.choice(REQUEST_CATEGORIES[category])
        request_item = subcategory
    priority, severity, impact, urgency, sla_target = priority_profile(rng, ticket_type, service)
    elapsed = duration_minutes(rng, ticket_type, priority, category)
    assigned_delay = max(1, int(rng.lognormvariate(0, .55) * {"P1": 5, "P2": 12, "P3": 35, "P4": 90}[priority]))
    response_delay = assigned_delay + max(1, int(rng.lognormvariate(0, .5) * {"P1": 5, "P2": 15, "P3": 45, "P4": 120}[priority]))
    resolved_candidate = opened + timedelta(minutes=elapsed)
    age_days = (AS_OF-opened).total_seconds()/86400
    if age_days <= 7:
        completion_probability = .48
    elif age_days <= 30:
        completion_probability = .78
    elif age_days <= 90:
        completion_probability = .93
    else:
        completion_probability = .985
    completed = resolved_candidate <= AS_OF and rng.random() < completion_probability
    status = status_for(rng, opened, ticket_type, completed)
    assigned = min(opened + timedelta(minutes=assigned_delay), AS_OF)
    first_response = min(opened + timedelta(minutes=response_delay), AS_OF)
    resolved = resolved_candidate if completed else None
    closed = (resolved + timedelta(minutes=rng.randint(30, 1440))) if completed and status == "Closed" else None
    if closed and closed > AS_OF: closed = None; status = "Resolved" if ticket_type == "Incident" else "Fulfilled"
    measured = elapsed if completed else int((AS_OF-opened).total_seconds()/60)
    breached = measured > sla_target
    breach_minutes = max(0, measured-sla_target)
    is_outage = ticket_type == "Incident" and priority in {"P1", "P2"} and rng.random() < (.72 if priority == "P1" else .26)
    outage = min(elapsed, rng.randint(10, max(11, int(elapsed*.75)))) if is_outage else 0
    affected = 0 if ticket_type == "Service Request" else max(1, int(rng.lognormvariate(0, 1.2) * {"P1": 900, "P2": 160, "P3": 25, "P4": 3}[priority]))
    caused_change = ticket_type == "Incident" and rng.random() < {"P1": .32, "P2": .23, "P3": .12, "P4": .05}[priority]
    change_id = f"CHG{opened.year}{rng.randint(1,9999):04d}" if caused_change or (ticket_type == "Service Request" and category in {"Cloud Service", "Security Service"} and rng.random()<.3) else ""
    root = root_cause(category, rng) if ticket_type == "Incident" and completed else ""
    problem_key = zlib.crc32(f"{service}|{root}".encode("utf-8")) % 180 + 1
    problem_id = f"PRB{opened.year}{problem_key:04d}" if root and (priority in {"P1","P2"} or rng.random()<.18) else ""
    resolution_code = ""
    if completed:
        resolution_code = rng.choice(["Permanent fix", "Workaround applied", "Configuration corrected", "Component replaced", "User guidance", "Request fulfilled"] if ticket_type == "Incident" else ["Request fulfilled", "Access provisioned", "Configuration completed", "Item delivered"])
    support_group = {
        "Hardware": "Infrastructure Operations", "Software": "Application Support", "Network": "Network Operations",
        "Database": "Database Operations", "Security": "Security Operations", "Batch & Integration": "Application Support",
        "Storage & Backup": "Infrastructure Operations", "Cloud Platform": "Cloud Platform",
        "Access Management": "Service Desk L1", "Software Service": "End User Support", "Hardware Service": "End User Support",
        "Data & Report": "Application Support", "Cloud Service": "Cloud Platform", "Security Service": "Security Operations", "User Service": "Service Desk L1",
    }[category]
    vendor = rng.choices(VENDORS, weights=[58, 8, 8, 11, 7, 8], k=1)[0]
    if category == "Hardware" and rng.random()<.55: vendor="Hardware Vendor"
    elif category == "Network" and rng.random()<.5: vendor="Network Vendor"
    elif category == "Cloud Platform" and rng.random()<.55: vendor="Cloud Provider"
    counters[(ticket_type, opened.year)] += 1
    prefix = "INC" if ticket_type == "Incident" else "SR"
    ticket_number = f"{prefix}{opened.year}{counters[(ticket_type,opened.year)]:06d}"
    last_updated = max(x for x in [opened, assigned, first_response, resolved, closed] if x)
    csat = ""
    if completed and rng.random() < .62:
        base = 4.45 - (1.2 if breached else 0) - (.45 if ticket_type=="Incident" and priority in {"P1","P2"} else 0)
        csat = max(1, min(5, round(rng.gauss(base,.65))))
    return {
        "record_id": idx, "ticket_number": ticket_number, "ticket_type": ticket_type,
        "opened_at": iso(opened), "assigned_at": iso(assigned), "first_response_at": iso(first_response),
        "resolved_at": iso(resolved), "closed_at": iso(closed), "last_updated_at": iso(last_updated), "status": status,
        "priority": priority, "severity": severity, "impact": impact, "urgency": urgency,
        "channel": rng.choices(CHANNELS, weights=[32,22,18 if ticket_type=="Incident" else 2,14,10,4], k=1)[0],
        "requester_department": rng.choice(DEPARTMENTS), "business_service": service, "application_service": app,
        "environment": environment, "category": category, "subcategory": subcategory, "ci_type": ci_type,
        "configuration_item": ci, "assignment_group": support_group,
        "support_tier": rng.choices(["L1","L2","L3"],weights=[22,58,20],k=1)[0], "vendor": vendor,
        "site": rng.choices(SITES,weights=[38,12,20,16,14],k=1)[0],
        "short_description": description(ticket_type,service,subcategory,ci,rng), "request_item": request_item,
        "affected_users": affected, "outage_minutes": outage, "response_minutes": response_delay,
        "resolution_minutes": elapsed if ticket_type=="Incident" and completed else "",
        "fulfillment_minutes": elapsed if ticket_type=="Service Request" and completed else "",
        "sla_target_minutes": sla_target, "sla_breached": "Yes" if breached else "No", "sla_breach_minutes": breach_minutes,
        "reopen_count": rng.choices([0,1,2,3],weights=[90,8,1.5,.5],k=1)[0] if completed else 0,
        "related_change_id": change_id, "caused_by_change": "Yes" if caused_change else "No", "problem_id": problem_id,
        "root_cause_category": root, "resolution_code": resolution_code,
        "knowledge_used": "Yes" if completed and rng.random()<.46 else "No", "customer_satisfaction": csat,
        "data_year": opened.year, "data_month": opened.strftime("%Y-%m"),
    }


def create_database(rows):
    if DB_PATH.exists(): DB_PATH.unlink()
    conn=sqlite3.connect(DB_PATH)
    text_columns={f for f in FIELDS if f not in {"record_id","affected_users","outage_minutes","response_minutes","resolution_minutes","fulfillment_minutes","sla_target_minutes","sla_breach_minutes","reopen_count","customer_satisfaction","data_year"}}
    integer_columns=set(FIELDS)-text_columns
    definitions=[]
    for f in FIELDS:
        typ="INTEGER" if f in integer_columns else "TEXT"
        definitions.append(f'"{f}" {typ}')
    conn.execute(f'CREATE TABLE tickets ({", ".join(definitions)}, PRIMARY KEY (record_id), UNIQUE(ticket_number))')
    placeholders=",".join("?" for _ in FIELDS)
    conn.executemany(f'INSERT INTO tickets ({",".join(FIELDS)}) VALUES ({placeholders})',[[r[f] if r[f]!="" else None for f in FIELDS] for r in rows])
    conn.executescript("""
    CREATE INDEX idx_tickets_type_opened ON tickets(ticket_type, opened_at);
    CREATE INDEX idx_tickets_service_priority ON tickets(business_service, priority);
    CREATE INDEX idx_tickets_status ON tickets(status);
    CREATE INDEX idx_tickets_category ON tickets(category, subcategory);
    CREATE INDEX idx_tickets_sla ON tickets(sla_breached, data_month);
    CREATE VIEW v_incidents AS SELECT * FROM tickets WHERE ticket_type='Incident';
    CREATE VIEW v_service_requests AS SELECT * FROM tickets WHERE ticket_type='Service Request';
    CREATE VIEW v_monthly_ticket_summary AS
      SELECT data_month, ticket_type, business_service, category, priority, severity,
             COUNT(*) AS ticket_count,
             SUM(CASE WHEN sla_breached='Yes' THEN 1 ELSE 0 END) AS sla_breached_count,
             ROUND(100.0*SUM(CASE WHEN sla_breached='No' THEN 1 ELSE 0 END)/COUNT(*),2) AS sla_met_percent,
             ROUND(AVG(CASE WHEN ticket_type='Incident' THEN resolution_minutes ELSE fulfillment_minutes END),1) AS avg_completion_minutes
      FROM tickets GROUP BY data_month,ticket_type,business_service,category,priority,severity;
    CREATE VIEW v_incident_service_performance AS
      SELECT business_service, priority, COUNT(*) incident_count,
             SUM(outage_minutes) total_outage_minutes,
             ROUND(AVG(resolution_minutes),1) avg_resolution_minutes,
             ROUND(100.0*SUM(CASE WHEN sla_breached='No' THEN 1 ELSE 0 END)/COUNT(*),2) sla_met_percent,
             SUM(CASE WHEN caused_by_change='Yes' THEN 1 ELSE 0 END) change_related_count,
             SUM(CASE WHEN reopen_count>0 THEN 1 ELSE 0 END) reopened_count
      FROM tickets WHERE ticket_type='Incident'
      GROUP BY business_service,priority;
    CREATE VIEW v_open_backlog AS
      SELECT *, CAST(julianday('2026-11-12 17:00:00')-julianday(opened_at) AS INTEGER) backlog_age_days
      FROM tickets WHERE status NOT IN ('Closed','Resolved','Fulfilled','Cancelled','Rejected');
    CREATE VIEW v_problem_candidates AS
      SELECT business_service, category, subcategory, root_cause_category,
             COUNT(*) incident_count, SUM(outage_minutes) outage_minutes,
             ROUND(AVG(resolution_minutes),1) avg_resolution_minutes
      FROM tickets WHERE ticket_type='Incident' AND root_cause_category IS NOT NULL
      GROUP BY business_service,category,subcategory,root_cause_category
      HAVING COUNT(*)>=3;
    """)
    conn.commit(); conn.close()


def write_readme(rows):
    counts=Counter(r["ticket_type"] for r in rows)
    years=Counter(r["data_year"] for r in rows)
    breached=sum(r["sla_breached"]=="Yes" for r in rows)
    text=f"""# Synthetic Banking IT Operations dataset

This package contains **synthetic demonstration data only**. It contains no real bank, employee, customer, credential, account or production-system data.

## Files

- `banking_it_operations_tickets_2024_2026.csv` — {len(rows):,} UTF-8 ticket records.
- `banking_it_operations_demo.sqlite` — ready-to-query SQLite database.
- `data_dictionary.md` — field definitions and interpretation notes.

## Coverage

- As-of date: 12 November 2026, 17:00.
- Incident records: {counts['Incident']:,}.
- Service Request records: {counts['Service Request']:,}.
- Records by year: 2024 = {years[2024]:,}; 2025 = {years[2025]:,}; 2026 YTD = {years[2026]:,}.
- SLA-breached records: {breached:,}.
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
"""
    (OUT/"README.md").write_text(text,encoding="utf-8")


def write_dictionary():
    definitions={
        "record_id":"Synthetic integer primary key.", "ticket_number":"Year-scoped INC or SR identifier.", "ticket_type":"Incident or Service Request.",
        "opened_at":"Ticket creation timestamp.", "assigned_at":"First assignment timestamp.", "first_response_at":"First response timestamp.",
        "resolved_at":"Incident resolution or SR fulfillment timestamp when completed.", "closed_at":"Administrative closure timestamp.", "last_updated_at":"Latest lifecycle timestamp represented in the row.",
        "status":"Lifecycle status appropriate to the ticket type.", "priority":"P1–P4 priority derived from impact and urgency.", "severity":"Critical/High/Medium/Low operational severity.",
        "impact":"Estimated breadth of business/user impact.", "urgency":"Required response urgency.", "channel":"Ticket origin.",
        "requester_department":"Synthetic requesting business department.", "business_service":"Business-facing service.", "application_service":"Technical/application service supporting the business service.",
        "environment":"Production/UAT/Development/DR/Corporate context.", "category":"Top-level ITSM category.", "subcategory":"More specific issue or request type.",
        "ci_type":"Configuration Item class.", "configuration_item":"Synthetic CI identifier.", "assignment_group":"Responsible support group.",
        "support_tier":"L1/L2/L3 support tier.", "vendor":"Synthetic internal/external resolver classification.", "site":"Synthetic hosting/user location.",
        "short_description":"Synthetic ticket summary.", "request_item":"Requested item for Service Requests; blank for Incidents.",
        "affected_users":"Estimated Incident user impact; zero for SR.", "outage_minutes":"Estimated service outage minutes; zero when no outage.",
        "response_minutes":"Elapsed minutes to first response.", "resolution_minutes":"Incident elapsed minutes to resolution.", "fulfillment_minutes":"SR elapsed minutes to fulfillment.",
        "sla_target_minutes":"Synthetic elapsed-clock completion target.", "sla_breached":"Yes/No at completion or as-of date.", "sla_breach_minutes":"Minutes beyond target.",
        "reopen_count":"Number of synthetic reopen events.", "related_change_id":"Synthetic related Change ID when applicable.", "caused_by_change":"Whether the Incident is synthetically classified as change-related.",
        "problem_id":"Synthetic related Problem ID for selected recurring/major Incidents.", "root_cause_category":"Synthetic verified cause category for completed Incidents.",
        "resolution_code":"Synthetic completion classification.", "knowledge_used":"Whether a Knowledge article/runbook was synthetically used.",
        "customer_satisfaction":"Optional 1–5 synthetic score.", "data_year":"Opened year.", "data_month":"Opened month in YYYY-MM format.",
    }
    lines=["# Data dictionary","","All fields are synthetic and intended only for demonstration.","","| Field | Definition |","| --- | --- |"]
    lines.extend(f"| `{f}` | {definitions[f]} |" for f in FIELDS)
    (OUT/"data_dictionary.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rng=random.Random(SEED); counters=Counter()
    rows=[generate_record(rng,i,counters) for i in range(1,RECORD_COUNT+1)]
    rows.sort(key=lambda r:(r["opened_at"],r["ticket_number"]))
    for i,row in enumerate(rows,1): row["record_id"]=i
    with CSV_PATH.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    create_database(rows); write_readme(rows); write_dictionary()
    print(CSV_PATH); print(DB_PATH); print(f"records={len(rows)}")


if __name__ == "__main__": main()
