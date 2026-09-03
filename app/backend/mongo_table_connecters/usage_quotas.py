from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from core.usage_quotas import LLMTokenQuotaRule, UsageQuotaPolicy, effective_quota_policy
from mongo_table_connecters.mongo_connector import get_database


db = get_database()
settings = db["application_settings"]
llm_usage = db["users_usage"]
document_usage = db["document_processing_usage"]
request_windows = db["usage_quota_requests"]
reservations = db["usage_quota_reservations"]
audit_events = db["usage_quota_audit_events"]


def ensure_usage_quota_indexes() -> bool:
    try:
        request_windows.create_index("expires_at", expireAfterSeconds=0, name="quota_request_expiry")
        reservations.create_index("expires_at", expireAfterSeconds=0, name="quota_reservation_expiry")
        reservations.create_index(
            [("state", 1), ("team_id", 1), ("user_id", 1), ("expires_at", 1)],
            name="quota_active_reservations",
        )
        audit_events.create_index("expires_at", expireAfterSeconds=0, name="quota_audit_expiry")
        audit_events.create_index(
            [("level", 1), ("subject_id", 1), ("created_at", -1)],
            name="quota_audit_scope",
        )
        return True
    except PyMongoError:
        logging.warning("One or more usage quota indexes are unavailable", exc_info=True)
        return False


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


def _team_user_subject_id(team_id: str, user_id: str) -> str:
    return f"{team_id}:{user_id}"


def get_team_user_quota_settings(team_id: str, user_id: str) -> dict[str, Any] | None:
    return get_quota_settings("team_user", _team_user_subject_id(team_id, user_id))


def save_team_user_quota_settings(team_id: str, user_id: str, policy: object) -> dict[str, Any]:
    normalized = UsageQuotaPolicy.from_config(policy)
    # Team-member overrides intentionally replace only the Team's default
    # per-member LLM allowance. Other dimensions remain governed by their
    # System, Team, and legacy User policies.
    scoped = UsageQuotaPolicy(
        enabled=normalized.enabled,
        monthly_llm_tokens=normalized.monthly_llm_tokens,
    )
    return save_quota_settings(
        "team_user", _team_user_subject_id(team_id, user_id), scoped.serialize()
    )


def team_member_quota_policy(team_id: str, user_id: str) -> tuple[UsageQuotaPolicy | None, str]:
    if not team_id or not user_id:
        return None, ""
    override_raw = get_team_user_quota_settings(team_id, user_id)
    override = UsageQuotaPolicy.from_config(override_raw)
    if override_raw is not None and override.enabled:
        return override, "override"
    team_raw = get_quota_settings("team", team_id)
    team = UsageQuotaPolicy.from_config(team_raw)
    if team_raw is not None and team.enabled and team.monthly_llm_tokens_per_user:
        return UsageQuotaPolicy(
            enabled=True,
            monthly_llm_tokens=team.monthly_llm_tokens_per_user,
        ), "team_default"
    return None, ""


def effective_quota_settings(team_id: str, user_id: str) -> tuple[UsageQuotaPolicy, dict[str, Any]]:
    member_policy, member_source = team_member_quota_policy(team_id, user_id)
    configured = {
        "system": get_quota_settings("system"),
        "team": get_quota_settings("team", team_id) if team_id else None,
        "user": get_quota_settings("user", user_id) if user_id else None,
        "team_user": get_team_user_quota_settings(team_id, user_id) if team_id and user_id else None,
        "team_user_source": member_source,
    }
    policy = effective_quota_policy(
        UsageQuotaPolicy.from_config(configured["system"]) if configured["system"] is not None else None,
        UsageQuotaPolicy.from_config(configured["team"]) if configured["team"] is not None else None,
        UsageQuotaPolicy.from_config(configured["user"]) if configured["user"] is not None else None,
        member_policy,
    )
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


def _reservation_query(team_id: str, user_id: str) -> dict[str, Any]:
    query: dict[str, Any] = {
        "state": {"$in": ["active", "metering_failed"]},
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    }
    if team_id:
        query["team_id"] = team_id
    if user_id:
        query["user_id"] = user_id
    return query


def current_reserved_tokens(
    team_id: str,
    user_id: str,
    *,
    provider_id: str = "",
    profile_id: str = "",
    workload: str = "all",
) -> int:
    query = _reservation_query(team_id, user_id)
    if provider_id:
        query["provider_id"] = provider_id
    if profile_id:
        query["profile_id"] = profile_id
    if workload != "all":
        query["workload"] = workload
    return sum(
        max(0, int(item.get("reserved_tokens") or 0))
        for item in reservations.find(query, {"reserved_tokens": 1})
    )


