import React, { useEffect, useState } from "react";
import {
    Box,
    Typography,
    Button,
    Stack,
    Paper,
    IconButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    CircularProgress,
    Chip,
    Alert,
    MenuItem,
    Skeleton
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";

import { Endpoint, ExternalApi, TeamProfile } from "../../../api/models";
import { get_external_apis_by_team, insert_external_api, edit_external_api, delete_external_api } from "../../../api/api";
import { getToken } from "../../../authConfig";
import { useMsal } from "@azure/msal-react";
import { useNotification } from "../../../utill/NotificationProvider";
import { AssignIntegrationTeamButton } from "./AssignIntegrationTeamButton";

/* ================= PAGE ================= */

export function ExternalApiListPage({ team, onBack }: { team: TeamProfile | null; onBack: () => void }) {
    const [apis, setApis] = useState<ExternalApi[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState<ExternalApi | null>(null);
    const client = useMsal().instance;
    const { showNotification } = useNotification();
    const teamId = team?._id ?? "";

    /* ================= LOAD ================= */
    useEffect(() => {
        async function load() {
            try {
                setLoading(true);
                const token = await getToken(client);
                if (!token) throw new Error("No authentication token");
                const res = await get_external_apis_by_team(teamId, token);
                const apiData = res?.result || res?.data || res || [];
                setApis(Array.isArray(apiData) ? apiData : []);
            } catch (err) {
                console.error("load external apis failed", err);
            } finally {
                setLoading(false);
            }
        }

        load();
    }, [teamId]);

    /* ================= SAVE ================= */

    const handleSave = async (api: ExternalApi) => {
        try {
            setSaving(true);
            setLoading(true);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            const payload: any = {
                team_id: teamId,
                name: api.name,
                type: api.type,
                base_url: api.base_url,
                auth: api.auth,
                endpoints: api.endpoints
            };

            if (editing) {
                payload.api_id = api._id;
                await edit_external_api(payload, token);
                showNotification("External API updated successfully", "success");
            } else {
                await insert_external_api(payload, token);
                showNotification("External API created successfully", "success");
            }

            setOpen(false);
            setEditing(null);

            // Reload list
            const res = await get_external_apis_by_team(teamId, token);
            const apiData = res?.result || res?.data || res || [];
            setApis(Array.isArray(apiData) ? apiData : []);
            setLoading(false);
        } catch (err) {
            console.error("save external api failed", err);
            showNotification("Failed to save External API", "error");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!window.confirm("Delete this REST API connection? Agent endpoint bindings that reference it will stop working.")) return;

        try {
            setDeletingId(id);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            await delete_external_api(id, token);

            setApis(prev => prev.filter(a => a._id !== id));
            showNotification("External API deleted successfully", "success");
        } catch (err) {
            console.error("delete external api failed", err);
            showNotification("Failed to delete External API", "error");
        } finally {
            setDeletingId(null);
        }
    };

    /* ================= RENDER ================= */

    return (
        <Box p={3} sx={{ height: "100%", overflowY: "auto" }}>
            <Stack direction="row" alignItems="center" spacing={2} mb={2}>
                <IconButton onClick={onBack}>
                    <ArrowBackIcon />
                </IconButton>
                <Box>
                    <Typography variant="h6">REST APIs</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Connection catalog for REST endpoints. Agents receive only endpoints explicitly assigned from Agent → Integrations.
                    </Typography>
                </Box>
            </Stack>

            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)} sx={{ mb: 2 }}>
                Add REST API
            </Button>

            {!team && (
                <Alert severity="info" sx={{ mb: 2 }}>
                    New connections remain unavailable to Agents until assigned to a team.
                </Alert>
            )}

            {loading ? (
                <ExternalApiListSkeleton count={4} />
            ) : (
                <Stack spacing={2}>
                    {apis.map(api => (
                        <Paper
                            key={api._id}
                            variant="outlined"
                            sx={{
                                p: 2,
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center"
                            }}
                        >
                            <Box minWidth={0}>
                                <Typography fontWeight={600}>{api.name}</Typography>
                                <Typography variant="body2" color="text.secondary">
                                    {api.base_url}
                                </Typography>

                                <Stack direction="row" spacing={0.75} mt={1} flexWrap="wrap" useFlexGap>
                                    <Chip size="small" label={`${api.endpoints.length} endpoint${api.endpoints.length === 1 ? "" : "s"}`} />
                                    <Chip size="small" color="primary" variant="outlined" label={`${api.agent_usage_count ?? 0} Agent(s)`} />
                                    {!team && <Chip size="small" color="warning" variant="outlined" label="Unassigned" />}
                                    <Chip
                                        size="small"
                                        variant="outlined"
                                        color={api.auth?.type && api.auth.type !== "none" ? "success" : "default"}
                                        label={api.auth?.type && api.auth.type !== "none" ? "Credentials configured" : "No authentication"}
                                    />
                                    {api.endpoints.map((endpoint, index) => (
                                        <Chip
                                            key={`${api._id}-${endpoint.name}-${index}`}
                                            size="small"
                                            variant="outlined"
                                            color={endpoint.method === "GET" ? "success" : "warning"}
                                            label={`${endpoint.method} ${endpoint.name || endpoint.path}`}
                                        />
                                    ))}
                                </Stack>
                            </Box>

                            <Box>
                                {!team && (
                                    <AssignIntegrationTeamButton
                                        integrationId={api._id}
                                        integrationType="rest_api"
                                        onAssigned={async () => {
                                            const token = await getToken(client);
                                            if (!token) return;
                                            const res = await get_external_apis_by_team(teamId, token);
                                            const apiData = res?.result || res?.data || res || [];
                                            setApis(Array.isArray(apiData) ? apiData : []);
                                        }}
                                    />
                                )}
                                <IconButton
                                    onClick={() => {
                                        setEditing(api);
                                        setOpen(true);
                                    }}
                                >
                                    <EditIcon />
                                </IconButton>

                                <IconButton color="error" disabled={deletingId === api._id} onClick={() => handleDelete(api._id)}>
                                    {deletingId === api._id ? <CircularProgress size={20} color="inherit" /> : <DeleteIcon />}
                                </IconButton>
                            </Box>
                        </Paper>
                    ))}
                </Stack>
            )}

            <ExternalApiDialog
                open={open}
                api={editing}
                team={team}
                loading={loading}
                saving={saving}
                onClose={() => {
                    if (saving) return;
                    setOpen(false);
                    setEditing(null);
                }}
                onSave={handleSave}
            />
        </Box>
    );
}

