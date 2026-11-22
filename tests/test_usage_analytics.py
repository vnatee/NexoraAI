from datetime import datetime, timezone

import mongo_table_connecters.usage_analytics as usage_module
from mongo_table_connecters.usage_analytics import aggregate_usage, usage_cost_csv


def _llm_record(model="gpt-4.1-mini", provider="openai"):
    return {
        "create_at": datetime(2026, 9, 1, 12, tzinfo=timezone.utc),
        "user": {"_id": "user-1", "name": "Natee"},
        "group": {"_id": "team-1", "name": "DIG"},
        "metadata": {
            "agent_id": "agent-1",
            "agent_name": "Analyst",
            "provider": provider,
            "model": model,
            "route_type": "external_gateway",
        },
        "model_calls": [{
            "model": model,
            "provider": provider,
            "prompt_tokens": 100,
            "completion_tokens": 25,
            "reasoning_tokens": 5,
            "total_tokens": 130,
        }],
    }


def test_aggregate_usage_builds_safe_overview_timeline_and_breakdowns():
    result = aggregate_usage(
        [_llm_record()],
        [{
            "create_at": datetime(2026, 9, 1, 13, tzinfo=timezone.utc),
            "user": {"_id": "user-1", "name": "Natee"},
            "team": {"_id": "team-1"},
            "scope": "team",
            "provider_name": "Docling",
            "profile_id": "profile-1",
            "profile_name": "PDF documents",
            "file_type": "pdf",
            "page_count": 7,
            "duration_ms": 1200,
        }],
        team_labels={"team-1": "DIG"},
    )

    assert result["overview"] == {
        "requests": 1,
        "input_tokens": 100,
        "output_tokens": 25,
        "reasoning_tokens": 5,
        "total_tokens": 130,
        "documents": 1,
        "processed_pages": 7,
        "processing_duration_ms": 1200,
        "estimated_cost_usd": 0.0,
        "priced_tokens": 0,
        "unpriced_tokens": 130,
        "priced_model_calls": 0,
        "unpriced_model_calls": 1,
        "pricing_coverage_percent": 0.0,
    }
    assert result["timeline"][0]["period"] == "2026-09-01"
    assert result["breakdowns"]["models"][0]["label"] == "gpt-4.1-mini"
    assert result["breakdowns"]["routes"][0]["label"] == "External AI Gateway"
    assert result["filter_options"]["routes"] == [{
        "value": "external_gateway",
        "label": "External AI Gateway",
    }]
    assert result["breakdowns"]["teams"][0]["label"] == "DIG"
    assert result["document_providers"][0]["label"] == "Docling"
    assert result["document_breakdowns"]["users"][0]["label"] == "Natee"
    assert result["document_breakdowns"]["teams"][0]["label"] == "DIG"
    assert result["document_breakdowns"]["profiles"][0]["label"] == "PDF documents"
    assert result["document_breakdowns"]["file_types"][0]["label"] == "PDF"
    assert result["document_breakdowns"]["scopes"][0]["label"] == "Team"
    assert result["document_filter_options"]["users"] == [{"value": "user-1", "label": "Natee"}]


def test_aggregate_usage_filters_model_and_provider_without_mixing_calls():
    result = aggregate_usage(
        [_llm_record(), _llm_record("bge-m3", "ollama")],
        [],
        model="bge-m3",
        provider="ollama",
    )

    assert result["overview"]["requests"] == 1
    assert result["overview"]["total_tokens"] == 130
    assert [item["label"] for item in result["breakdowns"]["models"]] == ["bge-m3"]


def test_aggregate_usage_filters_llm_route_type():
    built_in = _llm_record()
    built_in["metadata"]["route_type"] = "built_in"

    result = aggregate_usage(
        [built_in, _llm_record()],
        [],
        route_type="built_in",
    )

    assert result["overview"]["requests"] == 1
    assert result["breakdowns"]["routes"][0]["label"] == "Built-in Providers"


def test_aggregate_usage_calculates_cost_and_coverage_from_effective_price():
    result = aggregate_usage(
        [_llm_record()],
        [],
        price_profiles=[{
            "_id": "price-1",
            "name": "Test rate",
            "enabled": True,
            "pricing_type": "token",
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "effective_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "input_usd_per_million": 2,
            "cached_input_usd_per_million": 0.5,
            "output_usd_per_million": 8,
        }],
    )

    assert result["overview"]["estimated_cost_usd"] == 0.0004
    assert result["overview"]["pricing_coverage_percent"] == 100
    assert result["overview"]["priced_model_calls"] == 1
    assert result["overview"]["unpriced_model_calls"] == 0
    assert result["breakdowns"]["providers"][0]["estimated_cost_usd"] == 0.0004


def test_aggregate_usage_filters_document_dimensions_and_keeps_legacy_owner_unknown():
    records = [
        {
            "create_at": datetime(2026, 9, 1, 13, tzinfo=timezone.utc),
            "user": {"_id": "user-1", "name": "Natee"},
            "team": {"_id": "team-1"},
            "scope": "team",
            "provider_name": "Docling",
            "profile_id": "profile-1",
            "profile_name": "PDF documents",
            "file_type": ".pdf",
            "page_count": 7,
            "duration_ms": 1200,
        },
        {
            "create_at": datetime(2026, 9, 1, 14, tzinfo=timezone.utc),
            "user": "legacy@example.com",
            "team": "team-1",
            "upload_type": "team",
            "ocr_pages": 3,
        },
    ]

    result = aggregate_usage(
        [],
        records,
        profile_id="profile-1",
        file_type="pdf",
        document_scope="team",
        team_labels={"team-1": "DIG"},
    )

    assert result["overview"]["documents"] == 1
    assert result["overview"]["processed_pages"] == 7
    assert [row["label"] for row in result["document_breakdowns"]["users"]] == ["Natee"]
    assert {item["label"] for item in result["document_filter_options"]["users"]} == {"Natee"}
    assert result["document_filter_options"]["profiles"] == [{"value": "profile-1", "label": "PDF documents"}]

    legacy = aggregate_usage([], [records[1]], team_labels={"team-1": "DIG"})
    assert legacy["document_breakdowns"]["users"][0]["label"] == "Unknown / legacy"
    assert legacy["document_breakdowns"]["teams"][0]["label"] == "DIG"


def test_raw_cost_csv_excludes_content_and_escapes_spreadsheet_formulas(monkeypatch):
    record = _llm_record()
    record.update({"_id": "event-1", "prompt": "private prompt", "response": "private response"})
    record["metadata"]["agent_name"] = "=IMPORTXML(secret)"

    class Cursor(list):
        def sort(self, *_args, **_kwargs):
            return self

    class Collection:
        def find(self, _query):
            return Cursor([record])

    monkeypatch.setattr(usage_module, "llm_collection", Collection())
    monkeypatch.setattr(usage_module, "list_price_profiles", lambda: [])

    exported = usage_cost_csv({"delete_at": None})

    assert "private prompt" not in exported
    assert "private response" not in exported
    assert "'=IMPORTXML(secret)" in exported
    assert "pricing_status" in exported
