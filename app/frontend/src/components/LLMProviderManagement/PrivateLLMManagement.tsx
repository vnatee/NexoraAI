import { useEffect, useMemo, useState } from "react";
import {
    Alert,
    Autocomplete,
    Box,
    Button,
    Chip,
    CircularProgress,
    Collapse,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    MenuItem,
    Paper,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Typography
} from "@mui/material";
import DnsIcon from "@mui/icons-material/Dns";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import RefreshIcon from "@mui/icons-material/Refresh";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import SaveIcon from "@mui/icons-material/Save";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import StopCircleOutlinedIcon from "@mui/icons-material/StopCircleOutlined";
import SwapHorizIcon from "@mui/icons-material/SwapHoriz";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import { useMsal } from "@azure/msal-react";

import {
    createPrivateLLMRolloutApi,
    deployPrivateLLMModelApi,
    getPrivateLLMCatalogApi,
    getPrivateLLMCatalogSpecsApi,
    getAIGatewaySettingsApi,
    getPrivateLLMInventoryApi,
    getPrivateLLMSettingsApi,
    listPrivateLLMRolloutsApi,
    managePrivateLLMModelApi,
    preflightPrivateLLMModelApi,
    testPrivateLLMModelApi,
    transitionPrivateLLMRolloutApi,
    updatePrivateLLMSettingsApi
} from "../../api";
import type { AIGatewaySettings, PrivateLLMCatalogModel, PrivateLLMCatalogSpec, PrivateLLMInventory, PrivateLLMModel, PrivateLLMModelAction, PrivateLLMModelPreflight, PrivateLLMModelTestResult, PrivateLLMRollout, PrivateLLMSettings } from "../../api/models";
import { getToken } from "../../authConfig";

const bytes = (value: number) => {
    if (!value) return "0 GB";
    return `${(value / 1024 ** 3).toFixed(value >= 100 * 1024 ** 3 ? 0 : 1)} GB`;
};

const ratio = (used: number, total: number) => total > 0 ? `${(used / total * 100).toFixed(0)}%` : "0%";

const stateColor = (state: string): "success" | "warning" | "error" | "default" => {
    const normalized = state.toLowerCase();
    if (["ready", "running", "active", "rolled_back"].includes(normalized)) return "success";
    if (["pending_approval", "pending", "starting", "initializing", "downloading"].includes(normalized)) return "warning";
    if (["error", "unreachable", "not_ready"].includes(normalized)) return "error";
    return "default";
};

