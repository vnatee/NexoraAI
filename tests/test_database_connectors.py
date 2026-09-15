import sqlite3
from unittest.mock import MagicMock

import pytest

from agent_runtime.adapters import database as database_adapter
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext
from database_connectors import (
    execute_database_request,
    normalize_database_config,
)
from database_connectors import (
    test_database_connection as check_database_connection,
)
from mongo_table_connecters.database_binding import normalize_query_profile
from mongo_table_connecters.external_database import serialize_external_database


def _sqlite_connection(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_DATABASE_ROOT", str(tmp_path))
    path = tmp_path / "operations.db"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer TEXT, region TEXT, total REAL)"
        )
        db.executemany(
            "INSERT INTO orders (customer, region, total) VALUES (?, ?, ?)",
            [("Alice", "North", 100.5), ("Bob", "South", 42.0)],
        )
    return {"db_type": "sqlite", "database": "operations.db"}


def test_normalize_database_config_applies_vendor_defaults():
    config = normalize_database_config(
        {
            "db_type": "postgres",
            "host": "db.internal",
            "database": "app",
            "username": "reader",
        }
    )

    assert config["db_type"] == "postgresql"
    assert config["port"] == 5432
    assert config["options"]["ssl_mode"] == "prefer"


def test_sqlite_connector_tests_schema_and_query(tmp_path, monkeypatch):
    connection = _sqlite_connection(tmp_path, monkeypatch)

    assert check_database_connection(connection)["ok"] is True
    schema = execute_database_request(connection, {"action": "schema"})
    result = execute_database_request(
        connection,
        {
            "action": "query",
            "query": "SELECT customer, total FROM orders ORDER BY id",
            "limit": 1,
        },
    )

    assert schema["objects"][0]["name"] == "orders"
    assert schema["objects"][0]["primary_key"] == ["id"]
    assert result["rows"] == [{"customer": "Alice", "total": 100.5}]


def test_sqlite_heatmap_aggregation_uses_full_filtered_dataset(tmp_path, monkeypatch):
    connection = _sqlite_connection(tmp_path, monkeypatch)

    result = execute_database_request(
        connection,
        {
            "action": "chart_aggregate",
            "chart_type": "heatmap",
            "table": "orders",
            "x_field": "customer",
            "y_field": "region",
            "aggregation": "count",
        },
        {"allowed_objects": ["orders"]},
    )

    assert result["chart_mapping"] == {
        "x_field": "customer",
        "y_field": "region",
        "value_field": "chart_value",
    }
    assert result["chart_aggregation"]["method"] == "sql_group_by"
    assert result["chart_aggregation"]["sourceRecordCount"] == 2
    assert {row["chart_value"] for row in result["rows"]} == {1}


def test_sqlite_boxplot_uses_bounded_server_full_scan_fallback(tmp_path, monkeypatch):
    connection = _sqlite_connection(tmp_path, monkeypatch)

    result = execute_database_request(
        connection,
        {
            "action": "chart_aggregate",
            "chart_type": "boxplot",
            "table": "orders",
            "category_field": "region",
            "value_field": "total",
        },
        {"allowed_objects": ["orders"]},
    )

    assert result["chart_aggregation"]["method"] == "server_full_scan"
    assert result["chart_aggregation"]["fullDataset"] is True
    assert result["chart_aggregation"]["sourceRecordCount"] == 2
    assert result["rows"][0]["box_q1"] in (42.0, 100.5)


def test_query_profile_allowlist_is_enforced_server_side(tmp_path, monkeypatch):
    connection = _sqlite_connection(tmp_path, monkeypatch)
    profile = {"allowed_objects": ["orders"]}

    result = execute_database_request(
        connection,
        {
            "action": "query",
            "query": "WITH recent AS (SELECT * FROM orders) SELECT * FROM recent",
        },
        profile,
    )
    assert len(result["rows"]) == 2

    with pytest.raises(ValueError, match="not allowed"):
        execute_database_request(
            connection,
            {"action": "query", "query": "SELECT * FROM suppliers"},
            profile,
        )


def test_sql_server_allowlist_accepts_fully_qualified_table_name():
    from database_connectors import _validate_read_only_sql

    query = "SELECT PO_Number FROM demo.dbo.po_scored"

    assert _validate_read_only_sql(query, "mssql", ["demo.dbo.po_scored"]) == query
    assert _validate_read_only_sql(query, "mssql", ["dbo.po_scored"]) == query


def test_query_profile_is_normalized_and_bounded():
    profile = normalize_query_profile(
        {
            "business_context": "  Purchase order evaluation  ",
            "allowed_objects": ["po_header", "po_header", "po_line"],
            "query_examples": [
                {
                    "question": "Late POs",
                    "query": "SELECT * FROM po_header WHERE actual_date > promised_date",
                },
                {"question": "", "query": "SELECT 1"},
            ],
        }
    )

    assert profile["business_context"] == "Purchase order evaluation"
    assert profile["allowed_objects"] == ["po_header", "po_line"]
    assert len(profile["query_examples"]) == 1


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE orders SET total = 0",
        "DELETE FROM orders",
        "DROP TABLE orders",
        "SELECT * FROM orders; SELECT 1",
    ],
)
def test_sql_connector_rejects_non_read_only_queries(tmp_path, monkeypatch, query):
    connection = _sqlite_connection(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="read-only|Only one"):
        execute_database_request(connection, {"action": "query", "query": query})


