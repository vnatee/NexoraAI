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

    stored = collection.insert_one.call_args.args[0]
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

    stored = collection.insert_one.call_args.args[0]
    assert stored["user"] == {"_id": "user-1", "name": "user@example.com"}
    assert stored["group"] == {"_id": "team-1", "name": "DIG"}
