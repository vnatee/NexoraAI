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
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import SearchIcon from "@mui/icons-material/Search";
import MicrosoftIcon from "@mui/icons-material/Microsoft";
import HubIcon from "@mui/icons-material/Hub";
import TravelExploreIcon from "@mui/icons-material/TravelExplore";
import GroupWorkIcon from "@mui/icons-material/GroupWork";
import SpeedIcon from "@mui/icons-material/Speed";
import MemoryIcon from "@mui/icons-material/Memory";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import { useMsal } from "@azure/msal-react";
import { siAnthropic, siGooglegemini, siMistralai, siOllama, siOpenai, siOpenrouter } from "simple-icons";

import {
    createLLMProviderApi,
    deleteLLMProviderApi,
    listLLMProvidersApi,
    testLLMProviderApi,
    updateLLMProviderApi
} from "../../api";
import { LLMProviderAdapter, LLMProviderModel, LLMProviderPayload, LLMVendor, ManagedLLMProvider } from "../../api/models";
import { getToken } from "../../authConfig";

const emptyModel = (): LLMProviderModel => ({
    id: "",
    label: "",
    model: "",
    deployment: "",
    supports_tools: true,
    supports_vision: false
});

const vendorOptions: { id: LLMVendor; label: string; provider: LLMProviderAdapter; defaultBaseUrl?: string; requiresApiKey?: boolean }[] = [
    { id: "azure_openai", label: "Azure OpenAI", provider: "azure_openai" },
    { id: "openai", label: "OpenAI", provider: "openai", requiresApiKey: true },
    { id: "google_gemini", label: "Google Gemini", provider: "openai_compatible", defaultBaseUrl: "https://generativelanguage.googleapis.com/v1beta/openai/", requiresApiKey: true },
    { id: "anthropic_claude", label: "Anthropic Claude", provider: "openai_compatible", defaultBaseUrl: "https://api.anthropic.com/v1/", requiresApiKey: true },
    { id: "ollama", label: "Ollama (Local)", provider: "openai_compatible", defaultBaseUrl: "http://localhost:11434/v1/" },
    { id: "groq", label: "Groq", provider: "openai_compatible", defaultBaseUrl: "https://api.groq.com/openai/v1", requiresApiKey: true },
    { id: "openrouter", label: "OpenRouter", provider: "openai_compatible", defaultBaseUrl: "https://openrouter.ai/api/v1", requiresApiKey: true },
    { id: "mistral", label: "Mistral AI", provider: "openai_compatible", defaultBaseUrl: "https://api.mistral.ai/v1", requiresApiKey: true },
    { id: "deepseek", label: "DeepSeek", provider: "openai_compatible", defaultBaseUrl: "https://api.deepseek.com/v1", requiresApiKey: true },
    { id: "together", label: "Together AI", provider: "openai_compatible", defaultBaseUrl: "https://api.together.xyz/v1", requiresApiKey: true },
    { id: "vllm", label: "vLLM (Local)", provider: "openai_compatible", defaultBaseUrl: "http://localhost:8000/v1" },
    { id: "localai", label: "LocalAI (Local)", provider: "openai_compatible", defaultBaseUrl: "http://localhost:8080/v1" },
    { id: "other_openai_compatible", label: "Other OpenAI-compatible", provider: "openai_compatible" }
];

const providerBrandIcons: Partial<Record<LLMVendor, { title: string; path: string; hex: string }>> = {
    openai: siOpenai,
    google_gemini: siGooglegemini,
    anthropic_claude: siAnthropic,
    ollama: siOllama,
    openrouter: siOpenrouter,
    mistral: siMistralai
};

const providerFallbackIcons: Partial<Record<LLMVendor, typeof SmartToyIcon>> = {
    azure_openai: MicrosoftIcon,
    groq: HubIcon,
    deepseek: TravelExploreIcon,
    together: GroupWorkIcon,
    vllm: SpeedIcon,
    localai: MemoryIcon,
    other_openai_compatible: SmartToyIcon
};

