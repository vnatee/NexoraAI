import { useCallback, useEffect, useState } from "react";
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Divider,
    Stack,
    Typography
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import StorageOutlinedIcon from "@mui/icons-material/StorageOutlined";
import HubOutlinedIcon from "@mui/icons-material/HubOutlined";
import WorkHistoryOutlinedIcon from "@mui/icons-material/WorkHistoryOutlined";
import MemoryOutlinedIcon from "@mui/icons-material/MemoryOutlined";
import { useMsal } from "@azure/msal-react";

import { getSystemHealthApi } from "../../api/api";
import { IntegrationKind, SystemHealthSnapshot, SystemHealthStatus } from "../../api/models";
import { getToken } from "../../authConfig";

const KIND_LABELS: Record<IntegrationKind, string> = {
    rest_api: "REST APIs",
    database: "Databases",
    mail: "Mail",
    messaging: "Messaging",
    mcp: "MCP",
    business_documents: "Business documents",
    web_search: "Web Search"
};

const statusColor = (status: SystemHealthStatus | "degraded") => {
    if (["healthy", "running"].includes(status)) return "success" as const;
    if (["degraded", "stopped"].includes(status)) return "warning" as const;
    if (status === "unavailable") return "error" as const;
    return "default" as const;
};

const resourceColor = (status: "healthy" | "warning" | "critical" | "unavailable") => {
    if (status === "healthy") return "success" as const;
    if (status === "warning") return "warning" as const;
    return "error" as const;
};

const formatBytes = (value: number) => {
    if (!Number.isFinite(value) || value <= 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
    return `${(value / 1024 ** index).toFixed(index >= 3 ? 1 : 0)} ${units[index]}`;
};

function Metric({ label, value, tone = "default" }: { label: string; value: number; tone?: "default" | "warning" | "error" }) {
    return (
        <Card variant="outlined" sx={{ minWidth: 150, borderColor: tone === "error" ? "error.light" : tone === "warning" ? "warning.light" : "divider" }}>
            <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
                <Typography variant="h5" fontWeight={700}>{value}</Typography>
                <Typography variant="body2" color="text.secondary">{label}</Typography>
            </CardContent>
        </Card>
    );
}

export function SystemHealthManagement() {
    const { instance } = useMsal();
    const [snapshot, setSnapshot] = useState<SystemHealthSnapshot | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const load = useCallback(async (showSpinner = true) => {
        if (showSpinner) setLoading(true);
        setError("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            setSnapshot(await getSystemHealthApi(token));
        } catch (value) {
            setError(value instanceof Error ? value.message : "Unable to load system health");
        } finally {
            if (showSpinner) setLoading(false);
        }
    }, [instance]);

    useEffect(() => {
        void load();
    }, [load]);

    return (
        <Stack spacing={2.5} sx={{ pt: 1 }}>
            <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "center" }} gap={1}>
                <Box>
                    <Typography variant="h6">System Health</Typography>
                    <Typography variant="body2" color="text.secondary">
                        On-demand system-wide snapshot. Data changes only when this page opens or you select Refresh.
                    </Typography>
                </Box>
                <Button startIcon={<RefreshIcon />} variant="outlined" onClick={() => void load()} disabled={loading}>Refresh</Button>
            </Stack>

            {error && <Alert severity="error">{error}</Alert>}
            {loading && !snapshot ? (
                <Box textAlign="center" py={6}><CircularProgress /></Box>
            ) : snapshot && (
                <>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ xs: "stretch", sm: "center" }}>
                        <Chip color={statusColor(snapshot.status)} label={`Overall · ${snapshot.status}`} sx={{ alignSelf: { xs: "flex-start", sm: "center" }, textTransform: "capitalize" }} />
                        <Typography variant="caption" color="text.secondary">
                            Last checked {new Date(snapshot.checked_at).toLocaleString()}
                        </Typography>
                    </Stack>

                    <Card variant="outlined">
                        <CardContent>
                            <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
                                <MemoryOutlinedIcon color="primary" />
                                <Typography fontWeight={700}>Runtime resources</Typography>
                                <Chip size="small" color={resourceColor(snapshot.resources.status)} label={snapshot.resources.status} sx={{ ml: "auto", textTransform: "capitalize" }} />
                            </Stack>
                            <Typography variant="caption" color="text.secondary" display="block" mb={2}>
                                {snapshot.resources.scope_label}. Container deployments may differ from physical host capacity.
                            </Typography>
                            {snapshot.resources.cpu && snapshot.resources.memory && snapshot.resources.disk ? (
                                <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 1.5 }}>
                                    <ResourceMetric
                                        label="CPU"
                                        percent={snapshot.resources.cpu.usage_percent}
                                        detail={`${snapshot.resources.cpu.logical_cores} logical cores${snapshot.resources.cpu.load_average_1m === null ? "" : ` · Load ${snapshot.resources.cpu.load_average_1m}`}`}
                                    />
                                    <ResourceMetric
                                        label="Memory"
                                        percent={snapshot.resources.memory.usage_percent}
                                        detail={`${formatBytes(snapshot.resources.memory.used_bytes)} / ${formatBytes(snapshot.resources.memory.total_bytes)}`}
                                    />
                                    <ResourceMetric
                                        label="Disk /"
                                        percent={snapshot.resources.disk.usage_percent}
                                        detail={`${formatBytes(snapshot.resources.disk.used_bytes)} / ${formatBytes(snapshot.resources.disk.total_bytes)}`}
                                    />
                                    <Card variant="outlined">
                                        <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
                                            <Typography variant="h5" fontWeight={700}>{formatBytes(snapshot.resources.process?.resident_memory_bytes ?? 0)}</Typography>
                                            <Typography variant="body2" color="text.secondary">Application memory</Typography>
                                        </CardContent>
                                    </Card>
                                </Box>
                            ) : (
                                <Alert severity="warning">Runtime resource metrics are unavailable.</Alert>
                            )}
                        </CardContent>
                    </Card>

                    <Card variant="outlined">
                        <CardContent>
                            <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                                <StorageOutlinedIcon color="primary" />
                                <Typography fontWeight={700}>Core services</Typography>
                            </Stack>
                            <Stack divider={<Divider flexItem />}>
                                {snapshot.services.map(service => (
                                    <Stack key={service.id} direction={{ xs: "column", md: "row" }} gap={1} py={1.25} alignItems={{ md: "center" }}>
                                        <Box flex={1}>
                                            <Typography fontWeight={600}>{service.name}</Typography>
                                            <Typography variant="body2" color="text.secondary">
                                                {[service.provider, service.detail].filter(Boolean).join(" · ")}
                                            </Typography>
                                        </Box>
                                        {service.latency_ms !== undefined && <Typography variant="body2" color="text.secondary">{service.latency_ms} ms</Typography>}
                                        <Chip size="small" color={statusColor(service.status)} label={service.status.replace("_", " ")} sx={{ textTransform: "capitalize" }} />
                                    </Stack>
                                ))}
                            </Stack>
                        </CardContent>
                    </Card>

                    <Card variant="outlined">
                        <CardContent>
                            <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                                <HubOutlinedIcon color="primary" />
                                <Typography fontWeight={700}>Integration health</Typography>
                            </Stack>
                            <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 1.5, mb: 2 }}>
                                <Metric label="Configured" value={snapshot.integrations.total} />
                                <Metric label="Enabled" value={snapshot.integrations.enabled} />
                                <Metric label="Disabled" value={snapshot.integrations.disabled} />
                                <Metric label="Needs attention" value={snapshot.integrations.attention} tone={snapshot.integrations.attention ? "warning" : "default"} />
                            </Box>
                            <Stack direction="row" gap={1} flexWrap="wrap">
                                {snapshot.integrations.by_kind.filter(item => item.total > 0).map(item => (
                                    <Chip key={item.kind} variant="outlined" label={`${KIND_LABELS[item.kind]} · ${item.total}`} color={item.attention ? "warning" : "default"} />
                                ))}
                                {!snapshot.integrations.total && <Typography variant="body2" color="text.secondary">No integrations configured.</Typography>}
                            </Stack>
                        </CardContent>
                    </Card>

                    <Card variant="outlined">
                        <CardContent>
                            <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                                <WorkHistoryOutlinedIcon color="primary" />
                                <Typography fontWeight={700}>Background jobs</Typography>
                            </Stack>
                            <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 2 }}>
                                <JobGroup title="Document ingestion" values={snapshot.jobs.ingestion} />
                                <JobGroup title="Chat attachments" values={snapshot.jobs.attachments} />
                            </Box>
                        </CardContent>
                    </Card>
                </>
            )}
        </Stack>
    );
}

