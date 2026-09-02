from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

from mongo_table_connecters.mongo_connector import get_database


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


def _breakdown_rows(items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items.values(), key=lambda item: (-item["total_tokens"], item["label"].lower()))


def aggregate_usage(
    llm_records: Iterable[dict[str, Any]],
    document_records: Iterable[dict[str, Any]],
    *,
    bucket: str = "day",
    agent_id: str = "",
    provider: str = "",
    model: str = "",
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
    }
    timeline: dict[str, dict[str, Any]] = {}
    breakdowns: dict[str, dict[str, dict[str, Any]]] = {
        key: {} for key in ("models", "providers", "agents", "teams", "users")
    }
    options: dict[str, dict[str, str]] = {
        key: {} for key in ("models", "providers", "agents", "teams", "users")
    }

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
        })
        row["requests"] += 1
        for call in calls:
            _add_tokens(row, call)

    for record in llm_records:
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        if agent_id and str(metadata.get("agent_id") or "") != agent_id:
            continue
        matching_calls = []
        for call in _calls(record):
            call_provider = str(call.get("provider") or metadata.get("provider") or "Unknown")
            call_model = str(call.get("model") or metadata.get("model") or "Unknown")
            if provider and call_provider != provider:
                continue
            if model and call_model != model:
                continue
            matching_calls.append({**call, "provider": call_provider, "model": call_model})
        if not matching_calls:
            continue

        overview["requests"] += 1
        for call in matching_calls:
            _add_tokens(overview, call)
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
        })
        point["requests"] += 1
        for call in matching_calls:
            _add_tokens(point, call)

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

    document_providers: dict[str, dict[str, Any]] = {}
    for record in document_records:
        record_provider = str(record.get("provider_name") or "Azure Document Intelligence")
        options["providers"][record_provider] = record_provider
        if provider and record_provider != provider:
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
        })
        point["documents"] += 1
        point["processed_pages"] += pages
        row = document_providers.setdefault(record_provider, {
            "key": record_provider,
            "label": record_provider,
            "documents": 0,
            "processed_pages": 0,
            "processing_duration_ms": 0,
        })
        row["documents"] += 1
        row["processed_pages"] += pages
        row["processing_duration_ms"] += duration

    return {
        "overview": overview,
        "timeline": [timeline[key] for key in sorted(timeline)],
        "breakdowns": {kind: _breakdown_rows(rows) for kind, rows in breakdowns.items()},
        "document_providers": sorted(
            document_providers.values(), key=lambda item: (-item["processed_pages"], item["label"].lower())
        ),
        "filter_options": {
            kind: [{"value": key, "label": label} for key, label in sorted(values.items(), key=lambda item: item[1].lower())]
            for kind, values in options.items()
        },
    }


def get_usage_analytics(
    query: dict[str, Any],
    *,
    bucket: str,
    agent_id: str = "",
    provider: str = "",
    model: str = "",
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
    return aggregate_usage(
        llm_records,
        document_records,
        bucket=bucket,
        agent_id=agent_id,
        provider=provider,
        model=model,
    )
