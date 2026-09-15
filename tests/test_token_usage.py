from unittest.mock import MagicMock

from tokens_usage import save_tokens_usage


def _tokens():
    return {
        "tokens_prompt_sum": 10,
        "tokens_completion_sum": 5,
        "tokens_total_sum": 15,
        "files": ["report.pdf"],
    }


def test_insert_user_usage_supports_request_without_team(monkeypatch):
    collection = MagicMock()
    monkeypatch.setattr(save_tokens_usage, "usage_collection", collection)
    monkeypatch.setattr(save_tokens_usage, "summarize_turn", lambda _response: _tokens())
    monkeypatch.setattr(
        save_tokens_usage,
        "get_user_by_ad_email",
        lambda _username: {"_id": "user-1"},
    )
    get_team = MagicMock()
    monkeypatch.setattr(save_tokens_usage, "get_team_by_id", get_team)

    save_tokens_usage.insert_user_usage(
        {"preferred_username": "user@example.com"}, "response"
    )

    stored = collection.update_one.call_args.args[1]["$setOnInsert"]
    assert stored["user"] == {"_id": "user-1", "name": "user@example.com"}
    assert stored["group"] is None
    get_team.assert_not_called()


def test_insert_user_usage_uses_validated_application_user_and_team(monkeypatch):
    collection = MagicMock()
    monkeypatch.setattr(save_tokens_usage, "usage_collection", collection)
    monkeypatch.setattr(save_tokens_usage, "summarize_turn", lambda _response: _tokens())
    monkeypatch.setattr(
        save_tokens_usage,
        "get_user_by_ad_email",
        lambda _username: {"_id": "legacy-user"},
    )
    monkeypatch.setattr(
        save_tokens_usage,
        "get_team_by_id",
        lambda team_id: {"_id": team_id, "name": "DIG"},
    )

    save_tokens_usage.insert_user_usage(
        {
            "preferred_username": "user@example.com",
            "application_user_id": "user-1",
            "team_id": "team-1",
        },
        "response",
    )

    stored = collection.update_one.call_args.args[1]["$setOnInsert"]
    assert stored["user"] == {"_id": "user-1", "name": "user@example.com"}
    assert stored["group"] == {"_id": "team-1", "name": "DIG"}


def test_insert_user_usage_persists_safe_analytics_dimensions(monkeypatch):
    collection = MagicMock()
    monkeypatch.setattr(save_tokens_usage, "usage_collection", collection)
    monkeypatch.setattr(save_tokens_usage, "summarize_turn", lambda _response: {
        **_tokens(),
        "tokens_reasoning_sum": 2,
        "model_calls": [{
            "title": "Generate answer",
            "model": "gpt-4.1-mini",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "reasoning_tokens": 2,
            "total_tokens": 17,
        }],
    })
    monkeypatch.setattr(save_tokens_usage, "get_user_by_ad_email", lambda _username: {"_id": "user-1"})

    save_tokens_usage.insert_user_usage(
        {"preferred_username": "user@example.com"},
        "raw response that must not be stored",
        metadata={
            "agent_id": "agent-1",
            "agent_name": "Analyst",
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "runtime": "langgraph",
        },
    )

    stored = collection.update_one.call_args.args[1]["$setOnInsert"]
    assert stored["schema_version"] == 3
    assert stored["metadata"]["agent_id"] == "agent-1"
    assert stored["metadata"]["provider"] == "openai"
    assert stored["model_calls"][0]["total_tokens"] == 17
    assert "raw response" not in str(stored)


def test_insert_user_usage_is_idempotent_by_usage_event_id(monkeypatch):
    collection = MagicMock()
    collection.update_one.return_value.upserted_id = "request-1"
    monkeypatch.setattr(save_tokens_usage, "usage_collection", collection)
    monkeypatch.setattr(save_tokens_usage, "summarize_turn", lambda _response: _tokens())
    monkeypatch.setattr(save_tokens_usage, "get_user_by_ad_email", lambda _username: {"_id": "user-1"})

    result = save_tokens_usage.insert_user_usage(
        {"preferred_username": "user@example.com"},
        "response",
        metadata={"usage_event_id": "request-1"},
    )

    assert collection.update_one.call_args.args[0] == {"_id": "request-1"}
    assert collection.update_one.call_args.kwargs["upsert"] is True
    assert result == {"usage_event_id": "request-1", "tokens_total": 15, "inserted": True}
