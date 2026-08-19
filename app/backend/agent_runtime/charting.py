from __future__ import annotations

import json
import math
import re
from typing import Any

from agent_runtime.tools import ToolRegistry, ToolSpec

SAFE_CHART_TYPES = (
    "bar",
    "line",
    "area",
    "pie",
    "scatter",
    "radar",
    "heatmap",
    "treemap",
    "sunburst",
    "funnel",
    "gauge",
    "boxplot",
    "candlestick",
    "sankey",
    "graph",
)
BASIC_CHART_TYPES = ("bar", "line", "area", "pie", "scatter")
STRUCTURED_CHART_TYPES = (
    *BASIC_CHART_TYPES,
    "gauge",
    "funnel",
    "treemap",
    "heatmap",
    "radar",
    "boxplot",
    "sankey",
)
MAX_SERIES = 20
MAX_POINTS_PER_SERIES = 1_000
MAX_TOTAL_POINTS = 5_000
MIN_HEIGHT = 240
MAX_HEIGHT = 1_200
MAX_TEXT_LENGTH = 500
MAX_TABLE_ROWS = 200
FORBIDDEN_KEYS = {"__proto__", "prototype", "constructor"}
NUMBER_TEXT = re.compile(r"^-?\d+(?:\.\d+)?$")


class ChartValidationError(ValueError):
    pass


def _safe_text(value: Any, field: str, *, max_length: int = MAX_TEXT_LENGTH) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise ChartValidationError(f"{field} is too long")
    return text


