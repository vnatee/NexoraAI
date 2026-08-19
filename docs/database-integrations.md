# Database integrations

NexoraAI agents can use team-managed database connections through the LangGraph runtime. Each enabled database binding becomes a separate tool, so an agent only sees the connections explicitly assigned to it.

## Supported databases

| Type | Driver | Default port | Connection-specific options |
| --- | --- | ---: | --- |
| PostgreSQL | SQLAlchemy + psycopg 3 | 5432 | `ssl_mode` |
| MySQL / MariaDB | SQLAlchemy + PyMySQL | 3306 | TLS |
| Microsoft SQL Server | SQLAlchemy + pymssql/FreeTDS | 1433 | Require TLS |
| MongoDB | PyMongo | 27017 | TLS and authentication source |
| SQLite | Python sqlite3 | local file | Existing file under `LOCAL_DATABASE_ROOT` |

The **Test Connection** action uses the same normalized configuration and driver as the agent tool. A successful test verifies connectivity with `SELECT 1` for SQL databases or `ping` for MongoDB.

## Environment

Database passwords use the same Fernet key as managed LLM provider secrets:

```bash
APP_DATA_ENCRYPTION_KEY=<persistent-fernet-key>
```

Generate the key once and keep the same value across restarts. Changing it makes existing encrypted passwords unreadable.

SQLite is restricted to a dedicated directory and opens existing files in read-only mode:

```bash
LOCAL_DATABASE_ROOT=data/databases
```

Paths outside that directory, missing files, and file extensions other than `.db`, `.sqlite`, and `.sqlite3` are rejected.

## Agent setup

1. In Team Management, add and test the database connection.
2. In Agent Management, enable **External Database**.
3. Bind one or more connections to the agent and give each a clear alias and optional trigger keywords.
4. Configure the binding's **Database Query Profile**.
5. Use the LangGraph runtime for that agent.

For SQL connections, the generated tool supports `action=schema`, `action=query`, and `action=chart_aggregate`. For MongoDB it supports schema inspection and a collection/filter query. Ordinary query results are capped at 200 rows/documents per call.

## Full-dataset chart statistics

`action=chart_aggregate` avoids calculating a heatmap or boxplot from the ordinary 50–200 row tool window. It accepts schema-validated table/field names and bounded parameterized filters; the backend builds the SQL rather than executing chart SQL supplied by the model.

- Heatmaps use SQL `GROUP BY` with `count`, `count_distinct`, `sum`, `avg`, `min`, or `max`.
- PostgreSQL and SQL Server boxplots use database percentile functions and Tukey whiskers.
- MySQL/MariaDB and SQLite boxplots use a bounded server-side full scan, reject inputs over 50,000 rows, and never silently calculate partial statistics.
- At most 200 aggregate groups are rendered. All matching records still participate in the calculation, and `resultTruncated` reports when additional groups were omitted from display.
- Chart audit metadata includes the aggregation method, source record count, aggregate group count, and whether the full filtered dataset was analyzed.

## Database Query Profile

The profile belongs to the agent/database binding rather than the shared connection. This lets two agents use the same database with different business meanings and table access.

- **Business Context** explains the purpose of the data and the task the agent should perform.
- **Allowed Tables / Collections** is an enforced server-side allowlist. Qualified names such as `purchasing.po_header` are supported.
- **Business Rules** defines status meanings, joins, filters, calculations, exclusions, and evaluation criteria.
- **Glossary** maps user language to database concepts and expressions.
- **Verified Query Examples** contains reviewed question/query pairs that guide query planning.

Every database tool run must inspect the schema before querying. SQL schema results include columns, primary keys, and foreign keys. The query is then validated against both the read-only policy and the binding's allowed-object list. Database errors are returned to the LangGraph loop so the model can correct a query within the runtime iteration limit.

## Read-only safety

The runtime applies multiple controls:

- SQL is parsed server-side and only one `SELECT`/`WITH` statement is accepted.
- Data-changing statements and `SELECT ... FOR UPDATE` are rejected.
- PostgreSQL, MySQL/MariaDB, SQL Server, and SQLite also request read-only behavior at the connection/session layer.
- MongoDB blocks server-side JavaScript and write pipeline operators.
- Credentials are never returned by the connection-list API.

These controls are defense in depth, not a replacement for database permissions. Production connections should use a dedicated database account that has only the minimum read access to approved schemas, tables, views, or collections.
