from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any

from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["llm_price_catalog"]

MATCH_FIELDS = ("provider", "provider_id", "model", "profile_id", "route_type")


def _number(value: Any, field: str, *, minimum: float = 0, maximum: float = 1_000_000_000) -> float:
    try:
        result = float(value or 0)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be numeric") from error
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return result


def _date(value: Any, field: str, *, required: bool = False) -> datetime | None:
    if value in (None, ""):
        if required:
            raise ValueError(f"{field} is required")
        return None
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{field} must be an ISO-8601 date") from error
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _local_tco(payload: dict[str, Any]) -> dict[str, float]:
    tco = payload.get("local_tco") if isinstance(payload.get("local_tco"), dict) else {}
    purchase = _number(tco.get("hardware_purchase_usd"), "hardware_purchase_usd")
    residual = _number(tco.get("residual_value_usd"), "residual_value_usd")
    if residual > purchase:
        raise ValueError("residual_value_usd cannot exceed hardware_purchase_usd")
    life_years = _number(tco.get("useful_life_years", 3), "useful_life_years", minimum=0.1, maximum=20)
    maintenance = _number(tco.get("annual_maintenance_usd"), "annual_maintenance_usd")
    operations = _number(tco.get("annual_operations_usd"), "annual_operations_usd")
    power_kw = _number(tco.get("average_power_kw"), "average_power_kw", maximum=10_000)
    pue = _number(tco.get("pue", 1), "pue", minimum=1, maximum=5)
    electricity = _number(tco.get("electricity_usd_per_kwh"), "electricity_usd_per_kwh", maximum=100)
    cloud_hourly = _number(tco.get("cloud_gpu_usd_per_hour"), "cloud_gpu_usd_per_hour", maximum=1_000_000)
    throughput = _number(tco.get("aggregate_tokens_per_second"), "aggregate_tokens_per_second", minimum=0.000001)
    utilization = _number(tco.get("utilization", 0.5), "utilization", minimum=0.000001, maximum=1)
    hardware_hourly = (purchase - residual) / (life_years * 365 * 24)
    maintenance_hourly = (maintenance + operations) / (365 * 24)
    energy_hourly = power_kw * pue * electricity
    loaded_hourly = hardware_hourly + maintenance_hourly + energy_hourly + cloud_hourly
    per_million = loaded_hourly / (throughput * 3600 * utilization) * 1_000_000
    return {
        "hardware_purchase_usd": purchase,
        "residual_value_usd": residual,
        "useful_life_years": life_years,
        "annual_maintenance_usd": maintenance,
        "annual_operations_usd": operations,
        "average_power_kw": power_kw,
        "pue": pue,
        "electricity_usd_per_kwh": electricity,
        "cloud_gpu_usd_per_hour": cloud_hourly,
        "aggregate_tokens_per_second": throughput,
        "utilization": utilization,
        "loaded_cost_usd_per_hour": round(loaded_hourly, 8),
        "blended_usd_per_million_tokens": round(per_million, 8),
    }


def normalize_price_profile(payload: dict[str, Any], *, actor_id: str) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name or len(name) > 120:
        raise ValueError("name must contain 1 to 120 characters")
    pricing_type = str(payload.get("pricing_type") or "token").strip().lower()
    if pricing_type not in {"token", "local_tco"}:
        raise ValueError("pricing_type must be token or local_tco")
    effective_from = _date(payload.get("effective_from"), "effective_from", required=True)
    effective_to = _date(payload.get("effective_to"), "effective_to")
    if effective_to and effective_to <= effective_from:
        raise ValueError("effective_to must be later than effective_from")
    match = {key: str(payload.get(key) or "").strip()[:200] for key in MATCH_FIELDS}
    if not any(match.values()):
        raise ValueError("At least one provider, provider_id, model, profile_id, or route_type match is required")
    now = datetime.now(timezone.utc)
    document: dict[str, Any] = {
        "_id": str(uuid.uuid4()),
        "schema_version": 1,
        "name": name,
        "pricing_type": pricing_type,
        **match,
        "currency": "USD",
        "source_type": str(payload.get("source_type") or ("local_tco" if pricing_type == "local_tco" else "manual"))[:40],
        "source_reference": str(payload.get("source_reference") or "").strip()[:500],
        "effective_from": effective_from,
        "effective_to": effective_to,
        "enabled": True,
        "created_at": now,
        "created_by": actor_id,
        "retired_at": None,
    }
    if pricing_type == "local_tco":
        document["local_tco"] = _local_tco(payload)
        document["input_usd_per_million"] = 0.0
        document["cached_input_usd_per_million"] = 0.0
        document["output_usd_per_million"] = 0.0
    else:
        document["input_usd_per_million"] = _number(payload.get("input_usd_per_million"), "input_usd_per_million")
        document["cached_input_usd_per_million"] = _number(
            payload.get("cached_input_usd_per_million"), "cached_input_usd_per_million"
        )
        document["output_usd_per_million"] = _number(payload.get("output_usd_per_million"), "output_usd_per_million")
    return document