/* ================= DIALOG ================= */

function ExternalApiDialog({
    open,
    api,
    team,
    loading,
    saving,
    onClose,
    onSave
}: {
    open: boolean;
    api: ExternalApi | null;
    team: TeamProfile | null;
    loading?: boolean;
    saving?: boolean;
    onClose: () => void;
    onSave: (api: ExternalApi) => void;
}) {
    const [name, setName] = useState("");
    const [baseUrl, setBaseUrl] = useState("");
    const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
    const [authType, setAuthType] = useState<"none" | "api_key" | "bearer">("none");
    const [authHeader, setAuthHeader] = useState("");
    const [authValue, setAuthValue] = useState("");

    useEffect(() => {
        if (open) {
            if (api) {
                setName(api.name);
                setBaseUrl(api.base_url);

                setAuthType(api.auth?.type ?? "none");
                setAuthHeader(api.auth?.header ?? "");
                setAuthValue(api.auth?.value ?? "");

                setEndpoints(api.endpoints);
            } else {
                setName("");
                setBaseUrl("");
                setEndpoints([]);
                setAuthType("none");
                setAuthHeader("");
                setAuthValue("");
            }
        }
    }, [api, open]);

    const addEndpoint = () => {
        setEndpoints(prev => [...prev, { name: "", method: "GET", path: "" }]);
    };

    const updateEndpoint = (index: number, field: keyof Endpoint, value: any) => {
        const updated = [...endpoints];
        updated[index][field] = value;
        setEndpoints(updated);
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle>{api ? "Edit REST API" : "Add REST API"}</DialogTitle>

            <DialogContent dividers>
                <Stack spacing={3}>
                    <TextField label="Name" disabled={saving} value={name} onChange={e => setName(e.target.value)} />

                    <TextField label="Base URL" disabled={saving} value={baseUrl} onChange={e => setBaseUrl(e.target.value)} />

                    <TextField select label="Auth Type" disabled={saving} value={authType} onChange={e => setAuthType(e.target.value as any)}>
                        <MenuItem value="none">None</MenuItem>
                        <MenuItem value="api_key">API Key</MenuItem>
                        <MenuItem value="bearer">Bearer Token</MenuItem>
                    </TextField>

                    {authType !== "none" && (
                        <>
                            <TextField label="Header" disabled={saving} value={authHeader} onChange={e => setAuthHeader(e.target.value)} />

                            <TextField
                                label="Credential Value"
                                type="password"
                                disabled={saving}
                                value={authValue}
                                onChange={e => setAuthValue(e.target.value)}
                                autoComplete="new-password"
                                helperText="Credentials are managed centrally and are never copied into an Agent binding"
                            />
                        </>
                    )}

                    <Box>
                        <Typography fontWeight={600} mb={1}>
                            Endpoints
                        </Typography>

                        <Stack spacing={2}>
                            {endpoints.map((ep, idx) => (
                                <Paper key={idx} variant="outlined" sx={{ p: 2 }}>
                                    <Stack spacing={2}>
                                        {/* Header */}
                                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                                            <Stack direction="row" spacing={1} alignItems="center">
                                                <Typography fontWeight={600}>Endpoint {idx + 1}</Typography>
                                                <Chip
                                                    size="small"
                                                    variant="outlined"
                                                    color={ep.method === "GET" ? "success" : "warning"}
                                                    label={ep.method === "GET" ? "Read action" : "Write action"}
                                                />
                                            </Stack>

                                            <IconButton
                                                size="small"
                                                color="error"
                                                disabled={saving}
                                                onClick={() => setEndpoints(prev => prev.filter((_, i) => i !== idx))}
                                            >
                                                <DeleteIcon fontSize="small" />
                                            </IconButton>
                                        </Stack>

                                        <TextField
                                            label="Endpoint Name"
                                            disabled={saving}
                                            value={ep.name}
                                            onChange={e => updateEndpoint(idx, "name", e.target.value)}
                                        />

                                        <TextField
                                            select
                                            label="Method"
                                            disabled={saving}
                                            value={ep.method}
                                            onChange={e => updateEndpoint(idx, "method", e.target.value as "GET" | "POST")}
                                        >
                                            <MenuItem value="GET">GET</MenuItem>
                                            <MenuItem value="POST">POST</MenuItem>
                                        </TextField>

                                        <TextField label="Path" disabled={saving} value={ep.path} onChange={e => updateEndpoint(idx, "path", e.target.value)} />
                                        {ep.method !== "GET" && (
                                            <Alert severity="warning">
                                                This endpoint can change an external system. Assign it only to Agents that require this action.
                                            </Alert>
                                        )}
                                    </Stack>
                                </Paper>
                            ))}

                            <Button onClick={addEndpoint}>+ Add Endpoint</Button>
                        </Stack>
                    </Box>
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} disabled={loading}>
                    Cancel
                </Button>

                <Button
                    variant="contained"
                    disabled={!name || !baseUrl || loading}
                    onClick={() =>
                        onSave({
                            _id: api?._id ?? "",
                            team_id: team?._id ?? "",
                            name,
                            base_url: baseUrl,
                            type: "rest",
                            auth: {
                                type: authType,
                                header: authHeader,
                                value: authValue
                            },

                            endpoints
                        })
                    }
                >
                    {loading ? "Saving..." : "Save"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

function ExternalApiListSkeleton({ count = 4 }: { count?: number }) {
    return (
        <Stack spacing={2}>
            {Array.from({ length: count }).map((_, idx) => (
                <Paper
                    key={idx}
                    variant="outlined"
                    sx={{
                        p: 2,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center"
                    }}
                >
                    <Box sx={{ width: "70%" }}>
                        <Skeleton variant="text" width="30%" height={28} />
                        <Skeleton variant="text" width="50%" height={20} sx={{ mt: 0.5 }} />
                        <Skeleton variant="text" width="20%" height={18} sx={{ mt: 0.5 }} />
                    </Box>

                    <Box sx={{ display: "flex", gap: 1 }}>
                        <Skeleton variant="circular" width={36} height={36} />
                        <Skeleton variant="circular" width={36} height={36} />
                    </Box>
                </Paper>
            ))}
        </Stack>
    );
}
