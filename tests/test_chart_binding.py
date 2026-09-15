import pytest

from mongo_table_connecters.chart_binding import _normalize_selection


def test_chart_binding_selection_is_normalized():
    assert _normalize_selection("manual", "line", ["bar", "line", "line"]) == (
        "manual",
        "line",
        ["bar", "line"],
    )


def test_chart_binding_rejects_invalid_mode_and_default():
    with pytest.raises(ValueError, match="chart_selection_mode"):
        _normalize_selection("free", "bar", ["bar"])
    with pytest.raises(ValueError, match="included"):
        _normalize_selection("manual", "pie", ["bar"])


def test_chart_binding_auto_mode_repairs_stale_default():
    assert _normalize_selection("auto", "candlestick", ["bar", "heatmap"]) == (
        "auto",
        "bar",
        ["bar", "heatmap"],
    )
