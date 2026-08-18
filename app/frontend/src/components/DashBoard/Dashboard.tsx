import React, { useState, useEffect, ChangeEvent } from "react";

import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Box,
    Paper,
    Typography,
    Stack,
    FormControlLabel,
    Checkbox,
    LinearProgress,
    Divider
} from "@mui/material";
import { BarChart as MuiBarChart } from "@mui/x-charts/BarChart";
import { Button } from "@fluentui/react-components";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import ForumIcon from "@mui/icons-material/Forum";
import OutboxIcon from "@mui/icons-material/Outbox";
import styles from "./Dashboard.module.css";
import { listUsageApi, get_teams, list_doc_ai } from "../../api/api";
import { getToken } from "../../authConfig";
import { useMsal } from "@azure/msal-react";
import { Skeleton } from "@mui/material";
import MoveToInboxIcon from "@mui/icons-material/MoveToInbox";
import StorageIcon from "@mui/icons-material/Storage";
import InsertPageBreakIcon from "@mui/icons-material/InsertPageBreak";
import { FormControl, InputLabel, MenuItem, Select } from "@mui/material";
import { Team } from "../../api/models";
import { Pagination } from "@mui/material";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { DataGrid } from "@mui/x-data-grid";
import DocumentScannerIcon from "@mui/icons-material/DocumentScanner";
import PersonIcon from "@mui/icons-material/Person";

const BarChart = MuiBarChart as any;

function generateCurrentYearMonths() {
    const months = [];
    const currentYear = new Date().getFullYear();

    for (let i = 0; i < 12; i++) {
        const d = new Date(currentYear, i, 1);
        months.push(d);
    }
    return months;
}

function initializeDashboardTotals(records: any[]) {
    if (!records || records.length === 0) {
        return { totalMessages: 0, totalPrompt: 0, totalCompletion: 0 };
    }

    const totalMessages = records.length;
    const totalPrompt = records.reduce((sum, rec) => sum + rec.tokens_prompt_sum, 0);
    const totalCompletion = records.reduce((sum, rec) => sum + rec.tokens_completion_sum, 0);

    return { totalMessages, totalPrompt, totalCompletion };
}

function initializeDashboardData(records: any[], year: number, selectedGroup: string) {
    const monthLabels = generateCurrentYearMonths();

    // group ข้อมูลตาม group + เดือน
    const grouped = records.reduce((acc: Record<string, any>, rec) => {
        const d = new Date(rec.create_at);
        const matchYear = d.getFullYear() === year;
        const matchGroup = selectedGroup === "all" || rec.group?.name === selectedGroup;

        if (!matchYear || !matchGroup) return acc;

        const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
        if (!acc[key]) acc[key] = { prompt: 0, completion: 0, total: 0 };
        acc[key].prompt += rec.tokens_prompt_sum;
        acc[key].completion += rec.tokens_completion_sum;
        acc[key].total += rec.tokens_total_sum;
        return acc;
    }, {});

    // ✅ เติมข้อมูลให้ครบ 12 เดือน
    const monthlyData = monthLabels.map(date => {
        const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
        return {
            month: date.toLocaleString("en-US", { month: "short" }),
            prompt: grouped[key]?.prompt ?? 0,
            completion: grouped[key]?.completion ?? 0,
            total: grouped[key]?.total ?? 0
        };
    });

    const totalMessages = records.filter(rec => {
        const d = new Date(rec.create_at);
        return d.getFullYear() === year && (selectedGroup === "all" || rec.group?.name === selectedGroup);
    }).length;

    const totalPrompt = monthlyData.reduce((sum, d) => sum + d.prompt, 0);
    const totalCompletion = monthlyData.reduce((sum, d) => sum + d.completion, 0);

    return {
        totalMessages,
        totalPrompt,
        totalCompletion,
        monthlyData
    };
}

