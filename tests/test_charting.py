import json

import pytest

from agent_runtime.charting import (
    ChartValidationError,
    build_chart_spec,
    register_chart_tool,
    validate_echarts_spec,
)
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext


def test_build_chart_spec_creates_controlled_option():
    spec = build_chart_spec(
        {
            "type": "bar",
            "title": "PO risk by vendor",
            "categories": ["A", "B"],
            "series": [{"name": "High risk", "values": [4, 2]}],
        },
        ["bar", "line"],
    )

    assert spec["option"]["series"][0] == {
        "name": "High risk",
        "type": "bar",
        "data": [4, 2],
    }
    assert spec["option"]["xAxis"]["data"] == ["A", "B"]


def test_build_chart_spec_rejects_mismatched_or_disallowed_data():
    with pytest.raises(ChartValidationError, match="not allowed"):
        build_chart_spec(
            {
                "type": "pie",
                "categories": ["A"],
                "series": [{"name": "x", "values": [1]}],
            },
            ["bar"],
        )
    with pytest.raises(ChartValidationError, match="categories length"):
        build_chart_spec(
            {
                "type": "bar",
                "categories": ["A"],
                "series": [{"name": "x", "values": [1, 2]}],
            }
        )


def test_validate_legacy_echarts_spec_blocks_unsafe_and_oversized_specs():
    assert (
        validate_echarts_spec(
            {"option": {"series": [{"type": "line", "data": [1, 2]}]}}
        )["height"]
        == 400
    )
    with pytest.raises(ChartValidationError, match="forbidden key"):
        validate_echarts_spec(
            {"option": {"series": [{"type": "line", "data": [1]}], "__proto__": {}}}
        )
    with pytest.raises(ChartValidationError, match="not allowed"):
        validate_echarts_spec({"option": {"series": [{"type": "custom", "data": [1]}]}})
    with pytest.raises(ChartValidationError, match="external resource"):
        validate_echarts_spec(
            {
                "option": {
                    "series": [
                        {
                            "type": "bar",
                            "data": [1],
                            "symbol": "image://https://example.test/a.png",
                        }
                    ]
                }
            }
        )


def test_validate_area_chart_uses_logical_area_allowlist():
    spec = {"option": {"series": [{"type": "line", "areaStyle": {}, "data": [1, 2]}]}}
    assert (
        validate_echarts_spec(spec, ["area"])["option"]["series"][0]["type"] == "line"
    )


@pytest.mark.asyncio
async def test_create_chart_tool_returns_chart_context():
    registry = ToolRegistry(ToolRuntimeContext(agent_id="agent-1", auth_claims={}))
    register_chart_tool(
        registry, {"chart_selection_mode": "manual", "allowed_chart_types": ["bar"]}
    )

    output = json.loads(
        await registry.execute(
            "create_chart",
            {
                "type": "bar",
                "categories": ["A"],
                "series": [{"name": "Risk", "values": [3]}],
                "source_tool": "user",
            },
        )
    )

    assert output["status"] == "ready"
    assert output["chartType"] == "bar"
    assert output["source"] == "user"
    chart = registry.context.metadata["chart"]
    assert chart["data"]["rows"] == [{"category": "A", "Risk": 3}]


def test_create_chart_tool_exposes_advanced_structured_types():
    registry = ToolRegistry(ToolRuntimeContext(agent_id="agent-1", auth_claims={}))
    assert register_chart_tool(
        registry,
        {
            "allowed_chart_types": [
                "gauge",
                "funnel",
                "treemap",
                "heatmap",
                "radar",
                "boxplot",
                "sankey",
            ]
        },
    )
    chart_types = registry.specs()[0].input_schema["properties"]["type"]["enum"]
    assert chart_types == [
        "gauge",
        "funnel",
        "treemap",
        "heatmap",
        "radar",
        "boxplot",
        "sankey",
    ]


