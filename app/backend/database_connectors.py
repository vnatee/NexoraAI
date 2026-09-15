import os
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import sqlglot
from bson import ObjectId
from pymongo import MongoClient
from sqlalchemy import URL, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlglot import exp

from core.provider_secrets import decrypt_secret

SUPPORTED_DATABASES = {
    "postgresql": {"label": "PostgreSQL", "default_port": 5432, "kind": "sql"},
    "mysql": {"label": "MySQL / MariaDB", "default_port": 3306, "kind": "sql"},
    "mssql": {"label": "Microsoft SQL Server", "default_port": 1433, "kind": "sql"},
    "mongodb": {"label": "MongoDB", "default_port": 27017, "kind": "document"},
    "sqlite": {"label": "SQLite (Local)", "default_port": 0, "kind": "sql"},
}

MAX_CHART_GROUPS = 200
MAX_SERVER_STAT_ROWS = 50_000


def normalize_database_type(value: object) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "postgres": "postgresql",
        "mariadb": "mysql",
        "sqlserver": "mssql",
        "sql_server": "mssql",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_DATABASES:
        raise ValueError(f"Unsupported database type '{value}'")
    return normalized


def normalize_database_config(data: dict[str, Any]) -> dict[str, Any]:
    db_type = normalize_database_type(data.get("db_type"))
    options = data.get("options") or {}
    if not isinstance(options, dict):
        raise ValueError("Database options must be an object")
    database = str(data.get("database") or "").strip()
    host = str(data.get("host") or "").strip()
    username = str(data.get("username") or "").strip()
    port = int(data.get("port") or SUPPORTED_DATABASES[db_type]["default_port"])
    if not database:
        raise ValueError("Database name or SQLite file is required")
    if db_type != "sqlite" and not host:
        raise ValueError("Database host is required")
    if db_type != "sqlite" and not 1 <= port <= 65535:
        raise ValueError("Database port must be between 1 and 65535")
    return {
        "db_type": db_type,
        "host": host,
        "port": port,
        "database": database,
        "username": username,
        "options": {
            "ssl_mode": str(options.get("ssl_mode") or "prefer"),
            "auth_source": str(options.get("auth_source") or "admin"),
            "tls": options.get("tls") is True,
            "connect_timeout_seconds": max(
                1, min(int(options.get("connect_timeout_seconds") or 10), 60)
            ),
        },
    }


def password_for(connection: dict[str, Any]) -> str | None:
    encrypted = connection.get("password_ciphertext")
    if encrypted:
        return decrypt_secret(str(encrypted))
    # Backward compatibility for records created before secret encryption.
    return str(connection.get("password")) if connection.get("password") else None


def _sqlite_path(database: str) -> Path:
    root = Path(os.getenv("LOCAL_DATABASE_ROOT", "data/databases")).resolve()
    candidate = Path(database)
    resolved = (
        candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    )
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"SQLite files must be inside LOCAL_DATABASE_ROOT ({root})")
    if resolved.suffix.lower() not in (".db", ".sqlite", ".sqlite3"):
        raise ValueError("SQLite file must end with .db, .sqlite, or .sqlite3")
    return resolved


def _sqlalchemy_url(connection: dict[str, Any]) -> URL | str:
    config = normalize_database_config(connection)
    password = password_for(connection)
    if config["db_type"] == "sqlite":
        return f"sqlite:///{_sqlite_path(config['database'])}"
    drivers = {
        "postgresql": "postgresql+psycopg",
        "mysql": "mysql+pymysql",
        "mssql": "mssql+pymssql",
    }
    return URL.create(
        drivers[config["db_type"]],
        username=config["username"] or None,
        password=password,
        host=config["host"],
        port=config["port"],
        database=config["database"],
    )


