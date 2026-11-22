import React, { useEffect, useMemo, useRef, useState } from "react";
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
import AutorenewIcon from "@mui/icons-material/Autorenew";
import CloseIcon from "@mui/icons-material/Close";
import DownloadIcon from "@mui/icons-material/Download";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import { BarChart } from "@mui/x-charts/BarChart";
import { Button } from "@fluentui/react-components";
import { useMsal } from "@azure/msal-react";

import { exportUsageAnalyticsCsvApi, getUsageAnalyticsApi, UsageAnalyticsParams } from "../../api/api";
import { getToken } from "../../authConfig";
import styles from "./Dashboard.module.css";
import { UsagePricingPanel } from "./UsagePricingPanel";

type Option = { value: string; label: string };
type Breakdown = {
    key: string; label: string; requests: number; input_tokens: number;
    output_tokens: number; reasoning_tokens: number; total_tokens: number;
    estimated_cost_usd: number; pricing_coverage_percent: number;
};
type DocumentBreakdown = {
    key: string; label: string; documents: number; processed_pages: number;
    processing_duration_ms: number;
};
type AnalyticsData = {
    scope: string;
    period: { from: string; to: string; bucket: string };
    overview: {
        requests: number; input_tokens: number; output_tokens: number;
        reasoning_tokens: number; total_tokens: number; documents: number;
        processed_pages: number; processing_duration_ms: number;
        estimated_cost_usd: number; pricing_coverage_percent: number;
        priced_tokens: number; unpriced_tokens: number;
        priced_model_calls: number; unpriced_model_calls: number;
    };
    timeline: Array<Record<string, number | string>>;
    breakdowns: Record<string, Breakdown[]>;
    document_breakdowns: Record<string, DocumentBreakdown[]>;
    document_providers: Array<{
        key: string; label: string; documents: number; processed_pages: number;
        processing_duration_ms: number;
    }>;
    filter_options: Record<string, Option[]>;
    document_filter_options: Record<string, Option[]>;
};

interface Props {
    disabled?: boolean;
    className?: string;
    dialogRef?: React.RefObject<HTMLDivElement>;
    teamId?: string;
    teamName?: string;
    canViewSystem?: boolean;
    canViewTeam?: boolean;
    canManagePricing?: boolean;
    controlledOpen?: boolean;
    onControlledClose?: () => void;
    hideLauncher?: boolean;
}

const number = new Intl.NumberFormat("en-US");
const dateValue = (date: Date) => date.toISOString().slice(0, 10);

function MetricCard({ icon, label, value, loading }: {
    icon: React.ReactNode; label: string; value: number | string; loading: boolean;
}) {
    return (
        <Paper variant="outlined" sx={{ p: 2.25, borderRadius: 3, minWidth: 170, flex: 1 }}>
            <Stack direction="row" alignItems="center" spacing={1.5}>
                <Box sx={{ color: "primary.main", bgcolor: "action.hover", borderRadius: 2, p: 1, display: "flex" }}>{icon}</Box>
                <Box>
                    <Typography variant="caption" color="text.secondary" fontWeight={700}>{label}</Typography>
                    {loading ? <Skeleton width={90} /> : <Typography variant="h5" fontWeight={800}>{typeof value === "number" ? number.format(value) : value}</Typography>}
                </Box>
            </Stack>
        </Paper>
    );
}

function BreakdownTable({ title, rows, cost = false }: { title: string; rows: Breakdown[]; cost?: boolean }) {
    return (
        <Paper variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
            <Typography sx={{ px: 2.5, py: 2, fontWeight: 800, borderBottom: "1px solid", borderColor: "divider" }}>{title}</Typography>
            {rows.length === 0 ? <Typography color="text.secondary" sx={{ p: 3 }}>No usage in this period.</Typography> : rows.slice(0, 10).map(row => (
                <Stack key={row.key} direction="row" alignItems="center" spacing={2} sx={{ px: 2.5, py: 1.5, borderBottom: "1px solid", borderColor: "divider" }}>
                    <Typography flex={1} noWrap title={row.label}>{row.label}</Typography>
                    <Chip size="small" label={`${number.format(row.requests)} requests`} variant="outlined" />
                    <Typography minWidth={110} textAlign="right" fontWeight={700}>
                        {cost ? `$${row.estimated_cost_usd.toFixed(4)}` : number.format(row.total_tokens)}
                    </Typography>
                    {cost && <Chip size="small" color={row.pricing_coverage_percent === 100 ? "success" : "warning"} label={`${row.pricing_coverage_percent}% priced`} />}
                </Stack>
            ))}
        </Paper>
    );
}

