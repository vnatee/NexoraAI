import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
    Alert,
    Autocomplete,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControlLabel,
    IconButton,
    Stack,
    MenuItem,
    Switch,
    TextField,
    Tooltip,
    Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ContentCopyOutlinedIcon from "@mui/icons-material/ContentCopyOutlined";
import KeyOutlinedIcon from "@mui/icons-material/KeyOutlined";
import AutorenewOutlinedIcon from "@mui/icons-material/AutorenewOutlined";
import BlockOutlinedIcon from "@mui/icons-material/BlockOutlined";
import CloseIcon from "@mui/icons-material/Close";
import HelpOutlineOutlinedIcon from "@mui/icons-material/HelpOutlineOutlined";
import OpenInNewOutlinedIcon from "@mui/icons-material/OpenInNewOutlined";
import { useMsal } from "@azure/msal-react";

import {
    createAgentInvocationKey,
    getAgentInvocationKeys,
    revokeAgentInvocationKey,
    rotateAgentInvocationKey
} from "../../../api";
import {
    AgentInvocationKey,
    AgentInvocationKeyCreatePayload,
    AgentInvocationKeyOptions,
    TeamProfile
} from "../../../api/models";
import { getToken } from "../../../authConfig";
import { useNotification } from "../../../utill/NotificationProvider";

interface Props {
    team: TeamProfile | null;
    canManageExternalChannels?: boolean;
}

const EMPTY_OPTIONS: AgentInvocationKeyOptions = {
    items: [],
    available_agents: [],
    available_data_groups: [],
    available_external_data_groups: []
};

const DEFAULT_FORM: AgentInvocationKeyCreatePayload = {
    name: "",
    access_type: "internal_service",
    allowed_agent_ids: [],
    allowed_data_group_ids: [],
    allow_global_knowledge: false,
    expiry_days: 90,
    rate_limit_per_minute: 60
};