def _audit(
    event_type: str,
    *,
    request_id: str,
    level: str,
    subject_id: str,
    provider_id: str,
    profile_id: str,
    workload: str,
    limit: int = 0,
    projected: int = 0,
    threshold: int = 0,
) -> None:
    if not request_id:
        return
    now = datetime.now(timezone.utc)
    identity = now.strftime("%Y-%m") if event_type == "quota_threshold" else request_id
    event_id = f"{event_type}:{identity}:{level}:{subject_id}:{provider_id}:{profile_id}:{workload}:{threshold}"
    try:
        audit_events.update_one(
            {"_id": event_id},
            {"$setOnInsert": {
                "event_type": event_type,
                "request_id": request_id,
                "level": level,
                "subject_id": subject_id,
                "provider_id": provider_id,
                "profile_id": profile_id,
                "workload": workload,
                "limit": limit,
                "projected": projected,
                "threshold": threshold,
                "created_at": now,
                "expires_at": now + timedelta(days=90),
            }},
            upsert=True,
        )
    except PyMongoError:
        logging.warning("Unable to persist usage quota audit event", exc_info=True)


def _record_thresholds(
    *,
    request_id: str,
    level: str,
    subject_id: str,
    provider_id: str,
    profile_id: str,
    workload: str,
    limit: int,
    projected: int,
) -> None:
    if not limit:
        return
    percentage = projected * 100 / limit
    for threshold in (80, 90, 100):
        if percentage >= threshold:
            _audit(
                "quota_threshold",
                request_id=request_id,
                level=level,
                subject_id=subject_id,
                provider_id=provider_id,
                profile_id=profile_id,
                workload=workload,
                limit=limit,
                projected=projected,
                threshold=threshold,
            )