function DocumentBreakdownTable({ title, rows }: { title: string; rows: DocumentBreakdown[] }) {
    return (
        <Paper variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
            <Typography sx={{ px: 2.5, py: 2, fontWeight: 800, borderBottom: "1px solid", borderColor: "divider" }}>{title}</Typography>
            {rows.length === 0 ? <Typography color="text.secondary" sx={{ p: 3 }}>No processing usage in this period.</Typography> : rows.slice(0, 10).map(row => (
                <Stack key={row.key} direction="row" alignItems="center" spacing={2} sx={{ px: 2.5, py: 1.5, borderBottom: "1px solid", borderColor: "divider" }}>
                    <Typography flex={1} noWrap title={row.label}>{row.label}</Typography>
                    <Chip size="small" label={`${number.format(row.documents)} documents`} variant="outlined" />
                    <Typography minWidth={90} textAlign="right" fontWeight={700}>{number.format(row.processed_pages)} pages</Typography>
                </Stack>
            ))}
        </Paper>
    );
}

export const Dashboard: React.FC<Props> = ({
    disabled, dialogRef, className, teamId = "", teamName = "",
    canViewSystem = false, canViewTeam = false, canManagePricing = false, controlledOpen,
    onControlledClose, hideLauncher = false
}) => {
    const client = useMsal().instance;
    const [open, setOpen] = useState(false);
    const dialogOpen = controlledOpen ?? open;
    const closeDialog = () => controlledOpen === undefined ? setOpen(false) : onControlledClose?.();
    const [tab, setTab] = useState<"tokens" | "cost" | "documents" | "pricing">("tokens");
    const [scope, setScope] = useState<UsageAnalyticsParams["scope"]>(canViewSystem ? "system" : canViewTeam && teamId ? "team" : "personal");
    const [from, setFrom] = useState(dateValue(new Date(Date.now() - 29 * 86400000)));
    const [to, setTo] = useState(dateValue(new Date()));
    const [bucket, setBucket] = useState<"day" | "week" | "month">("day");
    const [agentId, setAgentId] = useState("");
    const [selectedTeamId, setSelectedTeamId] = useState("");
    const [userId, setUserId] = useState("");
    const [provider, setProvider] = useState("");
    const [model, setModel] = useState("");
    const [profileId, setProfileId] = useState("");
    const [routeType, setRouteType] = useState("");
    const [fileType, setFileType] = useState("");
    const [documentScope, setDocumentScope] = useState("");
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [autoRefresh, setAutoRefresh] = useState(false);
    const [exporting, setExporting] = useState(false);
    const loadSequence = useRef(0);
    const loadRef = useRef<() => Promise<void>>(async () => undefined);

    const analyticsParams = (): UsageAnalyticsParams => ({
        scope,
        team_id: scope === "team" ? teamId : selectedTeamId || undefined,
        user_id: scope !== "personal" ? userId || undefined : undefined,
        from, to, bucket,
        agent_id: agentId || undefined,
        provider: provider || undefined,
        model: model || undefined,
        profile_id: profileId || undefined,
        route_type: routeType || undefined,
        file_type: fileType || undefined,
        document_scope: documentScope || undefined
    });

    const load = async () => {
        if (tab === "pricing") return;
        const sequence = ++loadSequence.current;
        setLoading(true);
        setData(null);
        setError("");
        try {
            const token = await getToken(client);
            if (!token) throw new Error("Authentication is required");
            const result = await getUsageAnalyticsApi(token, analyticsParams());
            if (sequence !== loadSequence.current) return;
            setData(result);
        } catch (reason) {
            if (sequence !== loadSequence.current) return;
            setError(reason instanceof Error ? reason.message : "Unable to load usage analytics");
        } finally {
            if (sequence === loadSequence.current) setLoading(false);
        }
    };

    loadRef.current = load;

    useEffect(() => {
        const scopeIsAllowed = scope === "personal" || (scope === "system" && canViewSystem) || (scope === "team" && canViewTeam && Boolean(teamId));
        if (scopeIsAllowed) return;
        loadSequence.current += 1;
        setScope("personal");
        setSelectedTeamId("");
        setUserId("");
        setData(null);
    }, [scope, canViewSystem, canViewTeam, teamId]);

    useEffect(() => { if (dialogOpen) void load(); }, [dialogOpen, tab, scope, from, to, bucket, selectedTeamId, userId, agentId, provider, model, profileId, routeType, fileType, documentScope]);

    useEffect(() => {
        if (!dialogOpen || !autoRefresh) return;
        const interval = window.setInterval(() => {
            void loadRef.current();
        }, 30_000);
        return () => window.clearInterval(interval);
    }, [dialogOpen, autoRefresh]);

    const overview = data?.overview ?? {
        requests: 0, input_tokens: 0, output_tokens: 0, reasoning_tokens: 0,
        total_tokens: 0, documents: 0, processed_pages: 0, processing_duration_ms: 0,
        estimated_cost_usd: 0, pricing_coverage_percent: 0, priced_tokens: 0,
        unpriced_tokens: 0, priced_model_calls: 0, unpriced_model_calls: 0
    };
    const series = useMemo(() => tab === "cost"
        ? [{ dataKey: "estimated_cost_usd", label: "Estimated cost (USD)", color: "#b45309" }]
        : tab === "tokens"
            ? [{ dataKey: "input_tokens", label: "Input", color: "#2563eb" }, { dataKey: "output_tokens", label: "Output", color: "#7c3aed" }]
            : [{ dataKey: "processed_pages", label: "Processed pages", color: "#0f766e" }], [tab]);
    const options = (kind: string) => (tab === "documents" ? data?.document_filter_options?.[kind] : data?.filter_options?.[kind]) ?? [];
    const hasElevatedAnalyticsAccess = canViewSystem || canViewTeam;
    const dashboardLabel = hasElevatedAnalyticsAccess ? "Usage Analytics" : "My Usage";
    const dialogTitle = scope === "personal" ? "My Usage" : "Usage Analytics";

    const download = (blob: Blob, filename: string) => {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = filename;
        anchor.click();
        URL.revokeObjectURL(url);
    };

    const exportCsv = async () => {
        setExporting(true); setError("");
        try {
            const token = await getToken(client);
            if (!token) throw new Error("Authentication is required");
            download(await exportUsageAnalyticsCsvApi(token, analyticsParams()), `usage-cost-${from}-${to}.csv`);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Unable to export CSV");
        } finally { setExporting(false); }
    };

    const exportPdf = async () => {
        if (!data) return;
        setExporting(true); setError("");
        try {
            const { jsPDF } = await import("jspdf");
            const pdf = new jsPDF();
            pdf.setFontSize(18); pdf.text("NexoraAI Usage & Cost Report", 14, 18);
            pdf.setFontSize(10); pdf.text(`Scope: ${scope}   Period: ${from} to ${to}   Currency: USD`, 14, 27);
            pdf.text("Costs are estimates from the versioned Price Catalog, not provider invoices.", 14, 34);
            pdf.setFontSize(13); pdf.text("Summary", 14, 46);
            pdf.setFontSize(10);
            pdf.text(`Requests: ${number.format(overview.requests)}`, 14, 54);
            pdf.text(`Total tokens: ${number.format(overview.total_tokens)}`, 14, 61);
            pdf.text(`Estimated cost: $${overview.estimated_cost_usd.toFixed(6)}`, 14, 68);
            pdf.text(`Pricing coverage: ${overview.pricing_coverage_percent}%`, 14, 75);
            pdf.text(`Unpriced tokens: ${number.format(overview.unpriced_tokens)} (${number.format(overview.unpriced_model_calls)} calls)`, 14, 82);
            let y = 96;
            pdf.setFontSize(13); pdf.text("Top models", 14, y); y += 8; pdf.setFontSize(9);
            (data.breakdowns.models ?? []).slice(0, 12).forEach(row => {
                pdf.text(`${row.label}: ${number.format(row.total_tokens)} tokens | $${row.estimated_cost_usd.toFixed(6)} | ${row.pricing_coverage_percent}% priced`, 14, y);
                y += 6;
            });
            pdf.save(`usage-cost-${from}-${to}.pdf`);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Unable to export PDF");
        } finally { setExporting(false); }
    };

    return (
        <Box>
            {!hideLauncher && (
                <div className={`${styles.container} ${className ?? ""}`} ref={dialogRef}>
                    <Button icon={<AnalyticsOutlinedIcon />} className="buttonText" onClick={() => setOpen(true)} disabled={disabled}>{dashboardLabel}</Button>
                </div>
            )}
            <Dialog
                open={dialogOpen}
                onClose={(_event, reason) => {
                    if (reason === "backdropClick") return;
                    closeDialog();
                }}
                maxWidth={false}
                PaperProps={{ sx: { width: "94vw", height: "92vh", borderRadius: 3 } }}
            >
                <DialogTitle sx={{ borderBottom: "1px solid", borderColor: "divider", py: 2.25 }}>
                    <Stack direction={{ xs: "column", md: "row" }} alignItems={{ xs: "stretch", md: "center" }} justifyContent="space-between" gap={2}>
                        <Box>
                            <Typography variant="h5" fontWeight={850}>{dialogTitle}</Typography>
                            <Typography variant="body2" color="text.secondary">
                                {scope === "personal"
                                    ? "Your LLM and document activity without storing prompt or response content."
                                    : "LLM and document activity without storing prompt or response content."}
                            </Typography>
                        </Box>
                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                            <MuiButton
                                variant={autoRefresh ? "contained" : "outlined"}
                                startIcon={<AutorenewIcon />}
                                onClick={() => setAutoRefresh(current => !current)}
                            >
                                Auto refresh: {autoRefresh ? "On (30s)" : "Off"}
                            </MuiButton>
                            {tab !== "pricing" && <MuiButton variant="outlined" startIcon={<DownloadIcon />} onClick={() => void exportCsv()} disabled={loading || exporting}>Raw CSV</MuiButton>}
                            {tab !== "pricing" && <MuiButton variant="outlined" startIcon={<PictureAsPdfIcon />} onClick={() => void exportPdf()} disabled={loading || exporting || !data}>PDF report</MuiButton>}
                            <MuiButton variant="outlined" startIcon={<RefreshIcon />} onClick={() => void load()} disabled={loading}>
                                Refresh
                            </MuiButton>
                            <MuiButton startIcon={<CloseIcon />} onClick={closeDialog}>
                                Close
                            </MuiButton>
                        </Stack>
                    </Stack>
                </DialogTitle>
                <DialogContent sx={{ bgcolor: "#f7f8fb", p: 3 }}>
                    <Stack spacing={3}>
                        {tab !== "pricing" && <Paper variant="outlined" sx={{ p: 2, borderRadius: 3 }}>
                            <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
                                {hasElevatedAnalyticsAccess ? (
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
                                ) : (
                                    <Chip label="My usage" color="primary" variant="outlined" />
                                )}
                                <TextField size="small" type="date" label="From" value={from} onChange={event => setFrom(event.target.value)} InputLabelProps={{ shrink: true }} />
                                <TextField size="small" type="date" label="To" value={to} onChange={event => setTo(event.target.value)} InputLabelProps={{ shrink: true }} />
                                <FormControl size="small" sx={{ minWidth: 110 }}><InputLabel>Bucket</InputLabel><Select value={bucket} label="Bucket" onChange={event => setBucket(event.target.value as typeof bucket)}><MenuItem value="day">Daily</MenuItem><MenuItem value="week">Weekly</MenuItem><MenuItem value="month">Monthly</MenuItem></Select></FormControl>
                                {scope === "system" && <FormControl size="small" sx={{ minWidth: 150 }}><InputLabel>Team</InputLabel><Select value={selectedTeamId} label="Team" onChange={event => { setSelectedTeamId(event.target.value); setUserId(""); }}><MenuItem value="">All teams</MenuItem>{options("teams").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>}
                                {scope !== "personal" && <FormControl size="small" sx={{ minWidth: 150 }}><InputLabel>User</InputLabel><Select value={userId} label="User" onChange={event => setUserId(event.target.value)}><MenuItem value="">All users</MenuItem>{options("users").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>}
                                {(tab === "tokens" || tab === "cost") && <FormControl size="small" sx={{ minWidth: 150 }}><InputLabel>Agent</InputLabel><Select value={agentId} label="Agent" onChange={event => setAgentId(event.target.value)}><MenuItem value="">All agents</MenuItem>{options("agents").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>}
                                {(tab === "tokens" || tab === "cost") && <FormControl size="small" sx={{ minWidth: 170 }}><InputLabel>LLM route</InputLabel><Select value={routeType} label="LLM route" onChange={event => setRouteType(event.target.value)}><MenuItem value="">All routes</MenuItem>{options("routes").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>}
                                <FormControl size="small" sx={{ minWidth: 150 }}><InputLabel>Provider</InputLabel><Select value={provider} label="Provider" onChange={event => setProvider(event.target.value)}><MenuItem value="">All providers</MenuItem>{options("providers").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>
                                {tab !== "documents" ? (
                                    <FormControl size="small" sx={{ minWidth: 170 }}><InputLabel>Model</InputLabel><Select value={model} label="Model" onChange={event => setModel(event.target.value)}><MenuItem value="">All models</MenuItem>{options("models").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>
                                ) : (
                                    <>
                                        <FormControl size="small" sx={{ minWidth: 170 }}><InputLabel>Profile</InputLabel><Select value={profileId} label="Profile" onChange={event => setProfileId(event.target.value)}><MenuItem value="">All profiles</MenuItem>{options("profiles").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>
                                        <FormControl size="small" sx={{ minWidth: 140 }}><InputLabel>File type</InputLabel><Select value={fileType} label="File type" onChange={event => setFileType(event.target.value)}><MenuItem value="">All file types</MenuItem>{options("file_types").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>
                                        <FormControl size="small" sx={{ minWidth: 140 }}><InputLabel>Document scope</InputLabel><Select value={documentScope} label="Document scope" onChange={event => setDocumentScope(event.target.value)}><MenuItem value="">All scopes</MenuItem>{options("scopes").map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}</Select></FormControl>
                                    </>
                                )}
                            </Stack>
                        </Paper>}
                        {error && <Alert severity="error">{error}</Alert>}
                        <Tabs value={tab} onChange={(_, value) => {
                            setTab(value);
                            setAgentId("");
                            setProvider("");
                            setModel("");
                            setProfileId("");
                            setRouteType("");
                            setFileType("");
                            setDocumentScope("");
                        }}><Tab value="tokens" label="LLM tokens" /><Tab value="cost" label="Cost (USD)" /><Tab value="documents" label="Document processing" />{canManagePricing && <Tab value="pricing" label="Price catalog" />}</Tabs>
                        {tab === "pricing" ? <UsagePricingPanel visible={dialogOpen && tab === "pricing"} suggestions={data?.filter_options} /> : <>
                        <Stack direction="row" gap={2} flexWrap="wrap">
                            {tab === "tokens" ? <>
                                <MetricCard icon={<AutoAwesomeOutlinedIcon />} label="Requests" value={overview.requests} loading={loading} />
                                <MetricCard icon={<InputOutlinedIcon />} label="Input tokens" value={overview.input_tokens} loading={loading} />
                                <MetricCard icon={<OutputOutlinedIcon />} label="Output tokens" value={overview.output_tokens} loading={loading} />
                                <MetricCard icon={<AnalyticsOutlinedIcon />} label="Total tokens" value={overview.total_tokens} loading={loading} />
                            </> : tab === "cost" ? <>
                                <MetricCard icon={<AnalyticsOutlinedIcon />} label="Estimated cost (USD)" value={`$${overview.estimated_cost_usd.toFixed(6)}`} loading={loading} />
                                <MetricCard icon={<AutoAwesomeOutlinedIcon />} label="Pricing coverage" value={`${overview.pricing_coverage_percent}%`} loading={loading} />
                                <MetricCard icon={<InputOutlinedIcon />} label="Unpriced tokens" value={overview.unpriced_tokens} loading={loading} />
                                <MetricCard icon={<OutputOutlinedIcon />} label="Unpriced calls" value={overview.unpriced_model_calls} loading={loading} />
                            </> : <>
                                <MetricCard icon={<DescriptionOutlinedIcon />} label="Documents" value={overview.documents} loading={loading} />
                                <MetricCard icon={<AnalyticsOutlinedIcon />} label="Processed pages" value={overview.processed_pages} loading={loading} />
                            </>}
                        </Stack>
                        <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3 }}>
                            <Typography fontWeight={800} mb={1}>{tab === "cost" ? "Estimated cost over time" : tab === "tokens" ? "Token usage over time" : "Processed pages over time"}</Typography>
                            {loading ? <Skeleton height={320} /> : <BarChart height={320} dataset={data?.timeline ?? []} xAxis={[{ scaleType: "band", dataKey: "period" }]} series={series as any} />}
                        </Paper>
                        {tab === "tokens" || tab === "cost" ? (
                            <Box display="grid" gridTemplateColumns={{ xs: "1fr", lg: "1fr 1fr" }} gap={2}>
                                <BreakdownTable title="Models" rows={data?.breakdowns?.models ?? []} cost={tab === "cost"} />
                                <BreakdownTable title="Providers" rows={data?.breakdowns?.providers ?? []} cost={tab === "cost"} />
                                <BreakdownTable title="LLM routes" rows={data?.breakdowns?.routes ?? []} cost={tab === "cost"} />
                                <BreakdownTable title="Agents" rows={data?.breakdowns?.agents ?? []} cost={tab === "cost"} />
                                <BreakdownTable title="Teams" rows={data?.breakdowns?.teams ?? []} cost={tab === "cost"} />
                                {scope !== "personal" && <BreakdownTable title="Users" rows={data?.breakdowns?.users ?? []} cost={tab === "cost"} />}
                            </Box>
                        ) : (
                            <Box display="grid" gridTemplateColumns={{ xs: "1fr", lg: "1fr 1fr" }} gap={2}>
                                <DocumentBreakdownTable title="Processing providers" rows={data?.document_breakdowns?.providers ?? data?.document_providers ?? []} />
                                <DocumentBreakdownTable title="Processing profiles" rows={data?.document_breakdowns?.profiles ?? []} />
                                <DocumentBreakdownTable title="File types" rows={data?.document_breakdowns?.file_types ?? []} />
                                <DocumentBreakdownTable title="Document scopes" rows={data?.document_breakdowns?.scopes ?? []} />
                                {scope === "system" && <DocumentBreakdownTable title="Teams" rows={data?.document_breakdowns?.teams ?? []} />}
                                {scope !== "personal" && <DocumentBreakdownTable title="Users" rows={data?.document_breakdowns?.users ?? []} />}
                            </Box>
                        )}</>}
                    </Stack>
                </DialogContent>
            </Dialog>
        </Box>
    );
};
