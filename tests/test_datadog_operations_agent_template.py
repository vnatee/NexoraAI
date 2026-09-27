from core.catalog_seed import select_tool_profile_id
from core.catalog_templates import (
    DATADOG_OPERATIONS_SOURCE_ID,
    datadog_operations_analyst_template,
)
from mongo_table_connecters.agent_catalog import snapshot_requirements


def test_datadog_operations_template_is_portable_read_only_and_evidence_led():
    template = datadog_operations_analyst_template()
    agent = template["agent"]
    tools = agent["config"]["tool_settings"]
    prompt = agent["prompt"]

    assert agent["_id"] == DATADOG_OPERATIONS_SOURCE_ID
    assert agent["config"]["runtime"] == "langgraph"
    assert agent["config"]["llm_profile_id"] == "system"
    assert tools["knowledge_search"] == "always"
    assert tools["chart"] is True
    assert tools["mcp"] is True
    assert tools["mcp_execution"] == "required"
    assert tools["mcp_server_ids"] == []
    assert tools["mcp_tool_allowlists"] == {}
    assert all(
        tools[name] is False
        for name in ("external_database", "rest_integrations", "mail", "business_documents", "messaging", "subagents")
    )
    assert "Never fabricate evidence" in prompt["constraints"]
    assert "Never execute write or destructive actions" in prompt["constraints"]
    assert "Evidence timeline" in prompt["output_format"]
    assert "create_chart" in prompt["output_format"]
    assert agent["config"]["chart_settings"] == {
        "enabled": True,
        "auto_generate": True,
        "chart_selection_mode": "auto",
        "default_chart_type": "line",
        "allowed_chart_types": ["line", "area", "bar", "gauge", "scatter", "heatmap"],
        "color_palette": ["#632CA6", "#1F70C1", "#00A78E", "#F59E0B", "#DC2626", "#64748B"],
        "title_template": "Datadog operational evidence",
        "trigger_keywords": ["chart", "graph", "plot", "visualize", "กราฟ", "แนวโน้ม"],
    }
    assert template["visibility"] == "all_teams"
    assert "Authorization" not in str(template)
    assert "DD_API_KEY" not in str(template)
    assert "DD_APPLICATION_KEY" not in str(template)
    assert snapshot_requirements(agent)["declared_tools"] == ["chart", "mcp"]


def test_datadog_template_can_use_a_selected_managed_profile():
    template = datadog_operations_analyst_template(llm_profile_id="managed:provider:model")

    assert template["agent"]["config"]["llm_profile_id"] == "managed:provider:model"


def test_datadog_seed_prefers_tested_azure_tool_profile():
    providers = [
        {
            "_id": "local-provider",
            "provider": "openai_compatible",
            "enabled": True,
            "delete_at": None,
            "models": [{"id": "local-model", "supports_tools": True, "tool_capability_status": "supported"}],
        },
        {
            "_id": "azure-provider",
            "provider": "azure_openai",
            "enabled": True,
            "delete_at": None,
            "models": [{"id": "gpt41", "supports_tools": True, "tool_capability_status": "supported"}],
        },
    ]

    assert select_tool_profile_id(providers) == "managed:azure-provider:gpt41"


def test_datadog_seed_falls_back_to_system_without_a_usable_managed_profile():
    providers = [
        {
            "_id": "disabled-provider",
            "provider": "azure_openai",
            "enabled": False,
            "delete_at": None,
            "models": [{"id": "gpt41", "supports_tools": True, "tool_capability_status": "supported"}],
        }
    ]

    assert select_tool_profile_id(providers) == "system"
