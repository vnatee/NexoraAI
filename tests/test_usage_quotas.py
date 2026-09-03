from unittest.mock import MagicMock

import pytest

from core.usage_quotas import LLMTokenQuotaRule, UsageQuotaPolicy, effective_quota_policy
from mongo_table_connecters import usage_quotas


def test_effective_quota_uses_strictest_non_zero_limit():
    result = effective_quota_policy(
        UsageQuotaPolicy(True, 100000, 1000, 60),
        UsageQuotaPolicy(True, 50000, 0, 30),
        UsageQuotaPolicy(True, 0, 100, 0),
    )
    assert result.monthly_llm_tokens == 50000
    assert result.monthly_document_pages == 100
    assert result.llm_requests_per_minute == 30


def test_zero_means_unlimited_and_disabled_policy_does_not_apply():
    result = effective_quota_policy(
        UsageQuotaPolicy(True, 0, 0, 0),
        UsageQuotaPolicy(False, 1, 1, 1),
    )
    assert result == UsageQuotaPolicy(enabled=True)


def test_system_limit_is_evaluated_against_system_usage(monkeypatch):
    monkeypatch.setattr(usage_quotas, "get_quota_settings", lambda level, subject_id="": {
        "enabled": level == "system",
        "monthly_llm_tokens": 100,
        "monthly_document_pages": 0,
        "llm_requests_per_minute": 0,
    })
    observed = []

    def usage(team_id, user_id):
        observed.append((team_id, user_id))
        return {"monthly_llm_tokens": 100 if not team_id and not user_id else 0, "monthly_document_pages": 0}

    monkeypatch.setattr(usage_quotas, "current_usage", usage)
    with pytest.raises(ValueError, match="for system"):
        usage_quotas.check_and_record_request("team-1", "user-1")
    assert ("", "") in observed


def test_request_rate_counter_is_atomic(monkeypatch):
    monkeypatch.setattr(usage_quotas, "get_quota_settings", lambda level, subject_id="": {
        "enabled": level == "user",
        "monthly_llm_tokens": 0,
        "monthly_document_pages": 0,
        "llm_requests_per_minute": 2,
    })
    monkeypatch.setattr(usage_quotas, "current_usage", lambda *_args: {"monthly_llm_tokens": 0, "monthly_document_pages": 0})
    counter = MagicMock()
    counter.find_one_and_update.return_value = {"count": 3}
    monkeypatch.setattr(usage_quotas, "request_windows", counter)

    with pytest.raises(ValueError, match="for user"):
        usage_quotas.check_and_record_request("team-1", "user-1")
    assert counter.find_one_and_update.called


def test_policy_normalizes_provider_and_profile_token_rules():
    policy = UsageQuotaPolicy.from_config({
        "enabled": True,
        "llm_token_rules": [
            {
                "dimension": "provider",
                "target_id": "provider-1",
                "target_label": "OpenAI",
                "workload": "chat",
                "monthly_tokens": 5000,
            }
        ],
    })
    assert policy.llm_token_rules == (
        LLMTokenQuotaRule("provider", "provider-1", "OpenAI", 5000, "chat", True),
    )
    assert policy.serialize()["llm_token_rules"][0]["target_id"] == "provider-1"


def test_duplicate_token_rule_is_rejected():
    rule = {
        "dimension": "profile",
        "target_id": "managed:provider-1:model-1",
        "monthly_tokens": 100,
    }
    with pytest.raises(ValueError, match="Only one"):
        UsageQuotaPolicy.from_config({"llm_token_rules": [rule, rule]})


def test_team_default_per_member_limit_is_normalized():
    policy = UsageQuotaPolicy.from_config({
        "enabled": True,
        "monthly_llm_tokens": 10_000,
        "monthly_llm_tokens_per_user": 1_000,
    })

    assert policy.monthly_llm_tokens_per_user == 1_000
    assert policy.serialize()["monthly_llm_tokens_per_user"] == 1_000


