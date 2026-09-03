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