function ResourceMetric({ label, percent, detail }: { label: string; percent: number; detail: string }) {
    const tone = percent >= 90 ? "error" : percent >= 80 ? "warning" : "success";
    return (
        <Card variant="outlined">
            <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="h5" fontWeight={700}>{percent.toFixed(1)}%</Typography>
                    <Chip size="small" color={tone} label={percent >= 90 ? "Critical" : percent >= 80 ? "Warning" : "Healthy"} />
                </Stack>
                <Typography variant="body2" fontWeight={600}>{label}</Typography>
                <Typography variant="caption" color="text.secondary">{detail}</Typography>
            </CardContent>
        </Card>
    );
}

function JobGroup({ title, values }: { title: string; values: { queued: number; processing: number; failed: number; worker_status: SystemHealthStatus; cleanup_status?: SystemHealthStatus } }) {
    return (
        <Box>
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
                <Typography fontWeight={650}>{title}</Typography>
                <Chip size="small" color={statusColor(values.worker_status)} label={`Worker · ${values.worker_status.replace("_", " ")}`} sx={{ textTransform: "capitalize" }} />
            </Stack>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                <Metric label="Queued" value={values.queued} />
                <Metric label="Processing" value={values.processing} />
                <Metric label="Failed" value={values.failed} tone={values.failed ? "error" : "default"} />
            </Stack>
            {values.cleanup_status && (
                <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                    Cleanup worker: {values.cleanup_status.replace("_", " ")}
                </Typography>
            )}
        </Box>
    );
}
