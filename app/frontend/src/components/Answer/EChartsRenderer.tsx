import { Paper, Typography, IconButton, Tooltip } from "@mui/material";
import React, { Component, useEffect, useRef } from "react";
import ReactECharts from "echarts-for-react";
import type { ECharts } from "echarts";
import DownloadIcon from "@mui/icons-material/Download";
import "echarts-gl";
import { ChartDataPanel } from "./ChartDataPanel";

// ⭐ CHART CAPABILITY: EChartsRenderer
//    ใช้ Apache ECharts แทน MUI X Charts เพื่อความ Dynamic สูงสุด
//    รับ ECharts option object จาก backend/LLM แล้วส่งตรงไปยัง ReactECharts
//    รองรับทุกประเภทกราฟ, สี, gradient, 3D-like effects, animations ฯลฯ
//
//    Spec format: { option: { ...ECharts option... }, height?: number }

const containerSx = {
    mt: 1.5,
    borderRadius: 3,
    border: "1px solid #e0e0e0",
    boxShadow: "0 4px 10px rgba(0,0,0,0.06)",
    backgroundColor: "#fff",
    width: "100%",
    overflow: "hidden"
} as const;

interface EChartsRendererProps {
    spec: {
        option?: any;
        height?: number;
        [key: string]: any;
    };
}

// ── Error Boundary สำหรับจับ crash ของ ECharts ──────────────────────────
class EChartsErrorBoundary extends Component<
    { children: React.ReactNode },
    { hasError: boolean; message: string }
> {
    state = { hasError: false, message: "" };

    static getDerivedStateFromError(error: Error) {
        return { hasError: true, message: error?.message ?? "Unknown chart error" };
    }

    componentDidCatch(error: Error) {
        console.error("[EChartsRenderer] chart render failed:", error);
    }

    render() {
        if (this.state.hasError) {
            return (
                <Paper variant="outlined" sx={containerSx}>
                    <Typography variant="body2" color="error" sx={{ p: 2 }}>
                        Failed to render chart
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ px: 2, pb: 2, wordBreak: "break-all" }}>
                        {this.state.message}
                    </Typography>
                </Paper>
            );
        }
        return this.props.children;
    }
}

// ── Fallback: แปลงสเปกเก่า (MUI X Charts format) ให้เป็น ECharts option อัตโนมัติ ─────
function convertLegacySpecToECharts(spec: any): any {
    const { chartType, title, dataset, series, xAxis } = spec;

    if (chartType === "pie") {
        const pieData = series?.[0]?.data || [];
        return {
            title: title ? { text: title, left: "center", textStyle: { fontSize: 14 } } : undefined,
            tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
            legend: { bottom: 0 },
            series: [
                {
                    type: "pie",
                    radius: "60%",
                    data: pieData.map((item: any) => ({
                        value: item.value,
                        name: item.label,
                        itemStyle: item.color ? { color: item.color } : undefined
                    }))
                }
            ]
        };
    }

    // สำหรับ bar, line, area
    const xAxisKey = xAxis?.[0]?.dataKey;
    const xAxisData = Array.isArray(dataset) && xAxisKey ? dataset.map((d: any) => d[xAxisKey]) : [];

    return {
        title: title ? { text: title, left: "center", textStyle: { fontSize: 14 } } : undefined,
        tooltip: { trigger: "axis" },
        legend: { bottom: 0 },
        xAxis: { type: "category", data: xAxisData },
        yAxis: { type: "value" },
        series: Array.isArray(series)
            ? series.map((s: any) => ({
                  name: s.label || s.dataKey,
                  type: chartType === "area" ? "line" : chartType || "bar",
                  areaStyle: chartType === "area" ? { opacity: 0.3 } : undefined,
                  data: Array.isArray(dataset) ? dataset.map((d: any) => d[s.dataKey]) : [],
                  itemStyle: s.color ? { color: s.color } : undefined
              }))
            : []
    };
}