@pytest.mark.asyncio
async def test_create_chart_maps_fields_directly_from_selected_tool_result():
    registry = ToolRegistry(ToolRuntimeContext(agent_id="agent-1", auth_claims={}))
    registry.execution_log.append(
        {
            "name": "database_po",
            "source": "external_database:mssql",
            "output": '{"query":"SELECT vendor, risk FROM po","rows":[{"vendor":"A","risk":3},{"vendor":"B","risk":"4"}]}',
            "raw_output": {
                "query": "SELECT vendor, risk FROM po",
                "rows": [{"vendor": "A", "risk": 3}, {"vendor": "B", "risk": "4"}],
            },
            "is_error": False,
        }
    )
    register_chart_tool(registry, {"allowed_chart_types": ["bar"]})

    valid = json.loads(
        await registry.execute(
            "create_chart",
            {
                "type": "bar",
                "source_tool": "database_po",
                "category_field": "vendor",
                "series_fields": [{"field": "risk", "name": "Risk"}],
            },
        )
    )
    invalid = json.loads(
        await registry.execute(
            "create_chart",
            {
                "type": "bar",
                "source_tool": "database_po",
                "category_field": "vendor",
                "series_fields": [{"field": "missing"}],
            },
        )
    )

    assert valid["status"] == "ready"
    chart = registry.context.metadata["chart"]
    assert chart["option"]["xAxis"]["data"] == ["A", "B"]
    assert chart["option"]["series"][0]["data"] == [3, 4]
    assert chart["data"]["query"] == "SELECT vendor, risk FROM po"
    assert chart["data"]["rows"][0] == {"vendor": "A", "risk": 3}
    assert "absent from source row" in invalid["error"]


async def _run_source_chart(chart_type, arguments, rows):
    registry = ToolRegistry(ToolRuntimeContext(agent_id="agent-1", auth_claims={}))
    registry.execution_log.append(
        {
            "name": "database_po",
            "source": "external_database:mssql",
            "output": "{}",
            "raw_output": {"query": "SELECT test data", "rows": rows},
            "is_error": False,
        }
    )
    register_chart_tool(registry, {"allowed_chart_types": [chart_type]})
    output = json.loads(
        await registry.execute(
            "create_chart",
            {"type": chart_type, "source_tool": "database_po", **arguments},
        )
    )
    return output, registry.context.metadata.get("chart")


