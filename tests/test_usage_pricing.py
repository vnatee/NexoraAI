from datetime import datetime, timezone

import pytest

from mongo_table_connecters.usage_pricing import (
    estimate_call_cost,
    normalize_price_profile,
)

WHEN = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _token_profile(**overrides):
    profile = normalize_price_profile({
        "name": "Cloud rate v1",
        "pricing_type": "token",
        "provider": "openai",
        "model": "gpt-test",
        "effective_from": "2026-01-01",
        "input_usd_per_million": 2,
        "cached_input_usd_per_million": 0.5,
        "output_usd_per_million": 8,
        **overrides,
    }, actor_id="admin-1")
    profile["_id"] = overrides.get("_id", "price-1")
    return profile


def test_token_price_separates_cached_input_and_output():
    result = estimate_call_cost({
        "provider": "openai", "model": "gpt-test", "prompt_tokens": 1_000_000,
        "cached_input_tokens": 250_000, "completion_tokens": 100_000,
    }, {}, WHEN, profiles=[_token_profile()])

    assert result["status"] == "estimated"
    assert result["input_cost_usd"] == 1.5
    assert result["cached_input_cost_usd"] == 0.125
    assert result["output_cost_usd"] == 0.8
    assert result["estimated_cost_usd"] == 2.425


def test_most_specific_effective_price_wins():
    generic = _token_profile(model="", _id="generic")
    specific = _token_profile(_id="specific", input_usd_per_million=3)

    result = estimate_call_cost(
        {"provider": "openai", "model": "gpt-test", "prompt_tokens": 1_000_000},
        {}, WHEN, profiles=[generic, specific],
    )

    assert result["price_profile_id"] == "specific"
    assert result["estimated_cost_usd"] == 3


def test_local_tco_computes_loaded_hourly_and_blended_token_rate():
    profile = normalize_price_profile({
        "name": "Local GPU v1", "pricing_type": "local_tco", "provider": "ollama",
        "effective_from": "2026-01-01", "local_tco": {
            "hardware_purchase_usd": 8_760, "residual_value_usd": 0,
            "useful_life_years": 1, "annual_maintenance_usd": 0,
            "annual_operations_usd": 0, "average_power_kw": 0,
            "pue": 1, "electricity_usd_per_kwh": 0,
            "cloud_gpu_usd_per_hour": 0, "aggregate_tokens_per_second": 100,
            "utilization": 0.5,
        },
    }, actor_id="admin-1")

    assert profile["local_tco"]["loaded_cost_usd_per_hour"] == 1
    assert profile["local_tco"]["blended_usd_per_million_tokens"] == pytest.approx(5.55555556)
    result = estimate_call_cost(
        {"provider": "ollama", "prompt_tokens": 100_000, "completion_tokens": 80_000},
        {}, WHEN, profiles=[profile],
    )
    assert result["estimated_cost_usd"] == pytest.approx(1.0)


def test_unknown_usage_is_unpriced_not_zero_cost():
    result = estimate_call_cost(
        {"provider": "unknown", "model": "unknown", "prompt_tokens": 10},
        {}, WHEN, profiles=[],
    )

    assert result == {"status": "unpriced", "estimated_cost_usd": None, "price_profile_id": None}


def test_retired_version_still_prices_usage_inside_its_historical_window():
    profile = _token_profile()
    profile.update({
        "enabled": False,
        "effective_to": datetime(2026, 10, 1, tzinfo=timezone.utc),
    })

    result = estimate_call_cost(
        {"provider": "openai", "model": "gpt-test", "prompt_tokens": 1_000_000},
        {}, WHEN, profiles=[profile],
    )

    assert result["status"] == "estimated"
    assert result["estimated_cost_usd"] == 2


def test_price_profile_rejects_missing_match_dimension():
    with pytest.raises(ValueError, match="At least one"):
        normalize_price_profile({
            "name": "Unsafe wildcard", "pricing_type": "token",
            "effective_from": "2026-01-01",
        }, actor_id="admin-1")