def create_sql_engine(connection: dict[str, Any]) -> Engine:
    config = normalize_database_config(connection)
    timeout = config["options"]["connect_timeout_seconds"]
    if config["db_type"] == "sqlite":
        path = _sqlite_path(config["database"])
        if not path.is_file():
            raise ValueError(f"SQLite file does not exist: {path}")
        return create_engine(
            "sqlite://",
            creator=lambda: sqlite3.connect(
                f"file:{path}?mode=ro", uri=True, timeout=timeout
            ),
            pool_pre_ping=True,
        )
    connect_args: dict[str, Any] = {}
    if config["db_type"] == "postgresql":
        connect_args = {
            "connect_timeout": timeout,
            "options": "-c default_transaction_read_only=on",
        }
        ssl_mode = config["options"]["ssl_mode"]
        if ssl_mode and ssl_mode != "prefer":
            connect_args["sslmode"] = ssl_mode
    elif config["db_type"] == "mysql":
        connect_args = {
            "connect_timeout": timeout,
            "init_command": "SET SESSION TRANSACTION READ ONLY",
        }
        if config["options"]["tls"]:
            connect_args["ssl"] = {}
    elif config["db_type"] == "mssql":
        connect_args = {
            "login_timeout": timeout,
            "timeout": timeout,
            "read_only": True,
            "encryption": "require" if config["options"]["tls"] else "request",
        }
    return create_engine(
        _sqlalchemy_url(connection),
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
    )


def _mongodb_uri(connection: dict[str, Any]) -> str:
    config = normalize_database_config(connection)
    host = config["host"]
    if host.startswith(("mongodb://", "mongodb+srv://")):
        return host
    credentials = ""
    password = password_for(connection)
    if config["username"]:
        credentials = quote_plus(config["username"])
        if password:
            credentials += f":{quote_plus(password)}"
        credentials += "@"
    return f"mongodb://{credentials}{host}:{config['port']}/{quote_plus(config['database'])}?authSource={quote_plus(config['options']['auth_source'])}"


def _mongo_client(connection: dict[str, Any]) -> MongoClient:
    config = normalize_database_config(connection)
    client_options: dict[str, Any] = {
        "serverSelectionTimeoutMS": config["options"]["connect_timeout_seconds"] * 1000,
    }
    if config["options"]["tls"]:
        client_options["tls"] = True
    return MongoClient(_mongodb_uri(connection), **client_options)


def mongodb_uri(connection: dict[str, Any]) -> str:
    """Build a MongoDB URI without exposing this helper's implementation to legacy callers."""
    return _mongodb_uri(connection)


def test_database_connection(connection: dict[str, Any]) -> dict[str, Any]:
    db_type = normalize_database_type(connection.get("db_type"))
    if db_type == "mongodb":
        with _mongo_client(connection) as client:
            client.admin.command("ping")
        return {"ok": True, "db_type": db_type, "message": "MongoDB ping succeeded"}
    engine = create_sql_engine(connection)
    try:
        with engine.connect() as db:
            db.execute(text("SELECT 1"))
        return {"ok": True, "db_type": db_type, "message": "SQL connection succeeded"}
    finally:
        engine.dispose()


def _object_parts(value: str) -> tuple[str | None, str]:
    parts = [part.strip() for part in value.split(".") if part.strip()]
    return (parts[-2], parts[-1]) if len(parts) > 1 else (None, parts[0])


def _mongo_field_types(
    document: dict[str, Any], prefix: str = ""
) -> list[dict[str, str]]:
    fields = []
    for key, value in document.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            fields.extend(_mongo_field_types(value, path))
        elif isinstance(value, list):
            item_type = type(value[0]).__name__ if value else "unknown"
            fields.append({"name": path, "type": f"array[{item_type}]"})
        else:
            fields.append({"name": path, "type": type(value).__name__})
    return fields