def test_team_default_per_member_limit_is_enforced_in_user_scope(monkeypatch):
    def configured(level, subject_id=""):
        if level == "team":
            return {
                "enabled": True,
                "monthly_llm_tokens": 10_000,
                "monthly_llm_tokens_per_user": 1_000,
            }
        return None

    monkeypatch.setattr(usage_quotas, "get_quota_settings", configured)
    monkeypatch.setattr(usage_quotas, "current_usage", lambda team_id, user_id: {
        "monthly_llm_tokens": 1_000 if user_id else 2_000,
        "monthly_document_pages": 0,
    })

    with pytest.raises(ValueError, match="for team_user"):
        usage_quotas.check_and_record_request("team-1", "user-1")


def test_team_member_override_replaces_team_default_but_not_team_total(monkeypatch):
    def configured(level, subject_id=""):
        if level == "team":
            return {
                "enabled": True,
                "monthly_llm_tokens": 10_000,
                "monthly_llm_tokens_per_user": 1_000,
            }
        if level == "team_user":
            return {"enabled": True, "monthly_llm_tokens": 2_000}
        return None

    monkeypatch.setattr(usage_quotas, "get_quota_settings", configured)
    monkeypatch.setattr(usage_quotas, "current_usage", lambda team_id, user_id: {
        "monthly_llm_tokens": 1_500 if user_id else 2_000,
        "monthly_document_pages": 0,
    })

    usage_quotas.check_and_record_request("team-1", "user-1")

    monkeypatch.setattr(usage_quotas, "current_usage", lambda team_id, user_id: {
        "monthly_llm_tokens": 1_500 if user_id else 10_000,
        "monthly_document_pages": 0,
    })
    with pytest.raises(ValueError, match="for team"):
        usage_quotas.check_and_record_request("team-1", "user-1")


def test_team_member_override_is_stored_by_team_and_strips_unrelated_limits(monkeypatch):
    save = MagicMock(return_value={"enabled": True, "monthly_llm_tokens": 2_000})
    monkeypatch.setattr(usage_quotas, "save_quota_settings", save)

    result = usage_quotas.save_team_user_quota_settings(
        "team-1",
        "user-1",
        {
            "enabled": True,
            "monthly_llm_tokens": 2_000,
            "monthly_document_pages": 99,
            "llm_requests_per_minute": 9,
        },
    )

    assert result["monthly_llm_tokens"] == 2_000
    level, subject_id, stored = save.call_args.args
    assert (level, subject_id) == ("team_user", "team-1:user-1")
    assert stored["monthly_document_pages"] == 0
    assert stored["llm_requests_per_minute"] == 0


def test_matching_profile_quota_is_enforced_for_its_workload(monkeypatch):
    monkeypatch.setattr(usage_quotas, "get_quota_settings", lambda level, subject_id="": {
        "enabled": level == "team",
        "llm_token_rules": [{
            "dimension": "profile",
            "target_id": "managed:provider-1:model-1",
            "target_label": "Model one",
            "workload": "chat",
            "monthly_tokens": 100,
        }],
    })
    monkeypatch.setattr(usage_quotas, "current_usage", lambda *_args: {
        "monthly_llm_tokens": 0,
        "monthly_document_pages": 0,
    })
    monkeypatch.setattr(usage_quotas, "current_llm_rule_usage", lambda *_args: 100)

    with pytest.raises(ValueError, match=r"Model one \(team\)"):
        usage_quotas.check_and_record_request(
            "team-1",
            "user-1",
            provider_id="provider-1",
            profile_id="managed:provider-1:model-1",
            workload="chat",
        )

    usage_quotas.check_and_record_request(
        "team-1",
        "user-1",
        provider_id="provider-1",
        profile_id="managed:provider-1:model-1",
        workload="ask",
    )


def test_effective_policy_keeps_strictest_matching_token_rule():
    broad = UsageQuotaPolicy.from_config({
        "enabled": True,
        "llm_token_rules": [{
            "dimension": "provider", "target_id": "provider-1",
            "target_label": "Provider", "monthly_tokens": 1000,
        }],
    })
    strict = UsageQuotaPolicy.from_config({
        "enabled": True,
        "llm_token_rules": [{
            "dimension": "provider", "target_id": "provider-1",
            "target_label": "Renamed provider", "monthly_tokens": 500,
        }],
    })
    result = effective_quota_policy(broad, strict)
    assert len(result.llm_token_rules) == 1
    assert result.llm_token_rules[0].monthly_tokens == 500


