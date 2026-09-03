from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from pymongo import ReturnDocument

from core.usage_quotas import LLMTokenQuotaRule, UsageQuotaPolicy, effective_quota_policy
from mongo_table_connecters.mongo_connector import get_database


db = get_database()
settings = db["application_settings"]
llm_usage = db["users_usage"]
document_usage = db["document_processing_usage"]
request_windows = db["usage_quota_requests"]


def _settings_id(level: str, subject_id: str = "") -> str:
    if level == "system":
        return "usage-quota:system"
    return f"usage-quota:{level}:{subject_id}"


def get_quota_settings(level: str, subject_id: str = "") -> dict[str, Any] | None:
    item = settings.find_one({"_id": _settings_id(level, subject_id)})
    return dict(item.get("policy") or {}) if item else None


def save_quota_settings(level: str, subject_id: str, policy: object) -> dict[str, Any]:
    normalized = UsageQuotaPolicy.from_config(policy).serialize()
    now = datetime.now(timezone.utc)
    settings.update_one(
        {"_id": _settings_id(level, subject_id)},
        {"$set": {"policy": normalized, "level": level, "subject_id": subject_id, "updated_at": now},
         "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return normalized


def effective_quota_settings(team_id: str, user_id: str) -> tuple[UsageQuotaPolicy, dict[str, Any]]:
    configured = {
        "system": get_quota_settings("system"),
        "team": get_quota_settings("team", team_id) if team_id else None,
        "user": get_quota_settings("user", user_id) if user_id else None,
    }
    policy = effective_quota_policy(*(
        UsageQuotaPolicy.from_config(value) if value is not None else None
        for value in configured.values()
    ))
    return policy, configured


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def current_usage(team_id: str, user_id: str) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    since = _month_start(now)
    llm_query: dict[str, Any] = {"create_at": {"$gte": since}, "delete_at": None}
    doc_query: dict[str, Any] = {"create_at": {"$gte": since}, "delete_at": None}
    if team_id:
        llm_query["group._id"] = team_id
        doc_query["team._id"] = team_id
    if user_id:
        llm_query["user._id"] = user_id
        doc_query["user._id"] = user_id
    tokens = sum(max(0, int(item.get("tokens_total_sum") or 0)) for item in llm_usage.find(llm_query, {"tokens_total_sum": 1}))
    pages = sum(max(0, int(item.get("page_count") or 0)) for item in document_usage.find(doc_query, {"page_count": 1}))
    return {"monthly_llm_tokens": tokens, "monthly_document_pages": pages}


def current_llm_rule_usage(
    team_id: str,
    user_id: str,
    rule: LLMTokenQuotaRule,
) -> int:
    query: dict[str, Any] = {
        "create_at": {"$gte": _month_start(datetime.now(timezone.utc))},
        "delete_at": None,
    }
    if team_id:
        query["group._id"] = team_id
    if user_id:
        query["user._id"] = user_id
    query[f"metadata.{rule.dimension}_id"] = rule.target_id
    if rule.workload != "all":
        query["metadata.workload"] = rule.workload
    return sum(
        max(0, int(item.get("tokens_total_sum") or 0))
        for item in llm_usage.find(query, {"tokens_total_sum": 1})
    )


def current_llm_rule_usages(
    policy: UsageQuotaPolicy, team_id: str, user_id: str
) -> list[dict[str, Any]]:
    return [
        {
            "dimension": rule.dimension,
            "target_id": rule.target_id,
            "workload": rule.workload,
            "monthly_tokens": current_llm_rule_usage(team_id, user_id, rule),
        }
        for rule in policy.llm_token_rules
    ]


def _configured_policies(team_id: str, user_id: str):
    subjects = [("system", "", "", "")]
    if team_id:
        subjects.append(("team", team_id, team_id, ""))
    if user_id:
        subjects.append(("user", user_id, "", user_id))
    for level, subject_id, usage_team_id, usage_user_id in subjects:
        raw = get_quota_settings(level, subject_id)
        policy = UsageQuotaPolicy.from_config(raw)
        if raw is not None and policy.enabled:
            yield level, subject_id, usage_team_id, usage_user_id, policy


def check_and_record_request(
    team_id: str,
    user_id: str,
    *,
    provider_id: str = "",
    profile_id: str = "",
    workload: str = "chat",
) -> tuple[UsageQuotaPolicy, dict[str, int]]:
    effective, _ = effective_quota_settings(team_id, user_id)
    usage = current_usage(team_id, user_id)
    for level, subject_id, usage_team_id, usage_user_id, policy in _configured_policies(team_id, user_id):
        scoped_usage = current_usage(usage_team_id, usage_user_id)
        if policy.monthly_llm_tokens and scoped_usage["monthly_llm_tokens"] >= policy.monthly_llm_tokens:
            raise ValueError(f"Monthly LLM token quota has been reached for {level}")
        for rule in policy.llm_token_rules:
            target = provider_id if rule.dimension == "provider" else profile_id
            if (
                not rule.enabled
                or not rule.monthly_tokens
                or target != rule.target_id
                or rule.workload not in {"all", workload}
            ):
                continue
            if current_llm_rule_usage(usage_team_id, usage_user_id, rule) >= rule.monthly_tokens:
                raise ValueError(
                    f"Monthly LLM token quota has been reached for {rule.target_label} ({level})"
                )
        if not policy.llm_requests_per_minute:
            continue
        now = datetime.now(timezone.utc)
        window = now.replace(second=0, microsecond=0)
        key = f"{level}:{subject_id}:{window.isoformat()}"
        counter = request_windows.find_one_and_update(
            {"_id": key},
            {
                "$inc": {"count": 1},
                "$setOnInsert": {
                    "level": level,
                    "subject_id": subject_id,
                    "created_at": now,
                    "expires_at": window + timedelta(minutes=2),
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if int((counter or {}).get("count") or 0) > policy.llm_requests_per_minute:
            raise ValueError(f"LLM requests-per-minute quota has been reached for {level}")
    return effective, usage


def check_document_quota(team_id: str, user_id: str) -> tuple[UsageQuotaPolicy, dict[str, int]]:
    effective, _ = effective_quota_settings(team_id, user_id)
    usage = current_usage(team_id, user_id)
    for level, _subject_id, usage_team_id, usage_user_id, policy in _configured_policies(team_id, user_id):
        scoped_usage = current_usage(usage_team_id, usage_user_id)
        if policy.monthly_document_pages and scoped_usage["monthly_document_pages"] >= policy.monthly_document_pages:
            raise ValueError(f"Monthly document page quota has been reached for {level}")
    return effective, usage