def describe_database(
    connection: dict[str, Any],
    max_objects: int = 30,
    allowed_objects: list[str] | None = None,
) -> dict[str, Any]:
    db_type = normalize_database_type(connection.get("db_type"))
    allowed_objects = [
        str(value).strip() for value in (allowed_objects or []) if str(value).strip()
    ]
    if db_type == "mongodb":
        with _mongo_client(connection) as client:
            database = client[connection["database"]]
            collections = [
                name
                for name in database.list_collection_names()
                if not name.startswith("system.")
                and (
                    not allowed_objects
                    or name.lower() in {item.lower() for item in allowed_objects}
                )
            ]
            objects = []
            for collection_name in collections[:max_objects]:
                sample = database[collection_name].find_one({}) or {}
                objects.append(
                    {
                        "name": collection_name,
                        "fields": _mongo_field_types(sample),
                        "note": "Field types are inferred from one document; values are not exposed.",
                    }
                )
        return {
            "db_type": db_type,
            "collections": collections[:max_objects],
            "objects": objects,
        }
    engine = create_sql_engine(connection)
    try:
        inspector = inspect(engine)
        objects = []
        if allowed_objects:
            candidates = [_object_parts(value) for value in allowed_objects]
        else:
            candidates = [
                (None, name)
                for name in (inspector.get_table_names() + inspector.get_view_names())[
                    :max_objects
                ]
            ]
        for schema_name, table_name in candidates[:max_objects]:
            columns = inspector.get_columns(table_name, schema=schema_name)
            try:
                primary_key = (
                    inspector.get_pk_constraint(table_name, schema=schema_name).get(
                        "constrained_columns"
                    )
                    or []
                )
            except (NotImplementedError, ValueError):
                primary_key = []
            foreign_keys = []
            try:
                inspected_foreign_keys = inspector.get_foreign_keys(
                    table_name, schema=schema_name
                )
            except (NotImplementedError, ValueError):
                inspected_foreign_keys = []
            for foreign_key in inspected_foreign_keys:
                foreign_keys.append(
                    {
                        "columns": foreign_key.get("constrained_columns") or [],
                        "referred_schema": foreign_key.get("referred_schema"),
                        "referred_table": foreign_key.get("referred_table"),
                        "referred_columns": foreign_key.get("referred_columns") or [],
                    }
                )
            objects.append(
                {
                    "name": table_name,
                    "schema": schema_name,
                    "qualified_name": f"{schema_name}.{table_name}"
                    if schema_name
                    else table_name,
                    "columns": [
                        {
                            "name": column["name"],
                            "type": str(column["type"]),
                            "nullable": column.get("nullable", True),
                            "comment": column.get("comment"),
                        }
                        for column in columns
                    ],
                    "primary_key": primary_key,
                    "foreign_keys": foreign_keys,
                }
            )
        return {"db_type": db_type, "objects": objects}
    finally:
        engine.dispose()


def _validate_read_only_sql(
    query: str, db_type: str, allowed_objects: list[str] | None = None
) -> str:
    query = query.strip()
    if not query:
        raise ValueError("SQL query is required")
    dialect = {
        "postgresql": "postgres",
        "mysql": "mysql",
        "mssql": "tsql",
        "sqlite": "sqlite",
    }[db_type]
    statements = sqlglot.parse(query, read=dialect)
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise ValueError("Only one read-only SELECT/WITH query is allowed")
    forbidden = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Merge,
        exp.Command,
        exp.Into,
    )
    if (
        any(statements[0].find(node_type) is not None for node_type in forbidden)
        or "FOR UPDATE" in query.upper()
    ):
        raise ValueError("Database tool only allows read-only SQL")
    if allowed_objects:
        allowed = {value.strip().lower() for value in allowed_objects if value.strip()}
        cte_names = {
            cte.alias_or_name.lower()
            for cte in statements[0].find_all(exp.CTE)
            if cte.alias_or_name
        }
        for table in statements[0].find_all(exp.Table):
            table_name = table.name.lower()
            if table_name in cte_names:
                continue
            qualified = f"{table.db}.{table.name}".lower() if table.db else table_name
            fully_qualified = (
                f"{table.catalog}.{qualified}".lower() if table.catalog else qualified
            )
            permitted = (
                table_name in allowed
                or qualified in allowed
                or fully_qualified in allowed
                or any(
                    item.endswith(".*") and qualified.startswith(item[:-1])
                    for item in allowed
                )
            )
            if not permitted:
                raise ValueError(
                    f"Query references '{fully_qualified}', which is not allowed by this agent's database profile"
                )
    return query


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date, Decimal, ObjectId)):
        return str(value)
    if isinstance(value, bytes):
        return f"<binary {len(value)} bytes>"
    return value