// ── Export หลัก ──────────────────────────────────────────────────────────
export function EChartsRenderer({ spec }: EChartsRendererProps) {
    if (!spec) return null;

    // ถ้าไม่มี option แต่มี chartType แปลว่าเป็นรูปแบบเก่า -> ให้ทำการแปลงก่อน
    const option = spec.option ? spec.option : convertLegacySpecToECharts(spec);
    if (!option) return null;

    // Show every category label and rotate long/crowded X-axis labels automatically.
    // This is renderer-side so it also applies to legacy and provider-generated specs.
    const xAxisLabelLayout = (() => {
        const axes = Array.isArray(option.xAxis) ? option.xAxis : option.xAxis ? [option.xAxis] : [];
        const categoryAxis = axes.find((axis: any) => axis?.type === "category" || Array.isArray(axis?.data));
        const labels = Array.isArray(categoryAxis?.data) ? categoryAxis.data.map((value: unknown) => String(value ?? "")) : [];
        const maxLength = labels.reduce((maximum: number, label: string) => Math.max(maximum, label.length), 0);
        const count = labels.length;

        let rotate = 0;
        if (count >= 12 || maxLength >= 24) rotate = 55;
        else if (count >= 7 || maxLength >= 12) rotate = 35;

        return {
            count,
            maxLength,
            rotate,
            requiredBottom: rotate ? Math.min(190, 60 + maxLength * (rotate >= 55 ? 4 : 3)) : 55
        };
    })();

    // ── คำนวณ height อัตโนมัติสำหรับ horizontal bar (yAxis = category) ──────
    // เพื่อให้ทุก item มีพื้นที่เพียงพอและไม่ถูกบีบเล็กลงเมื่อมีข้อมูลเยอะ
    const isHorizontalBar = (() => {
        const series = option.series;
        const firstSeries = Array.isArray(series) ? series[0] : series;
        const yAxisIsCategory =
            option.yAxis?.type === "category" ||
            (Array.isArray(option.yAxis) && option.yAxis[0]?.type === "category");
        return firstSeries?.type === "bar" && yAxisIsCategory;
    })();

    // ── detect multi-chart comparison (2+ charts ใน spec เดียว) ────────────
    // รองรับ: pie, bar, line, area, scatter, radar, heatmap, funnel, gauge, boxplot, candlestick
    const multiChartCount = (() => {
        const series = option.series;
        if (!Array.isArray(series)) return 1;

        // กรณี pie/funnel/sunburst/treemap — แต่ละ series คือ 1 chart ถ้ามี center ต่างกัน
        const positionedTypes = ["pie", "funnel", "sunburst", "treemap"];
        for (const t of positionedTypes) {
            const matched = series.filter((s: any) => s.type === t);
            if (matched.length > 1) return matched.length;
        }

        // กรณี gauge — แต่ละ series คือ 1 meter
        const gauges = series.filter((s: any) => s.type === "gauge");
        if (gauges.length > 1) return gauges.length;

        // กรณี bar/line/area/scatter/heatmap/boxplot/candlestick — ดูจาก multiple grid
        const gridCount = Array.isArray(option.grid) ? option.grid.length : 1;
        if (gridCount > 1) return gridCount;

        // กรณี radar — หลาย radar indicators ใน array
        const radarCount = Array.isArray(option.radar) ? option.radar.length : 1;
        if (radarCount > 1) return radarCount;

        return 1;
    })();

    const autoHeight = (() => {
        // horizontal bar: 40px/item
        if (isHorizontalBar) {
            const yAxisData =
                (Array.isArray(option.yAxis) ? option.yAxis[0]?.data : option.yAxis?.data) ?? [];
            const itemCount = yAxisData.length || 10;
            return Math.max(300, itemCount * 40 + 120);
        }
        // multi-chart comparison: 380px per chart
        if (multiChartCount > 1) {
            return Math.max(spec.height ?? 0, multiChartCount * 380);
        }
        // Rotated labels need extra vertical room so they do not overlap the legend.
        if (xAxisLabelLayout.rotate) {
            return Math.max(spec.height ?? 400, 400 + Math.min(120, xAxisLabelLayout.maxLength * 3));
        }
        return null;
    })();

    const chartHeight = Math.min(1200, Math.max(240, autoHeight ?? spec.height ?? 400));

    // ── Post-process option: enforce grid containLabel + minimum margins ──────
    // ป้องกัน label ถูกตัดขอบและกราฟล้นออกนอก container
    const safeOption = (() => {
        const opt = { ...option };

        if (opt.xAxis) {
            const axes = Array.isArray(opt.xAxis) ? opt.xAxis : [opt.xAxis];
            opt.xAxis = axes.map((axis: any) => {
                const isCategory = axis?.type === "category" || Array.isArray(axis?.data);
                if (!isCategory) return axis;
                const configuredRotation = Number(axis.axisLabel?.rotate || 0);
                return {
                    ...axis,
                    nameGap: axis.nameGap ?? 35,
                    axisTick: { ...axis.axisTick, alignWithLabel: true },
                    axisLabel: {
                        ...axis.axisLabel,
                        interval: 0,
                        hideOverlap: false,
                        rotate: Math.max(Math.abs(configuredRotation), xAxisLabelLayout.rotate),
                        fontSize: axis.axisLabel?.fontSize ?? 11,
                        margin: axis.axisLabel?.margin ?? 12
                    }
                };
            });
            if (!Array.isArray(option.xAxis)) opt.xAxis = opt.xAxis[0];
        }

        // enforce grid containLabel + right margin สำหรับ bar/line/area/scatter/heatmap
        if (opt.grid) {
            const grids = Array.isArray(opt.grid) ? opt.grid : [opt.grid];
            opt.grid = grids.map((g: any) => ({
                ...g,
                containLabel: true,
                right: g.right ?? "8%",
                left: g.left ?? "3%",
                bottom: xAxisLabelLayout.rotate ? xAxisLabelLayout.requiredBottom : (g.bottom ?? "10%"),
                top: g.top ?? "10%"
            }));
            if (!Array.isArray(option.grid)) opt.grid = opt.grid[0];
        } else if (opt.xAxis || opt.yAxis) {
            // มี axis แต่ไม่มี grid → inject grid default
            opt.grid = {
                containLabel: true,
                right: "8%",
                left: "3%",
                bottom: xAxisLabelLayout.rotate ? xAxisLabelLayout.requiredBottom : "10%",
                top: "10%"
            };
        }

        return opt;
    })();

    // ── Responsive: resize ECharts instance เมื่อ container width เปลี่ยน ──
    const chartRef = useRef<ReactECharts | null>(null);
    const containerRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        const observer = new ResizeObserver(() => {
            const instance: ECharts | undefined = chartRef.current?.getEchartsInstance();
            if (instance) {
                instance.resize();
            }
        });

        observer.observe(container);
        return () => observer.disconnect();
    }, []);

    // ── Download PNG ─────────────────────────────────────────────────────────
    const handleDownload = () => {
        const instance: ECharts | undefined = chartRef.current?.getEchartsInstance();
        if (!instance) return;
        // force resize ก่อน capture เพื่อให้ได้ขนาดจริง
        instance.resize();
        const url = instance.getDataURL({
            type: "png",
            pixelRatio: 2,
            backgroundColor: "#fff"
        });
        const link = document.createElement("a");
        link.href = url;
        link.download = `chart-${Date.now()}.png`;
        link.click();
    };

    return (
        <EChartsErrorBoundary>
            <Paper variant="outlined" sx={{ ...containerSx, position: "relative" }} ref={containerRef}>
                <Tooltip title="Download PNG" placement="top">
                    <IconButton
                        size="small"
                        onClick={handleDownload}
                        sx={{
                            position: "absolute",
                            top: 8,
                            right: 8,
                            zIndex: 10,
                            bgcolor: "rgba(255,255,255,0.85)",
                            backdropFilter: "blur(4px)",
                            border: "1px solid #e0e0e0",
                            "&:hover": { bgcolor: "#f5f5f5" }
                        }}
                    >
                        <DownloadIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
                <ReactECharts
                    ref={chartRef}
                    option={safeOption}
                    style={{ height: `${chartHeight}px`, width: "100%" }}
                    notMerge={true}
                    lazyUpdate={true}
                    opts={{ renderer: "canvas" }}
                />
                <ChartDataPanel data={spec.data} />
            </Paper>
        </EChartsErrorBoundary>
    );
}
