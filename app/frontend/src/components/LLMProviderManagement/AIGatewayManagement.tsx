import { useEffect, useState } from "react";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
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
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import HubIcon from "@mui/icons-material/Hub";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import SaveIcon from "@mui/icons-material/Save";
import { useMsal } from "@azure/msal-react";

import {
    getAIGatewaySettingsApi,
    runAIGatewayConformanceApi,
    testAIGatewayApi,
    updateAIGatewaySettingsApi
} from "../../api";
import {
    AIGatewayAuthType,
    AIGatewayConformanceReport,
    AIGatewayProxy,
    AIGatewaySettings,
    AIGatewaySettingsPayload
} from "../../api/models";
import { getToken } from "../../authConfig";

type GatewayForm = Omit<AIGatewaySettings, "models" | "default_model_id"> & {
    api_key: string;
    client_secret: string;
    ca_certificate: string;
    client_certificate: string;
    client_private_key: string;
};

const emptyProxy = (): AIGatewayProxy => ({
    id: "",
    label: "",
    model: "",
    routing_strategy: "model_based",
    proxy_path: "",
    base_url: "",
    supports_tools: true,
    supports_vision: false
});

const emptySettings = (): GatewayForm => ({
    mode: "built_in",
    name: "",
    gateway_adapter: "generic_openai",
    base_url: "",
    auth_type: "none",
    token_url: "",
    client_id: "",
    oauth_scope: "",
    oauth_audience: "",
    oauth_client_auth_method: "client_secret_post",
    mtls_enabled: false,
    proxies: [],
    default_proxy_id: "",
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

const toForm = (settings: AIGatewaySettings): GatewayForm => {
    const { models: legacyModels, default_model_id: legacyDefault, ...current } = settings;
    return ({
    ...current,
    proxies: (settings.proxies || legacyModels || []).map(proxy => ({
        ...proxy,
        routing_strategy: proxy.routing_strategy || "model_based",
        proxy_path: proxy.proxy_path || "",
        // A pre-P1.2.2 MuleSoft record stored the complete proxy endpoint in
        // the gateway Base URL. Preserve it as a per-proxy override until an
        // administrator splits it into the shared root and Proxy Path.
        base_url: proxy.base_url || (
            settings.gateway_adapter === "mulesoft" && !proxy.proxy_path
                ? settings.base_url
                : ""
        )
    })),
    default_proxy_id: settings.default_proxy_id || legacyDefault || "",
    api_key: "",
    client_secret: "",
    ca_certificate: "",
    client_certificate: "",
    client_private_key: ""
    });
};

const validateExternalForm = (form: GatewayForm): string | null => {
    if (form.mode !== "external") return null;
    if (!form.name.trim()) return "Enter a Gateway Name before saving.";
    if (!form.base_url.trim()) return "Enter a Gateway Base URL before saving.";
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
    if (form.proxies.length === 0) return "Add at least one Model Proxy before saving.";
    if (form.proxies.some(proxy => !proxy.id.trim() || (proxy.routing_strategy !== "semantic" && !proxy.model.trim()))) {
        return "Complete the Route ID and Gateway Model Alias for every model-based route before saving.";
    }
    if (form.gateway_adapter === "mulesoft" && form.proxies.some(proxy => !proxy.proxy_path.trim() && !proxy.base_url.trim())) {
        return "Enter a Proxy Path for each MuleSoft Model Proxy, or use the advanced full URL override.";
    }
    if (form.proxies.some(proxy => proxy.routing_strategy === "semantic") && form.gateway_adapter !== "mulesoft") {
        return "Semantic Routing requires the MuleSoft AI Gateway template.";
    }
    if (!form.default_proxy_id) return "Select a Default Proxy before saving.";
    return null;
};

const proxyEndpointPreview = (baseUrl: string, proxy: AIGatewayProxy): string => {
    if (proxy.base_url.trim()) return proxy.base_url.trim().replace(/\/$/, "");
    const base = baseUrl.trim().replace(/\/$/, "");
    const path = proxy.proxy_path.trim().replace(/^\/+|\/+$/g, "");
    return path ? `${base}/${path}` : base;
};

const configurationFingerprint = (form: GatewayForm): string => JSON.stringify(form);

export function AIGatewayManagement({ onChanged }: { onChanged?: () => void }) {
    const { instance } = useMsal();
    const [form, setForm] = useState<GatewayForm>(emptySettings());
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [testingProxyId, setTestingProxyId] = useState<string | null>(null);
    const [conformanceProxyId, setConformanceProxyId] = useState<string | null>(null);
    const [conformanceByProxy, setConformanceByProxy] = useState<Record<string, AIGatewayConformanceReport>>({});
    const [savedProxyIds, setSavedProxyIds] = useState<Set<string>>(new Set());
    const [savedFingerprint, setSavedFingerprint] = useState("");
    const [semanticProbePrompts, setSemanticProbePrompts] = useState<Record<string, string>>({});
    const [expandedProxyIndex, setExpandedProxyIndex] = useState<number | false>(false);
    const [notice, setNotice] = useState<{ severity: "success" | "warning" | "error"; text: string } | null>(null);

    const load = async () => {
        setLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const settings = await getAIGatewaySettingsApi(token);
            const loadedForm = toForm(settings);
            setForm(loadedForm);
            setSavedFingerprint(configurationFingerprint(loadedForm));
            setSavedProxyIds(new Set((settings.proxies || settings.models || []).map(proxy => proxy.id)));
            setExpandedProxyIndex(false);
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to load AI Gateway settings" });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void load();
    }, [instance]);

    const updateProxy = <K extends keyof AIGatewayProxy>(index: number, key: K, value: AIGatewayProxy[K]) => {
        setForm(current => ({
            ...current,
            proxies: current.proxies.map((proxy, proxyIndex) => proxyIndex === index ? { ...proxy, [key]: value } : proxy)
        }));
    };

    const selectGatewayAdapter = (adapter: GatewayForm["gateway_adapter"]) => {
        setForm(current => ({
            ...current,
            gateway_adapter: adapter,
            name: current.name || (adapter === "mulesoft" ? "MuleSoft AI Gateway" : "Enterprise AI Gateway"),
            auth_type: adapter === "mulesoft"
                ? "mulesoft_client_id_enforcement"
                : current.auth_type === "mulesoft_client_id_enforcement" ? "none" : current.auth_type
        }));
        setConformanceByProxy({});
    };

    const addProxy = () => {
        setExpandedProxyIndex(form.proxies.length);
        setForm(current => ({ ...current, proxies: [...current.proxies, emptyProxy()] }));
    };

    const removeProxy = (index: number) => {
        setForm(current => ({
            ...current,
            proxies: current.proxies.filter((_, proxyIndex) => proxyIndex !== index)
        }));
        setExpandedProxyIndex(current => {
            if (current === false || current === index) return false;
            return current > index ? current - 1 : current;
        });
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
                gateway_adapter: form.gateway_adapter,
                base_url: form.base_url,
                auth_type: form.auth_type,
                token_url: form.token_url,
                client_id: form.client_id,
                oauth_scope: form.oauth_scope,
                oauth_audience: form.oauth_audience,
                oauth_client_auth_method: form.oauth_client_auth_method,
                mtls_enabled: form.mtls_enabled,
                proxies: form.proxies,
                default_proxy_id: form.default_proxy_id,
                timeout_seconds: form.timeout_seconds,
                api_key: form.api_key || undefined,
                client_secret: form.client_secret || undefined,
                ca_certificate: form.ca_certificate || undefined,
                client_certificate: form.client_certificate || undefined,
                client_private_key: form.client_private_key || undefined
            };
            const saved = await updateAIGatewaySettingsApi(payload, token);
            const savedForm = toForm(saved);
            setForm(savedForm);
            setSavedFingerprint(configurationFingerprint(savedForm));
            setSavedProxyIds(new Set((saved.proxies || saved.models || []).map(proxy => proxy.id)));
            setConformanceByProxy({});
            window.dispatchEvent(new Event("nexora:llm-profiles-changed"));
            onChanged?.();
            setNotice({ severity: "success", text: "AI Gateway routing policy saved" });
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to save AI Gateway settings" });
        } finally {
            setSaving(false);
        }
    };

    const testProxy = async (proxyId: string) => {
        setTestingProxyId(proxyId);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const result = await testAIGatewayApi(token, proxyId, semanticProbePrompts[proxyId]);
            setNotice({ severity: "success", text: `Model Proxy ${result.proxy_id} connection succeeded` });
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Gateway connection failed" });
        } finally {
            setTestingProxyId(null);
        }
    };

    const runConformance = async (proxyId: string) => {
        setConformanceProxyId(proxyId);
        setConformanceByProxy(current => {
            const next = { ...current };
            delete next[proxyId];
            return next;
        });
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const report = await runAIGatewayConformanceApi(token, proxyId, semanticProbePrompts[proxyId]);
            setConformanceByProxy(current => ({ ...current, [proxyId]: report }));
            setNotice({
                severity: report.ready ? "success" : "warning",
                text: report.ready
                    ? "Gateway passed all required conformance checks"
                    : "Gateway is not ready; review the failed checks below"
            });
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Gateway conformance check failed" });
        } finally {
            setConformanceProxyId(null);
        }
    };

    if (loading) {
        return <Paper variant="outlined" sx={{ p: 3, display: "flex", justifyContent: "center" }}><CircularProgress size={28} /></Paper>;
    }

    const external = form.mode === "external";
    const configurationSaved = configurationFingerprint(form) === savedFingerprint;
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
                        <TextField
                            select
                            label="Gateway Template"
                            value={form.gateway_adapter}
                            onChange={event => selectGatewayAdapter(event.target.value as GatewayForm["gateway_adapter"])}
                            helperText="Templates set safe vendor defaults without changing InsightSphere Agent, Data, or Tool authorization."
                        >
                            <MenuItem value="generic_openai">Generic OpenAI-compatible Gateway</MenuItem>
                            <MenuItem value="mulesoft">MuleSoft AI Gateway</MenuItem>
                        </TextField>
                        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                            <TextField fullWidth required label="Gateway Name" value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} />
                            <TextField
                                fullWidth
                                required
                                label="Gateway Base URL"
                                value={form.base_url}
                                onChange={event => setForm({ ...form, base_url: event.target.value })}
                                helperText={form.gateway_adapter === "mulesoft" ? "Shared origin/root; each Model Proxy appends its Proxy Path." : form.insecure_http_allowed ? "HTTP is permitted by deployment policy." : "HTTPS is required."}
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
                                <Typography fontWeight={600}>Model Proxies</Typography>
                                <Typography variant="caption" color="text.secondary">Each MuleSoft proxy has its own path, routing strategy, capability contract, and test result.</Typography>
                            </Box>
                            <Button size="small" startIcon={<AddIcon />} onClick={addProxy}>Add Proxy</Button>
                        </Box>
                        {form.proxies.map((proxy, index) => {
                            const report = conformanceByProxy[proxy.id];
                            const saved = configurationSaved && savedProxyIds.has(proxy.id);
                            const endpointPreview = proxyEndpointPreview(form.base_url, proxy);
                            return (
                            <Accordion
                                key={index}
                                variant="outlined"
                                disableGutters
                                expanded={expandedProxyIndex === index}
                                onChange={(_, expanded) => setExpandedProxyIndex(expanded ? index : false)}
                                sx={{
                                    borderRadius: 1,
                                    "&:before": { display: "none" },
                                    "&.Mui-expanded": { m: 0 }
                                }}
                            >
                                <AccordionSummary
                                    expandIcon={<ExpandMoreIcon />}
                                    sx={{
                                        px: 2,
                                        minHeight: 64,
                                        "&.Mui-expanded": { minHeight: 64 },
                                        "& .MuiAccordionSummary-content": { my: 1.25, minWidth: 0 },
                                        "& .MuiAccordionSummary-content.Mui-expanded": { my: 1.25 }
                                    }}
                                >
                                    <Stack
                                        direction={{ xs: "column", md: "row" }}
                                        spacing={{ xs: 0.75, md: 1.5 }}
                                        alignItems={{ xs: "flex-start", md: "center" }}
                                        sx={{ minWidth: 0, width: "100%", pr: 1 }}
                                    >
                                        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ minWidth: 0 }}>
                                            <Typography fontWeight={700}>{proxy.label || proxy.id || `Model Proxy ${index + 1}`}</Typography>
                                            <Chip size="small" label={(proxy.routing_strategy || "model_based").replace("_", "-")} />
                                            {form.default_proxy_id === proxy.id && <Chip size="small" color="primary" label="Default" />}
                                            {report && <Chip size="small" color={report.ready ? "success" : "warning"} label={report.ready ? "Ready" : "Not ready"} />}
                                            {!saved && <Chip size="small" color="warning" variant="outlined" label="Unsaved" />}
                                        </Stack>
                                        <Typography
                                            variant="caption"
                                            color="text.secondary"
                                            sx={{ ml: { md: "auto !important" }, overflowWrap: "anywhere" }}
                                        >
                                            {endpointPreview || "Endpoint not configured"}
                                        </Typography>
                                    </Stack>
                                </AccordionSummary>
                                <AccordionDetails sx={{ px: 2, pb: 2, pt: 0.5, borderTop: 1, borderColor: "divider" }}>
                                <Stack spacing={1.25}>
                                    <Stack direction={{ xs: "column", md: "row" }} spacing={1.25}>
                                        <TextField fullWidth required label="Proxy ID" value={proxy.id} onChange={event => updateProxy(index, "id", event.target.value)} helperText="Stable InsightSphere identifier" />
                                        <TextField fullWidth label="Display Name" value={proxy.label} onChange={event => updateProxy(index, "label", event.target.value)} />
                                        <TextField
                                            fullWidth
                                            required={form.gateway_adapter === "mulesoft" && !proxy.base_url}
                                            label="Proxy Path"
                                            value={proxy.proxy_path}
                                            onChange={event => updateProxy(index, "proxy_path", event.target.value)}
                                            helperText="Relative to Gateway Base URL, for example smartmodel/v1"
                                        />
                                        <TextField
                                            fullWidth
                                            select
                                            label="Routing Strategy"
                                            value={proxy.routing_strategy || "model_based"}
                                            onChange={event => updateProxy(index, "routing_strategy", event.target.value as AIGatewayProxy["routing_strategy"])}
                                        >
                                            <MenuItem value="model_based">Model-Based</MenuItem>
                                            <MenuItem value="semantic" disabled={form.gateway_adapter !== "mulesoft"}>Semantic</MenuItem>
                                        </TextField>
                                    </Stack>
                                    <Stack direction={{ xs: "column", md: "row" }} spacing={1.25}>
                                        <TextField
                                            fullWidth
                                            required={proxy.routing_strategy !== "semantic"}
                                            label={proxy.routing_strategy === "semantic" ? "Internal Virtual Alias (not sent upstream)" : "Upstream Model Alias"}
                                            value={proxy.model}
                                            onChange={event => updateProxy(index, "model", event.target.value)}
                                            helperText={proxy.routing_strategy === "semantic" ? "May be blank; MuleSoft selects the model from request content." : "Sent as model for deterministic Model-Based routing."}
                                        />
                                        <TextField
                                            fullWidth
                                            label="Full Base URL Override (advanced)"
                                            value={proxy.base_url || ""}
                                            onChange={event => updateProxy(index, "base_url", event.target.value)}
                                            helperText="Optional for a proxy hosted on a different origin; overrides Gateway Base URL + Proxy Path."
                                        />
                                    </Stack>
                                    {proxy.routing_strategy === "semantic" && (
                                        <TextField
                                            fullWidth
                                            required
                                            multiline
                                            minRows={2}
                                            label="Semantic Probe Prompt"
                                            value={semanticProbePrompts[proxy.id] || ""}
                                            onChange={event => setSemanticProbePrompts(current => ({ ...current, [proxy.id]: event.target.value }))}
                                            inputProps={{ maxLength: 2000 }}
                                            helperText="Enter a short request that matches one configured MuleSoft topic. It is sent only for Test/Conformance and is not saved or audited."
                                        />
                                    )}
                                    <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: "anywhere" }}>
                                        Resolved endpoint: {endpointPreview || "Complete the Gateway Base URL and Proxy Path"}
                                    </Typography>
                                    <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
                                        <Stack direction="row" alignItems="center"><Switch size="small" checked={proxy.supports_tools} onChange={event => updateProxy(index, "supports_tools", event.target.checked)} /><Typography variant="body2">Tool calling</Typography></Stack>
                                        <Stack direction="row" alignItems="center"><Switch size="small" checked={proxy.supports_vision} onChange={event => updateProxy(index, "supports_vision", event.target.checked)} /><Typography variant="body2">Vision</Typography></Stack>
                                    </Stack>
                                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                        <Button
                                            size="small"
                                            variant="outlined"
                                            startIcon={testingProxyId === proxy.id ? <CircularProgress size={14} /> : <PlayArrowIcon />}
                                            disabled={!saved || (proxy.routing_strategy === "semantic" && !semanticProbePrompts[proxy.id]?.trim()) || saving || testingProxyId !== null || conformanceProxyId !== null}
                                            onClick={() => void testProxy(proxy.id)}
                                        >
                                            Test Proxy
                                        </Button>
                                        <Button
                                            size="small"
                                            variant="outlined"
                                            startIcon={conformanceProxyId === proxy.id ? <CircularProgress size={14} /> : <PlayArrowIcon />}
                                            disabled={!saved || (proxy.routing_strategy === "semantic" && !semanticProbePrompts[proxy.id]?.trim()) || saving || testingProxyId !== null || conformanceProxyId !== null}
                                            onClick={() => void runConformance(proxy.id)}
                                        >
                                            Run Conformance
                                        </Button>
                                        {!saved && <Typography variant="caption" color="warning.main" alignSelf="center">Save all Gateway changes before testing this proxy.</Typography>}
                                    </Stack>
                                    <Box>
                                        <Button size="small" color="error" startIcon={<DeleteIcon />} onClick={() => removeProxy(index)}>Remove Proxy</Button>
                                    </Box>
                                    {report && (
                                        <Box sx={{ pt: 1, borderTop: 1, borderColor: "divider" }}>
                                            <Box display="flex" justifyContent="space-between" alignItems="center" gap={1}>
                                                <Box>
                                                    <Typography variant="body2" fontWeight={700}>Proxy Conformance</Typography>
                                                    <Typography variant="caption" color="text.secondary">
                                                        {report.routing_strategy.replace("_", "-")}{report.selected_model ? ` · selected ${report.selected_model}` : ""}
                                                    </Typography>
                                                </Box>
                                                <Chip size="small" color={report.ready ? "success" : "warning"} label={report.ready ? "Ready" : "Not ready"} />
                                            </Box>
                                            {report.checks.map(check => {
                                                const references = Object.entries(check.correlation_ids || {}).map(([name, value]) => `${name}=${value}`).join(", ");
                                                return (
                                                    <Box key={check.name} display="flex" justifyContent="space-between" alignItems="flex-start" gap={2} sx={{ py: 0.75, mt: 0.75, borderTop: 1, borderColor: "divider" }}>
                                                        <Box>
                                                            <Typography variant="body2" fontWeight={600}>{check.name.replaceAll("_", " ")}{check.required ? " · required" : " · optional"}</Typography>
                                                            {(check.code || check.http_status || references) && <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: "anywhere" }}>{[check.code, check.http_status ? `HTTP ${check.http_status}` : "", references].filter(Boolean).join(" · ")}</Typography>}
                                                        </Box>
                                                        <Chip size="small" color={check.status === "passed" ? "success" : check.status === "skipped" ? "default" : "error"} label={check.status} />
                                                    </Box>
                                                );
                                            })}
                                        </Box>
                                    )}
                                </Stack>
                                </AccordionDetails>
                            </Accordion>
                            );
                        })}
                        <TextField
                            select
                            required
                            label="Default Proxy"
                            value={form.default_proxy_id}
                            onChange={event => setForm({ ...form, default_proxy_id: event.target.value })}
                        >
                            {form.proxies.filter(proxy => proxy.id).map(proxy => <MenuItem key={proxy.id} value={proxy.id}>{proxy.label || proxy.id}</MenuItem>)}
                        </TextField>
                    </>
                )}

                {notice && <Alert severity={notice.severity} onClose={() => setNotice(null)}>{notice.text}</Alert>}

                <Stack direction="row" justifyContent="flex-end" spacing={1} flexWrap="wrap" useFlexGap>
                    <Button
                        variant="contained"
                        startIcon={saving ? <CircularProgress color="inherit" size={16} /> : <SaveIcon />}
                        disabled={saving || testingProxyId !== null || conformanceProxyId !== null}
                        onClick={() => void save()}
                    >
                        Save Gateway Configuration
                    </Button>
                </Stack>
            </Stack>
        </Paper>
    );
}
