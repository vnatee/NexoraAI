import { Box, Card, CardContent, Typography, Stack, Chip } from "@mui/material";
import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";

interface Props {
    data: any[];
}

interface DateCount {
    date: string;
    count: number;
}

const DAYS_TH = ["อา.", "จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส."];
const MONTHS_TH = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];

/** Extract a YYYY-MM-DD string from any date-like value stored in MongoDB */
const extractDateKey = (raw: any): string => {
    if (!raw) return "Unknown";
    // unwrap { $date: "..." }
    const str: string = (raw && typeof raw === "object" && raw.$date)
        ? String(raw.$date)
        : String(raw);
    if (!str || str === "null" || str === "undefined") return "Unknown";
    try {
        const d = new Date(str);
        if (isNaN(d.getTime())) return "Unknown";
        // Use local date parts to avoid UTC-midnight shift issues
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const dd = String(d.getDate()).padStart(2, "0");
        return `${yyyy}-${mm}-${dd}`;
    } catch {
        return "Unknown";
    }
};

const formatDateLabel = (dateKey: string): string => {
    if (dateKey === "Unknown") return "ไม่ระบุวัน";
    try {
        const [y, m, d] = dateKey.split("-").map(Number);
        const date = new Date(y, m - 1, d);
        if (isNaN(date.getTime())) return dateKey;
        const dayName = DAYS_TH[date.getDay()];
        const monthName = MONTHS_TH[date.getMonth()];
        return `${dayName} ${d} ${monthName} ${y}`;
    } catch {
        return dateKey;
    }
};

const BAR_COLORS = [
    "linear-gradient(90deg, #6366f1, #818cf8)",
    "linear-gradient(90deg, #8b5cf6, #a78bfa)",
    "linear-gradient(90deg, #3b82f6, #60a5fa)",
    "linear-gradient(90deg, #10b981, #34d399)",
    "linear-gradient(90deg, #f59e0b, #fbbf24)",
];

const FeedbackByDateChart = ({ data }: Props) => {
    const result: Record<string, DateCount> = data.reduce((acc: Record<string, DateCount>, item: any) => {
        const rawField = item.create_at ?? item.created_at ?? item.date ?? item.createAt ?? null;
        const dateKey = extractDateKey(rawField);
        acc[dateKey] = acc[dateKey] || { date: dateKey, count: 0 };
        acc[dateKey].count++;
        return acc;
    }, {});

    const rows: DateCount[] = Object.values(result).sort((a, b) => {
        if (a.date === "Unknown") return 1;
        if (b.date === "Unknown") return -1;
        return b.date.localeCompare(a.date);
    });
    const maxCount = rows.length ? Math.max(...rows.map(r => r.count)) : 1;
    const total = rows.reduce((s, r) => s + r.count, 0);

    return (
        <Card
            sx={{
                borderRadius: 3,
                boxShadow: "0 4px 24px rgba(99,102,241,0.08)",
                height: 300,
                display: "flex",
                flexDirection: "column",
                border: "1px solid",
                borderColor: "divider",
                background: "linear-gradient(135deg, rgba(99,102,241,0.03) 0%, transparent 60%)"
            }}
        >
            <CardContent sx={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", pb: "16px !important" }}>

                {/* Header */}
                <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexShrink: 0, mb: 2 }}>
                    <Box>
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.3 }}>
                            <Box
                                sx={{
                                    width: 28, height: 28, borderRadius: 1.5,
                                    background: "linear-gradient(135deg, #6366f1, #818cf8)",
                                    display: "flex", alignItems: "center", justifyContent: "center"
                                }}
                            >
                                <CalendarMonthIcon sx={{ fontSize: 14, color: "white" }} />
                            </Box>
                            <Typography variant="h6" fontWeight={700} fontSize="1rem">
                                Feedback by Date
                            </Typography>
                        </Box>
                        <Typography variant="caption" color="text.secondary" sx={{ pl: 0.5 }}>
                            {total} items · {rows.filter(r => r.date !== "Unknown").length} day{rows.filter(r => r.date !== "Unknown").length !== 1 ? "s" : ""}
                        </Typography>
                    </Box>
                    <Chip
                        icon={<TrendingUpIcon sx={{ fontSize: 13 }} />}
                        label={`${rows.filter(r => r.date !== "Unknown").length} วัน`}
                        size="small"
                        sx={{
                            fontSize: "0.68rem", height: 22, fontWeight: 600,
                            background: "linear-gradient(135deg, #ede9fe, #ddd6fe)",
                            color: "#6366f1",
                            border: "none",
                            "& .MuiChip-icon": { color: "#6366f1" }
                        }}
                    />
                </Box>

                {/* Rows */}
                {rows.length === 0 ? (
                    <Box sx={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <Typography sx={{ opacity: 0.4, fontSize: "0.85rem" }}>ไม่มีข้อมูล</Typography>
                    </Box>
                ) : (
                    <Stack spacing={1.2} sx={{ flex: 1, overflowY: "auto", pr: 0.5 }}>
                        {rows.map((r, idx) => {
                            const pct = (r.count / maxCount) * 100;
                            const colorIdx = idx % BAR_COLORS.length;
                            return (
                                <Box key={r.date}>
                                    <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 0.5 }}>
                                        <Typography variant="body2" fontWeight={600} color="text.primary" fontSize="0.78rem">
                                            {formatDateLabel(r.date)}
                                        </Typography>
                                        <Box
                                            sx={{
                                                display: "flex", alignItems: "center", justifyContent: "center",
                                                minWidth: 24, height: 20, borderRadius: 1,
                                                background: BAR_COLORS[colorIdx],
                                                px: 0.8
                                            }}
                                        >
                                            <Typography variant="caption" fontWeight={700} color="white" fontSize="0.68rem">
                                                {r.count}
                                            </Typography>
                                        </Box>
                                    </Box>
                                    <Box sx={{ position: "relative", height: 7, borderRadius: 4, bgcolor: "action.hover", overflow: "hidden" }}>
                                        <Box
                                            sx={{
                                                position: "absolute", left: 0, top: 0, bottom: 0,
                                                width: `${pct}%`,
                                                borderRadius: 4,
                                                background: BAR_COLORS[colorIdx],
                                                transition: "width 0.7s cubic-bezier(.4,0,.2,1)",
                                                boxShadow: "0 2px 8px rgba(99,102,241,0.25)"
                                            }}
                                        />
                                    </Box>
                                </Box>
                            );
                        })}
                    </Stack>
                )}
            </CardContent>
        </Card>
    );
};

export default FeedbackByDateChart;