function formatDate(value?: string | null): string {
    if (!value) return "Never";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function keyStatus(item: AgentInvocationKey): { label: string; color: "success" | "error" | "warning" | "default" } {
    if (!item.active || item.revoked_at) return { label: "Revoked", color: "default" };
    if (new Date(item.expires_at).getTime() <= Date.now()) return { label: "Expired", color: "error" };
    const remaining = new Date(item.expires_at).getTime() - Date.now();
    if (remaining <= 7 * 24 * 60 * 60 * 1000) return { label: "Expiring soon", color: "warning" };
    return { label: "Active", color: "success" };
}

export function AgentApiAccessPage({ team, canManageExternalChannels = false }: Props) {
    const { instance } = useMsal();
    const { showNotification } = useNotification();
    const [options, setOptions] = useState<AgentInvocationKeyOptions>(EMPTY_OPTIONS);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [createOpen, setCreateOpen] = useState(false);
    const [guideOpen, setGuideOpen] = useState(false);
    const [secretOpen, setSecretOpen] = useState(false);
    const [secret, setSecret] = useState("");
    const [secretAgentId, setSecretAgentId] = useState("");
    const [form, setForm] = useState<AgentInvocationKeyCreatePayload>(DEFAULT_FORM);

    const agentNames = useMemo(
        () => new Map(options.available_agents.map(agent => [agent._id, agent.name])),
        [options.available_agents]
    );
    const groupNames = useMemo(
        () => new Map(
            [
                ...options.available_data_groups,
                ...options.available_external_data_groups
            ].map(group => [group._id, group.name])
        ),
        [options.available_data_groups, options.available_external_data_groups]
    );
    const availableKnowledgeGroups = form.access_type === "external_customer"
        ? options.available_external_data_groups
        : options.available_data_groups;

    const load = useCallback(async () => {
        if (!team?._id) return;
        setLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) return;
            setOptions(await getAgentInvocationKeys(team._id, token));
        } catch (error) {
            showNotification(error instanceof Error ? error.message : "Unable to load Agent API keys", "error");
        } finally {
            setLoading(false);
        }
    }, [instance, showNotification, team?._id]);

    useEffect(() => {
        void load();
    }, [load]);

    const revealSecret = (apiKey: string, agentId: string) => {
        setSecret(apiKey);
        setSecretAgentId(agentId);
        setSecretOpen(true);
    };

    const submitCreate = async () => {
        if (!team?._id || !form.name.trim() || form.allowed_agent_ids.length === 0) return;
        setSaving(true);
        try {
            const token = await getToken(instance);
            if (!token) return;
            const created = await createAgentInvocationKey(team._id, { ...form, name: form.name.trim() }, token);
            setCreateOpen(false);
            setForm(DEFAULT_FORM);
            revealSecret(created.api_key, created.item.allowed_agent_ids[0] || "");
            await load();
            showNotification("Agent API key created", "success");
        } catch (error) {
            showNotification(error instanceof Error ? error.message : "Unable to create Agent API key", "error");
        } finally {
            setSaving(false);
        }
    };

    const rotate = async (item: AgentInvocationKey) => {
        if (!team?._id || !window.confirm(`Rotate "${item.name}"? The current key will stop working immediately.`)) return;
        setSaving(true);
        try {
            const token = await getToken(instance);
            if (!token) return;
            const created = await rotateAgentInvocationKey(team._id, item._id, 90, token);
            revealSecret(created.api_key, created.item.allowed_agent_ids[0] || "");
            await load();
            showNotification("Agent API key rotated", "success");
        } catch (error) {
            showNotification(error instanceof Error ? error.message : "Unable to rotate Agent API key", "error");
        } finally {
            setSaving(false);
        }
    };

    const revoke = async (item: AgentInvocationKey) => {
        if (!team?._id || !window.confirm(`Revoke "${item.name}"? Applications using it will lose access immediately.`)) return;
        setSaving(true);
        try {
            const token = await getToken(instance);
            if (!token) return;
            await revokeAgentInvocationKey(team._id, item._id, token);
            await load();
            showNotification("Agent API key revoked", "success");
        } catch (error) {
            showNotification(error instanceof Error ? error.message : "Unable to revoke Agent API key", "error");
        } finally {
            setSaving(false);
        }
    };

    const copy = async (value: string) => {
        try {
            await navigator.clipboard.writeText(value);
            showNotification("Copied to clipboard", "success");
        } catch {
            showNotification("Unable to copy. Select and copy the text manually.", "error");
        }
    };

    if (!team) return <Alert severity="info">Select a Team to manage Agent API access.</Alert>;

    const curlExample = `curl -X POST "${window.location.origin}/api/v1/agents/${secretAgentId}/invoke" \\\n  -H "Authorization: Bearer ${secret}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"input":"Summarize the current policy."}'`;

    const guideAgentId = options.available_agents[0]?._id || "AGENT_ID";
    const guideSyncExample = [
        `curl -X POST "${window.location.origin}/api/v1/agents/${guideAgentId}/invoke" \\`,
        '  -H "Authorization: Bearer $NEXORA_API_KEY" \\',
        '  -H "Content-Type: application/json" \\',
        `  -d '{"input":"Summarize the current policy."}'`
    ].join("\n");
    const guideAsyncExample = [
        `curl -X POST "${window.location.origin}/api/v1/agents/${guideAgentId}/jobs" \\`,
        '  -H "Authorization: Bearer $NEXORA_API_KEY" \\',
        '  -H "Idempotency-Key: YOUR-UNIQUE-REQUEST-ID" \\',
        '  -H "Content-Type: application/json" \\',
        `  -d '{"input":"Analyze the incident and recommend next steps."}'`
    ].join("\n");
    return (
        <Stack spacing={3}>
            <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={2}>
                <Box>
                    <Typography variant="h5">Agent API access</Typography>
                    <Typography color="text.secondary">
                        Let approved applications invoke selected Team Agents with a restricted Knowledge scope.
                    </Typography>
                </Box>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                    <Button
                        variant="outlined"
                        startIcon={<HelpOutlineOutlinedIcon />}
                        onClick={() => setGuideOpen(true)}
                    >
                        Developer Guide
                    </Button>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => setCreateOpen(true)}
                        disabled={loading || options.available_agents.length === 0}
                    >
                        Create API key
                    </Button>
                </Stack>
            </Stack>

            <Alert severity="info">
                API keys inherit the selected Agent's guardrails, tool policy and usage quota. Personal and selected-user
                Data Groups cannot be exposed through a Team API key.
            </Alert>

            {loading ? (
                <Box display="flex" justifyContent="center" py={6}><CircularProgress /></Box>
            ) : options.available_agents.length === 0 ? (
                <Alert severity="warning">Create and activate a LangGraph Agent before enabling API access.</Alert>
            ) : options.items.length === 0 ? (
                <Card variant="outlined"><CardContent><Typography>No API keys have been created for this Team.</Typography></CardContent></Card>
            ) : (
                <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))", gap: 2 }}>
                    {options.items.map(item => {
                        const status = keyStatus(item);
                        return (
                            <Card key={item._id} variant="outlined">
                                <CardContent>
                                    <Stack spacing={1.5}>
                                        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
                                            <Stack direction="row" spacing={1} alignItems="center" minWidth={0}>
                                                <KeyOutlinedIcon color="primary" />
                                                <Box minWidth={0}>
                                                    <Typography fontWeight={700} noWrap>{item.name}</Typography>
                                                    <Typography variant="body2" color="text.secondary" sx={{ fontFamily: "monospace" }}>
                                                        {item.key_prefix}
                                                    </Typography>
                                                </Box>
                                            </Stack>
                                            <Stack direction="row" spacing={0.5} flexWrap="wrap" justifyContent="flex-end">
                                                <Chip size="small" variant="outlined" label={item.access_type === "external_customer" ? "External" : "Internal"} />
                                                <Chip size="small" label={status.label} color={status.color} />
                                            </Stack>
                                        </Stack>
                                        <Divider />
                                        <Typography variant="body2">
                                            Agents: {item.allowed_agent_ids.map(id => agentNames.get(id) || id).join(", ")}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Knowledge: {[
                                                ...item.allowed_data_group_ids.map(id => groupNames.get(id) || id),
                                                ...(item.allow_global_knowledge ? ["Global"] : [])
                                            ].join(", ") || "None"}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Expires {formatDate(item.expires_at)} · {item.rate_limit_per_minute} requests/minute
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Last used: {formatDate(item.last_used_at)}
                                        </Typography>
                                        {item.active && !item.revoked_at && (
                                            <Stack direction="row" spacing={1}>
                                                <Button size="small" startIcon={<AutorenewOutlinedIcon />} onClick={() => void rotate(item)} disabled={saving}>
                                                    Rotate
                                                </Button>
                                                <Button size="small" color="error" startIcon={<BlockOutlinedIcon />} onClick={() => void revoke(item)} disabled={saving}>
                                                    Revoke
                                                </Button>
                                            </Stack>
                                        )}
                                    </Stack>
                                </CardContent>
                            </Card>
                        );
                    })}
                </Box>
            )}

            <Dialog open={guideOpen} fullWidth maxWidth="lg" disableEscapeKeyDown>
                <DialogTitle sx={{ pr: 7 }}>
                    Agent API Developer Guide
                    <IconButton
                        aria-label="Close developer guide"
                        onClick={() => setGuideOpen(false)}
                        sx={{ position: "absolute", right: 12, top: 12 }}
                    >
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent dividers>
                    <Stack spacing={3}>
                        <Alert severity="warning">
                            Keep API keys on a trusted server. Never place a key in browser code, a mobile application,
                            source control, logs, or screenshots.
                        </Alert>
                        <Box>
                            <Typography variant="h6" gutterBottom>Quick start</Typography>
                            <Box sx={{
                                display: "grid",
                                gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
                                gap: 1.5
                            }}>
                                {[
                                    ["1", "Create a restricted key", "Select only the Agents and Team-wide Knowledge the application needs."],
                                    ["2", "Save the secret once", "Store the one-time secret in your server-side secret manager."],
                                    ["3", "Call the Agent", "Send the key as a Bearer token and handle HTTP errors explicitly."]
                                ].map(([step, title, detail]) => (
                                    <Card key={step} variant="outlined">
                                        <CardContent>
                                            <Stack direction="row" spacing={1.5} alignItems="flex-start">
                                                <Chip color="primary" label={step} size="small" />
                                                <Box>
                                                    <Typography fontWeight={700}>{title}</Typography>
                                                    <Typography variant="body2" color="text.secondary">{detail}</Typography>
                                                </Box>
                                            </Stack>
                                        </CardContent>
                                    </Card>
                                ))}
                            </Box>
                        </Box>
                        <Box>
                            <Typography variant="h6" gutterBottom>Choose an endpoint</Typography>
                            <Stack spacing={1}>
                                <Typography>
                                    <strong>Sync</strong> · <code>POST /api/v1/agents/:agent_id/invoke</code> for
                                    short requests that can keep the connection open.
                                </Typography>
                                <Typography>
                                    <strong>Lifecycle stream</strong> ·{" "}
                                    <code>POST /api/v1/agents/:agent_id/invoke/stream</code> for SSE status events.
                                </Typography>
                                <Typography>
                                    <strong>Background job</strong> · <code>POST /api/v1/agents/:agent_id/jobs</code>{" "}
                                    for durable work with polling, retry, and idempotency.
                                </Typography>
                            </Stack>
                        </Box>
                        <Box>
                            <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} mb={1}>
                                <Typography variant="h6">Synchronous request</Typography>
                                <Tooltip title="Copy example">
                                    <IconButton size="small" onClick={() => void copy(guideSyncExample)}>
                                        <ContentCopyOutlinedIcon fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                            </Stack>
                            <Box component="pre" sx={{
                                m: 0,
                                p: 2,
                                bgcolor: "grey.100",
                                borderRadius: 1,
                                overflowX: "auto",
                                whiteSpace: "pre"
                            }}>
                                {guideSyncExample}
                            </Box>
                        </Box>
                        <Box>
                            <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} mb={1}>
                                <Box>
                                    <Typography variant="h6">Background job</Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Reuse the same unique Idempotency-Key when safely replaying the same request,
                                        then poll the returned job URL.
                                    </Typography>
                                </Box>
                                <Tooltip title="Copy example">
                                    <IconButton size="small" onClick={() => void copy(guideAsyncExample)}>
                                        <ContentCopyOutlinedIcon fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                            </Stack>
                            <Box component="pre" sx={{
                                m: 0,
                                p: 2,
                                bgcolor: "grey.100",
                                borderRadius: 1,
                                overflowX: "auto",
                                whiteSpace: "pre"
                            }}>
                                {guideAsyncExample}
                            </Box>
                        </Box>
                        <Alert severity="info">
                            Background job status progresses through <code>queued</code>, <code>running</code>, and
                            then <code>succeeded</code> or <code>failed</code>. Retry is available only for eligible
                            failed jobs.
                        </Alert>
                        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
                            <Button
                                component="a"
                                href="/api/v1/openapi.yaml"
                                target="_blank"
                                rel="noreferrer"
                                variant="outlined"
                                startIcon={<OpenInNewOutlinedIcon />}
                            >
                                Open API specification
                            </Button>
                            <Typography variant="body2" color="text.secondary">
                                In Postman, select Import → Link and paste{" "}
                                <code>{window.location.origin}/api/v1/openapi.yaml</code>.
                            </Typography>
                        </Stack>
                    </Stack>
                </DialogContent>
            </Dialog>

            <Dialog open={createOpen} onClose={() => !saving && setCreateOpen(false)} fullWidth maxWidth="sm">
                <DialogTitle>Create Agent API key</DialogTitle>
                <DialogContent>
                    <Stack spacing={2.5} pt={1}>
                        <TextField
                            label="Key name"
                            value={form.name}
                            onChange={event => setForm(current => ({ ...current, name: event.target.value }))}
                            helperText="Use the calling application or environment name."
                            inputProps={{ maxLength: 120 }}
                            required
                        />
                        <Autocomplete
                            multiple
                            options={options.available_agents}
                            getOptionLabel={option => option.name}
                            value={options.available_agents.filter(agent => form.allowed_agent_ids.includes(agent._id))}
                            onChange={(_event, value) => setForm(current => ({ ...current, allowed_agent_ids: value.map(agent => agent._id) }))}
                            renderInput={params => <TextField {...params} label="Allowed Agents" required />}
                        />
                        <TextField
                            select
                            label="Access type"
                            value={form.access_type}
                            onChange={event => setForm(current => ({
                                ...current,
                                access_type: event.target.value as "internal_service" | "external_customer",
                                allowed_data_group_ids: [],
                                allow_global_knowledge: false
                            }))}
                            helperText={form.access_type === "external_customer"
                                ? "For a customer-facing backend. Only External Published Knowledge is eligible."
                                : "For trusted internal server-to-server applications."}
                        >
                            <MenuItem value="internal_service">Internal service</MenuItem>
                            {canManageExternalChannels && (
                                <MenuItem value="external_customer">External customer channel</MenuItem>
                            )}
                        </TextField>
                        {form.access_type === "external_customer" && (
                            <Alert severity="warning">
                                Use this key only from your website backend or BFF. Browser and mobile clients must never receive it.
                            </Alert>
                        )}
                        <Autocomplete
                            multiple
                            options={availableKnowledgeGroups}
                            getOptionLabel={option => option.name}
                            value={availableKnowledgeGroups.filter(group => form.allowed_data_group_ids.includes(group._id))}
                            onChange={(_event, value) => setForm(current => ({ ...current, allowed_data_group_ids: value.map(group => group._id) }))}
                            renderInput={params => <TextField {...params} label={form.access_type === "external_customer" ? "External Published Knowledge (optional)" : "Team-wide Knowledge (optional)"} />}
                        />
                        {form.access_type === "internal_service" && (
                            <FormControlLabel
                                control={<Switch checked={form.allow_global_knowledge} onChange={event => setForm(current => ({ ...current, allow_global_knowledge: event.target.checked }))} />}
                                label="Allow Global Knowledge"
                            />
                        )}
                        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                            <TextField
                                fullWidth
                                type="number"
                                label="Expires in days"
                                value={form.expiry_days}
                                onChange={event => setForm(current => ({ ...current, expiry_days: Number(event.target.value) }))}
                                inputProps={{ min: 1, max: 365 }}
                            />
                            <TextField
                                fullWidth
                                type="number"
                                label="Requests per minute"
                                value={form.rate_limit_per_minute}
                                onChange={event => setForm(current => ({ ...current, rate_limit_per_minute: Number(event.target.value) }))}
                                inputProps={{ min: 1, max: 1000 }}
                            />
                        </Stack>
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setCreateOpen(false)} disabled={saving}>Cancel</Button>
                    <Button variant="contained" onClick={() => void submitCreate()} disabled={saving || !form.name.trim() || form.allowed_agent_ids.length === 0}>
                        {saving ? "Creating..." : "Create key"}
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog open={secretOpen} onClose={() => setSecretOpen(false)} fullWidth maxWidth="md">
                <DialogTitle>Copy the API key now</DialogTitle>
                <DialogContent>
                    <Stack spacing={2} pt={1}>
                        <Alert severity="warning">This secret is shown only once. NexoraAI stores only its SHA-256 digest and cannot display it again.</Alert>
                        <Stack direction="row" spacing={1} alignItems="center">
                            <TextField fullWidth label="API key" value={secret} InputProps={{ readOnly: true }} />
                            <Tooltip title="Copy API key"><IconButton onClick={() => void copy(secret)}><ContentCopyOutlinedIcon /></IconButton></Tooltip>
                        </Stack>
                        <Typography variant="subtitle2">Example request</Typography>
                        <Box component="pre" sx={{ m: 0, p: 2, bgcolor: "grey.100", borderRadius: 1, overflowX: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                            {curlExample}
                        </Box>
                        <Button startIcon={<ContentCopyOutlinedIcon />} onClick={() => void copy(curlExample)}>Copy example</Button>
                    </Stack>
                </DialogContent>
                <DialogActions><Button variant="contained" onClick={() => setSecretOpen(false)}>Done</Button></DialogActions>
            </Dialog>
        </Stack>
    );
}
