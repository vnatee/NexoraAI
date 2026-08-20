from builtins import ExceptionGroup
from types import SimpleNamespace

import pytest

from agent_runtime.adapters.mcp import (
    MCPServerConfig,
    MCPToolExecutionError,
    _augment_tool_error,
    _render_result,
    _root_mcp_error,
    _tool_description,
)


def test_mcp_soft_error_is_raised_before_structured_content_is_returned():
    result = SimpleNamespace(
        is_error=True,
        structured_content={"apparently": "successful"},
        content=[SimpleNamespace(text="user lacks required permissions")],
    )

    with pytest.raises(MCPToolExecutionError, match="user lacks required permissions"):
        _render_result(result)


def test_mcp_success_keeps_structured_content():
    result = SimpleNamespace(
        is_error=False,
        structured_content={"monitors": [{"id": "1"}]},
        content=[],
    )

    assert _render_result(result) == {"monitors": [{"id": "1"}]}


def test_nested_mcp_exception_group_is_reduced_to_actionable_root_cause():
    error = ExceptionGroup(
        "transport task group",
        [
            ExceptionGroup(
                "session task group",
                [MCPToolExecutionError("user lacks required permissions")],
            )
        ],
    )

    root = _root_mcp_error(error)

    assert isinstance(root, MCPToolExecutionError)
    assert str(root) == "user lacks required permissions"


def test_datadog_monitor_description_routes_historical_alerts_to_events():
    description = _tool_description(
        MCPServerConfig(name="Datadog", url="https://mcp.datadoghq.com/v1/mcp"),
        SimpleNamespace(
            name="search_datadog_monitors",
            description="Search monitors",
        ),
    )

    assert "current statuses" in description
    assert "historical alert occurrences" in description
    assert "search_datadog_events" in description
    assert "search_datadog_monitor_groups" in description
    assert "Do not claim pagination" in description


def test_datadog_log_analysis_description_requires_field_discovery():
    description = _tool_description(
        MCPServerConfig(name="Datadog", url="https://mcp.datadoghq.com/v1/mcp"),
        SimpleNamespace(
            name="analyze_datadog_logs",
            description="Analyze logs",
        ),
    )

    assert "search_datadog_logs" in description
    assert "do not assume" in description
    assert "cannot be resolved" in description


def test_datadog_unresolved_column_error_adds_discovery_recovery():
    message = (
        'request failed: advanced query API returned 400: '
        '{"errors":[{"detail":"line 1:8: Column \'source\' cannot be resolved"}]}'
    )

    enriched = _augment_tool_error(
        MCPServerConfig(name="Datadog", url="https://mcp.datadoghq.com/v1/mcp"),
        "analyze_datadog_logs",
        message,
    )

    assert message in enriched
    assert "'source' is not a queryable column" in enriched
    assert "Call search_datadog_logs" in enriched
    assert "Do not retry the same advanced query" in enriched


def test_non_datadog_tool_error_is_not_changed():
    message = "Column 'source' cannot be resolved"

    assert (
        _augment_tool_error(
            MCPServerConfig(name="Other MCP", url="https://example.com/mcp"),
            "analyze_datadog_logs",
            message,
        )
        == message
    )
