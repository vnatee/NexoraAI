import { useEffect, useState } from "react";
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    MenuItem,
    Paper,
    Snackbar,
    Stack,
    Switch,
    TextField,
    Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PowerSettingsNewIcon from "@mui/icons-material/PowerSettingsNew";
import { useMsal } from "@azure/msal-react";

import {
    activateEmbeddingProfileApi,
    completeEmbeddingReindexApi,
    createEmbeddingProfileApi,
    deleteEmbeddingProfileApi,
    listEmbeddingProfilesApi,
    testEmbeddingProfileApi,
    updateEmbeddingProfileApi
} from "../../api";
import {
    EmbeddingProfilePayload,
    EmbeddingProfileSettings,
    EmbeddingProviderAdapter,
    ManagedEmbeddingProfile
} from "../../api/models";
import { getToken } from "../../authConfig";

const emptyPayload = (): EmbeddingProfilePayload => ({
    name: "",
    provider: "openai_compatible",
    model: "bge-m3",
    dimensions: 1024,
    collection_name: "nexora-knowledge-custom",
    base_url: "http://ollama:11434/v1",
    endpoint: "",
    deployment: "",
    api_version: "2024-10-21",
    organization: "",
    enabled: true,
    api_key: ""
});

export function EmbeddingProfileManagement() {
    const { instance } = useMsal();
    const [profiles, setProfiles] = useState<ManagedEmbeddingProfile[]>([]);
    const [settings, setSettings] = useState<EmbeddingProfileSettings | null>(null);
    const [loading, setLoading] = useState(true);
    const [busyId, setBusyId] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editing, setEditing] = useState<ManagedEmbeddingProfile | null>(null);
    const [form, setForm] = useState<EmbeddingProfilePayload>(emptyPayload());
    const [notice, setNotice] = useState<{ severity: "success" | "warning" | "error"; text: string } | null>(null);

    const load = async () => {
        setLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const result = await listEmbeddingProfilesApi(token);
            setProfiles(result.profiles);
            setSettings(result.settings);
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to load embedding profiles" });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { void load(); }, [instance]);

    const openCreate = () => {
        setEditing(null);
        setForm(emptyPayload());
        setDialogOpen(true);
    };

    const openEdit = (profile: ManagedEmbeddingProfile) => {
        setEditing(profile);
        setForm({
            name: profile.name,
            provider: profile.provider,
            model: profile.model,
            deployment: profile.deployment ?? "",
            dimensions: profile.dimensions,
            collection_name: profile.collection_name,
            endpoint: profile.endpoint ?? "",
            base_url: profile.base_url ?? "",
            api_version: profile.api_version ?? "2024-10-21",
            organization: profile.organization ?? "",
            enabled: profile.enabled,
            api_key: ""
        });
        setDialogOpen(true);
    };

    const save = async () => {
        setBusyId(editing?._id ?? "create");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            if (editing) await updateEmbeddingProfileApi(editing._id, form, token);
            else await createEmbeddingProfileApi(form, token);
            setDialogOpen(false);
            setNotice({ severity: "success", text: `Embedding profile ${editing ? "updated" : "created"}` });
            await load();
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to save embedding profile" });
        } finally {
            setBusyId(null);
        }
    };

    const activate = async (profile: ManagedEmbeddingProfile) => {
        if (!window.confirm(`Activate ${profile.name}? The application must be restarted and all Knowledge must be re-indexed.`)) return;
        setBusyId(profile._id);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const result = await activateEmbeddingProfileApi(profile._id, token);
            setSettings(result.settings);
            setNotice({ severity: "warning", text: "Profile selected. Restart the application, then re-index all Knowledge." });
            await load();
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to activate profile" });
        } finally {
            setBusyId(null);
        }
    };

    const test = async (profile: ManagedEmbeddingProfile) => {
        setBusyId(profile._id);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const result = await testEmbeddingProfileApi(profile._id, token);
            setNotice({ severity: "success", text: `${profile.name} returned ${result.dimensions} dimensions successfully` });
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Embedding test failed" });
        } finally {
            setBusyId(null);
        }
    };

    const completeReindex = async () => {
        if (!settings || !window.confirm("Confirm only after every Knowledge source has been re-indexed successfully.")) return;
        setBusyId("reindex");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const result = await completeEmbeddingReindexApi(settings.active_profile_id, token);
            setSettings(result.settings);
            setNotice({ severity: "success", text: "The active embedding profile is marked ready" });
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to complete re-index" });
        } finally {
            setBusyId(null);
        }
    };

    const remove = async (profile: ManagedEmbeddingProfile) => {
        if (!window.confirm(`Remove ${profile.name}? The Qdrant collection is not deleted.`)) return;
        setBusyId(profile._id);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            await deleteEmbeddingProfileApi(profile._id, token);
            await load();
            setNotice({ severity: "success", text: "Embedding profile removed; vector data was preserved" });
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to remove profile" });
        } finally {
            setBusyId(null);
        }
    };

    return (
        <Stack spacing={2} sx={{ pt: 1 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
                <Box>
                    <Typography variant="h6">Embedding Profiles</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Configure vector models for Knowledge. One profile is active system-wide in Phase 1.
                    </Typography>
                </Box>
                <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>Add Profile</Button>
            </Box>

            {settings?.restart_required && (
                <Alert severity="warning">The selected profile is not running yet. Restart the application before re-indexing.</Alert>
            )}
            {settings?.reindex_required && (
                <Alert severity="warning">
                    <Stack direction={{ xs: "column", sm: "row" }} alignItems={{ sm: "center" }} justifyContent="space-between" gap={1}>
                        <span>Full re-index required. Re-upload or re-index all Personal, Team, Global, and web Knowledge into the selected collection.</span>
                        <Button
                            size="small"
                            color="warning"
                            variant="outlined"
                            disabled={settings.restart_required || busyId === "reindex"}
                            onClick={() => void completeReindex()}
                        >
                            Mark re-index complete
                        </Button>
                    </Stack>
                </Alert>
            )}

            {loading ? <Box display="flex" justifyContent="center" py={6}><CircularProgress /></Box> : (
                <Stack spacing={1}>
                    {profiles.map(profile => {
                        const selected = settings?.active_profile_id === profile._id;
                        const running = settings?.runtime_profile_id === profile._id;
                        const locked = selected || running;
                        return (
                            <Paper key={profile._id} variant="outlined" sx={{ p: 2 }}>
                                <Box display="flex" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
                                    <Box minWidth={0}>
                                        <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
                                            <Typography fontWeight={600}>{profile.name}</Typography>
                                            {profile.environment && <Chip size="small" label="Environment" />}
                                            {selected && <Chip size="small" color="primary" label="Selected" />}
                                            {running && <Chip size="small" color="success" label="Running" />}
                                            {!profile.enabled && <Chip size="small" label="Disabled" />}
                                            {profile.has_api_key && <Chip size="small" variant="outlined" label="API key stored" />}
                                        </Stack>
                                        <Typography variant="body2" color="text.secondary">
                                            {profile.provider} · {profile.model} · {profile.dimensions} dimensions
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            Qdrant collection: {profile.collection_name}
                                        </Typography>
                                    </Box>
                                    <Stack direction="row" spacing={0.5}>
                                        <Button size="small" startIcon={<PlayArrowIcon />} disabled={busyId === profile._id} onClick={() => void test(profile)}>Test</Button>
                                        {!selected && <Button size="small" startIcon={<PowerSettingsNewIcon />} disabled={!profile.enabled || busyId === profile._id} onClick={() => void activate(profile)}>Activate</Button>}
                                        {!profile.environment && <IconButton aria-label="Edit embedding profile" disabled={locked} onClick={() => openEdit(profile)}><EditIcon /></IconButton>}
                                        {!profile.environment && <IconButton aria-label="Remove embedding profile" color="error" disabled={locked} onClick={() => void remove(profile)}><DeleteIcon /></IconButton>}
                                    </Stack>
                                </Box>
                            </Paper>
                        );
                    })}
                </Stack>
            )}

            <Dialog open={dialogOpen} onClose={() => busyId === null && setDialogOpen(false)} fullWidth maxWidth="sm">
                <DialogTitle>{editing ? "Edit Embedding Profile" : "Add Embedding Profile"}</DialogTitle>
                <DialogContent dividers>
                    <Stack spacing={2}>
                        <TextField label="Profile Name" required value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} />
                        <TextField select label="Provider" value={form.provider} onChange={event => setForm({ ...form, provider: event.target.value as EmbeddingProviderAdapter })}>
                            <MenuItem value="openai_compatible">OpenAI-compatible / Ollama</MenuItem>
                            <MenuItem value="azure_openai">Azure OpenAI</MenuItem>
                            <MenuItem value="openai">OpenAI</MenuItem>
                        </TextField>
                        <TextField label="Model" required value={form.model} onChange={event => setForm({ ...form, model: event.target.value })} />
                        {form.provider === "azure_openai" && <TextField label="Deployment" required value={form.deployment ?? ""} onChange={event => setForm({ ...form, deployment: event.target.value })} />}
                        {form.provider === "azure_openai" && <TextField label="Azure Endpoint" required value={form.endpoint ?? ""} onChange={event => setForm({ ...form, endpoint: event.target.value })} />}
                        {form.provider === "openai_compatible" && <TextField label="Base URL" required value={form.base_url ?? ""} onChange={event => setForm({ ...form, base_url: event.target.value })} helperText="Use http://ollama:11434/v1 for the bundled Docker service." />}
                        <TextField label="Dimensions" required type="number" value={form.dimensions} onChange={event => setForm({ ...form, dimensions: Number(event.target.value) })} />
                        <TextField label="Qdrant Collection" required value={form.collection_name} onChange={event => setForm({ ...form, collection_name: event.target.value })} helperText="Use a unique collection for every embedding vector space." />
                        <TextField label={editing?.has_api_key ? "Replace API Key (optional)" : "API Key (if required)"} type="password" value={form.api_key ?? ""} onChange={event => setForm({ ...form, api_key: event.target.value })} />
                        <Stack direction="row" alignItems="center" spacing={1}>
                            <Switch checked={form.enabled} onChange={event => setForm({ ...form, enabled: event.target.checked })} />
                            <Typography>Enabled</Typography>
                        </Stack>
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDialogOpen(false)} disabled={busyId !== null}>Cancel</Button>
                    <Button variant="contained" onClick={() => void save()} disabled={busyId !== null}>Save</Button>
                </DialogActions>
            </Dialog>

            <Snackbar open={Boolean(notice)} autoHideDuration={7000} onClose={() => setNotice(null)}>
                {notice ? <Alert severity={notice.severity} onClose={() => setNotice(null)}>{notice.text}</Alert> : undefined}
            </Snackbar>
        </Stack>
    );
}
