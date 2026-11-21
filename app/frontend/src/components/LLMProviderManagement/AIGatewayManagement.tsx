import { useEffect, useState } from "react";
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    MenuItem,
    Paper,
    Stack,
    Switch,
    TextField,
    Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import HubIcon from "@mui/icons-material/Hub";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import SaveIcon from "@mui/icons-material/Save";
import { useMsal } from "@azure/msal-react";

import { getAIGatewaySettingsApi, testAIGatewayApi, updateAIGatewaySettingsApi } from "../../api";
import {
    AIGatewayAuthType,
    AIGatewayModel,
    AIGatewaySettings,
    AIGatewaySettingsPayload
} from "../../api/models";
import { getToken } from "../../authConfig";

type GatewayForm = AIGatewaySettings & {
    api_key: string;
    client_secret: string;
    ca_certificate: string;
    client_certificate: string;
    client_private_key: string;
};

const emptyModel = (): AIGatewayModel => ({
    id: "",
    label: "",
    model: "",
    supports_tools: true,
    supports_vision: false
});

const emptySettings = (): GatewayForm => ({
    mode: "built_in",
    name: "",
    base_url: "",
    auth_type: "none",
    token_url: "",
    client_id: "",
    oauth_scope: "",
    oauth_audience: "",
    oauth_client_auth_method: "client_secret_post",
    mtls_enabled: false,
    models: [],
    default_model_id: "",
    timeout_seconds: 60,
    has_api_key: false,
    has_client_secret: false,
    has_ca_certificate: false,
    has_client_certificate: false,
    has_client_private_key: false,
    direct_provider_access_blocked: false,
    direct_development_allowed: false,
    insecure_http_allowed: false,
    api_key: "",
    client_secret: "",
    ca_certificate: "",
    client_certificate: "",
    client_private_key: ""
});

const toForm = (settings: AIGatewaySettings): GatewayForm => ({
    ...settings,
    api_key: "",
    client_secret: "",
    ca_certificate: "",
    client_certificate: "",
    client_private_key: ""
});

const validateExternalForm = (form: GatewayForm): string | null => {
    if (form.mode !== "external") return null;
    if (!form.name.trim()) return "Enter a Gateway Name before saving.";
    if (!form.base_url.trim()) return "Enter an OpenAI-compatible Base URL before saving.";
    if (form.auth_type === "api_key" && !form.api_key && !form.has_api_key) {
        return "Enter an API Key before saving.";
    }
    if (form.auth_type === "oauth2_client_credentials") {
        if (!form.token_url.trim()) return "Enter an OAuth Token URL before saving.";
        if (!form.client_id.trim()) return "Enter an OAuth Client ID before saving.";
        if (!form.client_secret && !form.has_client_secret) return "Enter an OAuth Client Secret before saving.";
    }
    if (form.auth_type === "mulesoft_client_id_enforcement") {
        if (!form.client_id.trim()) return "Enter a MuleSoft Client ID before saving.";
        if (!form.client_secret && !form.has_client_secret) return "Enter a MuleSoft Client Secret before saving.";
    }
    if (form.models.length === 0) return "Add at least one Gateway Model Alias before saving.";
    if (form.models.some(model => !model.id.trim() || !model.model.trim())) {
        return "Complete the Model ID and Gateway Model Alias for every model before saving.";
    }
    if (!form.default_model_id) return "Select a Default Model before saving.";
    return null;
};