def ensure_usage_pricing_indexes() -> None:
    collection.create_index([("enabled", 1), ("effective_from", -1)], name="usage_price_effective")
    collection.create_index([("provider", 1), ("model", 1), ("route_type", 1)], name="usage_price_match")


def create_price_profile(payload: dict[str, Any], *, actor_id: str) -> dict[str, Any]:
    document = normalize_price_profile(payload, actor_id=actor_id)
    collection.insert_one(document)
    return document


def list_price_profiles() -> list[dict[str, Any]]:
    return list(collection.find({}).sort([("enabled", -1), ("effective_from", -1), ("created_at", -1)]))


def retire_price_profile(profile_id: str, *, actor_id: str) -> bool:
    now = datetime.now(timezone.utc)
    current = collection.find_one({"_id": profile_id, "enabled": True}, {"effective_to": 1})
    if not current:
        return False
    existing_end = current.get("effective_to")
    effective_to = existing_end if isinstance(existing_end, datetime) and existing_end < now else now
    result = collection.update_one(
        {"_id": profile_id, "enabled": True},
        {"$set": {
            "enabled": False,
            "effective_to": effective_to,
            "retired_at": now,
            "retired_by": actor_id,
        }},
    )
    return result.modified_count == 1


def serialize_price_profile(document: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in document.items()
        if key not in {"created_by", "retired_by"}
    }


def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


def estimate_call_cost(
    call: dict[str, Any],
    metadata: dict[str, Any],
    occurred_at: datetime | None,
    *,
    profiles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    when = occurred_at if isinstance(occurred_at, datetime) else datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    values = {
        "provider": call.get("provider") or metadata.get("provider"),
        "provider_id": call.get("provider_id") or metadata.get("provider_id"),
        "model": call.get("model") or metadata.get("model"),
        "profile_id": call.get("profile_id") or metadata.get("profile_id"),
        "route_type": call.get("route_type") or metadata.get("route_type"),
    }
    candidates = []
    source_profiles = profiles if profiles is not None else list(collection.find({"effective_from": {"$lte": when}}))
    for profile in source_profiles:
        if not profile.get("effective_from") or profile["effective_from"] > when:
            continue
        if profile.get("effective_to") and profile["effective_to"] <= when:
            continue
        if any(profile.get(key) and _normalized(profile[key]) != _normalized(values[key]) for key in MATCH_FIELDS):
            continue
        specificity = sum(bool(profile.get(key)) for key in MATCH_FIELDS)
        candidates.append((specificity, profile.get("effective_from"), profile))
    if not candidates:
        return {"status": "unpriced", "estimated_cost_usd": None, "price_profile_id": None}
    profile = max(candidates, key=lambda item: (item[0], item[1]))[2]
    prompt = max(0, int(call.get("prompt_tokens") or 0))
    cached = min(prompt, max(0, int(call.get("cached_input_tokens") or 0)))
    output = max(0, int(call.get("completion_tokens") or 0))
    if profile.get("pricing_type") == "local_tco":
        rate = float((profile.get("local_tco") or {}).get("blended_usd_per_million_tokens") or 0)
        input_cost = (prompt / 1_000_000) * rate
        cached_cost = 0.0
        output_cost = (output / 1_000_000) * rate
        basis = "local_tco"
    else:
        input_cost = ((prompt - cached) / 1_000_000) * float(profile.get("input_usd_per_million") or 0)
        cached_cost = (cached / 1_000_000) * float(profile.get("cached_input_usd_per_million") or 0)
        output_cost = (output / 1_000_000) * float(profile.get("output_usd_per_million") or 0)
        basis = str(profile.get("source_type") or "manual")
    return {
        "status": "estimated",
        "estimated_cost_usd": round(input_cost + cached_cost + output_cost, 10),
        "input_cost_usd": round(input_cost, 10),
        "cached_input_cost_usd": round(cached_cost, 10),
        "output_cost_usd": round(output_cost, 10),
        "price_profile_id": str(profile.get("_id") or ""),
        "price_profile_name": str(profile.get("name") or ""),
        "pricing_basis": basis,
    }