function ProviderLogo({ vendor, label }: { vendor: LLMVendor; label: string }) {
    const brand = providerBrandIcons[vendor];
    const FallbackIcon = providerFallbackIcons[vendor];
    const fallbackColors: Partial<Record<LLMVendor, string>> = {
        azure_openai: "#0078D4",
        groq: "#F55036",
        deepseek: "#4D6BFE",
        together: "#6B57E0",
        vllm: "#3568D4",
        localai: "#269B78",
        other_openai_compatible: "#64748B"
    };

    return (
        <Avatar
            variant="rounded"
            sx={{
                width: 72,
                height: 72,
                mt: 3,
                mb: 2,
                bgcolor: "background.paper",
                color: fallbackColors[vendor] ?? "text.primary",
                border: "1px solid",
                borderColor: "divider",
                boxShadow: 1
            }}
        >
            {brand ? (
                <svg width="42" height="42" viewBox="0 0 24 24" role="img" aria-label={brand.title}>
                    <path d={brand.path} fill={`#${brand.hex}`} />
                </svg>
            ) : FallbackIcon ? (
                <FallbackIcon sx={{ fontSize: 42 }} aria-label={`${label} icon`} />
            ) : (
                label.slice(0, 2).toUpperCase()
            )}
        </Avatar>
    );
}

const selectVendor = (form: LLMProviderPayload, vendorId: LLMVendor): LLMProviderPayload => {
    const vendor = vendorOptions.find(option => option.id === vendorId)!;
    return {
        ...form,
        vendor: vendor.id,
        provider: vendor.provider,
        endpoint: vendor.provider === "azure_openai" ? form.endpoint : "",
        base_url: vendor.provider === "openai_compatible" ? vendor.defaultBaseUrl ?? "" : "",
        api_version: vendor.provider === "azure_openai" ? form.api_version || "2024-10-21" : ""
    };
};

const emptyPayload = (): LLMProviderPayload => ({
    name: "",
    vendor: "azure_openai",
    provider: "azure_openai",
    endpoint: "",
    base_url: "",
    api_version: "2024-10-21",
    organization: "",
    models: [emptyModel()],
    enabled: true,
    api_key: ""
});

const notifyProfileCapabilitiesChanged = () => {
    window.dispatchEvent(new Event("nexora:llm-profiles-changed"));
};