def _chart_object(
    engine: Engine, table: object, allowed_objects: list[str]
) -> tuple[str, dict[str, str]]:
    requested = str(table or "").strip()
    parts = [part.strip() for part in requested.split(".") if part.strip()]
    if not parts or len(parts) > 3:
        raise ValueError("chart_aggregate requires a valid table name from schema")
    if allowed_objects:
        allowed = {
            str(value).strip().lower()
            for value in allowed_objects
            if str(value).strip()
        }
        variants = {parts[-1].lower()}
        if len(parts) >= 2:
            variants.add(".".join(parts[-2:]).lower())
        variants.add(".".join(parts).lower())
        permitted = bool(variants & allowed) or any(
            item.endswith(".*")
            and any(value.startswith(item[:-1]) for value in variants)
            for item in allowed
        )
        if not permitted:
            raise ValueError(
                f"Table '{requested}' is not allowed by this agent's database profile"
            )

    schema_name = parts[-2] if len(parts) >= 2 else None
    table_name = parts[-1]
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name, schema=schema_name)
    if not columns and len(parts) == 3:
        columns = inspector.get_columns(table_name, schema=parts[-2])
    if not columns:
        raise ValueError(f"Table or view '{requested}' was not found")
    column_map = {
        str(column["name"]).lower(): str(column["name"]) for column in columns
    }
    quote = engine.dialect.identifier_preparer.quote
    return ".".join(quote(part) for part in parts), column_map


def _chart_field(value: object, column_map: dict[str, str], name: str) -> str:
    requested = str(value or "").strip()
    actual = column_map.get(requested.lower())
    if not actual:
        raise ValueError(f"{name} '{requested}' is not a column in the selected table")
    return actual


def _chart_filters(
    filters: object,
    column_map: dict[str, str],
    quote,
) -> tuple[str, dict[str, Any]]:
    if filters is None:
        return "", {}
    if not isinstance(filters, list) or len(filters) > 10:
        raise ValueError("filters must be an array containing at most 10 items")
    clauses: list[str] = []
    params: dict[str, Any] = {}
    operators = {
        "eq": "=",
        "ne": "<>",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
    }
    for index, item in enumerate(filters):
        if not isinstance(item, dict):
            raise ValueError("each filter must be an object")
        field = _chart_field(item.get("field"), column_map, "filter field")
        operator = str(item.get("operator") or "eq").strip().lower()
        quoted_field = quote(field)
        if operator in ("is_null", "is_not_null"):
            clauses.append(
                f"{quoted_field} IS {'NOT ' if operator == 'is_not_null' else ''}NULL"
            )
            continue
        if operator == "in":
            values = item.get("value")
            if not isinstance(values, list) or not values or len(values) > 100:
                raise ValueError("filter operator 'in' requires 1-100 values")
            placeholders = []
            for value_index, value in enumerate(values):
                key = f"filter_{index}_{value_index}"
                placeholders.append(f":{key}")
                params[key] = value
            clauses.append(f"{quoted_field} IN ({', '.join(placeholders)})")
            continue
        sql_operator = operators.get(operator)
        if not sql_operator:
            raise ValueError(f"Unsupported filter operator '{operator}'")
        key = f"filter_{index}"
        clauses.append(f"{quoted_field} {sql_operator} :{key}")
        params[key] = item.get("value")
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _result_rows(result, columns: list[str] | None = None) -> list[dict[str, Any]]:
    columns = columns or list(result.keys())
    return [
        dict(zip(columns, (_json_value(value) for value in row), strict=True))
        for row in result
    ]


