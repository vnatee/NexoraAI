import { Card, CardContent, Typography, Stack, Box, Avatar, Chip } from "@mui/material";
import PeopleAltIcon from "@mui/icons-material/PeopleAlt";

interface Props {
    data: any[];
}

interface UserCount {
    name: string;
    count: number;
}

const avatarColor = (name: string) => {
    const colors = ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#ef4444"];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
};

const getInitials = (name: string) =>
    name.split(" ").map((n: string) => n[0]).slice(0, 2).join("").toUpperCase();

const BAR_GRADIENTS = [
    { bar: "linear-gradient(90deg, #6366f1, #818cf8)", bg: "rgba(99,102,241,0.08)" },
    { bar: "linear-gradient(90deg, #8b5cf6, #a78bfa)", bg: "rgba(139,92,246,0.08)" },
    { bar: "linear-gradient(90deg, #3b82f6, #60a5fa)", bg: "rgba(59,130,246,0.08)" },
    { bar: "linear-gradient(90deg, #10b981, #34d399)", bg: "rgba(16,185,129,0.08)" },
    { bar: "linear-gradient(90deg, #f59e0b, #fbbf24)", bg: "rgba(245,158,11,0.08)" },
    { bar: "linear-gradient(90deg, #ec4899, #f472b6)", bg: "rgba(236,72,153,0.08)" },
    { bar: "linear-gradient(90deg, #ef4444, #f87171)", bg: "rgba(239,68,68,0.08)" },
];

const FeedbackByUserChart = ({ data }: Props) => {
    const users: UserCount[] = Object.values(
        data.reduce((acc: Record<string, UserCount>, item: any) => {
            const name = item?.user?.name ?? "Unknown";
            acc[name] = acc[name] || { name, count: 0 };
            acc[name].count++;
            return acc;
        }, {})
    ).sort((a, b) => b.count - a.count);

    const maxValue = users.length ? Math.max(...users.map(u => u.count)) : 0;
    const total = users.reduce((s, u) => s + u.count, 0);

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
                background: "linear-gradient(135deg, rgba(139,92,246,0.03) 0%, transparent 60%)"
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
                                    background: "linear-gradient(135deg, #8b5cf6, #a78bfa)",
                                    display: "flex", alignItems: "center", justifyContent: "center"
                                }}
                            >
                                <PeopleAltIcon sx={{ fontSize: 14, color: "white" }} />
                            </Box>
                            <Typography variant="h6" fontWeight={700} fontSize="1rem">
                                Feedback by User
                            </Typography>
                        </Box>
                        <Typography variant="caption" color="text.secondary" sx={{ pl: 0.5 }}>
                            {total} items · {users.length} user{users.length !== 1 ? "s" : ""}
                        </Typography>
                    </Box>
                    <Chip
                        label={`${users.length} คน`}
                        size="small"
                        sx={{
                            fontSize: "0.68rem", height: 22, fontWeight: 600,
                            background: "linear-gradient(135deg, #f3e8ff, #ede9fe)",
                            color: "#8b5cf6",
                            border: "none"
                        }}
                    />
                </Box>

                {/* No data */}
                {users.length === 0 && (
                    <Box sx={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <Typography sx={{ opacity: 0.4, fontSize: "0.85rem" }}>ไม่มีข้อมูล</Typography>
                    </Box>
                )}

                {/* User rows */}
                <Stack spacing={1.2} sx={{ flex: 1, overflowY: "auto", pr: 0.5 }}>
                    {users.map((u, idx) => {
                        const pct = maxValue ? (u.count / maxValue) * 100 : 0;
                        const { bar, bg } = BAR_GRADIENTS[idx % BAR_GRADIENTS.length];
                        const color = avatarColor(u.name);
                        return (
                            <Box key={u.name}>
                                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                                    <Avatar
                                        sx={{
                                            width: 22, height: 22, fontSize: "0.62rem", fontWeight: 700,
                                            bgcolor: color, flexShrink: 0
                                        }}
                                    >
                                        {getInitials(u.name)}
                                    </Avatar>
                                    <Typography variant="body2" fontWeight={600} fontSize="0.78rem" noWrap sx={{ flex: 1 }}>
                                        {u.name}
                                    </Typography>
                                    <Box
                                        sx={{
                                            display: "flex", alignItems: "center", justifyContent: "center",
                                            minWidth: 24, height: 20, borderRadius: 1,
                                            background: bar, px: 0.8
                                        }}
                                    >
                                        <Typography variant="caption" fontWeight={700} color="white" fontSize="0.68rem">
                                            {u.count}
                                        </Typography>
                                    </Box>
                                </Box>
                                <Box sx={{ position: "relative", height: 7, borderRadius: 4, bgcolor: bg, overflow: "hidden" }}>
                                    <Box
                                        sx={{
                                            position: "absolute", left: 0, top: 0, bottom: 0,
                                            width: `${pct}%`,
                                            borderRadius: 4,
                                            background: bar,
                                            transition: "width 0.7s cubic-bezier(.4,0,.2,1)",
                                            boxShadow: "0 2px 8px rgba(139,92,246,0.2)"
                                        }}
                                    />
                                </Box>
                            </Box>
                        );
                    })}
                </Stack>
            </CardContent>
        </Card>
    );
};

export default FeedbackByUserChart;
