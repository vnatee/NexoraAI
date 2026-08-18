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

/* ================= PAGE ================= */

export function ExternalApiListPage({ team, onBack }: { team: TeamProfile; onBack: () => void }) {
    const [apis, setApis] = useState<ExternalApi[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState<ExternalApi | null>(null);
    const client = useMsal().instance;
    const { showNotification } = useNotification();

    /* ================= LOAD ================= */
    useEffect(() => {
        async function load() {
            try {
                setLoading(true);
                const token = await getToken(client);
                if (!token) throw new Error("No authentication token");
                const res = await get_external_apis_by_team(team._id, token);
                const apiData = res?.result || res?.data || res || [];
                setApis(Array.isArray(apiData) ? apiData : []);
            } catch (err) {
                console.error("load external apis failed", err);
            } finally {
                setLoading(false);
            }
        }

        load();
    }, [team._id]);

    /* ================= SAVE ================= */

    const handleSave = async (api: ExternalApi) => {
        try {
            setSaving(true);
            setLoading(true);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            const payload: any = {
                team_id: team._id,
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
            const res = await get_external_apis_by_team(team._id, token);
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
        if (!window.confirm("Are you sure you want to delete this external API?")) return;

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
                <Typography variant="h6">External API</Typography>
            </Stack>

            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)} sx={{ mb: 2 }}>
                Add External API
            </Button>

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
                            <Box>
                                <Typography fontWeight={600}>{api.name}</Typography>
                                <Typography variant="body2" color="text.secondary">
                                    {api.base_url}
                                </Typography>

                                <Typography variant="caption" color="text.secondary">
                                    Endpoints: {api.endpoints.length}
                                </Typography>
                            </Box>

                            <Box>
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
    team: TeamProfile;
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
            <DialogTitle>{api ? "Edit External API" : "Add External API"}</DialogTitle>

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

                            <TextField label="Value" disabled={saving} value={authValue} onChange={e => setAuthValue(e.target.value)} />
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
                                            <Typography fontWeight={600}>Endpoint {idx + 1}</Typography>

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
                            team_id: team._id,
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