export function PrivateLLMManagement({ onConfigureGateway }: { onConfigureGateway: () => void }) {
    const { instance } = useMsal();
    const [settings, setSettings] = useState<PrivateLLMSettings | null>(null);
    const [gateway, setGateway] = useState<AIGatewaySettings | null>(null);
    const [inventory, setInventory] = useState<PrivateLLMInventory | null>(null);
    const [rollouts, setRollouts] = useState<PrivateLLMRollout[]>([]);
    const [baseUrl, setBaseUrl] = useState("");
    const [consoleUrl, setConsoleUrl] = useState("");
    const [consoleAuthMode, setConsoleAuthMode] = useState<"local" | "oidc" | "saml">("local");
    const [apiKey, setApiKey] = useState("");
    const [timeoutSeconds, setTimeoutSeconds] = useState(30);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [notice, setNotice] = useState<{ severity: "success" | "warning" | "error"; text: string } | null>(null);
    const [proxyId, setProxyId] = useState("");
    const [candidateModel, setCandidateModel] = useState("");
    const [minReadyReplicas, setMinReadyReplicas] = useState(1);
    const [minReadyWorkers, setMinReadyWorkers] = useState(1);
    const [transition, setTransition] = useState<{ rollout: PrivateLLMRollout; action: "activate" | "rollback" } | null>(null);
    const [deployOpen, setDeployOpen] = useState(false);
    const [deployName, setDeployName] = useState("");
    const [deployRepository, setDeployRepository] = useState("");
    const [deployCategory, setDeployCategory] = useState<"llm" | "embedding">("llm");
    const [deployReplicas, setDeployReplicas] = useState(1);
    const [deployClusterId, setDeployClusterId] = useState(0);
    const [modelAction, setModelAction] = useState<{ model: PrivateLLMModel; action: PrivateLLMModelAction } | null>(null);
    const [scaleReplicas, setScaleReplicas] = useState(1);
    const [showConnectionSettings, setShowConnectionSettings] = useState(false);
    const [testModel, setTestModel] = useState<PrivateLLMModel | null>(null);
    const [testPrompt, setTestPrompt] = useState("Reply with exactly: InsightSphere model test passed");
    const [testResult, setTestResult] = useState<PrivateLLMModelTestResult | null>(null);
    const [catalogMode, setCatalogMode] = useState(true);
    const [catalogLoading, setCatalogLoading] = useState(false);
    const [catalogModels, setCatalogModels] = useState<PrivateLLMCatalogModel[]>([]);
    const [catalogModel, setCatalogModel] = useState<PrivateLLMCatalogModel | null>(null);
    const [catalogSpecs, setCatalogSpecs] = useState<PrivateLLMCatalogSpec[]>([]);
    const [catalogSpec, setCatalogSpec] = useState<PrivateLLMCatalogSpec | null>(null);
    const [deployPreflight, setDeployPreflight] = useState<PrivateLLMModelPreflight | null>(null);
    const [deployPreflightKey, setDeployPreflightKey] = useState("");

    const modelBasedProxies = useMemo(
        () => (gateway?.proxies || gateway?.models || []).filter(item => item.routing_strategy === "model_based"),
        [gateway]
    );
    const deployNameValid = /^[A-Za-z](?:[A-Za-z0-9_.:-]*[A-Za-z0-9])?$/.test(deployName.trim());
    const deployRepositoryValid = /^[A-Za-z0-9][A-Za-z0-9._-]*\/[A-Za-z0-9][A-Za-z0-9._-]*$/.test(deployRepository.trim());
    const deployNameExists = Boolean(inventory?.models.some(model => model.name === deployName.trim()));
    const deployFingerprint = JSON.stringify({
        name: deployName.trim(),
        repository: deployRepository.trim(),
        category: deployCategory,
        replicas: deployReplicas,
        cluster: deployClusterId
    });
    const deployPreflightCurrent = deployPreflightKey === deployFingerprint;

    const useSmallTestModel = () => {
        setCatalogMode(false);
        setCatalogModel(null);
        setCatalogSpecs([]);
        setCatalogSpec(null);
        setDeployName("qwen3-0.6b-demo");
        setDeployRepository("Qwen/Qwen3-0.6B");
        setDeployCategory("llm");
        setDeployReplicas(1);
        if (!deployClusterId) {
            setDeployClusterId(inventory?.clusters.find(cluster => cluster.state.toLowerCase() === "ready")?.id || 0);
        }
    };

    const loadCatalog = async (category: "llm" | "embedding") => {
        setCatalogLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            setCatalogModels(await getPrivateLLMCatalogApi(category, token));
        } catch (error) {
            setNotice({ severity: "warning", text: error instanceof Error ? error.message : "GPUStack catalog is unavailable" });
            setCatalogModels([]);
        } finally {
            setCatalogLoading(false);
        }
    };

    const selectCatalogModel = async (selected: PrivateLLMCatalogModel | null) => {
        setCatalogModel(selected);
        setCatalogSpecs([]);
        setCatalogSpec(null);
        if (!selected || !deployClusterId) return;
        setCatalogLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const specs = (await getPrivateLLMCatalogSpecsApi(selected.id, deployClusterId, token))
                .filter(spec => !spec.backend || spec.backend === "vLLM");
            setCatalogSpecs(specs);
            const preferred = specs.find(spec => spec.mode === "standard") || specs[0] || null;
            setCatalogSpec(preferred);
            if (preferred) {
                setDeployRepository(preferred.huggingface_repo_id);
                let suggestedName = selected.name.toLowerCase().replace(/[^a-z0-9_.:-]+/g, "-").replace(/^[^a-z]+/, "model-").replace(/[^a-z0-9]+$/, "");
                if (inventory?.models.some(model => model.name === suggestedName)) suggestedName = `${suggestedName}-2`;
                setDeployName(suggestedName);
            }
        } catch (error) {
            setNotice({ severity: "warning", text: error instanceof Error ? error.message : "No compatible catalog variant was found" });
        } finally {
            setCatalogLoading(false);
        }
    };

    const load = async (includeInventory = true) => {
        setLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const [saved, gatewaySettings, rolloutRecords] = await Promise.all([
                getPrivateLLMSettingsApi(token),
                getAIGatewaySettingsApi(token),
                listPrivateLLMRolloutsApi(token)
            ]);
            setSettings(saved);
            setGateway(gatewaySettings);
            setRollouts(rolloutRecords);
            setBaseUrl(saved.base_url);
            setConsoleUrl(saved.console_url || "");
            setConsoleAuthMode(saved.console_auth_mode || "local");
            setTimeoutSeconds(saved.timeout_seconds);
            if (!proxyId && (gatewaySettings.proxies || gatewaySettings.models || []).length > 0) {
                const first = (gatewaySettings.proxies || gatewaySettings.models || []).find(item => item.routing_strategy === "model_based");
                setProxyId(first?.id || "");
            }
            if (includeInventory && saved.base_url) {
                try {
                    const currentInventory = await getPrivateLLMInventoryApi(token);
                    setInventory(currentInventory);
                    if (!deployClusterId) {
                        const preferredCluster = currentInventory.clusters.find(cluster => cluster.is_default && cluster.state.toLowerCase() === "ready")
                            || currentInventory.clusters.find(cluster => cluster.state.toLowerCase() === "ready");
                        setDeployClusterId(preferredCluster?.id || 0);
                    }
                    if (!candidateModel) {
                        setCandidateModel(currentInventory.models.find(item => item.state === "running")?.name || "");
                    }
                } catch (error) {
                    setInventory(null);
                    setNotice({ severity: "warning", text: error instanceof Error ? error.message : "GPUStack inventory is unavailable" });
                }
            }
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to load private LLM management" });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void load();
    }, [instance]);

    useEffect(() => {
        if (!deployOpen || !catalogMode) return;
        setCatalogModel(null);
        setCatalogSpecs([]);
        setCatalogSpec(null);
        void loadCatalog(deployCategory);
    }, [deployOpen, catalogMode, deployCategory]);

    const save = async () => {
        setBusy(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const saved = await updatePrivateLLMSettingsApi(
                {
                    base_url: baseUrl,
                    console_url: consoleUrl,
                    console_auth_mode: consoleAuthMode,
                    timeout_seconds: timeoutSeconds,
                    api_key: apiKey || undefined
                },
                token
            );
            setSettings(saved);
            setApiKey("");
            setNotice({ severity: "success", text: "GPUStack control-plane settings saved" });
            await load(true);
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to save settings" });
        } finally {
            setBusy(false);
        }
    };

    const createRollout = async () => {
        setBusy(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            await createPrivateLLMRolloutApi(
                { proxy_id: proxyId, candidate_model: candidateModel, min_ready_replicas: minReadyReplicas, min_ready_workers: minReadyWorkers },
                token
            );
            setNotice({ severity: "success", text: "Preflight passed. Rollout is waiting for explicit approval." });
            await load(true);
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Rollout preflight failed" });
        } finally {
            setBusy(false);
        }
    };

    const confirmTransition = async () => {
        if (!transition) return;
        setBusy(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            await transitionPrivateLLMRolloutApi(transition.rollout._id, transition.action, token);
            setNotice({
                severity: "success",
                text: transition.action === "activate" ? "Candidate model is now active" : "Previous model route was restored"
            });
            setTransition(null);
            await load(true);
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Rollout transition failed" });
        } finally {
            setBusy(false);
        }
    };

    const deploymentPayload = () => ({
        name: deployName.trim(),
        huggingface_repo_id: deployRepository.trim(),
        category: deployCategory,
        replicas: deployReplicas,
        cluster_id: deployClusterId
    });

    const runDeployPreflight = async () => {
        setBusy(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const result = await preflightPrivateLLMModelApi(deploymentPayload(), token);
            setDeployPreflight(result);
            setDeployPreflightKey(deployFingerprint);
        } catch (error) {
            setDeployPreflight(null);
            setDeployPreflightKey("");
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Resource-fit preflight failed" });
        } finally {
            setBusy(false);
        }
    };

    const deployModel = async () => {
        setBusy(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            await deployPrivateLLMModelApi(deploymentPayload(), token);
            setDeployOpen(false);
            setDeployName("");
            setDeployRepository("");
            setDeployCategory("llm");
            setDeployReplicas(1);
            setDeployPreflight(null);
            setDeployPreflightKey("");
            setNotice({ severity: "success", text: "Model deployment was accepted. Inventory will show readiness as GPUStack schedules it." });
            await load(true);
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Model deployment failed" });
        } finally {
            setBusy(false);
        }
    };

    const manageModel = async () => {
        if (!modelAction) return;
        setBusy(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            await managePrivateLLMModelApi(
                modelAction.model.id,
                modelAction.action,
                token,
                modelAction.action === "scale" ? scaleReplicas : undefined
            );
            const label = modelAction.action === "restart" ? "Restart" : modelAction.action === "stop" ? "Stop" : "Scale";
            setModelAction(null);
            setNotice({ severity: "success", text: `${label} request accepted. Inventory will refresh with the current convergence state.` });
            await load(true);
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Model action failed" });
        } finally {
            setBusy(false);
        }
    };

    const runModelTest = async () => {
        if (!testModel) return;
        setBusy(true);
        setTestResult(null);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            setTestResult(await testPrivateLLMModelApi(testModel.id, testPrompt.trim(), token));
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Model test failed" });
        } finally {
            setBusy(false);
        }
    };

    if (loading && !settings) return <Box display="flex" justifyContent="center" py={7}><CircularProgress /></Box>;

    return (
        <Stack spacing={2}>
            {notice && <Alert severity={notice.severity} onClose={() => setNotice(null)}>{notice.text}</Alert>}
            <Paper variant="outlined" sx={{ p: 3 }}>
                <Stack spacing={2}>
                    <Box display="flex" alignItems="center" justifyContent="space-between" gap={2} flexWrap="wrap">
                        <Box display="flex" alignItems="center" gap={1.5}>
                            <DnsIcon color="primary" />
                            <Box>
                                <Typography variant="h6">Private AI Infrastructure</Typography>
                                <Typography variant="caption" color="text.secondary">Powered by GPUStack</Typography>
                            </Box>
                        </Box>
                        <Stack direction="row" spacing={1}>
                            <Button variant="outlined" startIcon={<RefreshIcon />} disabled={busy || !settings?.base_url} onClick={() => void load(true)}>Refresh</Button>
                            <Button variant="outlined" startIcon={<SettingsOutlinedIcon />} onClick={() => setShowConnectionSettings(value => !value)}>Connection</Button>
                            <Button variant="contained" startIcon={<AddCircleOutlineIcon />} disabled={busy || !settings?.base_url} onClick={() => setDeployOpen(true)}>Deploy model</Button>
                        </Stack>
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                        Govern private model capacity, deployments, and controlled routing from InsightSphere. The infrastructure credential is encrypted and is never returned to the browser.
                    </Typography>
                    {!settings?.base_url && <Alert severity="warning">Configure the private infrastructure connection before deploying or managing models.</Alert>}
                    <Collapse in={showConnectionSettings}>
                    <Stack spacing={2} pt={1}>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                        <TextField fullWidth label="Control-plane URL" value={baseUrl} onChange={event => setBaseUrl(event.target.value)} helperText="HTTPS, or internal HTTP such as http://gpustack:80" />
                        <TextField sx={{ minWidth: 280 }} type="password" label={settings?.has_api_key ? "API key (saved)" : "API key"} value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder={settings?.has_api_key ? "Leave blank to keep saved key" : "GPUStack API key"} helperText="Use a dedicated key allowed to read inventory and create, update, and restart models." />
                        <TextField sx={{ width: 160 }} type="number" label="Timeout (sec)" value={timeoutSeconds} onChange={event => setTimeoutSeconds(Number(event.target.value))} inputProps={{ min: 5, max: 120 }} />
                    </Stack>
                    <Divider />
                    <Box>
                        <Typography fontWeight={700}>Advanced infrastructure console</Typography>
                        <Typography variant="body2" color="text.secondary">
                            Use the GPUStack console for advanced diagnostics and capabilities not exposed in InsightSphere. No password, API key, or InsightSphere session token is added to this link.
                        </Typography>
                    </Box>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                        <TextField
                            fullWidth
                            label="Console URL"
                            value={consoleUrl}
                            onChange={event => setConsoleUrl(event.target.value)}
                            placeholder="http://127.0.0.1:18080"
                            helperText="Use local/internal HTTP for development, or a private HTTPS URL for production."
                        />
                        <TextField
                            select
                            sx={{ minWidth: 260 }}
                            label="Console sign-in"
                            value={consoleAuthMode}
                            onChange={event => setConsoleAuthMode(event.target.value as "local" | "oidc" | "saml")}
                        >
                            <MenuItem value="local">Local login</MenuItem>
                            <MenuItem value="oidc">OIDC SSO</MenuItem>
                            <MenuItem value="saml">SAML SSO</MenuItem>
                        </TextField>
                    </Stack>
                    {consoleAuthMode === "local" ? (
                        <Alert severity="info">
                            Local login is active. Opening the console will show GPUStack's own sign-in page.
                        </Alert>
                    ) : (
                        <Alert severity="warning">
                            {consoleAuthMode.toUpperCase()} SSO must also be configured on GPUStack with the same organization IdP. This setting does not copy InsightSphere credentials or bypass GPUStack authentication.
                        </Alert>
                    )}
                    <Stack direction="row" spacing={1}>
                        <Button variant="contained" startIcon={<SaveIcon />} disabled={busy || !baseUrl} onClick={() => void save()}>Save</Button>
                        <Button
                            component="a"
                            href={settings?.console_url || undefined}
                            target="_blank"
                            rel="noopener noreferrer"
                            variant="outlined"
                            startIcon={<OpenInNewIcon />}
                            disabled={!settings?.console_url}
                        >
                            Advanced console
                        </Button>
                        <Button variant="text" onClick={onConfigureGateway}>Configure gateway proxies</Button>
                    </Stack>
                    </Stack>
                    </Collapse>
                </Stack>
            </Paper>

            {inventory && (
                <>
                    <Typography variant="caption" color="text.secondary" textAlign="right">
                        Inventory refreshed {new Date(inventory.generated_at).toLocaleString()}
                    </Typography>
                    <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(175px, 1fr))", gap: 1.5 }}>
                        {[
                            ["Ready workers", `${inventory.summary.ready_workers}/${inventory.summary.workers}`],
                            ["Ready clusters", `${inventory.summary.ready_clusters}/${inventory.summary.clusters}`],
                            ["GPU devices", inventory.summary.gpus],
                            ["Physical VRAM used", `${bytes(inventory.summary.vram_used_bytes)} · ${ratio(inventory.summary.vram_used_bytes, inventory.summary.vram_total_bytes)}`],
                            ["Allocated VRAM", bytes(inventory.summary.vram_allocated_bytes)],
                            ["Schedulable VRAM", bytes(inventory.summary.vram_schedulable_bytes)],
                            ["Ready models", `${inventory.summary.ready_models}/${inventory.summary.models}`],
                            ["Running instances", inventory.summary.running_instances]
                        ].map(([label, value]) => <Paper variant="outlined" sx={{ p: 2 }} key={String(label)}><Typography variant="overline" color="text.secondary">{label}</Typography><Typography variant="h5">{value}</Typography></Paper>)}
                    </Box>
                    <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography variant="h6" mb={1}>Workers and capacity</Typography>
                        <TableContainer>
                            <Table size="small">
                                <TableHead><TableRow><TableCell>Worker</TableCell><TableCell>Status</TableCell><TableCell>GPUs</TableCell><TableCell>Physical VRAM</TableCell><TableCell>Allocated</TableCell><TableCell>Schedulable</TableCell><TableCell>GPU compute</TableCell><TableCell>CPU</TableCell><TableCell>RAM</TableCell></TableRow></TableHead>
                                <TableBody>{inventory.workers.map(worker => {
                                    const total = worker.gpus.reduce((sum, gpu) => sum + gpu.memory_total_bytes, 0);
                                    const used = worker.gpus.reduce((sum, gpu) => sum + gpu.memory_used_bytes, 0);
                                    const allocated = worker.gpus.reduce((sum, gpu) => sum + gpu.memory_allocated_bytes, 0);
                                    const schedulable = worker.gpus.reduce((sum, gpu) => sum + gpu.memory_schedulable_bytes, 0);
                                    const compute = worker.gpus.length > 0 ? worker.gpus.reduce((sum, gpu) => sum + gpu.utilization_percent, 0) / worker.gpus.length : 0;
                                    return <TableRow key={String(worker.id)}><TableCell>{worker.name}</TableCell><TableCell><Chip size="small" color={stateColor(worker.state)} label={worker.state} /></TableCell><TableCell>{worker.gpus.map(gpu => gpu.name).join(", ") || "CPU only"}</TableCell><TableCell>{bytes(used)} / {bytes(total)} ({ratio(used, total)})</TableCell><TableCell>{bytes(allocated)}</TableCell><TableCell>{bytes(schedulable)}</TableCell><TableCell>{compute.toFixed(0)}%</TableCell><TableCell>{worker.cpu_utilization_percent.toFixed(0)}%</TableCell><TableCell>{bytes(Math.max(0, worker.memory_total_bytes - worker.memory_used_bytes))} free</TableCell></TableRow>;
                                })}</TableBody>
                            </Table>
                        </TableContainer>
                    </Paper>
                    <Paper variant="outlined" sx={{ p: 2 }}>
                        <Box display="flex" alignItems="center" justifyContent="space-between" mb={1} gap={2}>
                            <Typography variant="h6">Models</Typography>
                            <Typography variant="caption" color="text.secondary">Managed by InsightSphere · Powered by GPUStack</Typography>
                        </Box>
                        <TableContainer>
                            <Table size="small">
                                <TableHead><TableRow><TableCell>Model</TableCell><TableCell>Status</TableCell><TableCell>Backend</TableCell><TableCell>Ready replicas</TableCell><TableCell>Stale</TableCell><TableCell align="right">Actions</TableCell></TableRow></TableHead>
                                <TableBody>{inventory.models.map(model => <TableRow key={String(model.id)}>
                                    <TableCell>{model.name}</TableCell>
                                    <TableCell><Chip size="small" color={stateColor(model.state)} label={model.state} /></TableCell>
                                    <TableCell>{[model.backend, model.backend_version].filter(Boolean).join(" ") || "—"}</TableCell>
                                    <TableCell>{model.ready_replicas}/{model.replicas}</TableCell>
                                    <TableCell>{model.stale ? "Yes" : "No"}</TableCell>
                                    <TableCell align="right">
                                        <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                                            <Button size="small" startIcon={<ScienceOutlinedIcon />} disabled={busy || model.state.toLowerCase() !== "running" || model.ready_replicas < 1 || !model.categories.includes("llm")} onClick={() => { setTestModel(model); setTestResult(null); }}>Test</Button>
                                            <Button size="small" disabled={busy} onClick={() => { setScaleReplicas(model.replicas); setModelAction({ model, action: "scale" }); }}>Scale</Button>
                                            <Button size="small" startIcon={<RestartAltIcon />} disabled={busy || model.replicas === 0} onClick={() => setModelAction({ model, action: "restart" })}>Restart</Button>
                                            <Button size="small" color="warning" startIcon={<StopCircleOutlinedIcon />} disabled={busy || model.replicas === 0} onClick={() => setModelAction({ model, action: "stop" })}>Stop</Button>
                                        </Stack>
                                    </TableCell>
                                </TableRow>)}</TableBody>
                            </Table>
                        </TableContainer>
                        {inventory.models.length === 0 && <Typography variant="body2" color="text.secondary" py={2}>No private models have been deployed.</Typography>}
                    </Paper>
                </>
            )}

            <Paper variant="outlined" sx={{ p: 3 }}>
                <Stack spacing={2}>
                    <Box><Typography variant="h6">Controlled model rollout</Typography><Typography variant="body2" color="text.secondary">Preflight verifies replicas across workers, then gateway conformance must pass before an approved route switch. Rollback restores the recorded previous model.</Typography></Box>
                    {gateway?.mode !== "external" && <Alert severity="warning">External AI Gateway mode must be active before a private model can be rolled out.</Alert>}
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                        <TextField select fullWidth label="Model-based gateway proxy" value={proxyId} onChange={event => setProxyId(event.target.value)}>
                            {modelBasedProxies.map(proxy => <MenuItem key={proxy.id} value={proxy.id}>{proxy.label || proxy.id} · current {proxy.model}</MenuItem>)}
                        </TextField>
                        <TextField select fullWidth label="Candidate GPUStack model" value={candidateModel} onChange={event => setCandidateModel(event.target.value)}>
                            {(inventory?.models || []).filter(model => model.state === "running").map(model => <MenuItem key={String(model.id)} value={model.name}>{model.name} · {model.ready_replicas}/{model.replicas} ready</MenuItem>)}
                        </TextField>
                        <TextField sx={{ minWidth: 150 }} type="number" label="Min replicas" value={minReadyReplicas} onChange={event => setMinReadyReplicas(Number(event.target.value))} inputProps={{ min: 1, max: 100 }} />
                        <TextField sx={{ minWidth: 150 }} type="number" label="Min workers" value={minReadyWorkers} onChange={event => setMinReadyWorkers(Number(event.target.value))} inputProps={{ min: 1, max: 100 }} />
                    </Stack>
                    <Button sx={{ alignSelf: "flex-start" }} variant="contained" startIcon={<SwapHorizIcon />} disabled={busy || gateway?.mode !== "external" || !proxyId || !candidateModel} onClick={() => void createRollout()}>Run preflight</Button>
                    <Divider />
                    <TableContainer>
                        <Table size="small">
                            <TableHead><TableRow><TableCell>Proxy</TableCell><TableCell>Route change</TableCell><TableCell>Preflight</TableCell><TableCell>Status</TableCell><TableCell align="right">Action</TableCell></TableRow></TableHead>
                            <TableBody>{rollouts.map(rollout => <TableRow key={rollout._id}><TableCell>{rollout.proxy_id}</TableCell><TableCell>{rollout.previous_model} → {rollout.candidate_model}</TableCell><TableCell>{rollout.preflight.ready_replicas} replicas · {rollout.preflight.ready_workers} workers</TableCell><TableCell><Chip size="small" color={stateColor(rollout.status)} label={rollout.status.replaceAll("_", " ")} /></TableCell><TableCell align="right">{rollout.status === "pending_approval" && <Button size="small" onClick={() => setTransition({ rollout, action: "activate" })}>Review &amp; activate</Button>}{rollout.status === "active" && <Button size="small" color="warning" onClick={() => setTransition({ rollout, action: "rollback" })}>Rollback</Button>}</TableCell></TableRow>)}</TableBody>
                        </Table>
                    </TableContainer>
                    {rollouts.length === 0 && <Typography variant="body2" color="text.secondary">No rollout plans yet.</Typography>}
                </Stack>
            </Paper>

            <Dialog open={deployOpen} onClose={() => !busy && setDeployOpen(false)} maxWidth="md" fullWidth>
                <DialogTitle>Deploy private model</DialogTitle>
                <DialogContent>
                    <Stack spacing={2} mt={1}>
                        <Alert severity="info">
                            Choose from the GPUStack Catalog for guided setup, or use a Hugging Face model ID for a custom deployment. InsightSphere checks compatibility and estimated resource use before deployment.
                        </Alert>
                        <Stack direction="row" spacing={1}>
                            <Button
                                variant={catalogMode ? "contained" : "outlined"}
                                onClick={() => {
                                    setCatalogMode(true);
                                    setDeployName("");
                                    setDeployRepository("");
                                }}
                            >
                                GPUStack Catalog
                            </Button>
                            <Button
                                variant={!catalogMode ? "contained" : "outlined"}
                                onClick={() => {
                                    setCatalogMode(false);
                                    setCatalogModel(null);
                                    setCatalogSpecs([]);
                                    setCatalogSpec(null);
                                }}
                            >
                                Custom model
                            </Button>
                        </Stack>
                        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                            <TextField fullWidth select label="Workload" value={deployCategory} onChange={event => setDeployCategory(event.target.value as "llm" | "embedding")}>
                                <MenuItem value="llm">Chat / LLM</MenuItem>
                                <MenuItem value="embedding">Embedding</MenuItem>
                            </TextField>
                            <TextField
                                fullWidth
                                select
                                required
                                label="Deployment cluster"
                                value={deployClusterId || ""}
                                onChange={event => {
                                    setDeployClusterId(Number(event.target.value));
                                    if (catalogMode) {
                                        setCatalogModel(null);
                                        setCatalogSpecs([]);
                                        setCatalogSpec(null);
                                        setDeployRepository("");
                                    }
                                }}
                                helperText="Only ready clusters can accept a deployment."
                            >
                                {(inventory?.clusters || []).map(cluster => (
                                    <MenuItem key={cluster.id} value={cluster.id} disabled={cluster.state.toLowerCase() !== "ready"}>
                                        {cluster.name} · {cluster.state} · {cluster.ready_workers}/{cluster.workers} workers · {cluster.gpus} GPUs
                                    </MenuItem>
                                ))}
                            </TextField>
                        </Stack>
                        {catalogMode ? (
                            <>
                                <Autocomplete
                                    options={catalogModels}
                                    value={catalogModel}
                                    loading={catalogLoading}
                                    onChange={(_event, value) => void selectCatalogModel(value)}
                                    getOptionLabel={option => option.name}
                                    isOptionEqualToValue={(option, value) => option.id === value.id}
                                    renderOption={(props, option) => (
                                        <li {...props} key={option.id}>
                                            <Box>
                                                <Typography variant="body2" fontWeight={600}>{option.name}</Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    {[option.size ? `${option.size} ${option.size_unit}` : "", option.capabilities.join(", ")].filter(Boolean).join(" · ") || "GPUStack catalog model"}
                                                </Typography>
                                            </Box>
                                        </li>
                                    )}
                                    renderInput={params => (
                                        <TextField
                                            {...params}
                                            required
                                            label="Model from GPUStack Catalog"
                                            placeholder="Search by model name"
                                            helperText="Catalog entries are curated by GPUStack; use Custom model for other Hugging Face repositories."
                                            InputProps={{
                                                ...params.InputProps,
                                                endAdornment: <>{catalogLoading ? <CircularProgress color="inherit" size={18} /> : null}{params.InputProps.endAdornment}</>
                                            }}
                                        />
                                    )}
                                />
                                {catalogModel && (
                                    <Paper variant="outlined" sx={{ p: 2 }}>
                                        <Typography fontWeight={700}>{catalogModel.name}</Typography>
                                        {catalogModel.description && <Typography variant="body2" color="text.secondary" mt={0.5}>{catalogModel.description}</Typography>}
                                        <Stack direction="row" spacing={1} mt={1} useFlexGap flexWrap="wrap">
                                            {catalogModel.size ? <Chip size="small" label={`${catalogModel.size} ${catalogModel.size_unit}`} /> : null}
                                            {catalogModel.licenses.map(license => <Chip key={license} size="small" variant="outlined" label={`License: ${license}`} />)}
                                        </Stack>
                                    </Paper>
                                )}
                                {catalogModel && !catalogLoading && catalogSpecs.length === 0 && (
                                    <Alert severity="warning">No Hugging Face vLLM variant is available for this model and cluster. Select another model or use Custom model.</Alert>
                                )}
                                {catalogSpecs.length > 0 && (
                                    <TextField
                                        select
                                        label="Model variant"
                                        value={catalogSpec ? String(catalogSpecs.indexOf(catalogSpec)) : ""}
                                        onChange={event => {
                                            const selected = catalogSpecs[Number(event.target.value)] || null;
                                            setCatalogSpec(selected);
                                            setDeployRepository(selected?.huggingface_repo_id || "");
                                        }}
                                        helperText="Backend, precision and repository are supplied by the catalog."
                                    >
                                        {catalogSpecs.map((spec, index) => (
                                            <MenuItem key={`${spec.huggingface_repo_id}:${spec.quantization}:${spec.mode}:${index}`} value={String(index)}>
                                                {spec.huggingface_repo_id} · {spec.backend || "Auto"}{spec.backend_version ? ` ${spec.backend_version}` : ""} · {spec.quantization || "Default precision"} · {spec.mode}
                                            </MenuItem>
                                        ))}
                                    </TextField>
                                )}
                            </>
                        ) : (
                            <Alert
                                severity="info"
                                action={<Button color="inherit" size="small" onClick={useSmallTestModel}>Use test preset</Button>}
                            >
                                Enter an exact public Hugging Face repository ID. Private or gated repositories require credentials configured in GPUStack.
                            </Alert>
                        )}
                        <TextField
                            required
                            label="Model name in InsightSphere"
                            value={deployName}
                            onChange={event => setDeployName(event.target.value)}
                            error={Boolean(deployName) && (!deployNameValid || deployNameExists)}
                            helperText={deployNameExists ? "This model name already exists." : "The stable name used later by Gateway routes and model profiles, for example qwen3-0.6b-demo."}
                        />
                        <TextField
                            required
                            label="Hugging Face model ID"
                            value={deployRepository}
                            onChange={event => setDeployRepository(event.target.value)}
                            placeholder="Qwen/Qwen3-0.6B"
                            error={Boolean(deployRepository) && !deployRepositoryValid}
                            helperText={catalogMode ? "Filled from the selected catalog variant." : "The exact organization/model value from huggingface.co."}
                            InputProps={{ readOnly: catalogMode }}
                        />
                        <TextField type="number" label="Replicas" value={deployReplicas} onChange={event => setDeployReplicas(Number(event.target.value))} inputProps={{ min: 1, max: 100 }} helperText="Start with 1. Each replica consumes additional GPU capacity." />
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "stretch", sm: "center" }} spacing={1}>
                                <Box>
                                    <Typography fontWeight={700}>Resource-fit preflight</Typography>
                                    <Typography variant="body2" color="text.secondary">GPUStack estimates memory needs and checks whether the selected cluster can schedule this model.</Typography>
                                </Box>
                                <Button
                                    variant="outlined"
                                    disabled={busy || !deployNameValid || !deployRepositoryValid || deployNameExists || !deployClusterId || !Number.isInteger(deployReplicas) || deployReplicas < 1 || deployReplicas > 100}
                                    onClick={() => void runDeployPreflight()}
                                >
                                    {busy ? "Checking..." : "Check resource fit"}
                                </Button>
                            </Stack>
                            {deployPreflight && deployPreflightCurrent && (
                                <Alert severity={deployPreflight.compatible ? "success" : "error"} sx={{ mt: 2 }}>
                                    <Typography variant="body2" fontWeight={700}>
                                        {deployPreflight.compatible ? "Compatible with the selected cluster" : "This configuration cannot be scheduled"}
                                    </Typography>
                                    {(deployPreflight.resource_claim.vram_bytes > 0 || deployPreflight.resource_claim.ram_bytes > 0) && (
                                        <Typography variant="body2">Estimated VRAM: {bytes(deployPreflight.resource_claim.vram_bytes)} · RAM: {bytes(deployPreflight.resource_claim.ram_bytes)}</Typography>
                                    )}
                                    {deployPreflight.error_message && <Typography variant="body2" mt={0.5}>{deployPreflight.error_message}</Typography>}
                                    {[...deployPreflight.compatibility_messages, ...deployPreflight.scheduling_messages].map((message, index) => <Typography key={`${index}:${message}`} variant="body2" mt={0.5}>• {message}</Typography>)}
                                </Alert>
                            )}
                            {deployPreflight && !deployPreflightCurrent && <Alert severity="warning" sx={{ mt: 2 }}>Configuration changed. Run resource-fit preflight again.</Alert>}
                        </Paper>
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Typography fontWeight={700} mb={1}>Review</Typography>
                            <Typography variant="body2">Model: {deployName.trim() || "—"}</Typography>
                            <Typography variant="body2">Source: {deployRepository.trim() || "—"}</Typography>
                            <Typography variant="body2">Cluster: {inventory?.clusters.find(cluster => cluster.id === deployClusterId)?.name || "—"}</Typography>
                            <Typography variant="body2">Runtime: vLLM · {deployCategory === "llm" ? "Chat / LLM" : "Embedding"} · {deployReplicas} replica{deployReplicas === 1 ? "" : "s"}</Typography>
                            <Typography variant="body2" color="text.secondary" mt={1}>
                                Confirming starts a model download and GPU allocation. The request is asynchronous; watch Status and Ready replicas after submission.
                            </Typography>
                        </Paper>
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button disabled={busy} onClick={() => setDeployOpen(false)}>Cancel</Button>
                    <Button disabled={busy || !deployNameValid || !deployRepositoryValid || deployNameExists || !deployClusterId || !Number.isInteger(deployReplicas) || deployReplicas < 1 || deployReplicas > 100 || !deployPreflightCurrent || !deployPreflight?.compatible} variant="contained" onClick={() => void deployModel()}>{busy ? "Deploying..." : "Confirm deployment"}</Button>
                </DialogActions>
            </Dialog>

            <Dialog open={Boolean(modelAction)} onClose={() => !busy && setModelAction(null)} maxWidth="sm" fullWidth>
                <DialogTitle>{modelAction?.action === "restart" ? "Restart model" : modelAction?.action === "stop" ? "Stop model" : "Scale model"}</DialogTitle>
                <DialogContent>
                    <Stack spacing={2} mt={1}>
                        <Alert severity={modelAction?.action === "stop" ? "warning" : "info"}>
                            {modelAction?.action === "restart" && `All running instances of ${modelAction.model.name} will be replaced. Requests may be temporarily unavailable while replicas converge.`}
                            {modelAction?.action === "stop" && `${modelAction.model.name} will be scaled to zero replicas and will stop serving requests. It can be started again with Scale.`}
                            {modelAction?.action === "scale" && `Change the desired replica count for ${modelAction.model.name}. Setting zero stops the model.`}
                        </Alert>
                        {modelAction?.action === "scale" && (
                            <TextField autoFocus type="number" label="Desired replicas" value={scaleReplicas} onChange={event => setScaleReplicas(Number(event.target.value))} inputProps={{ min: 0, max: 100 }} />
                        )}
                        <Typography variant="body2" color="text.secondary">
                            GPUStack applies this asynchronously. InsightSphere will refresh the observed status after the request is accepted.
                        </Typography>
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button disabled={busy} onClick={() => setModelAction(null)}>Cancel</Button>
                    <Button
                        disabled={busy || (modelAction?.action === "scale" && (scaleReplicas < 0 || scaleReplicas > 100 || !Number.isInteger(scaleReplicas)))}
                        variant="contained"
                        color={modelAction?.action === "stop" ? "warning" : "primary"}
                        onClick={() => void manageModel()}
                    >
                        {busy ? "Working..." : "Confirm action"}
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog open={Boolean(testModel)} onClose={() => !busy && setTestModel(null)} maxWidth="md" fullWidth>
                <DialogTitle>Test {testModel?.name}</DialogTitle>
                <DialogContent>
                    <Stack spacing={2} mt={1}>
                        <Alert severity="info">
                            This calls the selected GPUStack model directly through the private server connection. It does not change or use the active MuleSoft Gateway route. Prompt and output are not written to the lifecycle audit.
                        </Alert>
                        <TextField multiline minRows={3} maxRows={8} label="Test prompt" value={testPrompt} onChange={event => setTestPrompt(event.target.value)} inputProps={{ maxLength: 4000 }} helperText={`${testPrompt.length}/4000 characters`} />
                        {testResult && (
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Typography fontWeight={700} mb={1}>Model response</Typography>
                                <Typography sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{testResult.content}</Typography>
                                <Divider sx={{ my: 1.5 }} />
                                <Typography variant="caption" color="text.secondary">
                                    {testResult.latency_ms} ms · {testResult.usage.total_tokens} tokens ({testResult.usage.prompt_tokens} prompt + {testResult.usage.completion_tokens} completion) · {testResult.finish_reason || "completed"}
                                </Typography>
                            </Paper>
                        )}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button disabled={busy} onClick={() => setTestModel(null)}>Close</Button>
                    <Button disabled={busy || !testPrompt.trim() || testPrompt.length > 4000} variant="contained" startIcon={<ScienceOutlinedIcon />} onClick={() => void runModelTest()}>{busy ? "Testing..." : "Run test"}</Button>
                </DialogActions>
            </Dialog>

            <Dialog open={Boolean(transition)} onClose={() => !busy && setTransition(null)} maxWidth="sm" fullWidth>
                <DialogTitle>{transition?.action === "activate" ? "Activate private model route" : "Rollback private model route"}</DialogTitle>
                <DialogContent>
                    <Alert severity={transition?.action === "activate" ? "warning" : "info"}>
                        {transition?.action === "activate"
                            ? `This reruns capacity and gateway conformance checks, then changes ${transition.rollout.proxy_id} from ${transition.rollout.previous_model} to ${transition.rollout.candidate_model}.`
                            : `This validates and restores ${transition?.rollout.proxy_id} to ${transition?.rollout.previous_model}.`}
                    </Alert>
                </DialogContent>
                <DialogActions><Button disabled={busy} onClick={() => setTransition(null)}>Cancel</Button><Button disabled={busy} variant="contained" color={transition?.action === "rollback" ? "warning" : "primary"} onClick={() => void confirmTransition()}>{busy ? "Working..." : transition?.action === "activate" ? "Approve & activate" : "Confirm rollback"}</Button></DialogActions>
            </Dialog>
        </Stack>
    );
}