def _percentile(values: list[float], percentile: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def _server_boxplot_rows(
    db,
    *,
    table_sql: str,
    category: str,
    value: str,
    where_sql: str,
    params: dict[str, Any],
    quote,
) -> tuple[list[dict[str, Any]], int, int]:
    conjunction = " AND " if where_sql else " WHERE "
    query = (
        f"SELECT {quote(category)} AS chart_category, {quote(value)} AS chart_value "
        f"FROM {table_sql}{where_sql}{conjunction}{quote(value)} IS NOT NULL"
    )
    raw = db.execute(text(query), params).fetchmany(MAX_SERVER_STAT_ROWS + 1)
    if len(raw) > MAX_SERVER_STAT_ROWS:
        raise ValueError(
            f"Boxplot fallback exceeds {MAX_SERVER_STAT_ROWS} rows; add filters or use PostgreSQL/SQL Server percentile support"
        )
    groups: dict[str, list[float]] = {}
    for category_value, numeric_value in raw:
        if isinstance(numeric_value, bool):
            raise ValueError("boxplot value_field must be numeric")
        try:
            number = float(numeric_value)
        except (TypeError, ValueError) as error:
            raise ValueError("boxplot value_field must be numeric") from error
        groups.setdefault(str(category_value), []).append(number)
    rows = []
    for name, numbers in groups.items():
        numbers.sort()
        q1 = _percentile(numbers, 0.25)
        median = _percentile(numbers, 0.5)
        q3 = _percentile(numbers, 0.75)
        iqr = q3 - q1
        lower_values = [number for number in numbers if number >= q1 - 1.5 * iqr]
        upper_values = [number for number in numbers if number <= q3 + 1.5 * iqr]
        rows.append(
            {
                category: name,
                "box_lower": min(lower_values) if lower_values else numbers[0],
                "box_q1": q1,
                "box_median": median,
                "box_q3": q3,
                "box_upper": max(upper_values) if upper_values else numbers[-1],
                "sample_count": len(numbers),
            }
        )
    rows.sort(key=lambda row: row["sample_count"], reverse=True)
    return rows[:MAX_CHART_GROUPS], len(raw), len(rows)


def execute_chart_aggregation(
    connection: dict[str, Any],
    arguments: dict[str, Any],
    query_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_profile = query_profile or {}
    db_type = normalize_database_type(connection.get("db_type"))
    if db_type == "mongodb":
        raise ValueError("chart_aggregate currently supports SQL databases")
    chart_type = str(arguments.get("chart_type") or "").strip().lower()
    if chart_type not in ("heatmap", "boxplot"):
        raise ValueError("chart_type must be 'heatmap' or 'boxplot'")
    engine = create_sql_engine(connection)
    try:
        table_sql, column_map = _chart_object(
            engine, arguments.get("table"), query_profile.get("allowed_objects") or []
        )
        quote = engine.dialect.identifier_preparer.quote
        where_sql, params = _chart_filters(arguments.get("filters"), column_map, quote)
        with engine.connect() as db:
            if chart_type == "heatmap":
                x_field = _chart_field(arguments.get("x_field"), column_map, "x_field")
                y_field = _chart_field(arguments.get("y_field"), column_map, "y_field")
                aggregation = str(arguments.get("aggregation") or "count").lower()
                if aggregation not in (
                    "count",
                    "count_distinct",
                    "sum",
                    "avg",
                    "min",
                    "max",
                ):
                    raise ValueError("Unsupported heatmap aggregation")
                requested_value = str(arguments.get("value_field") or "").strip()
                if aggregation == "count" and not requested_value:
                    metric_sql = "*"
                    value_field = None
                else:
                    value_field = _chart_field(
                        requested_value, column_map, "value_field"
                    )
                    metric_sql = quote(value_field)
                dimension_conjunction = " AND " if where_sql else " WHERE "
                source_where = (
                    f"{where_sql}{dimension_conjunction}{quote(x_field)} IS NOT NULL "
                    f"AND {quote(y_field)} IS NOT NULL"
                )
                aggregate_sql = (
                    f"COUNT(DISTINCT {metric_sql})"
                    if aggregation == "count_distinct"
                    else f"{aggregation.upper()}({metric_sql})"
                )
                base_query = (
                    f"SELECT {quote(x_field)} AS {quote(x_field)}, "
                    f"{quote(y_field)} AS {quote(y_field)}, {aggregate_sql} AS chart_value "
                    f"FROM {table_sql}{source_where} "
                    f"GROUP BY {quote(x_field)}, {quote(y_field)}"
                )
                count_query = f"SELECT COUNT(*) FROM {table_sql}{source_where}"
                group_count_query = f"SELECT COUNT(*) FROM ({base_query}) chart_groups"
                source_record_count = int(
                    db.execute(text(count_query), params).scalar() or 0
                )
                aggregate_row_count = int(
                    db.execute(text(group_count_query), params).scalar() or 0
                )
                cursor = db.execute(
                    text(f"{base_query} ORDER BY chart_value DESC"), params
                )
                result = cursor.fetchmany(MAX_CHART_GROUPS)
                rows = _result_rows(result, list(cursor.keys()))
                mapping = {
                    "x_field": x_field,
                    "y_field": y_field,
                    "value_field": "chart_value",
                }
                method = "sql_group_by"
                query = base_query
            else:
                category = _chart_field(
                    arguments.get("category_field"), column_map, "category_field"
                )
                value = _chart_field(
                    arguments.get("value_field"), column_map, "value_field"
                )
                conjunction = " AND " if where_sql else " WHERE "
                source_where = (
                    f"{where_sql}{conjunction}{quote(category)} IS NOT NULL "
                    f"AND {quote(value)} IS NOT NULL"
                )
                if db_type == "postgresql":
                    query = (
                        "WITH source_data AS ("
                        f"SELECT {quote(category)} AS chart_category, {quote(value)} AS chart_value "
                        f"FROM {table_sql}{source_where}), quartiles AS ("
                        "SELECT chart_category, "
                        "percentile_cont(0.25) WITHIN GROUP (ORDER BY chart_value) AS q1, "
                        "percentile_cont(0.5) WITHIN GROUP (ORDER BY chart_value) AS median, "
                        "percentile_cont(0.75) WITHIN GROUP (ORDER BY chart_value) AS q3 "
                        "FROM source_data GROUP BY chart_category) "
                        f"SELECT s.chart_category AS {quote(category)}, "
                        "MIN(CASE WHEN s.chart_value >= q.q1 - 1.5 * (q.q3 - q.q1) THEN s.chart_value END) AS box_lower, "
                        "q.q1 AS box_q1, q.median AS box_median, q.q3 AS box_q3, "
                        "MAX(CASE WHEN s.chart_value <= q.q3 + 1.5 * (q.q3 - q.q1) THEN s.chart_value END) AS box_upper, "
                        "COUNT(*) AS sample_count FROM source_data s JOIN quartiles q "
                        "ON s.chart_category = q.chart_category "
                        "GROUP BY s.chart_category, q.q1, q.median, q.q3 ORDER BY sample_count DESC"
                    )
                    cursor = db.execute(text(query), params)
                    result = cursor.fetchmany(MAX_CHART_GROUPS + 1)
                    rows = _result_rows(result[:MAX_CHART_GROUPS], list(cursor.keys()))
                    source_record_count = int(
                        db.execute(
                            text(f"SELECT COUNT(*) FROM {table_sql}{source_where}"),
                            params,
                        ).scalar()
                        or 0
                    )
                    aggregate_row_count = int(
                        db.execute(
                            text(
                                f"SELECT COUNT(DISTINCT {quote(category)}) FROM {table_sql}{source_where}"
                            ),
                            params,
                        ).scalar()
                        or 0
                    )
                    method = "sql_percentile"
                elif db_type == "mssql":
                    query = (
                        "WITH source_data AS ("
                        f"SELECT {quote(category)} AS chart_category, {quote(value)} AS chart_value "
                        f"FROM {table_sql}{source_where}), ranked AS ("
                        "SELECT chart_category, chart_value, "
                        "PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY chart_value) OVER (PARTITION BY chart_category) AS q1, "
                        "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY chart_value) OVER (PARTITION BY chart_category) AS median, "
                        "PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY chart_value) OVER (PARTITION BY chart_category) AS q3 "
                        "FROM source_data) "
                        f"SELECT chart_category AS {quote(category)}, "
                        "MIN(CASE WHEN chart_value >= q1 - 1.5 * (q3 - q1) THEN chart_value END) AS box_lower, "
                        "MIN(q1) AS box_q1, MIN(median) AS box_median, MIN(q3) AS box_q3, "
                        "MAX(CASE WHEN chart_value <= q3 + 1.5 * (q3 - q1) THEN chart_value END) AS box_upper, "
                        "COUNT(*) AS sample_count FROM ranked GROUP BY chart_category ORDER BY sample_count DESC"
                    )
                    cursor = db.execute(text(query), params)
                    result = cursor.fetchmany(MAX_CHART_GROUPS + 1)
                    rows = _result_rows(result[:MAX_CHART_GROUPS], list(cursor.keys()))
                    source_record_count = int(
                        db.execute(
                            text(f"SELECT COUNT(*) FROM {table_sql}{source_where}"),
                            params,
                        ).scalar()
                        or 0
                    )
                    aggregate_row_count = int(
                        db.execute(
                            text(
                                f"SELECT COUNT(DISTINCT {quote(category)}) FROM {table_sql}{source_where}"
                            ),
                            params,
                        ).scalar()
                        or 0
                    )
                    method = "sql_percentile"
                else:
                    rows, source_record_count, aggregate_row_count = (
                        _server_boxplot_rows(
                            db,
                            table_sql=table_sql,
                            category=category,
                            value=value,
                            where_sql=where_sql,
                            params=params,
                            quote=quote,
                        )
                    )
                    query = "Server-side bounded boxplot aggregation"
                    method = "server_full_scan"
                mapping = {"category_field": category, "value_field": value}

        return {
            "columns": list(rows[0]) if rows else [],
            "rows": rows,
            "query": query,
            "chart_mapping": mapping,
            "chart_aggregation": {
                "type": chart_type,
                "method": method,
                "fullDataset": True,
                "resultTruncated": aggregate_row_count > MAX_CHART_GROUPS,
                "sourceRecordCount": source_record_count,
                "aggregateRowCount": aggregate_row_count,
                "displayedRowCount": len(rows),
                **(
                    {"aggregation": aggregation, "metric": value_field or "*"}
                    if chart_type == "heatmap"
                    else {"statistic": "Tukey five-number summary"}
                ),
            },
        }
    finally:
        engine.dispose()


def execute_database_request(
    connection: dict[str, Any],
    arguments: dict[str, Any],
    query_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_profile = query_profile or {}
    allowed_objects = query_profile.get("allowed_objects") or []
    action = str(arguments.get("action") or "schema").lower()
    if action not in ("schema", "query", "chart_aggregate"):
        raise ValueError(
            "Database action must be 'schema', 'query', or 'chart_aggregate'"
        )
    if action == "schema":
        return describe_database(connection, allowed_objects=allowed_objects)
    if action == "chart_aggregate":
        return execute_chart_aggregation(connection, arguments, query_profile)
    db_type = normalize_database_type(connection.get("db_type"))
    limit = max(1, min(int(arguments.get("limit") or 50), 200))
    if db_type == "mongodb":
        collection_name = str(arguments.get("collection") or "").strip()
        if not collection_name:
            raise ValueError("collection is required for MongoDB query")
        if allowed_objects and collection_name.lower() not in {
            str(value).lower() for value in allowed_objects
        }:
            raise ValueError(
                f"Collection '{collection_name}' is not allowed by this agent's database profile"
            )
        query_filter = arguments.get("filter") or {}
        if not isinstance(query_filter, dict):
            raise ValueError("MongoDB filter must be an object")
        if any(
            key in str(query_filter)
            for key in ("$where", "$function", "$accumulator", "$out", "$merge")
        ):
            raise ValueError("Unsafe MongoDB operator is not allowed")
        with _mongo_client(connection) as client:
            documents = list(
                client[connection["database"]][collection_name]
                .find(query_filter)
                .limit(limit + 1)
            )
        result_truncated = len(documents) > limit
        documents = documents[:limit]
        return {
            "collection": collection_name,
            "rows": [
                {key: _json_value(value) for key, value in row.items()}
                for row in documents
            ],
            "limit": limit,
            "resultTruncated": result_truncated,
        }
    query = _validate_read_only_sql(
        str(arguments.get("query") or ""), db_type, allowed_objects
    )
    engine = create_sql_engine(connection)
    try:
        with engine.connect() as db:
            result = db.execute(text(query))
            columns = list(result.keys())
            fetched_rows = result.fetchmany(limit + 1)
            result_truncated = len(fetched_rows) > limit
            rows = [
                dict(zip(columns, (_json_value(value) for value in row), strict=True))
                for row in fetched_rows[:limit]
            ]
        return {
            "columns": columns,
            "rows": rows,
            "limit": limit,
            "resultTruncated": result_truncated,
        }
    finally:
        engine.dispose()