export function LLMProviderManagement() {
    const { instance } = useMsal();
    const [providers, setProviders] = useState<ManagedLLMProvider[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [testingId, setTestingId] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editing, setEditing] = useState<ManagedLLMProvider | null>(null);
    const [form, setForm] = useState<LLMProviderPayload>(emptyPayload());
    const [notice, setNotice] = useState<{ severity: "success" | "warning" | "error"; text: string } | null>(null);
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<"all" | "enabled" | "disabled">("all");
    const [actionAnchor, setActionAnchor] = useState<HTMLElement | null>(null);
    const [actionProvider, setActionProvider] = useState<ManagedLLMProvider | null>(null);
    const selectedVendor = vendorOptions.find(vendor => vendor.id === form.vendor);
    const apiKeyRequired = Boolean(selectedVendor?.requiresApiKey && form.enabled && !editing?.has_api_key);

    const loadProviders = async () => {
        setLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            setProviders(await listLLMProvidersApi(token));
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Failed to load providers" });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadProviders();
    }, [instance]);

    const filteredProviders = useMemo(() => {
        const query = search.trim().toLowerCase();
        return providers.filter(provider => {
            if (statusFilter === "enabled" && !provider.enabled) return false;
            if (statusFilter === "disabled" && provider.enabled) return false;
            if (!query) return true;
            const modelText = provider.models.map(model => `${model.label} ${model.model}`).join(" ");
            return `${provider.name} ${provider.vendor_label} ${provider.endpoint ?? ""} ${provider.base_url ?? ""} ${modelText}`
                .toLowerCase()
                .includes(query);
        });
    }, [providers, search, statusFilter]);

    const closeActionMenu = () => {
        setActionAnchor(null);
        setActionProvider(null);
    };

    const openCreate = () => {
        setEditing(null);
        setForm(emptyPayload());
        setDialogOpen(true);
    };

    const openEdit = (provider: ManagedLLMProvider) => {
        setEditing(provider);
        setForm({
            name: provider.name,
            vendor: provider.vendor,
            provider: provider.provider,
            endpoint: provider.endpoint ?? "",
            base_url: provider.base_url ?? "",
            api_version: provider.api_version ?? "2024-10-21",
            organization: provider.organization ?? "",
            models: provider.models.map(model => ({
                ...model,
                supports_tools: model.supports_tools ?? true,
                supports_vision: model.supports_vision ?? false
            })),
            enabled: provider.enabled,
            api_key: ""
        });
        setDialogOpen(true);
    };

    const updateModel = (index: number, field: keyof LLMProviderModel, value: string) => {
        const models = form.models.map((model, modelIndex) => (modelIndex === index ? { ...model, [field]: value } : model));
        setForm({ ...form, models });
    };

    const save = async () => {
        setSaving(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            if (editing) {
                await updateLLMProviderApi(editing._id, form, token);
            } else {
                await createLLMProviderApi(form, token);
            }
            setDialogOpen(false);
            setNotice({ severity: "success", text: `Provider ${editing ? "updated" : "created"} successfully` });
            await loadProviders();
            notifyProfileCapabilitiesChanged();
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Failed to save provider" });
        } finally {
            setSaving(false);
        }
    };

    const remove = async (provider: ManagedLLMProvider) => {
        if (!window.confirm(`Remove ${provider.name}?`)) return;
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            await deleteLLMProviderApi(provider._id, token);
            setNotice({ severity: "success", text: "Provider removed" });
            await loadProviders();
            notifyProfileCapabilitiesChanged();
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Failed to remove provider" });
        }
    };

    const testConnection = async (provider: ManagedLLMProvider) => {
        if (provider.models.length === 0) return;
        setTestingId(provider._id);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const unsupported: string[] = [];
            const unknown: string[] = [];
            const visionUnsupported: string[] = [];
            const visionUnknown: string[] = [];
            const failed: string[] = [];
            for (const model of provider.models) {
                try {
                    const result = await testLLMProviderApi(provider._id, model.id, token);
                    if (result.tool_capability.status === "unsupported") unsupported.push(model.label || model.model);
                    if (result.tool_capability.status === "unknown") unknown.push(model.label || model.model);
                    if (result.vision_capability.status === "unsupported") visionUnsupported.push(model.label || model.model);
                    if (result.vision_capability.status === "unknown") visionUnknown.push(model.label || model.model);
                } catch {
                    failed.push(model.label || model.model);
                }
            }
            await loadProviders();
            notifyProfileCapabilitiesChanged();
            if (failed.length > 0) {
                setNotice({ severity: "error", text: `${provider.name}: connection failed for ${failed.join(", ")}` });
            } else if (unsupported.length > 0 || unknown.length > 0 || visionUnsupported.length > 0 || visionUnknown.length > 0) {
                const details = [
                    unsupported.length > 0 ? `tool calling unsupported: ${unsupported.join(", ")}` : "",
                    unknown.length > 0 ? `tool capability inconclusive: ${unknown.join(", ")}` : "",
                    visionUnsupported.length > 0 ? `vision unsupported: ${visionUnsupported.join(", ")}` : "",
                    visionUnknown.length > 0 ? `vision capability inconclusive: ${visionUnknown.join(", ")}` : ""
                ].filter(Boolean).join("; ");
                setNotice({ severity: "warning", text: `${provider.name} connection succeeded; ${details}` });
            } else {
                setNotice({ severity: "success", text: `${provider.name} connection, tool calling, and vision checks succeeded for all models` });
            }
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Connection failed" });
        } finally {
            setTestingId(null);
        }
    };

    return (
        <Stack spacing={2} sx={{ pt: 1 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                    <Typography variant="h6">LLM Providers</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Manage provider connections and models available to agents. Secrets are never shown after saving.
                    </Typography>
                </Box>
                <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
                    Add Provider
                </Button>
            </Box>

            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                <TextField
                    fullWidth
                    size="small"
                    placeholder="Search providers or models..."
                    value={search}
                    onChange={event => setSearch(event.target.value)}
                    InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon color="action" /></InputAdornment> }}
                />
                <TextField
                    select
                    size="small"
                    label="Status"
                    value={statusFilter}
                    onChange={event => setStatusFilter(event.target.value as typeof statusFilter)}
                    sx={{ minWidth: 170 }}
                >
                    <MenuItem value="all">All</MenuItem>
                    <MenuItem value="enabled">Enabled</MenuItem>
                    <MenuItem value="disabled">Disabled</MenuItem>
                </TextField>
            </Stack>

            {loading ? (
                <Box display="flex" justifyContent="center" py={6}><CircularProgress /></Box>
            ) : providers.length === 0 ? (
                <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
                    <Typography color="text.secondary">No managed LLM providers yet. System default remains available.</Typography>
                </Paper>
            ) : filteredProviders.length === 0 ? (
                <Alert severity="info">No providers match the current search and status filter.</Alert>
            ) : (
                <Box sx={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 240px), 1fr))",
                    gap: 2
                }}>
                    {filteredProviders.map(provider => {
                        const toolsCount = provider.models.filter(model => model.tool_capability_status === "supported").length;
                        const visionCount = provider.models.filter(model => model.vision_capability_status === "supported").length;
                        const endpoint = provider.endpoint || provider.base_url || "Default provider endpoint";
                        return (
                            <Paper
                                key={provider._id}
                                variant="outlined"
                                role="button"
                                tabIndex={0}
                                onClick={() => openEdit(provider)}
                                onKeyDown={event => {
                                    if (event.key === "Enter" || event.key === " ") {
                                        event.preventDefault();
                                        openEdit(provider);
                                    }
                                }}
                                sx={{
                                    p: 2,
                                    minHeight: 310,
                                    display: "flex",
                                    flexDirection: "column",
                                    alignItems: "center",
                                    textAlign: "center",
                                    position: "relative",
                                    cursor: "pointer",
                                    transition: "transform 150ms ease, box-shadow 150ms ease, border-color 150ms ease",
                                    "&:hover": { transform: "translateY(-2px)", boxShadow: 3, borderColor: "primary.light" },
                                    "&:focus-visible": { outline: "3px solid", outlineColor: "primary.light", outlineOffset: 2 }
                                }}
                            >
                                <Chip
                                    size="small"
                                    color={provider.enabled ? "success" : "default"}
                                    label={provider.enabled ? "Enabled" : "Disabled"}
                                    sx={{ position: "absolute", top: 12, left: 12 }}
                                />
                                <IconButton
                                    size="small"
                                    aria-label={`Actions for ${provider.name}`}
                                    onClick={event => {
                                        event.stopPropagation();
                                        setActionProvider(provider);
                                        setActionAnchor(event.currentTarget);
                                    }}
                                    sx={{ position: "absolute", top: 8, right: 8 }}
                                >
                                    {testingId === provider._id ? <CircularProgress size={20} /> : <MoreHorizIcon />}
                                </IconButton>
                                <ProviderLogo vendor={provider.vendor} label={provider.vendor_label} />
                                <Typography variant="h6" fontSize="1rem" fontWeight={700} sx={{ lineHeight: 1.3, minHeight: 42, overflowWrap: "anywhere" }}>
                                    {provider.name}
                                </Typography>
                                <Typography variant="body2" color="text.secondary" fontWeight={500}>
                                    {provider.vendor_label}
                                </Typography>
                                <Typography
                                    variant="caption"
                                    color="text.secondary"
                                    title={endpoint}
                                    sx={{ mt: 1, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", overflowWrap: "anywhere" }}
                                >
                                    {endpoint}
                                </Typography>
                                <Box sx={{ flex: 1 }} />
                                <Typography variant="caption" color="text.secondary" sx={{ mt: 2 }}>
                                    {provider.models.length} {provider.models.length === 1 ? "model" : "models"}
                                    {provider.has_api_key ? " · Credential stored" : ""}
                                </Typography>
                                <Stack direction="row" spacing={0.5} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap justifyContent="center">
                                    {toolsCount > 0 && <Chip size="small" color="success" variant="outlined" label={`Tools ${toolsCount}`} />}
                                    {visionCount > 0 && <Chip size="small" color="success" variant="outlined" label={`Vision ${visionCount}`} />}
                                    {provider.models.slice(0, 1).map(model => <Chip key={model.id} size="small" label={model.label || model.model} />)}
                                    {provider.models.length > 1 && <Chip size="small" variant="outlined" label={`+${provider.models.length - 1}`} />}
                                </Stack>
                            </Paper>
                        );
                    })}
                </Box>
            )}

            <Menu anchorEl={actionAnchor} open={Boolean(actionAnchor)} onClose={closeActionMenu}>
                <MenuItem
                    disabled={!actionProvider || testingId === actionProvider._id}
                    onClick={() => {
                        if (actionProvider) void testConnection(actionProvider);
                        closeActionMenu();
                    }}
                >
                    <PlayArrowIcon fontSize="small" sx={{ mr: 1.5 }} /> Test all models
                </MenuItem>
                <MenuItem onClick={() => { if (actionProvider) openEdit(actionProvider); closeActionMenu(); }}>
                    <EditIcon fontSize="small" sx={{ mr: 1.5 }} /> Edit
                </MenuItem>
                <MenuItem
                    onClick={() => {
                        const provider = actionProvider;
                        closeActionMenu();
                        if (provider) void remove(provider);
                    }}
                    sx={{ color: "error.main" }}
                >
                    <DeleteIcon fontSize="small" sx={{ mr: 1.5 }} /> Delete
                </MenuItem>
            </Menu>

            <Dialog open={dialogOpen} onClose={() => !saving && setDialogOpen(false)} fullWidth maxWidth="md">
                <DialogTitle>{editing ? "Edit LLM Provider" : "Add LLM Provider"}</DialogTitle>
                <DialogContent dividers>
                    <Stack spacing={2}>
                        <TextField label="Provider Name" value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} required />
                        <TextField select label="Provider Type" value={form.vendor} onChange={event => setForm(selectVendor(form, event.target.value as LLMVendor))}>
                            {vendorOptions.map(vendor => <MenuItem key={vendor.id} value={vendor.id}>{vendor.label}</MenuItem>)}
                        </TextField>
                        {form.provider === "azure_openai" && (
                            <TextField label="Azure Endpoint" value={form.endpoint ?? ""} onChange={event => setForm({ ...form, endpoint: event.target.value })} required />
                        )}
                        {form.provider === "openai_compatible" && (
                            <TextField
                                label="Base URL"
                                value={form.base_url ?? ""}
                                onChange={event => setForm({ ...form, base_url: event.target.value })}
                                helperText={form.vendor === "ollama" ? "If the app runs in Docker, use the Ollama service name or host.docker.internal instead of localhost when needed." : "OpenAI-compatible endpoint; you can override the suggested URL."}
                                required
                            />
                        )}
                        {form.provider === "azure_openai" && (
                            <TextField
                                label="API Version"
                                value={form.api_version ?? ""}
                                onChange={event => setForm({ ...form, api_version: event.target.value })}
                                helperText="Used only by Azure OpenAI"
                            />
                        )}
                        <TextField
                            label={editing?.has_api_key ? "Replace API Key (leave blank to keep current)" : apiKeyRequired ? "API Key" : "API Key (optional for local/Azure identity)"}
                            type="password"
                            value={form.api_key ?? ""}
                            onChange={event => setForm({ ...form, api_key: event.target.value })}
                            autoComplete="new-password"
                            required={apiKeyRequired}
                            helperText={apiKeyRequired ? `${selectedVendor?.label} requires an API key when enabled.` : undefined}
                        />
                        <Stack direction="row" alignItems="center" spacing={1}>
                            <Switch checked={form.enabled} onChange={event => setForm({ ...form, enabled: event.target.checked })} />
                            <Typography>Enabled for Agent selection</Typography>
                        </Stack>

                        <Box display="flex" justifyContent="space-between" alignItems="center">
                            <Typography fontWeight={600}>Models / Deployments</Typography>
                            <Button size="small" startIcon={<AddIcon />} onClick={() => setForm({ ...form, models: [...form.models, emptyModel()] })}>
                                Add Model
                            </Button>
                        </Box>
                        {form.models.map((model, index) => (
                            <Paper key={index} variant="outlined" sx={{ p: 2 }}>
                                <Stack spacing={1}>
                                    <Stack direction={{ xs: "column", md: "row" }} spacing={1} alignItems="center">
                                        <TextField label="Model ID" value={model.id} onChange={event => updateModel(index, "id", event.target.value)} required fullWidth />
                                        <TextField label="Display Label" value={model.label} onChange={event => updateModel(index, "label", event.target.value)} fullWidth />
                                        <TextField label="Model Name" value={model.model} onChange={event => updateModel(index, "model", event.target.value)} required fullWidth />
                                        {form.provider === "azure_openai" && (
                                            <TextField label="Azure Deployment" value={model.deployment ?? ""} onChange={event => updateModel(index, "deployment", event.target.value)} fullWidth />
                                        )}
                                        <IconButton
                                            aria-label="Remove model"
                                            color="error"
                                            disabled={form.models.length === 1}
                                            onClick={() => setForm({ ...form, models: form.models.filter((_, modelIndex) => modelIndex !== index) })}
                                        >
                                            <DeleteIcon />
                                        </IconButton>
                                    </Stack>
                                    <Stack direction="row" alignItems="center" spacing={1}>
                                        <Switch
                                            size="small"
                                            checked={model.supports_tools ?? true}
                                            disabled={model.tool_capability_status === "unsupported"}
                                            onChange={event => {
                                                const models = form.models.map((item, modelIndex) =>
                                                    modelIndex === index ? { ...item, supports_tools: event.target.checked } : item
                                                );
                                                setForm({ ...form, models });
                                            }}
                                        />
                                        <Typography variant="body2" color={model.tool_capability_status === "unsupported" ? "text.disabled" : "text.primary"}>
                                            Supports tool / function calling
                                            {model.tool_capability_status === "unsupported" ? " — Not supported (detected by Test)" : ""}
                                            {model.tool_capability_status === "supported" ? " — Supported (detected by Test)" : ""}
                                        </Typography>
                                    </Stack>
                                    <Stack direction="row" alignItems="center" spacing={1}>
                                        <Switch
                                            size="small"
                                            checked={model.supports_vision ?? false}
                                            disabled={model.vision_capability_status === "unsupported"}
                                            onChange={event => {
                                                const models = form.models.map((item, modelIndex) =>
                                                    modelIndex === index ? { ...item, supports_vision: event.target.checked } : item
                                                );
                                                setForm({ ...form, models });
                                            }}
                                        />
                                        <Typography variant="body2" color={model.vision_capability_status === "unsupported" ? "text.disabled" : "text.primary"}>
                                            Supports image / vision input
                                            {model.vision_capability_status === "unsupported" ? " — Not supported (detected by Test)" : ""}
                                            {model.vision_capability_status === "supported" ? " — Supported (detected by Test)" : ""}
                                        </Typography>
                                    </Stack>
                                </Stack>
                            </Paper>
                        ))}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDialogOpen(false)} disabled={saving}>Cancel</Button>
                    <Button variant="contained" onClick={save} disabled={saving || !form.name || form.models.some(model => !model.id || !model.model)}>
                        {saving ? "Saving..." : "Save"}
                    </Button>
                </DialogActions>
            </Dialog>

            <Snackbar open={Boolean(notice)} autoHideDuration={5000} onClose={() => setNotice(null)} anchorOrigin={{ vertical: "top", horizontal: "right" }}>
                <Alert severity={notice?.severity ?? "success"} onClose={() => setNotice(null)}>{notice?.text}</Alert>
            </Snackbar>
        </Stack>
    );
}
