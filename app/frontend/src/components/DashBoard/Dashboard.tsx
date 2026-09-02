import React, { useEffect, useMemo, useState } from "react";
import {
    Alert, Box, Button as MuiButton, Chip, Dialog, DialogContent, DialogTitle,
    FormControl, InputLabel, MenuItem, Paper, Select, Skeleton, Stack, Tab,
    Tabs, TextField, Typography
} from "@mui/material";
import AnalyticsOutlinedIcon from "@mui/icons-material/AnalyticsOutlined";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import InputOutlinedIcon from "@mui/icons-material/InputOutlined";
import OutputOutlinedIcon from "@mui/icons-material/OutputOutlined";
import RefreshIcon from "@mui/icons-material/Refresh";
import { BarChart } from "@mui/x-charts/BarChart";
import { Button } from "@fluentui/react-components";
import { useMsal } from "@azure/msal-react";

import { getUsageAnalyticsApi, UsageAnalyticsParams } from "../../api/api";
import { getToken } from "../../authConfig";
import styles from "./Dashboard.module.css";

type Option = { value: string; label: string };
type Breakdown = {
    key: string; label: string; requests: number; input_tokens: number;
    output_tokens: number; reasoning_tokens: number; total_tokens: number;
};
type AnalyticsData = {
    scope: string;
    period: { from: string; to: string; bucket: string };
    overview: {
        requests: number; input_tokens: number; output_tokens: number;
        reasoning_tokens: number; total_tokens: number; documents: number;
        processed_pages: number; processing_duration_ms: number;
    };
    timeline: Array<Record<string, number | string>>;
    breakdowns: Record<string, Breakdown[]>;
    document_providers: Array<{
        key: string; label: string; documents: number; processed_pages: number;
        processing_duration_ms: number;
    }>;
    filter_options: Record<string, Option[]>;
};

interface Props {
    disabled?: boolean;
    className?: string;
    dialogRef?: React.RefObject<HTMLDivElement>;
    teamId?: string;
    teamName?: string;
    canViewSystem?: boolean;
    canViewTeam?: boolean;
}

const number = new Intl.NumberFormat("en-US");
const dateValue = (date: Date) => date.toISOString().slice(0, 10);

function MetricCard({ icon, label, value, loading }: {
    icon: React.ReactNode; label: string; value: number; loading: boolean;
}) {
    return (
        <Paper variant="outlined" sx={{ p: 2.25, borderRadius: 3, minWidth: 170, flex: 1 }}>
            <Stack direction="row" alignItems="center" spacing={1.5}>
                <Box sx={{ color: "primary.main", bgcolor: "action.hover", borderRadius: 2, p: 1, display: "flex" }}>{icon}</Box>
                <Box>
                    <Typography variant="caption" color="text.secondary" fontWeight={700}>{label}</Typography>
                    {loading ? <Skeleton width={90} /> : <Typography variant="h5" fontWeight={800}>{number.format(value)}</Typography>}
                </Box>
            </Stack>
        </Paper>
    );
}

function BreakdownTable({ title, rows }: { title: string; rows: Breakdown[] }) {
    return (
        <Paper variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
            <Typography sx={{ px: 2.5, py: 2, fontWeight: 800, borderBottom: "1px solid", borderColor: "divider" }}>{title}</Typography>
            {rows.length === 0 ? <Typography color="text.secondary" sx={{ p: 3 }}>No usage in this period.</Typography> : rows.slice(0, 10).map(row => (
                <Stack key={row.key} direction="row" alignItems="center" spacing={2} sx={{ px: 2.5, py: 1.5, borderBottom: "1px solid", borderColor: "divider" }}>
                    <Typography flex={1} noWrap title={row.label}>{row.label}</Typography>
                    <Chip size="small" label={`${number.format(row.requests)} requests`} variant="outlined" />
                    <Typography minWidth={110} textAlign="right" fontWeight={700}>{number.format(row.total_tokens)}</Typography>
                </Stack>
            ))}
        </Paper>
    );
}