def reserve_llm_usage(
    request_id: str,
    team_id: str,
    user_id: str,
    *,
    provider_id: str,
    profile_id: str,
    workload: str,
    reserved_tokens: int,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    if llm_usage.find_one({"_id": request_id}, {"_id": 1}):
        raise ValueError("This usage request has already been completed")
    document = {
        "_id": request_id,
        "team_id": team_id,
        "user_id": user_id,
        "provider_id": provider_id,
        "profile_id": profile_id,
        "workload": workload,
        "reserved_tokens": max(1, min(int(reserved_tokens), 1_000_000)),
        "state": "active",
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(minutes=15),
    }
    result = reservations.update_one({"_id": request_id}, {"$setOnInsert": document}, upsert=True)
    stored = reservations.find_one({"_id": request_id}) or document
    if result.upserted_id is None:
        raise ValueError("This usage request is already in progress or completed")
    if stored.get("state") != "active":
        raise ValueError("This usage request has already been completed")
    return stored


def finish_llm_reservation(request_id: str, *, state: str, actual_tokens: int = 0) -> None:
    if state not in {"completed", "released", "metering_failed"}:
        raise ValueError("Invalid usage reservation state")
    now = datetime.now(timezone.utc)
    existing = reservations.find_one({"_id": request_id}) or {}
    retention = timedelta(minutes=15) if state == "metering_failed" else timedelta(days=90)
    result = reservations.update_one(
        {"_id": request_id, "state": "active"},
        {"$set": {
            "state": state,
            "actual_tokens": max(0, int(actual_tokens)),
            "updated_at": now,
            "expires_at": now + retention,
        }},
    )
    if state == "metering_failed" and existing and result.matched_count:
        _audit(
            "metering_failed",
            request_id=request_id,
            level="system",
            subject_id="",
            provider_id=str(existing.get("provider_id") or ""),
            profile_id=str(existing.get("profile_id") or ""),
            workload=str(existing.get("workload") or ""),
            projected=max(0, int(existing.get("reserved_tokens") or 0)),
        )


def list_quota_audit_events(level: str, subject_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"level": level, "subject_id": subject_id}
    return list(audit_events.find(query).sort("created_at", -1).limit(max(1, min(limit, 100))))


def quota_status(policy: UsageQuotaPolicy, team_id: str, user_id: str) -> list[dict[str, Any]]:
    if not policy.enabled:
        return []
    usage = current_usage(team_id, user_id)
    rows: list[dict[str, Any]] = []

    def add(kind: str, label: str, used: int, reserved: int, limit: int) -> None:
        if not limit:
            return
        percentage = min(999.9, (used + reserved) * 100 / limit)
        severity = "exceeded" if percentage >= 100 else "critical" if percentage >= 90 else "warning" if percentage >= 80 else "normal"
        rows.append({
            "kind": kind,
            "label": label,
            "used": used,
            "reserved": reserved,
            "limit": limit,
            "percentage": round(percentage, 1),
            "severity": severity,
        })

    add(
        "llm_tokens",
        "Overall LLM tokens",
        usage["monthly_llm_tokens"],
        current_reserved_tokens(team_id, user_id),
        policy.monthly_llm_tokens,
    )
    add("document_pages", "Document pages", usage["monthly_document_pages"], 0, policy.monthly_document_pages)
    for rule in policy.llm_token_rules:
        if not rule.enabled:
            continue
        used = current_llm_rule_usage(team_id, user_id, rule)
        reserved = current_reserved_tokens(
            team_id,
            user_id,
            provider_id=rule.target_id if rule.dimension == "provider" else "",
            profile_id=rule.target_id if rule.dimension == "profile" else "",
            workload=rule.workload,
        )
        add("llm_token_rule", rule.target_label, used, reserved, rule.monthly_tokens)
    return rows


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
    member_policy, _source = team_member_quota_policy(team_id, user_id)
    if member_policy and member_policy.enabled:
        yield (
            "team_user",
            _team_user_subject_id(team_id, user_id),
            team_id,
            user_id,
            member_policy,
        )


def check_and_record_request(
    team_id: str,
    user_id: str,
    *,
    provider_id: str = "",
    profile_id: str = "",
    workload: str = "chat",
    request_id: str = "",
    reserved_tokens: int = 0,
) -> tuple[UsageQuotaPolicy, dict[str, int]]:
    if request_id:
        reserve_llm_usage(
            request_id,
            team_id,
            user_id,
            provider_id=provider_id,
            profile_id=profile_id,
            workload=workload,
            reserved_tokens=reserved_tokens,
        )
    effective, _ = effective_quota_settings(team_id, user_id)
    usage = current_usage(team_id, user_id)
    try:
        for level, subject_id, usage_team_id, usage_user_id, policy in _configured_policies(team_id, user_id):
            scoped_usage = current_usage(usage_team_id, usage_user_id)
            reserved = current_reserved_tokens(usage_team_id, usage_user_id) if request_id else 0
            projected = scoped_usage["monthly_llm_tokens"] + reserved
            _record_thresholds(
                request_id=request_id,
                level=level,
                subject_id=subject_id,
                provider_id=provider_id,
                profile_id=profile_id,
                workload=workload,
                limit=policy.monthly_llm_tokens,
                projected=projected,
            )
            if policy.monthly_llm_tokens and (
                projected > policy.monthly_llm_tokens
                if request_id
                else projected >= policy.monthly_llm_tokens
            ):
                _audit("quota_blocked", request_id=request_id, level=level, subject_id=subject_id,
                       provider_id=provider_id, profile_id=profile_id, workload=workload,
                       limit=policy.monthly_llm_tokens, projected=projected)
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
                rule_used = current_llm_rule_usage(usage_team_id, usage_user_id, rule)
                rule_reserved = (
                    current_reserved_tokens(
                        usage_team_id,
                        usage_user_id,
                        provider_id=provider_id if rule.dimension == "provider" else "",
                        profile_id=profile_id if rule.dimension == "profile" else "",
                        workload=rule.workload,
                    )
                    if request_id
                    else 0
                )
                rule_projected = rule_used + rule_reserved
                _record_thresholds(
                    request_id=request_id, level=level, subject_id=subject_id,
                    provider_id=provider_id, profile_id=profile_id, workload=workload,
                    limit=rule.monthly_tokens, projected=rule_projected,
                )
                if (
                    rule_projected > rule.monthly_tokens
                    if request_id
                    else rule_projected >= rule.monthly_tokens
                ):
                    _audit("quota_blocked", request_id=request_id, level=level, subject_id=subject_id,
                           provider_id=provider_id, profile_id=profile_id, workload=workload,
                           limit=rule.monthly_tokens, projected=rule_projected)
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
                _audit("quota_blocked", request_id=request_id, level=level, subject_id=subject_id,
                       provider_id=provider_id, profile_id=profile_id, workload=workload,
                       limit=policy.llm_requests_per_minute, projected=int((counter or {}).get("count") or 0))
                raise ValueError(f"LLM requests-per-minute quota has been reached for {level}")
    except Exception:
        if request_id:
            finish_llm_reservation(request_id, state="released")
        raise
    return effective, usage


def check_document_quota(team_id: str, user_id: str) -> tuple[UsageQuotaPolicy, dict[str, int]]:
    effective, _ = effective_quota_settings(team_id, user_id)
    usage = current_usage(team_id, user_id)
    for level, _subject_id, usage_team_id, usage_user_id, policy in _configured_policies(team_id, user_id):
        scoped_usage = current_usage(usage_team_id, usage_user_id)
        if policy.monthly_document_pages and scoped_usage["monthly_document_pages"] >= policy.monthly_document_pages:
            raise ValueError(f"Monthly document page quota has been reached for {level}")
    return effective, usage