def test_reservation_is_idempotent(monkeypatch):
    collection = MagicMock()
    collection.find_one.return_value = {
        "_id": "request-1",
        "state": "active",
        "reserved_tokens": 1200,
    }
    monkeypatch.setattr(usage_quotas, "reservations", collection)
    usage_collection = MagicMock()
    usage_collection.find_one.return_value = None
    monkeypatch.setattr(usage_quotas, "llm_usage", usage_collection)

    result = usage_quotas.reserve_llm_usage(
        "request-1",
        "team-1",
        "user-1",
        provider_id="provider-1",
        profile_id="profile-1",
        workload="chat",
        reserved_tokens=1200,
    )

    assert result["reserved_tokens"] == 1200
    update = collection.update_one.call_args.args[1]
    assert update["$setOnInsert"]["_id"] == "request-1"
    assert collection.update_one.call_args.kwargs["upsert"] is True


def test_duplicate_active_reservation_is_rejected(monkeypatch):
    collection = MagicMock()
    collection.update_one.return_value.upserted_id = None
    collection.find_one.return_value = {"_id": "request-1", "state": "active"}
    monkeypatch.setattr(usage_quotas, "reservations", collection)
    usage_collection = MagicMock()
    usage_collection.find_one.return_value = None
    monkeypatch.setattr(usage_quotas, "llm_usage", usage_collection)

    with pytest.raises(ValueError, match="already in progress"):
        usage_quotas.reserve_llm_usage(
            "request-1", "team-1", "user-1",
            provider_id="provider-1", profile_id="profile-1",
            workload="chat", reserved_tokens=100,
        )


def test_projected_usage_releases_reservation_when_limit_would_be_exceeded(monkeypatch):
    monkeypatch.setattr(usage_quotas, "get_quota_settings", lambda level, subject_id="": {
        "enabled": level == "system",
        "monthly_llm_tokens": 100,
    })
    monkeypatch.setattr(usage_quotas, "current_usage", lambda *_args: {
        "monthly_llm_tokens": 20,
        "monthly_document_pages": 0,
    })
    monkeypatch.setattr(usage_quotas, "reserve_llm_usage", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(usage_quotas, "current_reserved_tokens", lambda *_args, **_kwargs: 90)
    finish = MagicMock()
    monkeypatch.setattr(usage_quotas, "finish_llm_reservation", finish)
    monkeypatch.setattr(usage_quotas, "_audit", lambda *_args, **_kwargs: None)

    with pytest.raises(ValueError, match="for system"):
        usage_quotas.check_and_record_request(
            "team-1", "user-1", request_id="request-1", reserved_tokens=90
        )
    finish.assert_called_once_with("request-1", state="released")


def test_metering_failure_audit_requires_active_reservation(monkeypatch):
    collection = MagicMock()
    collection.find_one.return_value = {
        "_id": "request-1",
        "state": "completed",
        "provider_id": "provider-1",
        "reserved_tokens": 100,
    }
    collection.update_one.return_value.matched_count = 0
    monkeypatch.setattr(usage_quotas, "reservations", collection)
    audit = MagicMock()
    monkeypatch.setattr(usage_quotas, "_audit", audit)

    usage_quotas.finish_llm_reservation("request-1", state="metering_failed")

    audit.assert_not_called()


def test_quota_status_includes_reserved_tokens_and_warning(monkeypatch):
    monkeypatch.setattr(usage_quotas, "current_usage", lambda *_args: {
        "monthly_llm_tokens": 70,
        "monthly_document_pages": 0,
    })
    monkeypatch.setattr(usage_quotas, "current_reserved_tokens", lambda *_args, **_kwargs: 15)
    policy = UsageQuotaPolicy(enabled=True, monthly_llm_tokens=100)

    result = usage_quotas.quota_status(policy, "team-1", "")

    assert result[0]["used"] == 70
    assert result[0]["reserved"] == 15
    assert result[0]["percentage"] == 85.0
    assert result[0]["severity"] == "warning"