function StatCard({
    icon,
    label,
    value,
    color,
    loading = false
}: {
    icon: React.ReactNode;
    label: string;
    value: string | number;
    color: string;
    loading?: boolean;
}) {
    // Derive a slightly darker shade for the gradient
    return (
        <Paper
            elevation={0}
            sx={{
                flex: 1,
                p: 2.5,
                borderRadius: 3,
                background: `linear-gradient(135deg, ${color}ee 0%, ${color}aa 100%)`,
                color: "white",
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                justifyContent: "space-between",
                textAlign: "left",
                minHeight: 130,
                position: "relative",
                overflow: "hidden",
                border: `1px solid ${color}55`,
                boxShadow: `0 4px 24px ${color}44`,
                "&::after": {
                    content: '""',
                    position: "absolute",
                    right: -20,
                    top: -20,
                    width: 90,
                    height: 90,
                    borderRadius: "50%",
                    background: "rgba(255,255,255,0.1)",
                    pointerEvents: "none"
                }
            }}
        >
            {/* Icon badge */}
            <Box
                sx={{
                    bgcolor: "rgba(255,255,255,0.2)",
                    borderRadius: 2,
                    p: 0.8,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    mb: 1.5
                }}
            >
                {icon}
            </Box>

            {/* Value */}
            {loading ? (
                <Skeleton variant="text" width={60} height={40} sx={{ bgcolor: "rgba(255,255,255,0.4)" }} />
            ) : (
                <Typography variant="h4" fontWeight={800} lineHeight={1} letterSpacing="-0.5px">
                    {value}
                </Typography>
            )}

            {/* Label */}
            {loading ? (
                <Skeleton variant="text" width={100} sx={{ bgcolor: "rgba(255,255,255,0.4)" }} />
            ) : (
                <Typography variant="caption" sx={{ opacity: 0.85, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase", mt: 0.5 }}>
                    {label}
                </Typography>
            )}
        </Paper>
    );
}

/** Consistent section card wrapper with a coloured left-border accent */
function SectionCard({
    title,
    icon,
    children,
    accentColor = "#6366f1"
}: {
    title: string;
    icon: React.ReactNode;
    children: React.ReactNode;
    accentColor?: string;
}) {
    return (
        <Paper
            elevation={0}
            sx={{
                p: 2.5,
                borderRadius: 3,
                border: "1px solid",
                borderColor: "divider",
                position: "relative",
                overflow: "hidden",
                "&::before": {
                    content: '""',
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: 4,
                    height: "100%",
                    background: `linear-gradient(180deg, ${accentColor} 0%, ${accentColor}55 100%)`,
                    borderRadius: "3px 0 0 3px"
                }
            }}
        >
            <Box display="flex" alignItems="center" gap={1} mb={2}>
                <Box sx={{ color: accentColor, display: "flex" }}>{icon}</Box>
                <Typography variant="subtitle1" fontWeight={700} letterSpacing="-0.2px">
                    {title}
                </Typography>
            </Box>
            {children}
        </Paper>
    );
}

function formatFileSize(sizeInBytes: number): string {
    if (!sizeInBytes) return "0 B";

    const units = ["B", "KB", "MB", "GB", "TB"];
    let size = sizeInBytes;
    let i = 0;

    while (size >= 1024 && i < units.length - 1) {
        size /= 1024;
        i++;
    }

    return size.toFixed(2) + " " + units[i];
}

type UploadType = "group" | "public" | "personal";

function aggregateDocAiByUploadTypeCurrentYear(records: any[]) {
    const currentYear = new Date().getFullYear();

    const result: Record<UploadType, number> = {
        group: 0,
        public: 0,
        personal: 0
    };

    records.forEach(r => {
        const year = new Date(r.create_at).getFullYear();
        if (year !== currentYear) return;

        const type = r.upload_type as UploadType;

        if (type in result) {
            result[type] += r.ocr_pages || 0;
        }
    });

    return [
        { type: "Group", pages: result.group },
        { type: "Public", pages: result.public },
        { type: "Personal", pages: result.personal }
    ];
}

function formatNumber(value: number): string {
    return new Intl.NumberFormat("en-US", {
        notation: "compact",
        maximumFractionDigits: 1
    }).format(value);
}

function aggregateTokensByUserPerMonth(records: any[], year: number, group: string) {
    if (!records || records.length === 0) return { monthlyData: [], users: [] };

    const monthLabels = generateCurrentYearMonths();

    // filter records ตาม year + group
    const filtered = records.filter(rec => {
        const d = new Date(rec.create_at);
        const matchYear = d.getFullYear() === year;
        const matchGroup = group === "all" || rec.group?.name === group;
        return matchYear && matchGroup;
    });

    // เก็บ user ทั้งหมด
    const users = Array.from(new Set(filtered.map(r => r.user?.name ?? "Unknown")));

    // group ข้อมูลตาม user+month
    const grouped: Record<string, any> = {};
    filtered.forEach(rec => {
        const d = new Date(rec.create_at);
        const monthKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
        const user = rec.user?.name ?? "Unknown";
        const key = `${user}|${monthKey}`;
        if (!grouped[key]) grouped[key] = { user, month: monthKey, total: 0 };
        grouped[key].total += rec.tokens_total_sum;
    });

    // คืนค่า dataset ให้ BarChart
    const monthlyData = monthLabels.map(date => {
        const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
        const row: any = { month: date.toLocaleString("en-US", { month: "short" }) };

        users.forEach(user => {
            const key = `${user}|${monthKey}`;
            row[user] = grouped[key]?.total ?? 0;
        });

        return row;
    });

    return { monthlyData, users };
}

// helper function สุ่มเลข
function getRandomInt(min: number, max: number) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

// mock data generator
function generateMockData() {
    const users = Array.from({ length: 50 }, (_, i) => `user${i + 1}@example.com`);
    const groups = ["GID", "DIG", "HR", "Finance"];
    const records: any[] = [];

    const currentYear = new Date().getFullYear();

    users.forEach(user => {
        for (let month = 0; month < 12; month++) {
            // generate 1–3 records per user per month
            const recordCount = getRandomInt(1, 3);
            for (let i = 0; i < recordCount; i++) {
                const date = new Date(currentYear, month, getRandomInt(1, 28));

                records.push({
                    create_at: date.toISOString(),
                    user: { name: user },
                    group: { name: groups[getRandomInt(0, groups.length - 1)] },
                    tokens_prompt_sum: getRandomInt(100, 2000),
                    tokens_completion_sum: getRandomInt(50, 1500),
                    tokens_total_sum: getRandomInt(200, 3000)
                });
            }
        }
    });

    return records;
}

// mock top files data
function generateMockTopFiles(count = 20) {
    const files: any[] = [];
    for (let i = 1; i <= count; i++) {
        files.push({
            file: `file_${i}.pdf`,
            count: Math.floor(Math.random() * 50) + 1 // 1 - 50 ครั้ง
        });
    }
    return files;
}

function getUserMonthlyData(user: string, userMonthlyData: any[]) {
    return userMonthlyData.map(row => ({
        month: row.month,
        total: row[user] ?? 0
    }));
}

function aggregateTopFiles(records: any[], limit = 10) {
    if (!records || records.length === 0) return [];

    const counts: Record<string, number> = {};
    records.forEach(rec => {
        (rec.reference_files || []).forEach((file: string) => {
            counts[file] = (counts[file] || 0) + 1;
        });
    });

    return Object.entries(counts)
        .map(([file, count]) => ({ file, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, limit);
}

function aggregateDocAiByUser(records: any[]) {
    const map: Record<string, number> = {};

    records.forEach(r => {
        const user = r.user ?? "Unknown";
        map[user] = (map[user] || 0) + (r.ocr_pages || 0);
    });

    return Object.entries(map).map(([user, totalPages]) => ({
        user,
        totalPages
    }));
}

function aggregateDocAiSummary(records: any[], selectedGroup: string, selectedUploadType: string) {
    return records
        .filter(r => {
            const matchGroup = selectedGroup === "all" || r.group === selectedGroup;
            const matchType = selectedUploadType === "all" || r.upload_type === selectedUploadType;
            return matchGroup && matchType;
        })
        .reduce((sum, r) => sum + (r.ocr_pages || 0), 0);
}

interface Props {
    disabled?: boolean;
    className?: string;
    dialogRef?: React.RefObject<HTMLDivElement>;
}

export const Dashboard: React.FC<Props> = ({ disabled, dialogRef, className }) => {
    const client = useMsal().instance;
    const [open, setOpen] = React.useState(false);
    const handleOpen = () => setOpen(true);
    const handleClose = () => setOpen(false);
    const [data, setData] = React.useState<any[]>([]);
    const [totalChunk, setTotalChunk] = React.useState(0);
    const [totalSize, setTotalSize] = React.useState(0);
    const [loading, setLoading] = React.useState(true);
    const [selectedYear, setSelectedYear] = React.useState(new Date().getFullYear());
    const years = Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i);
    const [selectedSeries, setSelectedSeries] = React.useState<("prompt" | "completion" | "total")[]>(["prompt", "completion", "total"]);
    const [groups, setGroups] = React.useState<Team[]>([]);
    const [selectedGroup, setSelectedGroup] = React.useState<string>("all");
    const [userLimit, setUserLimit] = React.useState("10"); // default Top 10
    const theme = useTheme();
    const isXs = useMediaQuery(theme.breakpoints.down("sm")); // มือถือเล็ก
    const isSm = useMediaQuery(theme.breakpoints.between("sm", "md")); // แท็บเล็ต
    const chartHeight = isXs ? 220 : isSm ? 280 : 320;
    const [docAi, setDocAi] = React.useState<any>([]);
    // 🆕 filter สำหรับ Doc AI
    const [docAiGroup, setDocAiGroup] = useState<string>("all");
    const [docAiUploadType, setDocAiUploadType] = useState<string>("all");

    // สำหรับ User Chart
    const [selectedUserYear, setSelectedUserYear] = React.useState(new Date().getFullYear());
    const userYears = Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i);
    const [selectedUserGroup, setSelectedUserGroup] = React.useState<string>("all");
    const { monthlyData: userMonthlyData, users: userList } = aggregateTokensByUserPerMonth(data, selectedUserYear, selectedUserGroup);
    // ✅ ใช้ mock
    const [selectedUserMonth, setSelectedUserMonth] = useState<number | "all">("all");

    const docAiBarData = aggregateDocAiByUploadTypeCurrentYear(docAi);

    const months = [
        { value: "all", label: "All Months" },
        { value: 1, label: "January" },
        { value: 2, label: "February" },
        { value: 3, label: "March" },
        { value: 4, label: "April" },
        { value: 5, label: "May" },
        { value: 6, label: "June" },
        { value: 7, label: "July" },
        { value: 8, label: "August" },
        { value: 9, label: "September" },
        { value: 10, label: "October" },
        { value: 11, label: "November" },
        { value: 12, label: "December" }
    ];

    let displayedUsers = userList;
    const sortedUsers = userList
        .map(user => ({
            user,
            total: userMonthlyData.reduce((sum, row) => sum + (row[user] ?? 0), 0)
        }))
        .sort((a, b) => b.total - a.total);

    if (userLimit !== "all") {
        displayedUsers = sortedUsers.slice(0, Number(userLimit)).map(u => u.user);
    } else {
        displayedUsers = sortedUsers.map(u => u.user); // All
    }

    // pagination state
    const [page, setPage] = useState(1);
    const chartsPerPage = 10; // 2 rows * 5 cols
    const totalPages = Math.ceil(displayedUsers.length / chartsPerPage);

    const paginatedUsers = displayedUsers.slice((page - 1) * chartsPerPage, page * chartsPerPage);
    const [sumDocAiPages, setSumDocAiPages] = useState(0);

    // simple color palette
    const colors = ["#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#795548", "#f44336", "#00bcd4", "#8bc34a", "#ffc107", "#607d8b"];
    const rankColors = ["#FFD700", "#C0C0C0", "#CD7F32"]; // gold, silver, bronze

    const fetchDocAiData = async () => {
        const token = await getToken(client);
        if (!token) throw new Error("No authentication token");

        const res = await list_doc_ai(token);
        console.log("doc ai data:", res.data);

        const totalPages = res.data.reduce((sum: number, item: any) => sum + (item.ocr_pages || 0), 0);
        setSumDocAiPages(totalPages);
        setDocAi(res.data);
    };

    // 🆕 1) OCR Pages by User
    const docAiByUser = aggregateDocAiByUser(docAi);

    // 🆕 2) OCR Pages summary (group + upload_type)
    const docAiFilteredTotal = aggregateDocAiSummary(docAi, docAiGroup, docAiUploadType);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const token = await getToken(client);
                if (!token) throw new Error("No authentication token");
                const res = await listUsageApi(token); // 🚀 call API จริง
                setData(res.data ?? []);
                setTotalChunk(res.total_chunk ?? 0);
                setTotalSize(res.total_size ?? 0);

                // ✅ fetch teams for group filters
                const teamList = await get_teams(token);
                setGroups(teamList.result ?? []);
            } catch (err) {
                console.error("Failed to fetch usage data", err);
            } finally {
                setLoading(false);
            }
        };
        if (open) {
            fetchData();
            fetchDocAiData();
        }
    }, [open]);

    const { totalMessages, totalPrompt, totalCompletion } = initializeDashboardTotals(data);
    const { monthlyData } = initializeDashboardData(data, selectedYear, selectedGroup);
    const topFiles = aggregateTopFiles(data, 10);

    return (
        <Box>
            <div className={`${styles.container} ${className ?? ""}`} ref={dialogRef}>
                <Button
                    id="calloutButton"
                    icon={<UploadFileIcon />}
                    className="buttonText"
                    style={{ columnGap: "0.5rem" }}
                    onClick={() => setOpen(true)}
                    disabled={disabled}
                >
                    Dashboard
                </Button>
            </div>

            <Dialog
                open={open}
                onClose={handleClose}
                PaperProps={{
                    sx: {
                        width: "90vw", // กว้าง 90% ของ viewport
                        height: "90vh", // สูง 90% ของ viewport
                        maxWidth: "90vw", // กันไม่ให้ maxWidth บังคับอีก
                        maxHeight: "90vh"
                    }
                }}
            >
                <DialogTitle
                    sx={{
                        bgcolor: "action.hover",
                        display: "flex",
                        alignItems: "center",
                        gap: 1.5,
                        borderBottom: "1px solid",
                        borderColor: "divider",
                        py: 2,
                        position: "relative",
                        "&::after": {
                            content: '""',
                            position: "absolute",
                            bottom: -1,
                            left: 0,
                            width: 100,
                            height: 3,
                            background: "primary.main"
                        }
                    }}
                >
                    <StorageIcon color="primary" />
                    <Typography variant="h6" fontWeight={800} letterSpacing="-0.3px">
                        Dashboard Insight
                    </Typography>
                </DialogTitle>
                <DialogContent sx={{ p: 4, bgcolor: "rgba(0,0,0,0.01)" }}>
                    {/* SVG Gradients for Charts */}
                    <svg width="0" height="0" style={{ position: "absolute" }}>
                        <defs>
                            <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={theme.palette.primary.main} />
                                <stop offset="100%" stopColor={theme.palette.primary.light} stopOpacity={0.3} />
                            </linearGradient>
                            <linearGradient id="tokenGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#6366f1" />
                                <stop offset="100%" stopColor="#6366f133" />
                            </linearGradient>
                        </defs>
                    </svg>

                    <Stack spacing={4}>
                        <>
                            {/* StatCards */}
                            <Stack direction="row" flexWrap="wrap" gap={2.5}>
                                <Box flex={1} minWidth={180}>
                                    <StatCard
                                        icon={<ForumIcon fontSize="medium" />}
                                        label="Processed Messages"
                                        value={formatNumber(totalMessages)}
                                        color="#4caf50"
                                        loading={loading}
                                    />
                                </Box>
                                <Box flex={1} minWidth={180}>
                                    <StatCard
                                        icon={<InsertPageBreakIcon fontSize="medium" />}
                                        label="Total Chunk"
                                        value={formatNumber(totalChunk)}
                                        color="#9c27b0"
                                        loading={loading}
                                    />
                                </Box>
                                <Box flex={1} minWidth={180}>
                                    <StatCard
                                        icon={<StorageIcon fontSize="medium" />}
                                        label="Total Chunk Size"
                                        value={formatFileSize(totalSize)}
                                        color="#795548"
                                        loading={loading}
                                    />
                                </Box>
                                <Box flex={1} minWidth={180}>
                                    <StatCard
                                        icon={<MoveToInboxIcon fontSize="medium" />}
                                        label="Token Input"
                                        value={formatNumber(totalPrompt)}
                                        color="#2196f3"
                                        loading={loading}
                                    />
                                </Box>
                                <Box flex={1} minWidth={180}>
                                    <StatCard
                                        icon={<OutboxIcon fontSize="medium" />}
                                        label="Token Output"
                                        value={formatNumber(totalCompletion)}
                                        color="#ff9800"
                                        loading={loading}
                                    />
                                </Box>
                                <Box flex={1} minWidth={180}>
                                    <StatCard
                                        icon={<DocumentScannerIcon fontSize="medium" />}
                                        label="Doc Intelligence"
                                        value={formatNumber(sumDocAiPages)}
                                        color="#6366f1"
                                        loading={loading}
                                    />
                                </Box>
                            </Stack>

                            <Box
                                display="grid"
                                gap={3}
                                sx={{
                                    gridTemplateColumns: { xs: "1fr", lg: "2fr 1fr" }
                                }}
                            >
                                {/* Token Usage */}
                                <SectionCard title="Token Usage Timeline" icon={<OutboxIcon />} accentColor="#6366f1">
                                    {!loading && (
                                        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2} flexWrap="wrap" gap={2}>
                                            <Stack direction="row" spacing={1.5}>
                                                <FormControl size="small" sx={{ minWidth: 100 }}>
                                                    <InputLabel>Year</InputLabel>
                                                    <Select value={selectedYear} onChange={e => setSelectedYear(e.target.value)} label="Year">
                                                        {years.map(y => (
                                                            <MenuItem key={y} value={y}>
                                                                {y}
                                                            </MenuItem>
                                                        ))}
                                                    </Select>
                                                </FormControl>
                                                <FormControl size="small" sx={{ minWidth: 140 }}>
                                                    <InputLabel>Teams</InputLabel>
                                                    <Select value={selectedGroup} onChange={e => setSelectedGroup(e.target.value)} label="Group">
                                                        <MenuItem value="all">All Team</MenuItem>
                                                        {groups.map(g => (
                                                            <MenuItem key={g._id} value={g.name}>
                                                                {g.name}
                                                            </MenuItem>
                                                        ))}
                                                    </Select>
                                                </FormControl>
                                            </Stack>

                                            <Stack direction="row" flexWrap="wrap">
                                                {["prompt", "completion", "total"].map(type => (
                                                    <FormControlLabel
                                                        key={type}
                                                        control={
                                                            <Checkbox
                                                                size="small"
                                                                checked={selectedSeries.includes(type as any)}
                                                                onChange={e => {
                                                                    if (e.target.checked) setSelectedSeries(prev => [...prev, type as any]);
                                                                    else setSelectedSeries(prev => prev.filter(s => s !== type));
                                                                }}
                                                            />
                                                        }
                                                        label={
                                                            <Typography variant="caption" fontWeight={600} color="text.secondary">
                                                                {type === "prompt" ? "Input" : type === "completion" ? "Output" : "Total"}
                                                            </Typography>
                                                        }
                                                    />
                                                ))}
                                            </Stack>
                                        </Box>
                                    )}

                                    {loading ? (
                                        <Skeleton variant="rectangular" width="100%" sx={{ borderRadius: 3, height: 280 }} />
                                    ) : (
                                        <BarChart
                                            height={280}
                                            dataset={monthlyData}
                                            xAxis={[
                                                {
                                                    dataKey: "month",
                                                    tickLabelPlacement: "middle",
                                                    tick: { fontSize: 11, fontWeight: 600 }
                                                }
                                            ]}
                                            series={selectedSeries.map(type => ({
                                                dataKey: type,
                                                label: type === "prompt" ? "Input" : type === "completion" ? "Output" : "Total",
                                                color: type === "prompt" ? "#2196f3" : type === "completion" ? "#ff9800" : "#6366f1"
                                            }))}
                                            sx={{
                                                [`.MuiBarElement-root`]: {
                                                    fill: "url(#tokenGradient)",
                                                    rx: 4
                                                }
                                            }}
                                        />
                                    )}
                                </SectionCard>

                                {/* Top Referenced Files */}
                                <SectionCard title="Common Referenced Files" icon={<InsertDriveFileIcon />} accentColor="#f59e0b">
                                    {loading ? (
                                        <Skeleton variant="rectangular" width="100%" sx={{ borderRadius: 3, height: 300 }} />
                                    ) : (
                                        <Stack spacing={1.2} sx={{ maxHeight: 310, overflowY: "auto", pr: 0.5 }}>
                                            {topFiles.map((file, idx) => (
                                                <Box
                                                    key={file.file}
                                                    sx={{
                                                        p: 1.5,
                                                        display: "flex",
                                                        alignItems: "center",
                                                        gap: 1.5,
                                                        borderRadius: 2.5,
                                                        bgcolor: "action.hover",
                                                        border: "1px solid transparent",
                                                        transition: "all 0.2s",
                                                        "&:hover": { bgcolor: "white", boxShadow: "0 2px 8px rgba(0,0,0,0.05)", borderColor: "divider" }
                                                    }}
                                                >
                                                    <Box
                                                        sx={{
                                                            width: 28,
                                                            height: 28,
                                                            borderRadius: 1,
                                                            bgcolor: idx < 3 ? rankColors[idx] : "action.selected",
                                                            display: "flex",
                                                            alignItems: "center",
                                                            justifyContent: "center",
                                                            fontSize: "0.75rem",
                                                            fontWeight: 800,
                                                            color: idx < 3 ? "white" : "text.secondary"
                                                        }}
                                                    >
                                                        {idx + 1}
                                                    </Box>
                                                    <Box flex={1} minWidth={0}>
                                                        <Typography variant="body2" fontWeight={700} noWrap>
                                                            {file.file}
                                                        </Typography>
                                                        <Box display="flex" alignItems="center" gap={1}>
                                                            <LinearProgress
                                                                variant="determinate"
                                                                value={Math.min(100, (file.count / topFiles[0].count) * 100)}
                                                                sx={{ flex: 1, height: 4, borderRadius: 2, bgcolor: "divider" }}
                                                            />
                                                            <Typography variant="caption" fontWeight={700} color="text.secondary">
                                                                {file.count}
                                                            </Typography>
                                                        </Box>
                                                    </Box>
                                                </Box>
                                            ))}
                                        </Stack>
                                    )}
                                </SectionCard>
                            </Box>

                            <SectionCard title="Token Usage by User (Monthly)" icon={<PersonIcon />} accentColor="#9c27b0">
                                {!loading && (
                                    <Box display="flex" justifyContent="flex-start" alignItems="center" gap={2} mb={2}>
                                        {/* Year / Group / User Limit filters */}
                                        <FormControl size="small" sx={{ minWidth: 120 }}>
                                            <InputLabel id="user-year-select-label">Year</InputLabel>
                                            <Select
                                                labelId="user-year-select-label"
                                                value={selectedUserYear}
                                                onChange={e => setSelectedUserYear(e.target.value)}
                                            >
                                                {userYears.map(year => (
                                                    <MenuItem key={year} value={year}>
                                                        {year}
                                                    </MenuItem>
                                                ))}
                                            </Select>
                                        </FormControl>

                                        <FormControl size="small" sx={{ minWidth: 150 }}>
                                            <InputLabel id="user-month-select-label">Month</InputLabel>
                                            <Select
                                                labelId="user-month-select-label"
                                                value={selectedUserMonth}
                                                onChange={e => setSelectedUserMonth(e.target.value)}
                                            >
                                                {months.map(m => (
                                                    <MenuItem key={m.value} value={m.value}>
                                                        {m.label}
                                                    </MenuItem>
                                                ))}
                                            </Select>
                                        </FormControl>

                                        <FormControl size="small" sx={{ minWidth: 150 }}>
                                            <InputLabel id="user-group-select-label">Teams</InputLabel>
                                            <Select
                                                labelId="user-group-select-label"
                                                value={selectedUserGroup}
                                                onChange={e => setSelectedUserGroup(e.target.value)}
                                            >
                                                <MenuItem value="all">All Teams</MenuItem>
                                                {groups.map(g => (
                                                    <MenuItem key={g._id} value={g.name}>
                                                        {g.name}
                                                    </MenuItem>
                                                ))}
                                            </Select>
                                        </FormControl>

                                        <FormControl size="small" sx={{ minWidth: 150 }}>
                                            <InputLabel id="user-limit-label">Users</InputLabel>
                                            <Select labelId="user-limit-label" value={userLimit} onChange={e => setUserLimit(e.target.value)}>
                                                <MenuItem value="5">Top 5</MenuItem>
                                                <MenuItem value="10">Top 10</MenuItem>
                                                <MenuItem value="20">Top 20</MenuItem>
                                                <MenuItem value="all">All Users</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </Box>
                                )}

                                {loading ? (
                                    <Skeleton variant="rectangular" width="100%" height={250} />
                                ) : (
                                    <Box sx={{ height: 500, width: "100%" }}>
                                        <DataGrid
                                            rows={
                                                displayedUsers.map((user, idx) => {
                                                    const userRecords = data.filter(rec => {
                                                        const d = new Date(rec.create_at);
                                                        const month = d.getMonth() + 1;
                                                        const matchYear = d.getFullYear() === selectedUserYear;
                                                        const matchMonth = selectedUserMonth === "all" || month === selectedUserMonth;
                                                        const matchGroup = selectedUserGroup === "all" || rec.group?.name === selectedUserGroup;
                                                        const matchUser = rec.user?.name === user;
                                                        return matchYear && matchMonth && matchGroup && matchUser;
                                                    });

                                                    const totalPrompt = userRecords.reduce((sum, rec) => sum + parseFloat(rec.tokens_prompt_sum ?? 0), 0);
                                                    const totalCompletion = userRecords.reduce(
                                                        (sum, rec) => sum + parseFloat(rec.tokens_completion_sum ?? 0),
                                                        0
                                                    );
                                                    const total = userRecords.reduce((sum, rec) => sum + parseFloat(rec.tokens_total_sum ?? 0), 0);

                                                    const groupName = userRecords[0]?.group?.name ?? "-";

                                                    return {
                                                        id: idx + 1,
                                                        user,
                                                        group: groupName,
                                                        token_input: Number(totalPrompt),
                                                        token_output: Number(totalCompletion),
                                                        token_total: Number(total)
                                                    };
                                                }) ?? []
                                            }
                                            columns={[
                                                { field: "user", headerName: "User", flex: 2, minWidth: 180 },
                                                { field: "group", headerName: "Teams", flex: 1, minWidth: 120 },
                                                {
                                                    field: "token_input",
                                                    headerName: "Token for Input",
                                                    flex: 1,
                                                    minWidth: 120,
                                                    renderCell: params => (isNaN(params.value) ? "-" : formatNumber(params.value))
                                                },
                                                {
                                                    field: "token_output",
                                                    headerName: "Token for Output",
                                                    flex: 1,
                                                    minWidth: 120,
                                                    renderCell: params => (isNaN(params.value) ? "-" : formatNumber(params.value))
                                                },
                                                {
                                                    field: "token_total",
                                                    headerName: "Total Token",
                                                    flex: 1,
                                                    minWidth: 120,
                                                    renderCell: params => (isNaN(params.value) ? "-" : formatNumber(params.value))
                                                }
                                            ]}
                                            initialState={{
                                                pagination: { paginationModel: { page: 0, pageSize: 10 } }
                                            }}
                                            pageSizeOptions={[5, 10, 20]}
                                            disableRowSelectionOnClick
                                            sx={{
                                                border: "none",
                                                "& .MuiDataGrid-columnHeaders": {
                                                    backgroundColor: "action.hover",
                                                    fontWeight: 700
                                                },
                                                "& .MuiDataGrid-footerContainer": {
                                                    borderTop: "1px solid",
                                                    borderColor: "divider"
                                                }
                                            }}
                                        />
                                    </Box>
                                )}
                            </SectionCard>

                            <SectionCard title="Document AI Usage by User" icon={<DocumentScannerIcon />} accentColor="#2196f3">
                                <Box sx={{ width: "100%" }}>
                                    <DataGrid
                                        autoHeight
                                        rows={docAiByUser.map((r, i) => ({
                                            id: i + 1,
                                            user: r.user,
                                            pages: r.totalPages
                                        }))}
                                        columns={[
                                            { field: "user", headerName: "User", flex: 2 },
                                            {
                                                field: "pages",
                                                headerName: "OCR Pages",
                                                flex: 1,
                                                renderCell: p => (
                                                    <Typography variant="body2" fontWeight={600}>
                                                        {formatNumber(p.value)}
                                                    </Typography>
                                                )
                                            }
                                        ]}
                                        initialState={{
                                            pagination: { paginationModel: { page: 0, pageSize: 10 } }
                                        }}
                                        pageSizeOptions={[5, 10, 20]}
                                        disableRowSelectionOnClick
                                        sx={{
                                            border: "none",
                                            "& .MuiDataGrid-columnHeaders": {
                                                backgroundColor: "action.hover"
                                            }
                                        }}
                                    />
                                </Box>
                            </SectionCard>

                            <SectionCard title="Document AI Usage (Current Year)" icon={<DocumentScannerIcon />} accentColor="#4caf50">
                                <BarChart
                                    height={280}
                                    dataset={docAiBarData}
                                    xAxis={[{ dataKey: "type", tickLabelPlacement: "middle" }]}
                                    yAxis={[
                                        {
                                            label: "OCR Pages",
                                            valueFormatter: (v: number) => v.toLocaleString("en-US")
                                        }
                                    ]}
                                    series={[{ dataKey: "pages", label: "OCR Pages", color: "#4caf50" }]}
                                    sx={{
                                        [`.MuiBarElement-root`]: {
                                            fill: "url(#barGradient)"
                                        }
                                    }}
                                />

                                {/* summary ใต้กราฟ */}
                                <Stack direction="row" justifyContent="space-around" mt={3} p={2} bgcolor="action.hover" borderRadius={2}>
                                    {docAiBarData.map(item => (
                                        <Box key={item.type} textAlign="center" sx={{ flex: 1 }}>
                                            <Typography variant="caption" color="text.secondary" fontWeight={700} textTransform="uppercase">
                                                {item.type}
                                            </Typography>
                                            <Typography variant="h6" fontWeight={800} color="primary.main">
                                                {formatNumber(item.pages)}
                                            </Typography>
                                        </Box>
                                    ))}
                                    <Divider orientation="vertical" flexItem sx={{ borderStyle: "dashed", mx: 1 }} />
                                    <Box textAlign="center" sx={{ flex: 1 }}>
                                        <Typography variant="caption" color="text.secondary" fontWeight={700} textTransform="uppercase">
                                            Total
                                        </Typography>
                                        <Typography variant="h6" fontWeight={800} color="#6366f1">
                                            {formatNumber(docAiBarData.reduce((sum, item) => sum + item.pages, 0))}
                                        </Typography>
                                    </Box>
                                </Stack>
                            </SectionCard>
                        </>
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleClose} color="primary">
                        Close
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};
