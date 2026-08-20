import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Chip, CircularProgress, LinearProgress, Paper, Stack, Typography } from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import ReplayIcon from "@mui/icons-material/Replay";
import { useMsal } from "@azure/msal-react";

import { listIngestionJobsApi, retryIngestionJobApi } from "../../api/api";
import { IngestionJob, IngestionJobStatus as JobStatus } from "../../api/models";
import { getToken } from "../../authConfig";

interface Props {
    scope: "personal" | "team" | "global";
    teamId?: string;
    refreshKey?: number;
}

const activeStatuses = new Set<JobStatus>(["uploaded", "extracting", "chunking", "embedding"]);
const statusLabels: Record<JobStatus, string> = {
    uploaded: "Uploaded",
    extracting: "Extracting",
    chunking: "Chunking",
    embedding: "Embedding",
    indexed: "Indexed",
    failed: "Failed"
};

const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString() : "—";
const formatDuration = (job: IngestionJob) => {
    if (!job.started_at) return "";
    const end = job.completed_at ? new Date(job.completed_at).getTime() : Date.now();
    const seconds = Math.max(0, Math.round((end - new Date(job.started_at).getTime()) / 1000));
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
};

export function IngestionJobStatus({ scope, teamId = "", refreshKey = 0 }: Props) {
    const { instance } = useMsal();
    const [jobs, setJobs] = useState<IngestionJob[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [retryingId, setRetryingId] = useState("");

    const load = useCallback(async () => {
        const token = await getToken(instance);
        if (!token) throw new Error("No authentication token");
        const result = await listIngestionJobsApi(token, { scope, teamId, limit: 10 });
        setJobs(result);
        setError("");
        return result;
    }, [instance, scope, teamId]);

    useEffect(() => {
        let disposed = false;
        let timer: ReturnType<typeof setTimeout> | undefined;
        const poll = async () => {
            try {
                const result = await load();
                const hasRecentWork = result.some(job => activeStatuses.has(job.status) || job.status === "indexed");
                if (!disposed) timer = setTimeout(poll, hasRecentWork ? 3000 : 15000);
            } catch (loadError) {
                if (!disposed) {
                    setError(loadError instanceof Error ? loadError.message : "Failed to load ingestion jobs");
                    timer = setTimeout(poll, 15000);
                }
            } finally {
                if (!disposed) setLoading(false);
            }
        };
        void poll();
        return () => {
            disposed = true;
            if (timer) clearTimeout(timer);
        };
    }, [load, refreshKey]);

    const retry = async (job: IngestionJob) => {
        setRetryingId(job._id);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            await retryIngestionJobApi(job._id, token);
            await load();
        } catch (retryError) {
            setError(retryError instanceof Error ? retryError.message : "Failed to retry ingestion");
        } finally {
            setRetryingId("");
        }
    };

    return (
        <Box>
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
                <Box>
                    <Typography variant="subtitle1" fontWeight={700}>Recent processing jobs</Typography>
                    <Typography variant="caption" color="text.secondary">
                        Active and failed jobs appear here. Indexed jobs move to the file details after 1 minute.
                    </Typography>
                </Box>
                <Button size="small" startIcon={<RefreshIcon />} onClick={() => void load()} disabled={loading}>Refresh</Button>
            </Stack>
            {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
            {loading && !jobs.length ? (
                <Box display="flex" alignItems="center" gap={1} py={2}><CircularProgress size={18} /><Typography variant="body2">Loading jobs…</Typography></Box>
            ) : !jobs.length ? (
                <Typography variant="body2" color="text.secondary">No active or failed processing jobs in this scope.</Typography>
            ) : (
                <Stack spacing={1}>
                    {jobs.map(job => {
                        const active = activeStatuses.has(job.status);
                        return (
                            <Paper key={job._id} variant="outlined" sx={{ p: 1.5 }}>
                                <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1}>
                                    <Box minWidth={0} flex={1}>
                                        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                                            <Typography fontWeight={600} noWrap title={job.filename}>{job.filename}</Typography>
                                            <Chip
                                                size="small"
                                                label={statusLabels[job.status]}
                                                color={job.status === "indexed" ? "success" : job.status === "failed" ? "error" : "primary"}
                                                variant={active ? "filled" : "outlined"}
                                            />
                                            {job.attempt > 1 && <Chip size="small" label={`Attempt ${job.attempt}`} variant="outlined" />}
                                        </Stack>
                                        <Typography variant="caption" color="text.secondary" display="block" mt={0.5}>
                                            {job.provider_name || "System parser"}{job.profile_name ? ` · ${job.profile_name}` : ""}{job.rule_name ? ` · Rule: ${job.rule_name}` : ""}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary" display="block">
                                            Submitted {formatTime(job.created_at)}{job.completed_at ? ` · Finished ${formatTime(job.completed_at)}` : ""}{job.started_at ? ` · Duration ${formatDuration(job)}` : ""}
                                        </Typography>
                                        {active && <LinearProgress sx={{ mt: 1 }} aria-label={`${job.filename}: ${statusLabels[job.status]}`} />}
                                        {job.result_message && <Alert severity="info" sx={{ mt: 1, py: 0 }}>{job.result_message}</Alert>}
                                        {job.error && <Alert severity="error" sx={{ mt: 1, py: 0 }}>{job.error.message}</Alert>}
                                    </Box>
                                    {job.status === "failed" && (
                                        <Button
                                            size="small"
                                            startIcon={retryingId === job._id ? <CircularProgress size={14} /> : <ReplayIcon />}
                                            disabled={Boolean(retryingId)}
                                            onClick={() => void retry(job)}
                                        >
                                            Retry
                                        </Button>
                                    )}
                                </Stack>
                            </Paper>
                        );
                    })}
                </Stack>
            )}
        </Box>
    );
}