export function AIGatewayManagement({ onChanged }: { onChanged?: () => void }) {
    const { instance } = useMsal();
    const [form, setForm] = useState<GatewayForm>(emptySettings());
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);
    const [notice, setNotice] = useState<{ severity: "success" | "warning" | "error"; text: string } | null>(null);

    const load = async () => {
        setLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            setForm(toForm(await getAIGatewaySettingsApi(token)));
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to load AI Gateway settings" });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void load();
    }, [instance]);

    const updateModel = <K extends keyof AIGatewayModel>(index: number, key: K, value: AIGatewayModel[K]) => {
        setForm(current => ({
            ...current,
            models: current.models.map((model, modelIndex) => modelIndex === index ? { ...model, [key]: value } : model)
        }));
    };

    const save = async () => {
        const validationError = validateExternalForm(form);
        if (validationError) {
            setNotice({ severity: "warning", text: validationError });
            return;
        }
        setSaving(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const payload: AIGatewaySettingsPayload = {
                mode: form.mode,
                name: form.name,
                base_url: form.base_url,
                auth_type: form.auth_type,
                token_url: form.token_url,
                client_id: form.client_id,
                oauth_scope: form.oauth_scope,
                oauth_audience: form.oauth_audience,
                oauth_client_auth_method: form.oauth_client_auth_method,
                mtls_enabled: form.mtls_enabled,
                models: form.models,
                default_model_id: form.default_model_id,
                timeout_seconds: form.timeout_seconds,
                api_key: form.api_key || undefined,
                client_secret: form.client_secret || undefined,
                ca_certificate: form.ca_certificate || undefined,
                client_certificate: form.client_certificate || undefined,
                client_private_key: form.client_private_key || undefined
            };
            const saved = await updateAIGatewaySettingsApi(payload, token);
            setForm(toForm(saved));
            window.dispatchEvent(new Event("nexora:llm-profiles-changed"));
            onChanged?.();
            setNotice({ severity: "success", text: "AI Gateway routing policy saved" });
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to save AI Gateway settings" });
        } finally {
            setSaving(false);
        }
    };

    const test = async () => {
        setTesting(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const result = await testAIGatewayApi(token);
            setNotice({ severity: "success", text: `Gateway connection succeeded through model ${result.model_id}` });
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Gateway connection failed" });
        } finally {
            setTesting(false);
        }
    };

    if (loading) {
        return <Paper variant="outlined" sx={{ p: 3, display: "flex", justifyContent: "center" }}><CircularProgress size={28} /></Paper>;
    }

    const external = form.mode === "external";
    const secretLabel = (label: string, stored: boolean) => stored ? `${label} (leave blank to keep stored value)` : label;

    return (
        <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 } }}>
            <Stack spacing={2.25}>
                <Box display="flex" alignItems="center" gap={1.5}>
                    <HubIcon color="primary" />
                    <Box flex={1}>
                        <Typography variant="h6">Enterprise AI Gateway</Typography>
                        <Typography variant="body2" color="text.secondary">
                            Select the deployment-wide route used by every Chat and Agent LLM request.
                        </Typography>
                    </Box>
                    <Chip
                        color={external ? "primary" : "default"}
                        label={external ? "Direct provider access blocked" : form.mode === "built_in" ? "Built-in routing" : "Development routing"}
                    />
                </Box>

                <TextField
                    select
                    label="Routing Mode"
                    value={form.mode}
                    onChange={event => setForm({ ...form, mode: event.target.value as GatewayForm["mode"] })}
                    helperText="External mode fails closed: saved direct-provider profiles are not exposed to runtime."
                >
                    <MenuItem value="built_in">Built-in Gateway — use InsightSphere managed providers</MenuItem>
                    <MenuItem value="external">External AI Gateway — route all LLM calls through one governed endpoint</MenuItem>
                    <MenuItem value="direct_development" disabled={!form.direct_development_allowed}>
                        Direct Development — environment profiles only{!form.direct_development_allowed ? " (disabled by deployment policy)" : ""}
                    </MenuItem>
                </TextField>

                {external && (
                    <>
                        <Alert severity="warning">
                            Saving External mode immediately replaces all effective LLM routes. If the gateway is unavailable, requests fail instead of bypassing it.
                        </Alert>
                        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                            <TextField fullWidth required label="Gateway Name" value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} />
                            <TextField
                                fullWidth
                                required
                                label="OpenAI-compatible Base URL"
                                value={form.base_url}
                                onChange={event => setForm({ ...form, base_url: event.target.value })}
                                helperText={form.insecure_http_allowed ? "HTTP is permitted by deployment policy." : "HTTPS is required."}
                            />
                            <TextField
                                sx={{ minWidth: 170 }}
                                type="number"
                                label="Timeout (seconds)"
                                value={form.timeout_seconds}
                                onChange={event => setForm({ ...form, timeout_seconds: Number(event.target.value) })}
                                inputProps={{ min: 5, max: 300 }}
                            />
                        </Stack>

                        <TextField
                            select
                            label="Authentication"
                            value={form.auth_type}
                            onChange={event => setForm({ ...form, auth_type: event.target.value as AIGatewayAuthType })}
                        >
                            <MenuItem value="none">Network / gateway-managed authentication</MenuItem>
                            <MenuItem value="api_key">API key</MenuItem>
                            <MenuItem value="oauth2_client_credentials">OAuth 2.0 client credentials</MenuItem>
                            <MenuItem value="mulesoft_client_id_enforcement">MuleSoft Client ID enforcement</MenuItem>
                        </TextField>
                        {form.auth_type === "api_key" && (
                            <TextField
                                type="password"
                                autoComplete="new-password"
                                required={!form.has_api_key}
                                label={secretLabel("API Key", form.has_api_key)}
                                value={form.api_key}
                                onChange={event => setForm({ ...form, api_key: event.target.value })}
                            />
                        )}
                        {form.auth_type === "oauth2_client_credentials" && (
                            <Stack spacing={1.5}>
                                <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                                    <TextField fullWidth required label="OAuth Token URL" value={form.token_url} onChange={event => setForm({ ...form, token_url: event.target.value })} />
                                    <TextField fullWidth required label="Client ID" value={form.client_id} onChange={event => setForm({ ...form, client_id: event.target.value })} />
                                    <TextField
                                        fullWidth
                                        required={!form.has_client_secret}
                                        type="password"
                                        autoComplete="new-password"
                                        label={secretLabel("Client Secret", form.has_client_secret)}
                                        value={form.client_secret}
                                        onChange={event => setForm({ ...form, client_secret: event.target.value })}
                                    />
                                </Stack>
                                <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                                    <TextField fullWidth label="OAuth Scope (optional)" value={form.oauth_scope} onChange={event => setForm({ ...form, oauth_scope: event.target.value })} />
                                    <TextField fullWidth label="OAuth Audience (optional)" value={form.oauth_audience} onChange={event => setForm({ ...form, oauth_audience: event.target.value })} />
                                    <TextField
                                        fullWidth select label="Client Authentication"
                                        value={form.oauth_client_auth_method}
                                        onChange={event => setForm({ ...form, oauth_client_auth_method: event.target.value as GatewayForm["oauth_client_auth_method"] })}
                                    >
                                        <MenuItem value="client_secret_post">Credentials in request body</MenuItem>
                                        <MenuItem value="client_secret_basic">HTTP Basic authentication</MenuItem>
                                    </TextField>
                                </Stack>
                            </Stack>
                        )}
                        {form.auth_type === "mulesoft_client_id_enforcement" && (
                            <Stack spacing={1.5}>
                                <Alert severity="info">
                                    Sends MuleSoft Client ID Enforcement headers: client_id, client_secret, and ClientId. This does not request an OAuth access token.
                                </Alert>
                                <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                                    <TextField
                                        fullWidth
                                        required
                                        label="Client ID"
                                        value={form.client_id}
                                        onChange={event => setForm({ ...form, client_id: event.target.value })}
                                    />
                                    <TextField
                                        fullWidth
                                        required={!form.has_client_secret}
                                        type="password"
                                        autoComplete="new-password"
                                        label={secretLabel("Client Secret", form.has_client_secret)}
                                        value={form.client_secret}
                                        onChange={event => setForm({ ...form, client_secret: event.target.value })}
                                    />
                                </Stack>
                            </Stack>
                        )}

                        <TextField
                            multiline
                            minRows={2}
                            label={secretLabel("Custom CA Certificate PEM (optional)", form.has_ca_certificate)}
                            value={form.ca_certificate}
                            onChange={event => setForm({ ...form, ca_certificate: event.target.value })}
                        />
                        <Stack direction="row" alignItems="center" spacing={1}>
                            <Switch checked={form.mtls_enabled} onChange={event => setForm({ ...form, mtls_enabled: event.target.checked })} />
                            <Typography>Use mutual TLS client authentication</Typography>
                        </Stack>
                        {form.mtls_enabled && (
                            <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                                <TextField
                                    fullWidth multiline minRows={3}
                                    required={!form.has_client_certificate}
                                    label={secretLabel("Client Certificate PEM", form.has_client_certificate)}
                                    value={form.client_certificate}
                                    onChange={event => setForm({ ...form, client_certificate: event.target.value })}
                                />
                                <TextField
                                    fullWidth multiline minRows={3}
                                    required={!form.has_client_private_key}
                                    label={secretLabel("Client Private Key PEM", form.has_client_private_key)}
                                    value={form.client_private_key}
                                    onChange={event => setForm({ ...form, client_private_key: event.target.value })}
                                />
                            </Stack>
                        )}

                        <Box display="flex" justifyContent="space-between" alignItems="center">
                            <Box>
                                <Typography fontWeight={600}>Gateway Model Aliases</Typography>
                                <Typography variant="caption" color="text.secondary">Map stable InsightSphere ids to model aliases understood by the gateway.</Typography>
                            </Box>
                            <Button startIcon={<AddIcon />} onClick={() => setForm({ ...form, models: [...form.models, emptyModel()] })}>Add Model</Button>
                        </Box>
                        {form.models.map((model, index) => (
                            <Paper key={index} variant="outlined" sx={{ p: 2 }}>
                                <Stack spacing={1.25}>
                                    <Stack direction={{ xs: "column", md: "row" }} spacing={1.25}>
                                        <TextField fullWidth required label="Model ID" value={model.id} onChange={event => updateModel(index, "id", event.target.value)} />
                                        <TextField fullWidth label="Display Label" value={model.label} onChange={event => updateModel(index, "label", event.target.value)} />
                                        <TextField fullWidth required label="Gateway Model Alias" value={model.model} onChange={event => updateModel(index, "model", event.target.value)} />
                                        <Button color="error" startIcon={<DeleteIcon />} onClick={() => setForm({ ...form, models: form.models.filter((_, i) => i !== index) })}>Remove</Button>
                                    </Stack>
                                    <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
                                        <Stack direction="row" alignItems="center"><Switch size="small" checked={model.supports_tools} onChange={event => updateModel(index, "supports_tools", event.target.checked)} /><Typography variant="body2">Tool calling</Typography></Stack>
                                        <Stack direction="row" alignItems="center"><Switch size="small" checked={model.supports_vision} onChange={event => updateModel(index, "supports_vision", event.target.checked)} /><Typography variant="body2">Vision</Typography></Stack>
                                    </Stack>
                                </Stack>
                            </Paper>
                        ))}
                        <TextField
                            select
                            required
                            label="Default Model"
                            value={form.default_model_id}
                            onChange={event => setForm({ ...form, default_model_id: event.target.value })}
                        >
                            {form.models.filter(model => model.id).map(model => <MenuItem key={model.id} value={model.id}>{model.label || model.id}</MenuItem>)}
                        </TextField>
                    </>
                )}

                {notice && <Alert severity={notice.severity} onClose={() => setNotice(null)}>{notice.text}</Alert>}

                <Stack direction="row" justifyContent="flex-end" spacing={1}>
                    {external && (
                        <Button variant="outlined" startIcon={testing ? <CircularProgress size={16} /> : <PlayArrowIcon />} disabled={testing || saving} onClick={() => void test()}>
                            Test Saved Route
                        </Button>
                    )}
                    <Button
                        variant="contained"
                        startIcon={saving ? <CircularProgress color="inherit" size={16} /> : <SaveIcon />}
                        disabled={saving || testing}
                        onClick={() => void save()}
                    >
                        Save Routing Policy
                    </Button>
                </Stack>
            </Stack>
        </Paper>
    );
}
