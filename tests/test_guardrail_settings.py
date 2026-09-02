from core.guardrails import GuardrailPolicy
from mongo_table_connecters import guardrail_settings


def test_effective_policy_combines_system_team_and_agent(monkeypatch):
    configured = {
        None: {"max_input_chars": 10_000, "pii_input_action": "warn"},
        "team-1": {"max_input_chars": 8_000, "pii_input_action": "block"},
    }
    monkeypatch.setattr(
        guardrail_settings,
        "get_guardrail_settings",
        lambda team_id=None: configured.get(team_id),
    )

    effective = guardrail_settings.effective_guardrail_policy(
        {
            "enabled": False,
            "max_input_chars": 200_000,
            "pii_input_action": "allow",
        },
        team_id="team-1",
    )

    assert effective.enabled is True
    assert effective.max_input_chars == 8_000
    assert effective.pii_input_action == "block"


def test_effective_policy_preserves_agent_behavior_when_no_parent_exists(monkeypatch):
    monkeypatch.setattr(guardrail_settings, "get_guardrail_settings", lambda team_id=None: None)
    agent = GuardrailPolicy.from_config(
        {"enabled": False, "max_input_chars": 42_000, "pii_output_action": "allow"}
    )

    effective = guardrail_settings.effective_guardrail_policy(
        agent.serialize(), team_id="team-1"
    )

    assert effective == agent