def _finite_number(value: Any, field: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ChartValidationError(f"{field} must contain only numbers or null")
    if not math.isfinite(float(value)):
        raise ChartValidationError(f"{field} must contain only finite numbers")
    return value


def build_chart_spec(
    arguments: dict[str, Any], allowed_types: list[str] | None = None
) -> dict[str, Any]:
    """Build a controlled ECharts option from the provider-neutral create_chart DTO."""
    chart_type = _safe_text(arguments.get("type"), "type", max_length=32)
    allowed = {item.lower() for item in (allowed_types or SAFE_CHART_TYPES)}
    if chart_type.lower() not in allowed or chart_type.lower() not in SAFE_CHART_TYPES:
        raise ChartValidationError(f"Chart type '{chart_type}' is not allowed")

    categories_raw = arguments.get("categories") or []
    series_raw = arguments.get("series") or []
    if not isinstance(categories_raw, list) or not isinstance(series_raw, list):
        raise ChartValidationError("categories and series must be arrays")
    if not series_raw or len(series_raw) > MAX_SERIES:
        raise ChartValidationError(
            f"series must contain between 1 and {MAX_SERIES} items"
        )
    if len(categories_raw) > MAX_POINTS_PER_SERIES:
        raise ChartValidationError(
            f"categories cannot exceed {MAX_POINTS_PER_SERIES} items"
        )

    categories = [
        _safe_text(item, "category", max_length=200) for item in categories_raw
    ]
    normalized_series: list[dict[str, Any]] = []
    total_points = 0
    for index, item in enumerate(series_raw):
        if not isinstance(item, dict):
            raise ChartValidationError("each series must be an object")
        values = item.get("values")
        if not isinstance(values, list) or len(values) > MAX_POINTS_PER_SERIES:
            raise ChartValidationError(
                f"series[{index}].values must be an array with at most {MAX_POINTS_PER_SERIES} items"
            )
        if categories and len(values) != len(categories):
            raise ChartValidationError(
                f"series[{index}].values must match the categories length"
            )
        total_points += len(values)
        if total_points > MAX_TOTAL_POINTS:
            raise ChartValidationError(
                f"chart cannot exceed {MAX_TOTAL_POINTS} total data points"
            )
        normalized_series.append(
            {
                "name": _safe_text(
                    item.get("name") or f"Series {index + 1}",
                    "series name",
                    max_length=200,
                ),
                "values": [
                    _finite_number(value, f"series[{index}].values") for value in values
                ],
            }
        )

    title = _safe_text(arguments.get("title"), "title")
    x_axis_label = _safe_text(
        arguments.get("x_axis_label"), "x_axis_label", max_length=200
    )
    y_axis_label = _safe_text(
        arguments.get("y_axis_label"), "y_axis_label", max_length=200
    )
    height = int(arguments.get("height") or 400)
    if not MIN_HEIGHT <= height <= MAX_HEIGHT:
        raise ChartValidationError(
            f"height must be between {MIN_HEIGHT} and {MAX_HEIGHT}"
        )

    effective_type = chart_type.lower()
    if effective_type not in BASIC_CHART_TYPES:
        raise ChartValidationError(
            f"Chart type '{effective_type}' requires tool-sourced field mapping"
        )
    if effective_type == "pie":
        if len(normalized_series) != 1 or not categories:
            raise ChartValidationError(
                "pie charts require categories and exactly one series"
            )
        option_series = [
            {
                "type": "pie",
                "radius": ["40%", "70%"],
                "data": [
                    {"name": category, "value": value}
                    for category, value in zip(
                        categories, normalized_series[0]["values"]
                    )
                ],
            }
        ]
        option: dict[str, Any] = {
            "tooltip": {"trigger": "item"},
            "legend": {"bottom": 0},
            "series": option_series,
        }
    else:
        echarts_type = "line" if effective_type == "area" else effective_type
        option_series = [
            {
                "name": item["name"],
                "type": echarts_type,
                "data": item["values"],
                **({"areaStyle": {"opacity": 0.3}} if effective_type == "area" else {}),
            }
            for item in normalized_series
        ]
        option = {
            "tooltip": {"trigger": "axis"},
            "legend": {"bottom": 0},
            "xAxis": {
                "type": "category",
                "data": categories,
                **({"name": x_axis_label} if x_axis_label else {}),
            },
            "yAxis": {
                "type": "value",
                **({"name": y_axis_label} if y_axis_label else {}),
            },
            "series": option_series,
        }
    if title:
        option["title"] = {"text": title, "left": "center"}
    return {
        "version": 1,
        "chartType": effective_type,
        "option": option,
        "height": height,
    }


def _tabular_rows(value: Any, *, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 5:
        return []
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    if isinstance(value, dict):
        rows = value.get("rows")
        if isinstance(rows, list) and all(isinstance(item, dict) for item in rows):
            return rows
        for child in value.values():
            found = _tabular_rows(child, depth=depth + 1)
            if found:
                return found
    if isinstance(value, str) and value.strip().startswith(("{", "[")):
        try:
            return _tabular_rows(json.loads(value), depth=depth + 1)
        except json.JSONDecodeError:
            return []
    return []


def _number_from_row(value: Any, field: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ChartValidationError(f"field '{field}' contains a non-numeric value")
    if isinstance(value, (int, float)):
        return _finite_number(value, field)
    if isinstance(value, str) and NUMBER_TEXT.fullmatch(value.strip()):
        number = float(value)
        return int(number) if number.is_integer() else number
    raise ChartValidationError(f"field '{field}' contains a non-numeric value")


def _chart_arguments_from_rows(
    arguments: dict[str, Any], source_payload: Any, source_tool: str, source_type: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = _tabular_rows(source_payload)
    if not rows:
        raise ChartValidationError("source tool result does not contain tabular rows")
    category_field = _safe_text(
        arguments.get("category_field"), "category_field", max_length=200
    )
    series_fields = arguments.get("series_fields") or []
    if not category_field or not isinstance(series_fields, list) or not series_fields:
        raise ChartValidationError(
            "category_field and series_fields are required for tool-sourced charts"
        )
    if len(series_fields) > MAX_SERIES:
        raise ChartValidationError(f"series_fields cannot exceed {MAX_SERIES} items")

    limit = max(
        1, min(int(arguments.get("row_limit") or MAX_TABLE_ROWS), MAX_TABLE_ROWS)
    )
    selected_rows = rows[:limit]
    normalized_fields: list[tuple[str, str]] = []
    for index, item in enumerate(series_fields):
        if not isinstance(item, dict):
            raise ChartValidationError("each series_fields item must be an object")
        field = _safe_text(item.get("field"), "series field", max_length=200)
        if not field:
            raise ChartValidationError("each series_fields item requires field")
        label = _safe_text(item.get("name") or field, "series name", max_length=200)
        normalized_fields.append((field, label))

    projected_rows = []
    categories = []
    series_values = [[] for _ in normalized_fields]
    for row_index, row in enumerate(selected_rows):
        if category_field not in row:
            raise ChartValidationError(
                f"category field '{category_field}' is absent from source row {row_index + 1}"
            )
        category = _safe_text(row.get(category_field), category_field, max_length=200)
        categories.append(category)
        projected = {category_field: row.get(category_field)}
        for series_index, (field, _) in enumerate(normalized_fields):
            if field not in row:
                raise ChartValidationError(
                    f"series field '{field}' is absent from source row {row_index + 1}"
                )
            number = _number_from_row(row.get(field), field)
            series_values[series_index].append(number)
            projected[field] = row.get(field)
        projected_rows.append(projected)

    chart_arguments = {
        **arguments,
        "categories": categories,
        "series": [
            {"name": label, "values": series_values[index]}
            for index, (_, label) in enumerate(normalized_fields)
        ],
    }
    query = source_payload.get("query") if isinstance(source_payload, dict) else None
    data = {
        "sourceTool": source_tool,
        "sourceType": source_type,
        "categoryField": category_field,
        "valueFields": [field for field, _ in normalized_fields],
        "columns": [category_field, *[field for field, _ in normalized_fields]],
        "rows": projected_rows,
        "rowCount": len(projected_rows),
        "sourceRowCount": len(rows),
        **({"query": query} if query else {}),
    }
    if isinstance(source_payload, dict) and "resultTruncated" in source_payload:
        data["resultTruncated"] = bool(source_payload["resultTruncated"])
        data["fullDataset"] = not data["resultTruncated"]
    return chart_arguments, data


def _user_chart_data(arguments: dict[str, Any]) -> dict[str, Any]:
    categories = arguments.get("categories") or []
    series = arguments.get("series") or []
    columns = ["category", *[str(item.get("name") or "value") for item in series]]
    rows = []
    for index, category in enumerate(categories[:MAX_TABLE_ROWS]):
        row = {"category": category}
        for item in series:
            values = item.get("values") or []
            row[str(item.get("name") or "value")] = (
                values[index] if index < len(values) else None
            )
        rows.append(row)
    return {
        "sourceTool": "user",
        "sourceType": "user",
        "categoryField": "category",
        "valueFields": columns[1:],
        "columns": columns,
        "rows": rows,
        "rowCount": len(rows),
        "sourceRowCount": len(categories),
    }


def _mapped_field(arguments: dict[str, Any], name: str) -> str:
    value = _safe_text(arguments.get(name), name, max_length=200)
    if not value:
        raise ChartValidationError(
            f"{name} is required for {arguments.get('type')} charts"
        )
    return value


def _mapped_rows(
    arguments: dict[str, Any], source_payload: Any
) -> tuple[list[dict[str, Any]], int]:
    rows = _tabular_rows(source_payload)
    if not rows:
        raise ChartValidationError("source tool result does not contain tabular rows")
    limit = max(
        1, min(int(arguments.get("row_limit") or MAX_TABLE_ROWS), MAX_TABLE_ROWS)
    )
    return rows[:limit], len(rows)


def _required_number(row: dict[str, Any], field: str, row_index: int) -> int | float:
    if field not in row:
        raise ChartValidationError(
            f"field '{field}' is absent from source row {row_index + 1}"
        )
    value = _number_from_row(row.get(field), field)
    if value is None:
        raise ChartValidationError(
            f"field '{field}' is null in source row {row_index + 1}"
        )
    return value


def _audit_data(
    *,
    source_tool: str,
    source_type: str,
    fields: list[str],
    rows: list[dict[str, Any]],
    source_row_count: int,
    source_payload: Any,
    category_field: str,
    value_fields: list[str],
) -> dict[str, Any]:
    projected = [{field: row.get(field) for field in fields} for row in rows]
    query = source_payload.get("query") if isinstance(source_payload, dict) else None
    audit = {
        "sourceTool": source_tool,
        "sourceType": source_type,
        "categoryField": category_field,
        "valueFields": value_fields,
        "columns": fields,
        "rows": projected,
        "rowCount": len(projected),
        "sourceRowCount": source_row_count,
        **({"query": query} if query else {}),
    }
    if isinstance(source_payload, dict):
        aggregation = source_payload.get("chart_aggregation")
        if isinstance(aggregation, dict):
            audit["aggregation"] = aggregation
            audit["sourceRecordCount"] = aggregation.get(
                "sourceRecordCount", source_row_count
            )
            audit["aggregateRowCount"] = aggregation.get(
                "aggregateRowCount", source_row_count
            )
            audit["fullDataset"] = aggregation.get("fullDataset", False)
            audit["resultTruncated"] = aggregation.get("resultTruncated", False)
        elif "resultTruncated" in source_payload:
            audit["resultTruncated"] = bool(source_payload["resultTruncated"])
            audit["fullDataset"] = not audit["resultTruncated"]
    return audit


def _with_chart_title(
    option: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    title = _safe_text(arguments.get("title"), "title")
    if title:
        option["title"] = {"text": title, "left": "center"}
    return option


def _chart_height(arguments: dict[str, Any]) -> int:
    height = int(arguments.get("height") or 400)
    if not MIN_HEIGHT <= height <= MAX_HEIGHT:
        raise ChartValidationError(
            f"height must be between {MIN_HEIGHT} and {MAX_HEIGHT}"
        )
    return height


def _percentile(values: list[float], percentile: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def _ensure_acyclic_sankey(links: dict[tuple[str, str], float]) -> None:
    adjacency: dict[str, set[str]] = {}
    for source, target in links:
        adjacency.setdefault(source, set()).add(target)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ChartValidationError("sankey links must not contain cycles")
        if node in visited:
            return
        visiting.add(node)
        for target in adjacency.get(node, set()):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in list(adjacency):
        visit(node)


def _build_specialized_chart(
    arguments: dict[str, Any],
    source_payload: Any,
    source_tool: str,
    source_type: str,
    allowed_types: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    chart_type = _safe_text(arguments.get("type"), "type", max_length=32).lower()
    if chart_type not in allowed_types or chart_type not in STRUCTURED_CHART_TYPES:
        raise ChartValidationError(
            f"Chart type '{chart_type}' is not allowed by this agent's Chart Capability. "
            f"Allowed types: {', '.join(allowed_types)}"
        )
    rows, source_row_count = _mapped_rows(arguments, source_payload)
    aggregation_meta = (
        source_payload.get("chart_aggregation")
        if isinstance(source_payload, dict)
        and isinstance(source_payload.get("chart_aggregation"), dict)
        else {}
    )
    chart_mapping = (
        source_payload.get("chart_mapping")
        if isinstance(source_payload, dict)
        and isinstance(source_payload.get("chart_mapping"), dict)
        else {}
    )
    if aggregation_meta.get("type") == chart_type:
        arguments = {**arguments, **chart_mapping}
    height = _chart_height(arguments)

    if chart_type == "gauge":
        if len(rows) != 1:
            raise ChartValidationError(
                "gauge source query must return exactly one KPI row"
            )
        value_field = _mapped_field(arguments, "value_field")
        name_field = _safe_text(
            arguments.get("name_field"), "name_field", max_length=200
        )
        value = _required_number(rows[0], value_field, 0)
        if value < 0:
            raise ChartValidationError("gauge value must be non-negative")
        configured_max = arguments.get("max_value")
        is_percentage = any(
            token in value_field.lower() for token in ("pct", "percent", "percentage")
        )
        maximum = (
            float(configured_max)
            if configured_max is not None
            else (100.0 if is_percentage else max(1.0, float(value) * 1.2))
        )
        if not math.isfinite(maximum) or maximum <= float(value):
            maximum = max(1.0, float(value) * 1.2)
        name = (
            _safe_text(rows[0].get(name_field), name_field, max_length=200)
            if name_field
            else value_field
        )
        option = _with_chart_title(
            {
                "series": [
                    {
                        "type": "gauge",
                        "max": maximum,
                        "progress": {"show": True},
                        "detail": {"valueAnimation": True, "formatter": "{value}"},
                        "data": [{"value": value, "name": name}],
                    }
                ]
            },
            arguments,
        )
        fields = [*([name_field] if name_field else []), value_field]
        audit = _audit_data(
            source_tool=source_tool,
            source_type=source_type,
            fields=fields,
            rows=rows[:1],
            source_row_count=source_row_count,
            source_payload=source_payload,
            category_field=name_field or value_field,
            value_fields=[value_field],
        )

    elif chart_type in ("funnel", "treemap"):
        name_field = _mapped_field(arguments, "name_field")
        value_field = _mapped_field(arguments, "value_field")
        totals: dict[str, float] = {}
        for index, row in enumerate(rows):
            if name_field not in row:
                raise ChartValidationError(
                    f"field '{name_field}' is absent from source row {index + 1}"
                )
            name = _safe_text(row.get(name_field), name_field, max_length=200)
            value = float(_required_number(row, value_field, index))
            if value < 0:
                raise ChartValidationError(f"{chart_type} values must be non-negative")
            totals[name] = totals.get(name, 0.0) + value
        data = [{"name": name, "value": value} for name, value in totals.items()]
        if chart_type == "funnel":
            data.sort(key=lambda item: item["value"], reverse=True)
            series = {
                "type": "funnel",
                "sort": "descending",
                "label": {"show": True},
                "data": data,
            }
        else:
            series = {
                "type": "treemap",
                "roam": False,
                "label": {"show": True, "formatter": "{b}"},
                "data": data,
            }
        option = _with_chart_title(
            {"tooltip": {"trigger": "item"}, "series": [series]}, arguments
        )
        audit = _audit_data(
            source_tool=source_tool,
            source_type=source_type,
            fields=[name_field, value_field],
            rows=rows,
            source_row_count=source_row_count,
            source_payload=source_payload,
            category_field=name_field,
            value_fields=[value_field],
        )

    elif chart_type == "heatmap":
        x_field = _mapped_field(arguments, "x_field")
        y_field = _mapped_field(arguments, "y_field")
        value_field = _mapped_field(arguments, "value_field")
        x_values: list[str] = []
        y_values: list[str] = []
        totals: dict[tuple[str, str], float] = {}
        for index, row in enumerate(rows):
            if x_field not in row or y_field not in row:
                missing = x_field if x_field not in row else y_field
                raise ChartValidationError(
                    f"field '{missing}' is absent from source row {index + 1}"
                )
            x_value = _safe_text(row.get(x_field), x_field, max_length=200)
            y_value = _safe_text(row.get(y_field), y_field, max_length=200)
            value = float(_required_number(row, value_field, index))
            if x_value not in x_values:
                x_values.append(x_value)
            if y_value not in y_values:
                y_values.append(y_value)
            totals[(x_value, y_value)] = totals.get((x_value, y_value), 0.0) + value
        heat_data = [
            [x_values.index(x), y_values.index(y), value]
            for (x, y), value in totals.items()
        ]
        numeric_values = [item[2] for item in heat_data]
        option = _with_chart_title(
            {
                "tooltip": {"position": "top"},
                "grid": {"containLabel": True},
                "xAxis": {"type": "category", "name": x_field, "data": x_values},
                "yAxis": {"type": "category", "name": y_field, "data": y_values},
                "visualMap": {
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "calculable": True,
                    "orient": "horizontal",
                    "left": "center",
                    "bottom": 0,
                },
                "series": [
                    {
                        "type": "heatmap",
                        "data": heat_data,
                        "label": {"show": len(heat_data) <= 100},
                    }
                ],
            },
            arguments,
        )
        audit = _audit_data(
            source_tool=source_tool,
            source_type=source_type,
            fields=[x_field, y_field, value_field],
            rows=rows,
            source_row_count=source_row_count,
            source_payload=source_payload,
            category_field=f"{x_field} × {y_field}",
            value_fields=[value_field],
        )

    elif chart_type == "radar":
        if len(rows) > 12:
            raise ChartValidationError(
                "radar source query must return at most 12 category rows"
            )
        category_field = _mapped_field(arguments, "category_field")
        indicators = arguments.get("indicator_fields") or []
        if (
            not isinstance(indicators, list)
            or len(indicators) < 3
            or len(indicators) > 12
        ):
            raise ChartValidationError(
                "radar indicator_fields must contain between 3 and 12 items"
            )
        normalized_indicators = []
        radar_rows = []
        maxima = []
        for item in indicators:
            if not isinstance(item, dict):
                raise ChartValidationError(
                    "each indicator_fields item must be an object"
                )
            field = _safe_text(item.get("field"), "indicator field", max_length=200)
            if not field:
                raise ChartValidationError("each indicator_fields item requires field")
            normalized_indicators.append(
                (
                    field,
                    _safe_text(
                        item.get("name") or field, "indicator name", max_length=200
                    ),
                )
            )
            maxima.append(0.0)
        for row_index, row in enumerate(rows):
            if category_field not in row:
                raise ChartValidationError(
                    f"field '{category_field}' is absent from source row {row_index + 1}"
                )
            values = []
            for indicator_index, (field, _) in enumerate(normalized_indicators):
                value = float(_required_number(row, field, row_index))
                if value < 0:
                    raise ChartValidationError("radar values must be non-negative")
                values.append(value)
                maxima[indicator_index] = max(maxima[indicator_index], value)
            radar_rows.append(
                {
                    "name": _safe_text(
                        row.get(category_field), category_field, max_length=200
                    ),
                    "value": values,
                }
            )
        indicator_config = [
            {"name": label, "max": max(1.0, maxima[index] * 1.1)}
            for index, (_, label) in enumerate(normalized_indicators)
        ]
        option = _with_chart_title(
            {
                "tooltip": {},
                "legend": {"bottom": 0},
                "radar": {"indicator": indicator_config},
                "series": [{"type": "radar", "data": radar_rows}],
            },
            arguments,
        )
        radar_fields = [field for field, _ in normalized_indicators]
        audit = _audit_data(
            source_tool=source_tool,
            source_type=source_type,
            fields=[category_field, *radar_fields],
            rows=rows,
            source_row_count=source_row_count,
            source_payload=source_payload,
            category_field=category_field,
            value_fields=radar_fields,
        )

    elif chart_type == "boxplot":
        category_field = _mapped_field(arguments, "category_field")
        value_field = _mapped_field(arguments, "value_field")
        if aggregation_meta.get("type") == "boxplot":
            required_stats = (
                "box_lower",
                "box_q1",
                "box_median",
                "box_q3",
                "box_upper",
            )
            categories = []
            box_data = []
            for index, row in enumerate(rows):
                if category_field not in row:
                    raise ChartValidationError(
                        f"field '{category_field}' is absent from source row {index + 1}"
                    )
                categories.append(
                    _safe_text(row.get(category_field), category_field, max_length=200)
                )
                box_data.append(
                    [_required_number(row, field, index) for field in required_stats]
                )
            option = _with_chart_title(
                {
                    "tooltip": {"trigger": "item"},
                    "xAxis": {
                        "type": "category",
                        "name": category_field,
                        "data": categories,
                    },
                    "yAxis": {"type": "value", "name": value_field},
                    "series": [
                        {"name": value_field, "type": "boxplot", "data": box_data}
                    ],
                },
                arguments,
            )
            audit_fields = [category_field, *required_stats]
            if rows and "sample_count" in rows[0]:
                audit_fields.append("sample_count")
            audit = _audit_data(
                source_tool=source_tool,
                source_type=source_type,
                fields=audit_fields,
                rows=rows,
                source_row_count=source_row_count,
                source_payload=source_payload,
                category_field=category_field,
                value_fields=[value_field],
            )
            spec = {
                "version": 1,
                "chartType": chart_type,
                "option": option,
                "height": height,
            }
            return spec, audit
        groups: dict[str, list[float]] = {}
        for index, row in enumerate(rows):
            if category_field not in row:
                raise ChartValidationError(
                    f"field '{category_field}' is absent from source row {index + 1}"
                )
            category = _safe_text(
                row.get(category_field), category_field, max_length=200
            )
            if value_field not in row:
                raise ChartValidationError(
                    f"field '{value_field}' is absent from source row {index + 1}"
                )
            value = _number_from_row(row.get(value_field), value_field)
            if value is not None:
                groups.setdefault(category, []).append(float(value))
        if not groups:
            raise ChartValidationError("boxplot source contains no numeric values")
        categories = list(groups)
        box_data = []
        outliers = []
        for category_index, category in enumerate(categories):
            values = sorted(groups[category])
            q1 = _percentile(values, 0.25)
            median = _percentile(values, 0.5)
            q3 = _percentile(values, 0.75)
            iqr = q3 - q1
            lower_candidates = [value for value in values if value >= q1 - 1.5 * iqr]
            upper_candidates = [value for value in values if value <= q3 + 1.5 * iqr]
            lower = min(lower_candidates) if lower_candidates else values[0]
            upper = max(upper_candidates) if upper_candidates else values[-1]
            box_data.append([lower, q1, median, q3, upper])
            outliers.extend(
                [
                    [category_index, value]
                    for value in values
                    if value < lower or value > upper
                ]
            )
        series: list[dict[str, Any]] = [
            {"name": value_field, "type": "boxplot", "data": box_data}
        ]
        if outliers:
            series.append({"name": "Outlier", "type": "scatter", "data": outliers})
        option = _with_chart_title(
            {
                "tooltip": {"trigger": "item"},
                "xAxis": {
                    "type": "category",
                    "name": category_field,
                    "data": categories,
                },
                "yAxis": {"type": "value", "name": value_field},
                "series": series,
            },
            arguments,
        )
        audit = _audit_data(
            source_tool=source_tool,
            source_type=source_type,
            fields=[category_field, value_field],
            rows=rows,
            source_row_count=source_row_count,
            source_payload=source_payload,
            category_field=category_field,
            value_fields=[value_field],
        )

    elif chart_type == "sankey":
        source_field = _mapped_field(arguments, "source_field")
        target_field = _mapped_field(arguments, "target_field")
        value_field = _mapped_field(arguments, "value_field")
        links: dict[tuple[str, str], float] = {}
        node_names: list[str] = []
        for index, row in enumerate(rows):
            if source_field not in row or target_field not in row:
                missing = source_field if source_field not in row else target_field
                raise ChartValidationError(
                    f"field '{missing}' is absent from source row {index + 1}"
                )
            source = _safe_text(row.get(source_field), source_field, max_length=200)
            target = _safe_text(row.get(target_field), target_field, max_length=200)
            if not source or not target or source == target:
                raise ChartValidationError(
                    "sankey source and target must be different non-empty values"
                )
            value = float(_required_number(row, value_field, index))
            if value <= 0:
                raise ChartValidationError("sankey values must be greater than zero")
            if source not in node_names:
                node_names.append(source)
            if target not in node_names:
                node_names.append(target)
            links[(source, target)] = links.get((source, target), 0.0) + value
        _ensure_acyclic_sankey(links)
        option = _with_chart_title(
            {
                "tooltip": {"trigger": "item"},
                "series": [
                    {
                        "type": "sankey",
                        "data": [{"name": name} for name in node_names],
                        "links": [
                            {"source": source, "target": target, "value": value}
                            for (source, target), value in links.items()
                        ],
                        "emphasis": {"focus": "adjacency"},
                        "lineStyle": {"curveness": 0.5},
                    }
                ],
            },
            arguments,
        )
        audit = _audit_data(
            source_tool=source_tool,
            source_type=source_type,
            fields=[source_field, target_field, value_field],
            rows=rows,
            source_row_count=source_row_count,
            source_payload=source_payload,
            category_field=f"{source_field} → {target_field}",
            value_fields=[value_field],
        )

    else:
        raise ChartValidationError(
            f"No structured builder exists for chart type '{chart_type}'"
        )

    spec = {"version": 1, "chartType": chart_type, "option": option, "height": height}
    return spec, audit


def _validate_safe_tree(
    value: Any, *, depth: int = 0, budget: list[int] | None = None
) -> None:
    budget = budget or [20_000]
    budget[0] -= 1
    if budget[0] < 0:
        raise ChartValidationError("chart option is too large")
    if depth > 20:
        raise ChartValidationError("chart option nesting is too deep")
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_KEYS:
                raise ChartValidationError(
                    f"chart option contains forbidden key '{key}'"
                )
            _validate_safe_tree(child, depth=depth + 1, budget=budget)
    elif isinstance(value, list):
        for child in value:
            _validate_safe_tree(child, depth=depth + 1, budget=budget)
    elif isinstance(value, str):
        lowered = value.strip().lower()
        if len(value) > 10_000:
            raise ChartValidationError("chart option contains an oversized string")
        if lowered.startswith(
            (
                "javascript:",
                "data:",
                "image://http://",
                "image://https://",
                "image://data:",
            )
        ):
            raise ChartValidationError(
                "chart option contains a forbidden external resource"
            )
    elif isinstance(value, float) and not math.isfinite(value):
        raise ChartValidationError("chart option contains a non-finite number")


def validate_echarts_spec(
    spec: Any, allowed_types: list[str] | None = None
) -> dict[str, Any]:
    """Validate legacy LLM-generated ECharts options before they reach the browser."""
    if not isinstance(spec, dict) or not isinstance(spec.get("option"), dict):
        raise ChartValidationError("chart spec must contain an option object")
    _validate_safe_tree(spec)
    height = int(spec.get("height") or 400)
    if not MIN_HEIGHT <= height <= MAX_HEIGHT:
        raise ChartValidationError(
            f"height must be between {MIN_HEIGHT} and {MAX_HEIGHT}"
        )
    series = spec["option"].get("series")
    if isinstance(series, dict):
        series = [series]
    if not isinstance(series, list) or not series or len(series) > MAX_SERIES:
        raise ChartValidationError(
            f"option.series must contain between 1 and {MAX_SERIES} items"
        )
    allowed = {item.lower() for item in (allowed_types or SAFE_CHART_TYPES)}
    total_points = 0
    for index, item in enumerate(series):
        if not isinstance(item, dict):
            raise ChartValidationError("each option.series item must be an object")
        chart_type = str(item.get("type") or "").strip().lower()
        logical_type = (
            "area"
            if chart_type == "line" and item.get("areaStyle") is not None
            else chart_type
        )
        if logical_type not in allowed or logical_type not in SAFE_CHART_TYPES:
            raise ChartValidationError(
                f"Chart type '{logical_type or '(missing)'}' is not allowed"
            )
        data = item.get("data") or []
        if not isinstance(data, list) or len(data) > MAX_POINTS_PER_SERIES:
            raise ChartValidationError(
                f"option.series[{index}].data exceeds the supported size"
            )
        total_points += len(data)
    if total_points > MAX_TOTAL_POINTS:
        raise ChartValidationError(
            f"chart cannot exceed {MAX_TOTAL_POINTS} total data points"
        )
    return {**spec, "height": height}


def register_chart_tool(registry: ToolRegistry, chart_binding: dict[str, Any]) -> bool:
    selection_mode = str(chart_binding.get("chart_selection_mode") or "auto").lower()
    configured = chart_binding.get("allowed_chart_types") or list(SAFE_CHART_TYPES)
    allowed_types = []
    for item in configured:
        normalized = str(item).strip().lower()
        if normalized in STRUCTURED_CHART_TYPES and normalized not in allowed_types:
            allowed_types.append(normalized)
    if not allowed_types:
        return False

    async def create_chart(arguments, context):
        source_tool = _safe_text(
            arguments.get("source_tool"), "source_tool", max_length=64
        )
        if not source_tool:
            raise ChartValidationError("source_tool is required")
        source_data = None
        if source_tool != "user":
            source_event = next(
                (
                    event
                    for event in reversed(registry.execution_log)
                    if event.get("name") == registry.normalize_name(source_tool)
                    and not event.get("is_error")
                ),
                None,
            )
            if source_event is None:
                raise ChartValidationError(
                    f"source tool '{source_tool}' has no successful result in this run"
                )
            source_payload = source_event.get("raw_output")
            if source_payload is None:
                try:
                    source_payload = json.loads(source_event.get("output") or "null")
                except json.JSONDecodeError as error:
                    raise ChartValidationError(
                        "source tool output is not structured JSON"
                    ) from error
            source_type = str(source_event.get("source") or "tool")
            chart_type = str(arguments.get("type") or "").strip().lower()
            if chart_type in BASIC_CHART_TYPES:
                chart_arguments, source_data = _chart_arguments_from_rows(
                    arguments, source_payload, source_tool, source_type
                )
                chart = build_chart_spec(chart_arguments, allowed_types)
            else:
                chart, source_data = _build_specialized_chart(
                    arguments, source_payload, source_tool, source_type, allowed_types
                )
        else:
            chart_arguments = arguments
            source_data = _user_chart_data(arguments)
            chart = build_chart_spec(chart_arguments, allowed_types)
        chart["source"] = source_tool
        chart["data"] = source_data
        context.metadata["chart"] = chart
        return {
            "status": "ready",
            "chartType": chart["chartType"],
            "source": source_tool,
            "rowCount": source_data["rowCount"],
        }

    source_tools = [spec.name for spec in registry.specs()] + ["user"]
    registry.register(
        ToolSpec(
            name="create_chart",
            description=(
                "Create a validated chart from numeric tabular data. For a tool result, pass source_tool, "
                "and exact field mappings; do not copy categories or numeric arrays. "
                "Mappings: basic charts use category_field+series_fields; gauge uses value_field; "
                "funnel/treemap use name_field+value_field; heatmap uses x_field+y_field+value_field; "
                "radar uses category_field+indicator_fields; boxplot uses category_field+value_field; "
                "sankey uses source_field+target_field+value_field. "
                "Use categories and series only when source_tool is 'user'. "
                + (
                    "Choose the most suitable allowed chart type. "
                    if selection_mode == "auto"
                    else "Use only the requested allowed chart type. "
                )
                + f"Allowed types: {', '.join(allowed_types)}."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": allowed_types},
                    "title": {"type": "string"},
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": MAX_POINTS_PER_SERIES,
                    },
                    "series": {
                        "type": "array",
                        "maxItems": MAX_SERIES,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "values": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "maxItems": MAX_POINTS_PER_SERIES,
                                },
                            },
                            "required": ["name", "values"],
                            "additionalProperties": False,
                        },
                    },
                    "x_axis_label": {"type": "string"},
                    "y_axis_label": {"type": "string"},
                    "height": {
                        "type": "integer",
                        "minimum": MIN_HEIGHT,
                        "maximum": MAX_HEIGHT,
                    },
                    "category_field": {
                        "type": "string",
                        "description": "Exact source row field to use as category labels. Required when source_tool is not 'user'.",
                    },
                    "series_fields": {
                        "type": "array",
                        "maxItems": MAX_SERIES,
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "name": {"type": "string"},
                            },
                            "required": ["field"],
                            "additionalProperties": False,
                        },
                        "description": "Exact numeric source row fields to plot. Required when source_tool is not 'user'.",
                    },
                    "name_field": {
                        "type": "string",
                        "description": "Category/name field for gauge, funnel, or treemap.",
                    },
                    "value_field": {
                        "type": "string",
                        "description": "Numeric value field for gauge, funnel, treemap, heatmap, boxplot, or sankey.",
                    },
                    "x_field": {
                        "type": "string",
                        "description": "X category field for heatmap.",
                    },
                    "y_field": {
                        "type": "string",
                        "description": "Y category field for heatmap.",
                    },
                    "indicator_fields": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 12,
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "name": {"type": "string"},
                            },
                            "required": ["field"],
                            "additionalProperties": False,
                        },
                        "description": "Three to twelve numeric dimensions for radar.",
                    },
                    "source_field": {
                        "type": "string",
                        "description": "Source node field for sankey.",
                    },
                    "target_field": {
                        "type": "string",
                        "description": "Target node field for sankey.",
                    },
                    "max_value": {
                        "type": "number",
                        "description": "Optional maximum scale for gauge.",
                    },
                    "row_limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_TABLE_ROWS,
                    },
                    "source_tool": {
                        "type": "string",
                        "enum": source_tools,
                        "description": "Exact name of the tool whose result contains these values, or 'user' when all values came directly from the user's message.",
                    },
                },
                "required": ["type", "source_tool"],
                "additionalProperties": False,
            },
            handler=create_chart,
            source="chart",
            max_output_chars=100_000,
        )
    )
    return True
