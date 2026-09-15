from builtins import ExceptionGroup
from types import SimpleNamespace

import pytest

from agent_runtime.adapters.mcp import (
    MCPServerConfig,
    MCPToolExecutionError,
    _augment_tool_error,
    _managed_tool_arguments,
    _record_drawio_artifact,
    _render_result,
    _root_mcp_error,
    _tool_description,
    _validated_drawio_arguments,
    is_read_only_mcp_tool,
    register_mcp_tools,
)
from agent_runtime.factory import _mcp_connection_matches_team


def test_team_owned_mcp_connection_is_available_only_to_its_team():
    connection = {"_id": "mcp-1", "team_id": "team-1"}

    assert _mcp_connection_matches_team(connection, "team-1") is True
    assert _mcp_connection_matches_team(connection, "team-2") is False


def test_legacy_unassigned_mcp_connection_remains_runtime_compatible():
    assert _mcp_connection_matches_team({"_id": "legacy"}, "team-1") is True


@pytest.mark.parametrize(
    "name",
    ["list_resources", "resourceGroupsList", "query_resource_graph", "get_subscription"],
)
def test_read_only_mcp_tool_classifier_allows_inventory_operations(name):
    assert is_read_only_mcp_tool(name) is True


@pytest.mark.parametrize(
    "name",
    ["create_resource", "deployTemplate", "role_assign", "restart_vm", "run_command"],
)
def test_read_only_mcp_tool_classifier_rejects_write_or_ambiguous_operations(name):
    assert is_read_only_mcp_tool(name) is False


def test_managed_azure_subscription_list_uses_connection_tenant():
    server = MCPServerConfig(
        name="Azure inventory",
        url="http://managed-azure:8080",
        vendor="azure",
        managed=True,
    )

    assert _managed_tool_arguments(
        server,
        "subscription_list",
        {"tenant": "tenantId", "retry": True},
    ) == {"retry": True}


def test_external_azure_subscription_list_preserves_explicit_tenant():
    server = MCPServerConfig(
        name="External Azure",
        url="https://azure.example/mcp",
        vendor="azure",
    )

    assert _managed_tool_arguments(
        server,
        "subscription_list",
        {"tenant": "example-tenant"},
    ) == {"tenant": "example-tenant"}


@pytest.mark.asyncio
async def test_read_only_mcp_server_registers_only_inventory_tools(monkeypatch):
    from agent_runtime.adapters import mcp as mcp_adapter

    tools = [
        SimpleNamespace(
            name="list_resources", description="List resources", input_schema={}
        ),
        SimpleNamespace(
            name="deploy_resource", description="Deploy resource", input_schema={}
        ),
    ]

    async def discover(_server):
        return tools

    class Registry:
        audit = None

        def __init__(self):
            self.names = []
            self.sources = []

        def register(self, spec):
            self.names.append(spec.name)
            self.sources.append(spec.source)

    monkeypatch.setattr(mcp_adapter, "discover_mcp_tools", discover)
    registry = Registry()

    await register_mcp_tools(
        registry,
        [
            MCPServerConfig(
                name="Azure inventory",
                url="https://example.test/mcp",
                vendor="azure",
                operation_mode="read_only",
            )
        ],
    )

    assert registry.names == ["mcp_Azure inventory_list_resources"]
    assert registry.sources == ["mcp:Azure inventory:azure:Azure inventory"]


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


def test_successful_drawio_xml_is_exposed_as_downloadable_artifact():
    context = SimpleNamespace(metadata={})
    xml = '<mxGraphModel><root><mxCell id="0"/></root></mxGraphModel>'

    _record_drawio_artifact(
        context,
        MCPServerConfig(name="Draw.io", url="https://mcp.draw.io/mcp", vendor="drawio"),
        "create_diagram",
        {"xml": xml, "routing": "libavoid"},
    )

    assert context.metadata["diagram"] == {
        "format": "drawio",
        "filename": "azure-architecture.drawio",
        "mime_type": "application/vnd.jgraph.mxfile",
        "content": xml,
    }


def test_drawio_xml_repairs_bare_ampersands_before_upload_and_download():
    server = MCPServerConfig(
        name="Draw.io", url="https://mcp.draw.io/mcp", vendor="drawio"
    )

    result = _validated_drawio_arguments(
        server,
        "create_diagram",
        {"xml": '<mxGraphModel><root><mxCell value="API & Web"/></root></mxGraphModel>'},
    )

    assert 'value="API &amp; Web"' in result["xml"]


def test_drawio_xml_rejects_malformed_attributes_with_retry_guidance():
    server = MCPServerConfig(
        name="Draw.io", url="https://mcp.draw.io/mcp", vendor="drawio"
    )

    with pytest.raises(MCPToolExecutionError, match="Regenerate the complete XML"):
        _validated_drawio_arguments(
            server,
            "create_diagram",
            {'xml': '<mxGraphModel><root><mxCell value="API "quoted""/></root></mxGraphModel>'},
        )


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


def test_drawio_description_requires_downloadable_xml_and_marks_inference():
    description = _tool_description(
        MCPServerConfig(
            name="Draw.io", url="https://mcp.draw.io/mcp", vendor="drawio"
        ),
        SimpleNamespace(name="create_diagram", description="Create a diagram"),
    )

    assert "downloadable .drawio file" in description
    assert "dashed edges labelled 'inferred'" in description
    assert "instead of printing XML" in description
    assert "call search_shapes before create_diagram" in description
    assert "copy each returned style string exactly" in description


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
