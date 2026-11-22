from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from mongo_table_connecters.mongo_connector import get_database
from mongo_table_connecters.usage_pricing import estimate_call_cost, list_price_profiles

db = get_database()
llm_collection = db["users_usage"]
document_collection = db["document_processing_usage"]
legacy_document_collection = db["doc_intel_usage"]


def _integer(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _id_and_name(value: Any) -> tuple[str, str]:
    if not isinstance(value, dict):
        return "", ""
    return str(value.get("_id") or ""), str(value.get("name") or "")


def _bucket_key(value: Any, bucket: str) -> str:
    if not isinstance(value, datetime):
        return "unknown"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if bucket == "month":
        return value.strftime("%Y-%m")
    if bucket == "week":
        year, week, _ = value.isocalendar()
        return f"{year}-W{week:02d}"
    return value.strftime("%Y-%m-%d")


def _calls(record: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    result = [item for item in (record.get("model_calls") or []) if isinstance(item, dict)]
    if result:
        return result
    return [{
        "model": metadata.get("model") or "Unknown",
        "provider": metadata.get("provider") or "Unknown",
        "prompt_tokens": record.get("tokens_prompt_sum"),
        "completion_tokens": record.get("tokens_completion_sum"),
        "reasoning_tokens": record.get("tokens_reasoning_sum"),
        "total_tokens": record.get("tokens_total_sum"),
    }]


def _add_tokens(target: dict[str, int], call: dict[str, Any]) -> None:
    prompt = _integer(call.get("prompt_tokens"))
    completion = _integer(call.get("completion_tokens"))
    reasoning = _integer(call.get("reasoning_tokens"))
    total = _integer(call.get("total_tokens")) or prompt + completion + reasoning
    target["input_tokens"] += prompt
    target["output_tokens"] += completion
    target["reasoning_tokens"] += reasoning
    target["total_tokens"] += total


def _add_cost(target: dict[str, Any], call: dict[str, Any]) -> None:
    cost = call.get("_cost") if isinstance(call.get("_cost"), dict) else {}
    tokens = _integer(call.get("total_tokens")) or _integer(call.get("prompt_tokens")) + _integer(call.get("completion_tokens"))
    value = cost.get("estimated_cost_usd")
    if value is None:
        target["unpriced_tokens"] += tokens
        target["unpriced_model_calls"] += 1
    else:
        target["estimated_cost_usd"] += float(value)
        target["priced_tokens"] += tokens
        target["priced_model_calls"] += 1


def _finalize_cost(target: dict[str, Any]) -> None:
    target["estimated_cost_usd"] = round(float(target.get("estimated_cost_usd") or 0), 8)
    denominator = int(target.get("priced_tokens") or 0) + int(target.get("unpriced_tokens") or 0)
    target["pricing_coverage_percent"] = round(int(target.get("priced_tokens") or 0) * 100 / denominator, 2) if denominator else 0


def _cost_fields() -> dict[str, int | float]:
    return {
        "estimated_cost_usd": 0.0,
        "priced_tokens": 0,
        "unpriced_tokens": 0,
        "priced_model_calls": 0,
        "unpriced_model_calls": 0,
    }


def _breakdown_rows(items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items.values(), key=lambda item: (-item["total_tokens"], item["label"].lower()))


def _document_breakdown_rows(items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items.values(), key=lambda item: (-item["processed_pages"], -item["documents"], item["label"].lower()))


def _route_label(route_type: str) -> str:
    return {
        "built_in": "Built-in Providers",
        "external_gateway": "External AI Gateway",
        "direct_development": "Direct Development",
    }.get(route_type, "Unknown / legacy")


def aggregate_usage(
    llm_records: Iterable[dict[str, Any]],
    document_records: Iterable[dict[str, Any]],
    *,
    bucket: str = "day",
    agent_id: str = "",
    provider: str = "",
    model: str = "",
    profile_id: str = "",
    route_type: str = "",
    file_type: str = "",
    document_scope: str = "",
    team_labels: dict[str, str] | None = None,
    price_profiles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    overview = {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "documents": 0,
        "processed_pages": 0,
        "processing_duration_ms": 0,
        **_cost_fields(),
    }
    timeline: dict[str, dict[str, Any]] = {}
    breakdowns: dict[str, dict[str, dict[str, Any]]] = {
        key: {} for key in ("models", "providers", "routes", "agents", "teams", "users")
    }
    options: dict[str, dict[str, str]] = {
        key: {} for key in ("models", "providers", "routes", "agents", "teams", "users")
    }
    document_breakdowns: dict[str, dict[str, dict[str, Any]]] = {
        key: {} for key in ("providers", "profiles", "file_types", "scopes", "teams", "users")
    }
    document_options: dict[str, dict[str, str]] = {
        key: {} for key in ("providers", "profiles", "file_types", "scopes", "teams", "users")
    }
    team_labels = team_labels or {}
    price_profiles = price_profiles or []

    def add_breakdown(kind: str, key: str, label: str, calls: list[dict[str, Any]]) -> None:
        normalized_key = key or "unknown"
        normalized_label = label or "Unknown"
        if normalized_key != "unknown":
            options[kind][normalized_key] = normalized_label
        row = breakdowns[kind].setdefault(normalized_key, {
            "key": normalized_key,
            "label": normalized_label,
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
            **_cost_fields(),
        })
        row["requests"] += 1
        for call in calls:
            _add_tokens(row, call)
            _add_cost(row, call)

    def add_document_breakdown(kind: str, key: str, label: str, *, pages: int, duration: int) -> None:
        normalized_key = key or "unknown"
        normalized_label = label or "Unknown / legacy"
        row = document_breakdowns[kind].setdefault(normalized_key, {
            "key": normalized_key,
            "label": normalized_label,
            "documents": 0,
            "processed_pages": 0,
            "processing_duration_ms": 0,
        })
        row["documents"] += 1
        row["processed_pages"] += pages
        row["processing_duration_ms"] += duration

    for record in llm_records:
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        if agent_id and str(metadata.get("agent_id") or "") != agent_id:
            continue
        record_route_type = str(metadata.get("route_type") or "unknown")
        if route_type and record_route_type != route_type:
            continue
        matching_calls = []
        for call in _calls(record):
            call_provider = str(call.get("provider") or metadata.get("provider") or "Unknown")
            call_model = str(call.get("model") or metadata.get("model") or "Unknown")
            if provider and call_provider != provider:
                continue
            if model and call_model != model:
                continue
            normalized_call = {**call, "provider": call_provider, "model": call_model}
            normalized_call["_cost"] = estimate_call_cost(
                normalized_call, metadata, record.get("create_at"), profiles=price_profiles
            )
            matching_calls.append(normalized_call)
        if not matching_calls:
            continue

        overview["requests"] += 1
        for call in matching_calls:
            _add_tokens(overview, call)
            _add_cost(overview, call)
        period = _bucket_key(record.get("create_at"), bucket)
        point = timeline.setdefault(period, {
            "period": period,
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
            "documents": 0,
            "processed_pages": 0,
            **_cost_fields(),
        })
        point["requests"] += 1
        for call in matching_calls:
            _add_tokens(point, call)
            _add_cost(point, call)

        calls_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
        calls_by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for call in matching_calls:
            calls_by_model[str(call["model"])].append(call)
            calls_by_provider[str(call["provider"])].append(call)
        for label, calls in calls_by_model.items():
            add_breakdown("models", label, label, calls)
        for label, calls in calls_by_provider.items():
            add_breakdown("providers", label, label, calls)
        team_id, team_name = _id_and_name(record.get("group"))
        user_id, user_name = _id_and_name(record.get("user"))
        add_breakdown("teams", team_id, team_name or team_id or "No team", matching_calls)
        add_breakdown("users", user_id, user_name or user_id, matching_calls)
        add_breakdown(
            "agents",
            str(metadata.get("agent_id") or "unknown"),
            str(metadata.get("agent_name") or "Unknown"),
            matching_calls,
        )
        add_breakdown(
            "routes",
            record_route_type,
            _route_label(record_route_type),
            matching_calls,
        )

    for record in document_records:
        record_provider = str(record.get("provider_name") or "Azure Document Intelligence")
        record_profile_id = str(record.get("profile_id") or record.get("profile_name") or "unknown")
        record_profile_name = str(record.get("profile_name") or "Unknown / legacy")
        record_file_type = str(record.get("file_type") or "unknown").lower().lstrip(".")
        record_scope = str(record.get("scope") or record.get("upload_type") or "legacy").lower()
        record_user_id, record_user_name = _id_and_name(record.get("user"))
        record_team_id, embedded_team_name = _id_and_name(record.get("team"))
        if not record_team_id and isinstance(record.get("team"), str):
            record_team_id = str(record.get("team") or "")
        record_team_name = embedded_team_name or team_labels.get(record_team_id, "") or record_team_id or "No team"

        document_options["providers"][record_provider] = record_provider
        if record_profile_id != "unknown":
            document_options["profiles"][record_profile_id] = record_profile_name
        if record_file_type != "unknown":
            document_options["file_types"][record_file_type] = record_file_type.upper()
        document_options["scopes"][record_scope] = record_scope.title()
        if record_team_id:
            document_options["teams"][record_team_id] = record_team_name
        if record_user_id:
            document_options["users"][record_user_id] = record_user_name or record_user_id

        if provider and record_provider != provider:
            continue
        if profile_id and record_profile_id != profile_id:
            continue
        if file_type and record_file_type != file_type.lower().lstrip("."):
            continue
        if document_scope and record_scope != document_scope.lower():
            continue
        pages = _integer(record.get("page_count", record.get("ocr_pages")))
        duration = _integer(record.get("duration_ms"))
        overview["documents"] += 1
        overview["processed_pages"] += pages
        overview["processing_duration_ms"] += duration
        period = _bucket_key(record.get("create_at"), bucket)
        point = timeline.setdefault(period, {
            "period": period,
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
            "documents": 0,
            "processed_pages": 0,
            **_cost_fields(),
        })
        point["documents"] += 1
        point["processed_pages"] += pages
        add_document_breakdown("providers", record_provider, record_provider, pages=pages, duration=duration)
        add_document_breakdown("profiles", record_profile_id, record_profile_name, pages=pages, duration=duration)
        add_document_breakdown("file_types", record_file_type, record_file_type.upper(), pages=pages, duration=duration)
        add_document_breakdown("scopes", record_scope, record_scope.title(), pages=pages, duration=duration)
        add_document_breakdown("teams", record_team_id, record_team_name, pages=pages, duration=duration)
        add_document_breakdown(
            "users",
            record_user_id,
            record_user_name or record_user_id or "Unknown / legacy",
            pages=pages,
            duration=duration,
        )

    for target in [overview, *timeline.values()]:
        _finalize_cost(target)
    for rows in breakdowns.values():
        for target in rows.values():
            _finalize_cost(target)

    return {
        "overview": overview,
        "timeline": [timeline[key] for key in sorted(timeline)],
        "breakdowns": {kind: _breakdown_rows(rows) for kind, rows in breakdowns.items()},
        "document_breakdowns": {kind: _document_breakdown_rows(rows) for kind, rows in document_breakdowns.items()},
        "document_providers": _document_breakdown_rows(document_breakdowns["providers"]),
        "filter_options": {
            kind: [{"value": key, "label": label} for key, label in sorted(values.items(), key=lambda item: item[1].lower())]
            for kind, values in options.items()
        },
        "document_filter_options": {
            kind: [{"value": key, "label": label} for key, label in sorted(values.items(), key=lambda item: item[1].lower())]
            for kind, values in document_options.items()
        },
    }


def get_usage_analytics(
    query: dict[str, Any],
    *,
    bucket: str,
    agent_id: str = "",
    provider: str = "",
    model: str = "",
    profile_id: str = "",
    route_type: str = "",
    file_type: str = "",
    document_scope: str = "",
) -> dict[str, Any]:
    llm_records = list(llm_collection.find(query).sort("create_at", 1))
    document_query = dict(query)
    if "group._id" in document_query:
        document_query["team._id"] = document_query.pop("group._id")
    document_records = list(document_collection.find(document_query).sort("create_at", 1))
    # Legacy Azure Document Intelligence rows remain visible during migration.
    legacy_query = dict(query)
    # Legacy rows stored an email instead of an immutable application user ID,
    # so they cannot safely participate in user-scoped reports.
    include_legacy = "user._id" not in legacy_query
    legacy_query.pop("user._id", None)
    if "group._id" in legacy_query:
        legacy_query["team"] = legacy_query.pop("group._id")
    if include_legacy:
        document_records.extend(legacy_document_collection.find(legacy_query).sort("create_at", 1))
    team_ids: set[str] = set()
    for record in document_records:
        team = record.get("team")
        if isinstance(team, dict) and team.get("_id"):
            team_ids.add(str(team["_id"]))
        elif isinstance(team, str) and team:
            team_ids.add(team)
    team_labels = {
        str(item.get("_id")): str(item.get("name") or item.get("_id"))
        for item in db["teams"].find({"_id": {"$in": list(team_ids)}, "delete_at": None}, {"_id": 1, "name": 1})
    } if team_ids else {}
    return aggregate_usage(
        llm_records,
        document_records,
        bucket=bucket,
        agent_id=agent_id,
        provider=provider,
        model=model,
        profile_id=profile_id,
        route_type=route_type,
        file_type=file_type,
        document_scope=document_scope,
        team_labels=team_labels,
        price_profiles=list_price_profiles(),
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value or "")
    return f"'{text}" if text[:1] in {"=", "+", "-", "@"} else text


def usage_cost_csv(
    query: dict[str, Any],
    *,
    agent_id: str = "",
    provider: str = "",
    model: str = "",
    route_type: str = "",
) -> str:
    output = io.StringIO()
    fields = [
        "timestamp", "usage_event_id", "request_mode", "team_id", "team_name",
        "user_id", "user_name", "agent_id", "agent_name", "provider",
        "provider_id", "model", "route_type", "prompt_tokens",
        "cached_input_tokens", "completion_tokens", "reasoning_tokens",
        "total_tokens", "pricing_status", "estimated_cost_usd",
        "input_cost_usd", "cached_input_cost_usd", "output_cost_usd",
        "price_profile_id", "price_profile_name", "pricing_basis",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    price_profiles = list_price_profiles()
    for record in llm_collection.find(query).sort("create_at", 1):
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        if agent_id and str(metadata.get("agent_id") or "") != agent_id:
            continue
        record_route = str(metadata.get("route_type") or "unknown")
        if route_type and record_route != route_type:
            continue
        team = record.get("group") if isinstance(record.get("group"), dict) else {}
        user = record.get("user") if isinstance(record.get("user"), dict) else {}
        for call in _calls(record):
            call_provider = str(call.get("provider") or metadata.get("provider") or "Unknown")
            call_model = str(call.get("model") or metadata.get("model") or "Unknown")
            if provider and call_provider != provider:
                continue
            if model and call_model != model:
                continue
            normalized_call = {**call, "provider": call_provider, "model": call_model}
            cost = estimate_call_cost(
                normalized_call, metadata, record.get("create_at"), profiles=price_profiles
            )
            row = {
                "timestamp": record.get("create_at"),
                "usage_event_id": record.get("_id"),
                "request_mode": metadata.get("request_mode"),
                "team_id": team.get("_id"),
                "team_name": team.get("name"),
                "user_id": user.get("_id"),
                "user_name": user.get("name"),
                "agent_id": metadata.get("agent_id"),
                "agent_name": metadata.get("agent_name"),
                "provider": call_provider,
                "provider_id": call.get("provider_id") or metadata.get("provider_id"),
                "model": call_model,
                "route_type": record_route,
                "prompt_tokens": _integer(call.get("prompt_tokens")),
                "cached_input_tokens": _integer(call.get("cached_input_tokens")),
                "completion_tokens": _integer(call.get("completion_tokens")),
                "reasoning_tokens": _integer(call.get("reasoning_tokens")),
                "total_tokens": _integer(call.get("total_tokens")) or (
                    _integer(call.get("prompt_tokens"))
                    + _integer(call.get("completion_tokens"))
                    + _integer(call.get("reasoning_tokens"))
                ),
                "pricing_status": cost.get("status"),
                "estimated_cost_usd": cost.get("estimated_cost_usd"),
                "input_cost_usd": cost.get("input_cost_usd"),
                "cached_input_cost_usd": cost.get("cached_input_cost_usd"),
                "output_cost_usd": cost.get("output_cost_usd"),
                "price_profile_id": cost.get("price_profile_id"),
                "price_profile_name": cost.get("price_profile_name"),
                "pricing_basis": cost.get("pricing_basis"),
            }
            writer.writerow({key: _csv_value(value) for key, value in row.items()})
    return output.getvalue()
