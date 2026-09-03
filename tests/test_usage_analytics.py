from datetime import datetime, timezone

from mongo_table_connecters.usage_analytics import aggregate_usage


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
    }
    assert result["timeline"][0]["period"] == "2026-09-01"
    assert result["breakdowns"]["models"][0]["label"] == "gpt-4.1-mini"
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
