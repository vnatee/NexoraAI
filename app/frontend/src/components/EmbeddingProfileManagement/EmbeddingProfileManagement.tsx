import { useEffect, useMemo, useState } from "react";
import {
    Alert,
    Avatar,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    InputAdornment,
    Menu,
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
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import SearchIcon from "@mui/icons-material/Search";
import GrainIcon from "@mui/icons-material/Grain";
import { useMsal } from "@azure/msal-react";

import {
    activateEmbeddingProfileApi,
    adoptEmbeddingCollectionApi,
    completeEmbeddingReindexApi,
    createEmbeddingProfileApi,
    deleteEmbeddingProfileApi,
    getEmbeddingReindexPlanApi,
    getLatestEmbeddingReindexApi,
    listEmbeddingProfilesApi,
    previewEmbeddingCollectionAdoptionApi,
    startEmbeddingReindexApi,
    testEmbeddingProfileApi,
    updateEmbeddingProfileApi
} from "../../api";
import {
    EmbeddingProfilePayload,
    EmbeddingProfileSettings,
    EmbeddingCollectionCompatibility,
    EmbeddingReindexPlan,
    EmbeddingReindexRun,
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
    gateway_proxy_path: "",
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
    const [search, setSearch] = useState("");
    const [actionAnchor, setActionAnchor] = useState<HTMLElement | null>(null);
    const [actionProfile, setActionProfile] = useState<ManagedEmbeddingProfile | null>(null);
    const [reindexPlan, setReindexPlan] = useState<EmbeddingReindexPlan | null>(null);
    const [reindexConfirmation, setReindexConfirmation] = useState("");
    const [latestRun, setLatestRun] = useState<EmbeddingReindexRun | null>(null);
    const [adoptProfile, setAdoptProfile] = useState<ManagedEmbeddingProfile | null>(null);
    const [adoptCollection, setAdoptCollection] = useState("");
    const [adoptConfirmation, setAdoptConfirmation] = useState("");
    const [compatibility, setCompatibility] = useState<EmbeddingCollectionCompatibility | null>(null);

    const filteredProfiles = useMemo(() => {
        const query = search.trim().toLowerCase();
        return profiles.filter(profile => !query || `${profile.name} ${profile.provider} ${profile.model} ${profile.collection_name}`.toLowerCase().includes(query));
    }, [profiles, search]);

    const closeActionMenu = () => {
        setActionAnchor(null);
        setActionProfile(null);
    };

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

    useEffect(() => {
        const profileId = settings?.active_profile_id;
        if (!profileId) return;
        let cancelled = false;
        let timer: number | undefined;
        const refreshRun = async () => {
            try {
                const token = await getToken(instance);
                if (!token || cancelled) return;
                const result = await getLatestEmbeddingReindexApi(profileId, token);
                if (cancelled) return;
                setLatestRun(result.run);
                if (result.run?.status === "queued" || result.run?.status === "running") {
                    timer = window.setTimeout(refreshRun, 3000);
                }
            } catch (error) {
                if (!cancelled) console.error("load embedding re-index progress failed", error);
            }
        };
        void refreshRun();
        return () => {
            cancelled = true;
            if (timer !== undefined) window.clearTimeout(timer);
        };
    }, [instance, settings?.active_profile_id, latestRun?.status]);

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
            gateway_proxy_path: profile.gateway_proxy_path ?? "",
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

    const openReindex = async () => {
        if (!settings) return;
        setBusyId("reindex-plan");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const plan = await getEmbeddingReindexPlanApi(settings.active_profile_id, token);
            setReindexPlan(plan);
            setReindexConfirmation("");
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to prepare full re-index" });
        } finally {
            setBusyId(null);
        }
    };

    const startReindex = async () => {
        if (!reindexPlan) return;
        setBusyId("reindex-start");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const result = await startEmbeddingReindexApi(reindexPlan.profile_id, reindexConfirmation, token);
            setLatestRun(result.run);
            setReindexPlan(null);
            setNotice({ severity: "warning", text: "Full re-index started. Keep the source files available until it completes." });
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to start full re-index" });
        } finally {
            setBusyId(null);
        }
    };

    const previewAdoption = async () => {
        if (!adoptProfile || !adoptCollection.trim()) return;
        setBusyId("adopt-preview");
        setCompatibility(null);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const result = await previewEmbeddingCollectionAdoptionApi(adoptProfile._id, adoptCollection.trim(), token);
            setCompatibility(result);
            setAdoptConfirmation("");
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Compatibility test failed" });
        } finally {
            setBusyId(null);
        }
    };

    const applyCollectionAdoption = async () => {
        if (!adoptProfile || !compatibility?.compatible) return;
        setBusyId("adopt-apply");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            await adoptEmbeddingCollectionApi(adoptProfile._id, compatibility.collection_name, adoptConfirmation, token);
            setAdoptProfile(null);
            setCompatibility(null);
            setNotice({ severity: "warning", text: "Existing collection adopted. Restart the application to use it." });
            await load();
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to adopt collection" });
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
                    <Stack spacing={1}>
                        <Typography variant="body2">Full re-index required. Stored Personal, Team, Company, and web sources can be reprocessed into the selected collection.</Typography>
                        {latestRun && (
                            <Typography variant="body2">
                                Run {latestRun.status}: {latestRun.progress.succeeded}/{latestRun.progress.total} succeeded
                                {latestRun.progress.running > 0 ? ` · ${latestRun.progress.running} running` : ""}
                                {latestRun.progress.failed > 0 ? ` · ${latestRun.progress.failed} failed` : ""}
                            </Typography>
                        )}
                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                            <Button
                                size="small"
                                color="warning"
                                variant="contained"
                                disabled={settings.restart_required || latestRun?.status === "queued" || latestRun?.status === "running" || busyId !== null}
                                onClick={() => void openReindex()}
                            >
                                Start full re-index
                            </Button>
                            <Button
                                size="small"
                                color="warning"
                                variant="outlined"
                                disabled={latestRun?.status !== "completed" || latestRun.progress.failed > 0 || busyId === "reindex"}
                                onClick={() => void completeReindex()}
                            >
                                Mark re-index complete
                            </Button>
                        </Stack>
                    </Stack>
                </Alert>
            )}

            <TextField
                fullWidth
                size="small"
                placeholder="Search embedding profiles..."
                value={search}
                onChange={event => setSearch(event.target.value)}
                InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon color="action" /></InputAdornment> }}
            />

            {loading ? <Box display="flex" justifyContent="center" py={6}><CircularProgress /></Box> : (
                <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 240px), 1fr))", gap: 2 }}>
                    {filteredProfiles.map(profile => {
                        const selected = settings?.active_profile_id === profile._id;
                        const running = settings?.runtime_profile_id === profile._id;
                        const locked = selected || running;
                        return (
                            <Paper
                                key={profile._id}
                                variant="outlined"
                                role="button"
                                tabIndex={0}
                                onClick={() => !profile.environment && !locked && openEdit(profile)}
                                onKeyDown={event => {
                                    if ((event.key === "Enter" || event.key === " ") && !profile.environment && !locked) {
                                        event.preventDefault();
                                        openEdit(profile);
                                    }
                                }}
                                sx={{
                                    p: 2,
                                    minHeight: 300,
                                    display: "flex",
                                    flexDirection: "column",
                                    alignItems: "center",
                                    textAlign: "center",
                                    position: "relative",
                                    cursor: !profile.environment && !locked ? "pointer" : "default",
                                    transition: "transform 150ms ease, box-shadow 150ms ease, border-color 150ms ease",
                                    "&:hover": { transform: "translateY(-2px)", boxShadow: 3, borderColor: "primary.light" },
                                    "&:focus-visible": { outline: "3px solid", outlineColor: "primary.light", outlineOffset: 2 }
                                }}
                            >
                                <Chip size="small" color={running ? "success" : selected ? "primary" : profile.enabled ? "default" : "default"} label={running ? "Running" : selected ? "Selected" : profile.enabled ? "Available" : "Disabled"} sx={{ position: "absolute", top: 12, left: 12 }} />
                                <IconButton size="small" aria-label={`Actions for ${profile.name}`} onClick={event => { event.stopPropagation(); setActionProfile(profile); setActionAnchor(event.currentTarget); }} sx={{ position: "absolute", top: 8, right: 8 }}>
                                    {busyId === profile._id ? <CircularProgress size={20} /> : <MoreHorizIcon />}
                                </IconButton>
                                <Avatar variant="rounded" sx={{ width: 72, height: 72, mt: 3, mb: 2, bgcolor: "secondary.main", boxShadow: 1 }}>
                                    <GrainIcon sx={{ fontSize: 42 }} />
                                </Avatar>
                                <Typography variant="h6" fontSize="1rem" fontWeight={700} sx={{ minHeight: 42, overflowWrap: "anywhere" }}>{profile.name}</Typography>
                                <Typography variant="body2" color="text.secondary" fontWeight={500}>{profile.model}</Typography>
                                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, overflowWrap: "anywhere" }}>{profile.provider}</Typography>
                                <Box sx={{ flex: 1 }} />
                                <Typography variant="caption" color="text.secondary" title={profile.collection_name} sx={{ mt: 2, maxWidth: "100%", overflowWrap: "anywhere" }}>
                                    {profile.dimensions} dimensions · {profile.collection_name}
                                </Typography>
                                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap justifyContent="center" sx={{ mt: 1 }}>
                                    {profile.environment && <Chip size="small" variant="outlined" label="Environment" />}
                                    {profile.has_api_key && <Chip size="small" variant="outlined" label="Credential stored" />}
                                </Stack>
                            </Paper>
                        );
                    })}
                </Box>
            )}

            <Menu anchorEl={actionAnchor} open={Boolean(actionAnchor)} onClose={closeActionMenu}>
                <MenuItem disabled={!actionProfile || busyId === actionProfile._id} onClick={() => { if (actionProfile) void test(actionProfile); closeActionMenu(); }}>
                    <PlayArrowIcon fontSize="small" sx={{ mr: 1.5 }} /> Test
                </MenuItem>
                {actionProfile && settings?.active_profile_id !== actionProfile._id && (
                    <MenuItem disabled={!actionProfile.enabled || busyId === actionProfile._id} onClick={() => { const profile = actionProfile; closeActionMenu(); void activate(profile); }}>
                        <PowerSettingsNewIcon fontSize="small" sx={{ mr: 1.5 }} /> Activate
                    </MenuItem>
                )}
                {actionProfile && !actionProfile.environment && settings?.active_profile_id === actionProfile._id && settings?.runtime_profile_id === actionProfile._id && (
                    <MenuItem onClick={() => {
                        setAdoptProfile(actionProfile);
                        setAdoptCollection("");
                        setAdoptConfirmation("");
                        setCompatibility(null);
                        closeActionMenu();
                    }}>
                        <GrainIcon fontSize="small" sx={{ mr: 1.5 }} /> Adopt existing collection
                    </MenuItem>
                )}
                {actionProfile && !actionProfile.environment && (
                    <MenuItem disabled={settings?.active_profile_id === actionProfile._id || settings?.runtime_profile_id === actionProfile._id} onClick={() => { openEdit(actionProfile); closeActionMenu(); }}>
                        <EditIcon fontSize="small" sx={{ mr: 1.5 }} /> Edit
                    </MenuItem>
                )}
                {actionProfile && !actionProfile.environment && (
                    <MenuItem disabled={settings?.active_profile_id === actionProfile._id || settings?.runtime_profile_id === actionProfile._id} onClick={() => { const profile = actionProfile; closeActionMenu(); void remove(profile); }} sx={{ color: "error.main" }}>
                        <DeleteIcon fontSize="small" sx={{ mr: 1.5 }} /> Delete
                    </MenuItem>
                )}
            </Menu>

            <Dialog open={Boolean(reindexPlan)} onClose={() => busyId === null && setReindexPlan(null)} fullWidth maxWidth="sm">
                <DialogTitle>Confirm full Knowledge re-index</DialogTitle>
                <DialogContent dividers>
                    {reindexPlan && (
                        <Stack spacing={2}>
                            <Alert severity="warning">
                                This reprocesses stored source files and approved web pages into <strong>{reindexPlan.collection_name}</strong>. It may consume provider capacity and take time.
                            </Alert>
                            <Typography>Profile: {reindexPlan.profile_name}</Typography>
                            <Typography>Model: {reindexPlan.model} · {reindexPlan.dimensions} dimensions</Typography>
                            <Typography>Total sources: {reindexPlan.total}</Typography>
                            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                                {Object.entries(reindexPlan.counts).map(([scope, count]) => <Chip key={scope} size="small" label={`${scope}: ${count}`} />)}
                            </Stack>
                            <TextField
                                label={`Type ${reindexPlan.confirmation} to confirm`}
                                value={reindexConfirmation}
                                onChange={event => setReindexConfirmation(event.target.value)}
                                autoComplete="off"
                            />
                        </Stack>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setReindexPlan(null)} disabled={busyId !== null}>Cancel</Button>
                    <Button color="warning" variant="contained" onClick={() => void startReindex()} disabled={!reindexPlan || reindexConfirmation !== reindexPlan.confirmation || busyId !== null}>Start re-index</Button>
                </DialogActions>
            </Dialog>

            <Dialog open={Boolean(adoptProfile)} onClose={() => busyId === null && setAdoptProfile(null)} fullWidth maxWidth="sm">
                <DialogTitle>Adopt existing vector collection</DialogTitle>
                <DialogContent dividers>
                    <Stack spacing={2}>
                        <Alert severity="info">
                            Use this only when the embedding model was moved without changing its vector space. The server compares fresh vectors with stored vectors before allowing adoption.
                        </Alert>
                        <TextField
                            label="Existing Qdrant Collection"
                            required
                            value={adoptCollection}
                            onChange={event => { setAdoptCollection(event.target.value); setCompatibility(null); setAdoptConfirmation(""); }}
                            disabled={busyId !== null}
                        />
                        <Button variant="outlined" onClick={() => void previewAdoption()} disabled={!adoptCollection.trim() || busyId !== null}>
                            Test vector compatibility
                        </Button>
                        {compatibility && (
                            <Alert severity={compatibility.compatible ? "success" : "error"}>
                                {compatibility.compatible ? "Compatible" : "Not compatible"}: minimum cosine {compatibility.minimum_cosine_similarity.toFixed(6)}, mean {compatibility.mean_cosine_similarity.toFixed(6)} across {compatibility.sample_count} samples.
                            </Alert>
                        )}
                        {compatibility?.compatible && (
                            <TextField
                                label={`Type ADOPT ${compatibility.collection_name} to confirm`}
                                value={adoptConfirmation}
                                onChange={event => setAdoptConfirmation(event.target.value)}
                                autoComplete="off"
                            />
                        )}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setAdoptProfile(null)} disabled={busyId !== null}>Cancel</Button>
                    <Button
                        variant="contained"
                        onClick={() => void applyCollectionAdoption()}
                        disabled={!compatibility?.compatible || adoptConfirmation !== `ADOPT ${compatibility?.collection_name ?? ""}` || busyId !== null}
                    >
                        Adopt and require restart
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog open={dialogOpen} onClose={() => busyId === null && setDialogOpen(false)} fullWidth maxWidth="sm">
                <DialogTitle>{editing ? "Edit Embedding Profile" : "Add Embedding Profile"}</DialogTitle>
                <DialogContent dividers>
                    <Stack spacing={2}>
                        <TextField label="Profile Name" required value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} />
                        <TextField select label="Provider" value={form.provider} onChange={event => setForm({ ...form, provider: event.target.value as EmbeddingProviderAdapter })}>
                            <MenuItem value="openai_compatible">OpenAI-compatible / Ollama</MenuItem>
                            <MenuItem value="ai_gateway">Enterprise AI Gateway</MenuItem>
                            <MenuItem value="azure_openai">Azure OpenAI</MenuItem>
                            <MenuItem value="openai">OpenAI</MenuItem>
                        </TextField>
                        <TextField label="Model" required value={form.model} onChange={event => setForm({ ...form, model: event.target.value })} />
                        {form.provider === "azure_openai" && <TextField label="Deployment" required value={form.deployment ?? ""} onChange={event => setForm({ ...form, deployment: event.target.value })} />}
                        {form.provider === "azure_openai" && <TextField label="Azure Endpoint" required value={form.endpoint ?? ""} onChange={event => setForm({ ...form, endpoint: event.target.value })} />}
                        {form.provider === "openai_compatible" && <TextField label="Base URL" required value={form.base_url ?? ""} onChange={event => setForm({ ...form, base_url: event.target.value })} helperText="Use http://ollama:11434/v1 for the bundled Docker service." />}
                        {form.provider === "ai_gateway" && (
                            <TextField
                                label="Embedding Proxy Path"
                                required
                                value={form.gateway_proxy_path ?? ""}
                                onChange={event => setForm({ ...form, gateway_proxy_path: event.target.value })}
                                helperText="Appended to the configured Enterprise Gateway Base URL. Authentication and TLS policy are reused; credentials are not copied."
                            />
                        )}
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
