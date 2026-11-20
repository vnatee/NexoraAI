/*
Connect directly to the existing Azure SQL database named [itopers], then run
this script. Azure SQL does not support switching databases with USE.
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'[dbo].[it_operations_tickets]', N'U') IS NOT NULL
    THROW 51000, 'Table dbo.it_operations_tickets already exists. No changes were made.', 1;
GO

CREATE TABLE [dbo].[it_operations_tickets]
(
    [record_id]                int            NOT NULL,
    [ticket_number]            varchar(20)    NOT NULL,
    [ticket_type]              varchar(20)    NOT NULL,
    [opened_at]                datetime2(0)   NOT NULL,
    [assigned_at]              datetime2(0)   NULL,
    [first_response_at]        datetime2(0)   NULL,
    [resolved_at]              datetime2(0)   NULL,
    [closed_at]                datetime2(0)   NULL,
    [last_updated_at]          datetime2(0)   NOT NULL,
    [status]                   nvarchar(30)   NOT NULL,
    [priority]                 varchar(2)     NOT NULL,
    [severity]                 varchar(10)    NOT NULL,
    [impact]                   varchar(10)    NOT NULL,
    [urgency]                  varchar(10)    NOT NULL,
    [channel]                  nvarchar(40)   NOT NULL,
    [requester_department]     nvarchar(80)   NOT NULL,
    [business_service]         nvarchar(100)  NOT NULL,
    [application_service]      nvarchar(120)  NOT NULL,
    [environment]              varchar(20)    NOT NULL,
    [category]                 nvarchar(80)   NOT NULL,
    [subcategory]              nvarchar(120)  NOT NULL,
    [ci_type]                  nvarchar(60)   NOT NULL,
    [configuration_item]       nvarchar(100)  NOT NULL,
    [assignment_group]         nvarchar(80)   NOT NULL,
    [support_tier]             varchar(2)     NOT NULL,
    [vendor]                   nvarchar(80)   NOT NULL,
    [site]                     nvarchar(100)  NOT NULL,
    [short_description]        nvarchar(300)  NOT NULL,
    [request_item]             nvarchar(120)  NULL,
    [affected_users]           int            NOT NULL CONSTRAINT [DF_itops_affected_users] DEFAULT (0),
    [outage_minutes]           int            NOT NULL CONSTRAINT [DF_itops_outage] DEFAULT (0),
    [response_minutes]         int            NOT NULL,
    [resolution_minutes]       int            NULL,
    [fulfillment_minutes]      int            NULL,
    [sla_target_minutes]       int            NOT NULL,
    [sla_breached]             varchar(3)     NOT NULL,
    [sla_breach_minutes]       int            NOT NULL CONSTRAINT [DF_itops_sla_breach] DEFAULT (0),
    [reopen_count]             tinyint        NOT NULL CONSTRAINT [DF_itops_reopen] DEFAULT (0),
    [related_change_id]        varchar(20)    NULL,
    [caused_by_change]         varchar(3)     NOT NULL,
    [problem_id]               varchar(20)    NULL,
    [root_cause_category]      nvarchar(100)  NULL,
    [resolution_code]          nvarchar(80)   NULL,
    [knowledge_used]           varchar(3)     NOT NULL,
    [customer_satisfaction]    tinyint        NULL,
    [data_year]                smallint       NOT NULL,
    [data_month]               char(7)        NOT NULL,

    CONSTRAINT [PK_it_operations_tickets] PRIMARY KEY CLUSTERED ([record_id]),
    CONSTRAINT [UQ_it_operations_ticket_number] UNIQUE ([ticket_number]),
    CONSTRAINT [CK_itops_ticket_type] CHECK ([ticket_type] IN ('Incident', 'Service Request')),
    CONSTRAINT [CK_itops_priority] CHECK ([priority] IN ('P1', 'P2', 'P3', 'P4')),
    CONSTRAINT [CK_itops_severity] CHECK ([severity] IN ('Critical', 'High', 'Medium', 'Low')),
    CONSTRAINT [CK_itops_impact] CHECK ([impact] IN ('High', 'Medium', 'Low')),
    CONSTRAINT [CK_itops_urgency] CHECK ([urgency] IN ('High', 'Medium', 'Low')),
    CONSTRAINT [CK_itops_support_tier] CHECK ([support_tier] IN ('L1', 'L2', 'L3')),
    CONSTRAINT [CK_itops_sla_breached] CHECK ([sla_breached] IN ('Yes', 'No')),
    CONSTRAINT [CK_itops_caused_by_change] CHECK ([caused_by_change] IN ('Yes', 'No')),
    CONSTRAINT [CK_itops_knowledge_used] CHECK ([knowledge_used] IN ('Yes', 'No')),
    CONSTRAINT [CK_itops_csat] CHECK ([customer_satisfaction] IS NULL OR [customer_satisfaction] BETWEEN 1 AND 5),
    CONSTRAINT [CK_itops_nonnegative] CHECK
    (
        [affected_users] >= 0 AND [outage_minutes] >= 0 AND
        [response_minutes] >= 0 AND [sla_target_minutes] > 0 AND
        [sla_breach_minutes] >= 0 AND [reopen_count] >= 0
    )
);
GO

CREATE INDEX [IX_itops_type_opened]
    ON [dbo].[it_operations_tickets] ([ticket_type], [opened_at]);
CREATE INDEX [IX_itops_service_priority]
    ON [dbo].[it_operations_tickets] ([business_service], [priority])
    INCLUDE ([status], [sla_breached], [resolution_minutes], [outage_minutes]);
CREATE INDEX [IX_itops_status]
    ON [dbo].[it_operations_tickets] ([status]);
CREATE INDEX [IX_itops_category]
    ON [dbo].[it_operations_tickets] ([category], [subcategory]);
CREATE INDEX [IX_itops_sla_month]
    ON [dbo].[it_operations_tickets] ([sla_breached], [data_month]);
GO

SELECT N'dbo.it_operations_tickets created successfully.' AS [result];
GO