export const Dashboard: React.FC<Props> = ({
    disabled, dialogRef, className, teamId = "", teamName = "",
    canViewSystem = false, canViewTeam = false
}) => {
    const client = useMsal().instance;
    const [open, setOpen] = useState(false);
    const [tab, setTab] = useState<"tokens" | "documents">("tokens");
    const [scope, setScope] = useState<UsageAnalyticsParams["scope"]>(canViewSystem ? "system" : canViewTeam && teamId ? "team" : "personal");
    const [from, setFrom] = useState(dateValue(new Date(Date.now() - 29 * 86400000)));
    const [to, setTo] = useState(dateValue(new Date()));
    const [bucket, setBucket] = useState<"day" | "week" | "month">("day");
    const [agentId, setAgentId] = useState("");
    const [selectedTeamId, setSelectedTeamId] = useState("");
    const [userId, setUserId] = useState("");
    const [provider, setProvider] = useState("");
    const [model, setModel] = useState("");
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const load = async () => {
        setLoading(true);
        setError("");
        try {
            const token = await getToken(client);
            if (!token) throw new Error("Authentication is required");
            const result = await getUsageAnalyticsApi(token, {
                scope,
                team_id: scope === "team" ? teamId : selectedTeamId || undefined,
                user_id: scope !== "personal" ? userId || undefined : undefined,
                from, to, bucket,
                agent_id: agentId || undefined,
                provider: provider || undefined,
                model: model || undefined
            });
            setData(result);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Unable to load usage analytics");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { if (open) void load(); }, [open, scope, from, to, bucket, selectedTeamId, userId, agentId, provider, model]);

    const overview = data?.overview ?? {
        requests: 0, input_tokens: 0, output_tokens: 0, reasoning_tokens: 0,
        total_tokens: 0, documents: 0, processed_pages: 0, processing_duration_ms: 0
    };
    const series = useMemo(() => tab === "tokens"
        ? [{ dataKey: "input_tokens", label: "Input", color: "#2563eb" }, { dataKey: "output_tokens", label: "Output", color: "#7c3aed" }]
        : [{ dataKey: "processed_pages", label: "Processed pages", color: "#0f766e" }], [tab]);
    const options = (kind: string) => data?.filter_options?.[kind] ?? [];

    return (
        <Box>
            <div className={`${styles.container} ${className ?? ""}`} ref={dialogRef}>
                <Button icon={<AnalyticsOutlinedIcon />} className="buttonText" onClick={() => setOpen(true)} disabled={disabled}>Usage Analytics</Button>
            </div>
            <Dialog open={open} onClose={() => setOpen(false)} maxWidth={false} PaperProps={{ sx: { width: "94vw", height: "92vh", borderRadius: 3 } }}>
                <DialogTitle sx={{ borderBottom: "1px solid", borderColor: "divider", py: 2.25 }}>
                    <Stack direction="row" alignItems="center" justifyContent="space-between">
                        <Box>
                            <Typography variant="h5" fontWeight={850}>Usage Analytics</Typography>
                            <Typography variant="body2" color="text.secondary">LLM and document activity without storing prompt or response content.</Typography>
                        </Box>
                        <MuiButton startIcon={<RefreshIcon />} onClick={() => void load()} disabled={loading}>Refresh</MuiButton>
                    </Stack>
                </DialogTitle>
                <DialogContent sx={{ bgcolor: "#f7f8fb", p: 3 }}>
                    <Stack spacing={3}>
                        <Paper variant="outlined" sx={{ p: 2, borderRadius: 3 }}>
                            <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
                                <FormControl size="small" sx={{ minWidth: 160 }}>
                                    <InputLabel>View</InputLabel>
                                    <Select value={scope} label="View" onChange={event => {
                                        setScope(event.target.value as UsageAnalyticsParams["scope"]);
                                        setSelectedTeamId("");
                                        setUserId("");
                                    }}>
                                        {canViewSystem && <MenuItem value="system">Entire system</MenuItem>}
                                        {canViewTeam && teamId && <MenuItem value="team">Team: {teamName || teamId}</MenuItem>}
                                        <MenuItem value="personal">My usage</MenuItem>
                                    </Select>
                                </FormControl>
                                <TextField size="small" type="date" label="From" value={from} onChange={event => setFrom(event.target.value)} InputLabelProps={{ shrink: true }} />
                                <TextField size="small" type="date" label="To" value={to} onChange={event => setTo(event.target.value)} InputLabelProps={{ shrink: true }} />
                                <FormControl size="small" sx={{ minWidth: 110 }}><InputLabel>Bucket</InputLabel><Select value={bucket} label="Bucket" onChange={event => setBucket(event.target.value as typeof bucket)}><MenuItem value="day">Daily</MenuItem><MenuItem value="week">Weekly</MenuItem><MenuItem value="month">Monthly</MenuItem></Select></FormControl>
                                {scope === "system" && <FormControl size="small" sx={{ minWidth: 150 }}><InputLabel>Team</InputLabel><Select value={selectedTeamId} label="Team" onChange={event => { setSelectedTeamId(event.target.value); setUserId(""); }}><MenuItem value="">All teams</MenuItem>{options("teams").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>}
                                {scope !== "personal" && <FormControl size="small" sx={{ minWidth: 150 }}><InputLabel>User</InputLabel><Select value={userId} label="User" onChange={event => setUserId(event.target.value)}><MenuItem value="">All users</MenuItem>{options("users").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>}
                                <FormControl size="small" sx={{ minWidth: 150 }}><InputLabel>Agent</InputLabel><Select value={agentId} label="Agent" onChange={event => setAgentId(event.target.value)}><MenuItem value="">All agents</MenuItem>{options("agents").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>
                                <FormControl size="small" sx={{ minWidth: 150 }}><InputLabel>Provider</InputLabel><Select value={provider} label="Provider" onChange={event => setProvider(event.target.value)}><MenuItem value="">All providers</MenuItem>{options("providers").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>
                                <FormControl size="small" sx={{ minWidth: 170 }}><InputLabel>Model</InputLabel><Select value={model} label="Model" onChange={event => setModel(event.target.value)}><MenuItem value="">All models</MenuItem>{options("models").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>
                            </Stack>
                        </Paper>
                        {error && <Alert severity="error">{error}</Alert>}
                        <Tabs value={tab} onChange={(_, value) => setTab(value)}><Tab value="tokens" label="LLM tokens" /><Tab value="documents" label="Document processing" /></Tabs>
                        <Stack direction="row" gap={2} flexWrap="wrap">
                            {tab === "tokens" ? <>
                                <MetricCard icon={<AutoAwesomeOutlinedIcon />} label="Requests" value={overview.requests} loading={loading} />
                                <MetricCard icon={<InputOutlinedIcon />} label="Input tokens" value={overview.input_tokens} loading={loading} />
                                <MetricCard icon={<OutputOutlinedIcon />} label="Output tokens" value={overview.output_tokens} loading={loading} />
                                <MetricCard icon={<AnalyticsOutlinedIcon />} label="Total tokens" value={overview.total_tokens} loading={loading} />
                            </> : <>
                                <MetricCard icon={<DescriptionOutlinedIcon />} label="Documents" value={overview.documents} loading={loading} />
                                <MetricCard icon={<AnalyticsOutlinedIcon />} label="Processed pages" value={overview.processed_pages} loading={loading} />
                            </>}
                        </Stack>
                        <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3 }}>
                            <Typography fontWeight={800} mb={1}>{tab === "tokens" ? "Token usage over time" : "Processed pages over time"}</Typography>
                            {loading ? <Skeleton height={320} /> : <BarChart height={320} dataset={data?.timeline ?? []} xAxis={[{ scaleType: "band", dataKey: "period" }]} series={series as any} />}
                        </Paper>
                        {tab === "tokens" ? (
                            <Box display="grid" gridTemplateColumns={{ xs: "1fr", lg: "1fr 1fr" }} gap={2}>
                                <BreakdownTable title="Models" rows={data?.breakdowns?.models ?? []} />
                                <BreakdownTable title="Agents" rows={data?.breakdowns?.agents ?? []} />
                                <BreakdownTable title="Teams" rows={data?.breakdowns?.teams ?? []} />
                                <BreakdownTable title="Users" rows={data?.breakdowns?.users ?? []} />
                            </Box>
                        ) : (
                            <Paper variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
                                <Typography sx={{ px: 2.5, py: 2, fontWeight: 800 }}>Processing providers</Typography>
                                {(data?.document_providers ?? []).map(row => <Stack key={row.key} direction="row" sx={{ px: 2.5, py: 1.5, borderTop: "1px solid", borderColor: "divider" }}><Typography flex={1}>{row.label}</Typography><Typography>{number.format(row.documents)} documents · {number.format(row.processed_pages)} pages</Typography></Stack>)}
                            </Paper>
                        )}
                    </Stack>
                </DialogContent>
            </Dialog>
        </Box>
    );
};
