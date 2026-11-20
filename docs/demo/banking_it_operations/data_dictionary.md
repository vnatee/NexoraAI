# Data dictionary

All fields are synthetic and intended only for demonstration.

| Field | Definition |
| --- | --- |
| `record_id` | Synthetic integer primary key. |
| `ticket_number` | Year-scoped INC or SR identifier. |
| `ticket_type` | Incident or Service Request. |
| `opened_at` | Ticket creation timestamp. |
| `assigned_at` | First assignment timestamp. |
| `first_response_at` | First response timestamp. |
| `resolved_at` | Incident resolution or SR fulfillment timestamp when completed. |
| `closed_at` | Administrative closure timestamp. |
| `last_updated_at` | Latest lifecycle timestamp represented in the row. |
| `status` | Lifecycle status appropriate to the ticket type. |
| `priority` | P1–P4 priority derived from impact and urgency. |
| `severity` | Critical/High/Medium/Low operational severity. |
| `impact` | Estimated breadth of business/user impact. |
| `urgency` | Required response urgency. |
| `channel` | Ticket origin. |
| `requester_department` | Synthetic requesting business department. |
| `business_service` | Business-facing service. |
| `application_service` | Technical/application service supporting the business service. |
| `environment` | Production/UAT/Development/DR/Corporate context. |
| `category` | Top-level ITSM category. |
| `subcategory` | More specific issue or request type. |
| `ci_type` | Configuration Item class. |
| `configuration_item` | Synthetic CI identifier. |
| `assignment_group` | Responsible support group. |
| `support_tier` | L1/L2/L3 support tier. |
| `vendor` | Synthetic internal/external resolver classification. |
| `site` | Synthetic hosting/user location. |
| `short_description` | Synthetic ticket summary. |
| `request_item` | Requested item for Service Requests; blank for Incidents. |
| `affected_users` | Estimated Incident user impact; zero for SR. |
| `outage_minutes` | Estimated service outage minutes; zero when no outage. |
| `response_minutes` | Elapsed minutes to first response. |
| `resolution_minutes` | Incident elapsed minutes to resolution. |
| `fulfillment_minutes` | SR elapsed minutes to fulfillment. |
| `sla_target_minutes` | Synthetic elapsed-clock completion target. |
| `sla_breached` | Yes/No at completion or as-of date. |
| `sla_breach_minutes` | Minutes beyond target. |
| `reopen_count` | Number of synthetic reopen events. |
| `related_change_id` | Synthetic related Change ID when applicable. |
| `caused_by_change` | Whether the Incident is synthetically classified as change-related. |
| `problem_id` | Synthetic related Problem ID for selected recurring/major Incidents. |
| `root_cause_category` | Synthetic verified cause category for completed Incidents. |
| `resolution_code` | Synthetic completion classification. |
| `knowledge_used` | Whether a Knowledge article/runbook was synthetically used. |
| `customer_satisfaction` | Optional 1–5 synthetic score. |
| `data_year` | Opened year. |
| `data_month` | Opened month in YYYY-MM format. |
