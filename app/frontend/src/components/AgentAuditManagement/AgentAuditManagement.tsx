import { useCallback, useEffect, useState } from "react";
import { Box, Button, Chip, CircularProgress, Paper, Stack, TextField, Typography } from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useMsal } from "@azure/msal-react";

import { listAgentAuditEventsApi } from "../../api/api";
import { AgentAuditEvent } from "../../api/models";
import { getToken } from "../../authConfig";

export function AgentAuditManagement() {
    const { instance } = useMsal();
    const [events, setEvents] = useState<AgentAuditEvent[]>([]);
    const [loading, setLoading] = useState(false);
    const [agentId, setAgentId] = useState("");
    const [runId, setRunId] = useState("");
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        setLoading(true);
        setError("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            setEvents(await listAgentAuditEventsApi({ agent_id: agentId.trim(), run_id: runId.trim(), hours: 24, limit: 300 }, token));
        } catch (value) {
            setError(value instanceof Error ? value.message : "Failed to load audit events");
        } finally {
            setLoading(false);
        }
    }, [agentId, instance, runId]);

    useEffect(() => {
        load();
    }, []);

    return (
        <Stack spacing={2} sx={{ pt: 1 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                    <Typography variant="h6">Agent Audit & Tracing</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Metadata-only events from the last 24 hours. Prompts, arguments, outputs and secrets are not stored.
                    </Typography>
                </Box>
                <Button startIcon={<RefreshIcon />} variant="outlined" onClick={load} disabled={loading}>
                    Refresh
                </Button>
            </Box>
            <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                <TextField size="small" label="Agent ID" value={agentId} onChange={event => setAgentId(event.target.value)} fullWidth />
                <TextField size="small" label="Run / Trace ID" value={runId} onChange={event => setRunId(event.target.value)} fullWidth />
                <Button variant="contained" onClick={load} disabled={loading}>
                    Apply
                </Button>
            </Stack>
            {error && <Typography color="error">{error}</Typography>}
            {loading ? (
                <Box textAlign="center" py={5}>
                    <CircularProgress />
                </Box>
            ) : (
                <Stack spacing={1} sx={{ overflowY: "auto" }}>
                    {events.map(event => (
                        <Paper key={event._id} variant="outlined" sx={{ p: 1.5 }}>
                            <Stack direction={{ xs: "column", md: "row" }} spacing={1} alignItems={{ md: "center" }}>
                                <Chip
                                    size="small"
                                    color={event.status === "ok" ? "success" : event.status === "policy_denied" ? "warning" : "error"}
                                    label={event.status}
                                />
                                <Typography fontWeight={600}>{event.event_type}</Typography>
                                {event.tool_name && <Chip size="small" variant="outlined" label={event.tool_name} />}
                                <Typography variant="caption" color="text.secondary" sx={{ ml: { md: "auto" } }}>
                                    {new Date(event.created_at).toLocaleString()}
                                </Typography>
                            </Stack>
                            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                                Agent {event.agent_id} · Run {event.run_id}
                                {event.parent_run_id ? ` · Parent ${event.parent_run_id}` : ""}
                            </Typography>
                            {Object.keys(event.details ?? {}).length > 0 && (
                                <Typography component="pre" variant="caption" sx={{ mt: 1, mb: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                                    {JSON.stringify(event.details, null, 2)}
                                </Typography>
                            )}
                        </Paper>
                    ))}
                    {!events.length && <Typography color="text.secondary">No audit events matched the filters.</Typography>}
                </Stack>
            )}
        </Stack>
    );
}
