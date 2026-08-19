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
import { useMsal } from "@azure/msal-react";

import {
    createLLMProviderApi,
    deleteLLMProviderApi,
    listLLMProvidersApi,
    testLLMProviderApi,
    updateLLMProviderApi
} from "../../api";
import { LLMProviderAdapter, LLMProviderModel, LLMProviderPayload, LLMVendor, ManagedLLMProvider } from "../../api/models";
import { getToken } from "../../authConfig";

const emptyModel = (): LLMProviderModel => ({ id: "", label: "", model: "", deployment: "", supports_tools: true });

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

export function LLMProviderManagement() {
    const { instance } = useMsal();
    const [providers, setProviders] = useState<ManagedLLMProvider[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [testingId, setTestingId] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editing, setEditing] = useState<ManagedLLMProvider | null>(null);
    const [form, setForm] = useState<LLMProviderPayload>(emptyPayload());
    const [notice, setNotice] = useState<{ severity: "success" | "error"; text: string } | null>(null);
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
            models: provider.models.map(model => ({ ...model, supports_tools: model.supports_tools ?? true })),
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
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Failed to remove provider" });
        }
    };

    const testConnection = async (provider: ManagedLLMProvider) => {
        const model = provider.models[0];
        if (!model) return;
        setTestingId(provider._id);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            await testLLMProviderApi(provider._id, model.id, token);
            setNotice({ severity: "success", text: `${provider.name} connection succeeded` });
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

            {loading ? (
                <Box display="flex" justifyContent="center" py={6}><CircularProgress /></Box>
            ) : providers.length === 0 ? (
                <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
                    <Typography color="text.secondary">No managed LLM providers yet. System default remains available.</Typography>
                </Paper>
            ) : (
                <Stack spacing={1}>
                    {providers.map(provider => (
                        <Paper key={provider._id} variant="outlined" sx={{ p: 2 }}>
                            <Box display="flex" justifyContent="space-between" alignItems="center" gap={2}>
                                <Box minWidth={0}>
                                    <Stack direction="row" spacing={1} alignItems="center">
                                        <Typography fontWeight={600}>{provider.name}</Typography>
                                        <Chip size="small" label={provider.vendor_label} />
                                        <Chip size="small" color={provider.enabled ? "success" : "default"} label={provider.enabled ? "Enabled" : "Disabled"} />
                                        {provider.has_api_key && <Chip size="small" variant="outlined" label="API key stored" />}
                                    </Stack>
                                    <Typography variant="body2" color="text.secondary" noWrap>
                                        {provider.endpoint || provider.base_url || "Default provider endpoint"}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {provider.models.map(model => model.label || model.model).join(", ")}
                                    </Typography>
                                </Box>
                                <Stack direction="row" spacing={0.5}>
                                    <Button
                                        size="small"
                                        startIcon={testingId === provider._id ? <CircularProgress size={14} /> : <PlayArrowIcon />}
                                        disabled={testingId === provider._id}
                                        onClick={() => testConnection(provider)}
                                    >
                                        Test
                                    </Button>
                                    <IconButton aria-label="Edit provider" onClick={() => openEdit(provider)}><EditIcon /></IconButton>
                                    <IconButton aria-label="Remove provider" color="error" onClick={() => remove(provider)}><DeleteIcon /></IconButton>
                                </Stack>
                            </Box>
                        </Paper>
                    ))}
                </Stack>
            )}

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
                                            onChange={event => {
                                                const models = form.models.map((item, modelIndex) =>
                                                    modelIndex === index ? { ...item, supports_tools: event.target.checked } : item
                                                );
                                                setForm({ ...form, models });
                                            }}
                                        />
                                        <Typography variant="body2">Supports tool / function calling</Typography>
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