def test_sqlite_connector_restricts_files_to_local_database_root(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_DATABASE_ROOT", str(tmp_path / "allowed"))

    with pytest.raises(ValueError, match="LOCAL_DATABASE_ROOT"):
        check_database_connection(
            {"db_type": "sqlite", "database": str(tmp_path / "outside.db")}
        )


def test_database_serialization_never_exposes_secrets():
    serialized = serialize_external_database(
        {
            "_id": "db-1",
            "name": "Operations",
            "password": "legacy-secret",
            "password_ciphertext": "encrypted-secret",
        }
    )

    assert serialized["has_password"] is True
    assert "password" not in serialized
    assert "password_ciphertext" not in serialized


def test_langgraph_registers_one_read_only_tool_per_database_binding(monkeypatch):
    monkeypatch.setattr(
        database_adapter,
        "get_enabled_database_bindings_by_agent_id",
        MagicMock(
            return_value=[
                {
                    "_id": "binding-123",
                    "integration_id": "db-1",
                    "alias": "Sales DB",
                    "query_profile": {
                        "business_context": "Approved sales reporting",
                        "allowed_objects": ["orders"],
                        "query_examples": [],
                    },
                }
            ]
        ),
    )
    monkeypatch.setattr(
        database_adapter,
        "get_external_database_by_id",
        MagicMock(
            return_value={"_id": "db-1", "name": "Sales", "db_type": "postgresql"}
        ),
    )
    monkeypatch.setattr(
        database_adapter,
        "execute_database_request",
        MagicMock(return_value={"objects": [{"name": "orders"}]}),
    )
    registry = ToolRegistry(ToolRuntimeContext(agent_id="agent-1", auth_claims={}))

    database_adapter.register_database_tools(registry, "agent-1")

    assert len(registry.specs()) == 1
    assert registry.specs()[0].name.startswith("database_sales_db")
    assert "read-only" in registry.specs()[0].description
    assert "Approved sales reporting" in registry.specs()[0].description
    assert "MUST call action=schema" in registry.specs()[0].description
    assert (
        registry.specs()[0]
        .input_schema["properties"]["query"]["description"]
        .startswith("One read-only")
    )


@pytest.mark.asyncio
async def test_database_tool_requires_schema_before_query(monkeypatch):
    async def immediate_to_thread(function, *args):
        return function(*args)

    monkeypatch.setattr(database_adapter.asyncio, "to_thread", immediate_to_thread)
    monkeypatch.setattr(
        database_adapter,
        "execute_database_request",
        MagicMock(
            side_effect=lambda connection, arguments, profile: (
                {"objects": []} if arguments["action"] == "schema" else {"rows": []}
            )
        ),
    )
    handler = database_adapter._handler_for(
        {"db_type": "sqlite"}, {"allowed_objects": ["orders"]}
    )

    with pytest.raises(ValueError, match="action=schema"):
        await handler({"action": "query", "query": "SELECT * FROM orders"}, None)

    schema = await handler({"action": "schema"}, None)
    result = await handler({"action": "query", "query": "SELECT * FROM orders"}, None)

    assert schema["query_profile"]["allowed_objects"] == ["orders"]
    assert result == {"rows": [], "query": "SELECT * FROM orders"}


@pytest.mark.asyncio
async def test_database_chart_aggregate_validates_schema_without_separate_schema_call(
    monkeypatch,
):
    async def immediate_to_thread(function, *args):
        return function(*args)

    execute_request = MagicMock(
        return_value={
            "rows": [{"Vendor": "A", "chart_value": 2}],
            "chart_mapping": {
                "x_field": "PO_Month",
                "y_field": "Vendor",
                "value_field": "chart_value",
            },
            "chart_aggregation": {"type": "heatmap", "fullDataset": True},
        }
    )
    monkeypatch.setattr(database_adapter.asyncio, "to_thread", immediate_to_thread)
    monkeypatch.setattr(database_adapter, "execute_database_request", execute_request)
    handler = database_adapter._handler_for(
        {"db_type": "mssql"}, {"allowed_objects": ["po_scored"]}
    )

    result = await handler(
        {
            "action": "chart_aggregate",
            "chart_type": "heatmap",
            "table": "po_scored",
            "x_field": "PO_Month",
            "y_field": "Vendor",
            "aggregation": "count",
        },
        None,
    )

    assert result["chart_aggregation"]["fullDataset"] is True
    assert "Call create_chart" in result["next_step"]
    execute_request.assert_called_once()