@pytest.mark.asyncio
async def test_gauge_uses_one_exact_kpi_value():
    output, chart = await _run_source_chart(
        "gauge",
        {"value_field": "High_Risk_Pct", "name_field": "KPI"},
        [{"KPI": "High Risk PO", "High_Risk_Pct": 32.5}],
    )

    assert output["status"] == "ready"
    assert chart["option"]["series"][0]["data"] == [
        {"value": 32.5, "name": "High Risk PO"}
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("chart_type", ["funnel", "treemap"])
async def test_funnel_and_treemap_aggregate_name_value_rows(chart_type):
    _, chart = await _run_source_chart(
        chart_type,
        {"name_field": "Stage", "value_field": "PO_Count"},
        [
            {"Stage": "Review", "PO_Count": 4},
            {"Stage": "Review", "PO_Count": 3},
            {"Stage": "Approved", "PO_Count": 5},
        ],
    )

    data = chart["option"]["series"][0]["data"]
    assert {item["name"]: item["value"] for item in data} == {
        "Review": 7.0,
        "Approved": 5.0,
    }


@pytest.mark.asyncio
async def test_heatmap_aggregates_vendor_month_cells():
    _, chart = await _run_source_chart(
        "heatmap",
        {"x_field": "PO_Month", "y_field": "Vendor", "value_field": "Risk_Count"},
        [
            {"PO_Month": "2026-01", "Vendor": "A", "Risk_Count": 2},
            {"PO_Month": "2026-01", "Vendor": "A", "Risk_Count": 3},
            {"PO_Month": "2026-02", "Vendor": "B", "Risk_Count": 4},
        ],
    )

    assert chart["option"]["xAxis"]["data"] == ["2026-01", "2026-02"]
    assert chart["option"]["yAxis"]["data"] == ["A", "B"]
    assert [0, 0, 5.0] in chart["option"]["series"][0]["data"]


@pytest.mark.asyncio
async def test_radar_maps_multiple_risk_dimensions():
    _, chart = await _run_source_chart(
        "radar",
        {
            "category_field": "Vendor",
            "indicator_fields": [
                {"field": "Price_Risk"},
                {"field": "Contract_Risk"},
                {"field": "Anomaly_Risk"},
            ],
        },
        [
            {
                "Vendor": "A",
                "Price_Risk": 7,
                "Contract_Risk": 5,
                "Anomaly_Risk": 3,
            }
        ],
    )

    assert [item["name"] for item in chart["option"]["radar"]["indicator"]] == [
        "Price_Risk",
        "Contract_Risk",
        "Anomaly_Risk",
    ]
    assert chart["option"]["series"][0]["data"][0]["value"] == [7.0, 5.0, 3.0]


@pytest.mark.asyncio
async def test_boxplot_calculates_quartiles_and_outliers_from_raw_prices():
    _, chart = await _run_source_chart(
        "boxplot",
        {"category_field": "Vendor", "value_field": "Unit_Price"},
        [{"Vendor": "A", "Unit_Price": value} for value in [10, 11, 12, 13, 14, 100]],
    )

    box = chart["option"]["series"][0]["data"][0]
    assert box[2] == 12.5
    assert chart["option"]["series"][1]["data"] == [[0, 100.0]]


@pytest.mark.asyncio
async def test_boxplot_accepts_preaggregated_full_dataset_statistics():
    registry = ToolRegistry(ToolRuntimeContext(agent_id="agent-1", auth_claims={}))
    registry.execution_log.append(
        {
            "name": "database_po",
            "source": "external_database:mssql",
            "output": "{}",
            "raw_output": {
                "rows": [
                    {
                        "Vendor": "A",
                        "box_lower": 10,
                        "box_q1": 12,
                        "box_median": 15,
                        "box_q3": 18,
                        "box_upper": 22,
                        "sample_count": 500,
                    }
                ],
                "chart_mapping": {
                    "category_field": "Vendor",
                    "value_field": "Unit_Price",
                },
                "chart_aggregation": {
                    "type": "boxplot",
                    "method": "sql_percentile",
                    "fullDataset": True,
                    "sourceRecordCount": 500,
                    "aggregateRowCount": 1,
                    "displayedRowCount": 1,
                    "resultTruncated": False,
                },
            },
            "is_error": False,
        }
    )
    register_chart_tool(registry, {"allowed_chart_types": ["boxplot"]})

    output = json.loads(
        await registry.execute(
            "create_chart",
            {
                "type": "boxplot",
                "source_tool": "database_po",
                "category_field": "ignored_by_mapping",
                "value_field": "ignored_by_mapping",
            },
        )
    )

    assert output["status"] == "ready"
    chart = registry.context.metadata["chart"]
    assert chart["option"]["series"][0]["data"] == [[10, 12, 15, 18, 22]]
    assert chart["data"]["sourceRecordCount"] == 500
    assert chart["data"]["fullDataset"] is True


@pytest.mark.asyncio
async def test_sankey_aggregates_source_target_links():
    _, chart = await _run_source_chart(
        "sankey",
        {
            "source_field": "From_Status",
            "target_field": "To_Status",
            "value_field": "PO_Count",
        },
        [
            {"From_Status": "Created", "To_Status": "Review", "PO_Count": 3},
            {"From_Status": "Created", "To_Status": "Review", "PO_Count": 2},
            {"From_Status": "Review", "To_Status": "Approved", "PO_Count": 4},
        ],
    )

    links = chart["option"]["series"][0]["links"]
    assert {(item["source"], item["target"]): item["value"] for item in links} == {
        ("Created", "Review"): 5.0,
        ("Review", "Approved"): 4.0,
    }


@pytest.mark.asyncio
async def test_sankey_rejects_cycles_before_echarts_rendering():
    output, chart = await _run_source_chart(
        "sankey",
        {
            "source_field": "From_Status",
            "target_field": "To_Status",
            "value_field": "PO_Count",
        },
        [
            {"From_Status": "Created", "To_Status": "Review", "PO_Count": 3},
            {"From_Status": "Review", "To_Status": "Created", "PO_Count": 2},
        ],
    )

    assert chart is None
    assert "must not contain cycles" in output["error"]
