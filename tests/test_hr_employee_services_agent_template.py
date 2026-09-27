from core.catalog_templates import (
    HR_EMPLOYEE_SERVICES_SOURCE_ID,
    hr_employee_services_advisor_template,
)
from mongo_table_connecters.agent_catalog import snapshot_requirements


def test_hr_employee_services_template_is_rag_only_and_privacy_preserving():
    template = hr_employee_services_advisor_template()
    agent = template["agent"]
    tools = agent["config"]["tool_settings"]
    prompt = agent["prompt"]

    assert agent["_id"] == HR_EMPLOYEE_SERVICES_SOURCE_ID
    assert agent["config"]["runtime"] == "langgraph"
    assert agent["config"]["llm_profile_id"] == "system"
    assert tools["knowledge_search"] == "always"
    assert all(
        tools[name] is False
        for name in (
            "chart",
            "external_database",
            "rest_integrations",
            "mail",
            "business_documents",
            "messaging",
            "mcp",
            "subagents",
        )
    )
    assert tools["mcp_server_ids"] == []
    assert tools["subagent_ids"] == []
    assert "Search authorized Knowledge before answering" in prompt["detail_context"]
    assert "Do not expose personal, payroll" in prompt["constraints"]
    assert "Do not make" in prompt["constraints"]
    assert "Sources" in prompt["output_format"]
    assert template["visibility"] == "all_teams"
    assert template["category"] == "HR & Employee Services"
    assert snapshot_requirements(agent) == {
        "llm_profile_id": "system",
        "runtime": "langgraph",
        "uses_knowledge": True,
        "declared_tools": [],
    }


def test_hr_employee_services_template_accepts_deployment_selected_profile():
    template = hr_employee_services_advisor_template(llm_profile_id="managed:provider:model")

    assert template["agent"]["config"]["llm_profile_id"] == "managed:provider:model"
