import React, { useEffect, useMemo, useState } from "react";
import {
    Box,
    Typography,
    Divider,
    Paper,
    Stack,
    Button,
    IconButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Chip,
    Skeleton,
    Switch,
    CircularProgress,
    Tab,
    Tabs
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import VisibilityIcon from "@mui/icons-material/Visibility";
import EditIcon from "@mui/icons-material/Edit";
import { useMsal } from "@azure/msal-react";
import {
    Agent,
    AgentConfig,
    BindingInput,
    create_agent,
    DatabaseConnection,
    delete_agent,
    edit_agent,
    get_agent_by_team,
    Integration,
    Prompt,
    TeamProfile,
    DatabaseBindingData,
    MailBindingData,
    MailEmailConfig,
    ChartBindingData
} from "../../../api";
import { getToken, getUsername } from "../../../authConfig";
import { STORAGE_KEYS } from "../../../utill/storageKeys";
import { Storage } from "../../../utill/storage";
import { useNotification } from "../../../utill/NotificationProvider";
import { AgentBindingDialog } from "../dialog/AgentBindingDialog";
import { DatabaseBindingDialog, DatabaseBindingInput } from "../dialog/DatabaseBindingDialog";
import { MailBindingDialog, MailBindingInput } from "../dialog/MailBindingDialog";
import { ChartBindingDialog, ChartBindingInput } from "../dialog/ChartBindingDialog";
import { getIntegrationIcon } from "../utils/integrationIcons";
import {
    delete_agent_binding_by_id,
    get_agent_bindings_by_agent,
    get_db_connections,
    get_integrations_by_team,
    insert_agent_binding,
    insert_database_binding,
    toggle_agent_binding_by_id,
    get_database_bindings_by_agent,
    delete_database_binding_by_id,
    toggle_database_binding_by_id,
    get_mail_configs,
    get_mail_bindings_by_agent,
    insert_mail_binding,
    delete_mail_binding_by_id,
    toggle_mail_binding_by_id,
    // ⭐ CHART CAPABILITY
    get_chart_bindings_by_agent,
    insert_chart_binding,
    delete_chart_binding_by_id,
    toggle_chart_binding_by_id,
    update_chart_binding
} from "../../../api/api";

/* =========================
   TYPES
========================= */

type AgentDialogMode = "new" | "view" | "edit";

type Binding = BindingInput & {
    _id: string;
};

/* =========================================================
   PAGE
========================================================= */
export function AgentManagementPage() {
    const { instance } = useMsal();
    const [agents, setAgents] = useState<Agent[]>([]);
    const [loading, setLoading] = useState(false);
    const [openDialog, setOpenDialog] = useState(false);
    const [mode, setMode] = useState<AgentDialogMode>("new");
    const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
    const [search, setSearch] = useState("");
    const [team, setTeam] = useState<TeamProfile | null>(null);
    const { showNotification } = useNotification();

    // ✅ ADD
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);

    // confirm delete
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [agentToDelete, setAgentToDelete] = useState<Agent | null>(null);

    /* =========================
       LOAD ACTIVE TEAM
    ========================= */
    useEffect(() => {
        const loadTeam = async () => {
            const activeTeams = Storage.get<Record<string, TeamProfile>>(STORAGE_KEYS.Active_Teams);
            if (!activeTeams) return;

            const username = (await getUsername(instance)) ?? "";
            if (!username) return;

            setTeam(activeTeams[username] ?? null);
        };

        loadTeam();
    }, [instance]);

    /* =========================
       LOAD AGENTS
    ========================= */
    useEffect(() => {
        const loadAgents = async () => {
            if (!team?._id) return;

            try {
                setLoading(true);
                const token = await getToken(instance);
                if (!token) return;

                const result = await get_agent_by_team(team._id, token);
                setAgents(result ?? []);
            } catch (err) {
                console.error("load agents failed:", err);
            } finally {
                setLoading(false);
            }
        };

        loadAgents();
    }, [team, instance]);

    /* =========================
       ACTIONS
    ========================= */
    const openNew = () => {
        setMode("new");
        setSelectedAgent(null);
        setOpenDialog(true);
    };

    const openView = (agent: Agent) => {
        setMode("view");
        setSelectedAgent(agent);
        setOpenDialog(true);
    };

    const openEdit = (agent: Agent) => {
        setMode("edit");
        setSelectedAgent(agent);
        setOpenDialog(true);
    };

    const handleSave = async (agent: Agent) => {
        if (!team?._id) return;

        try {
            setSaving(true); // ✅ ADD
            const token = await getToken(instance);
            if (!token) return;

            if (mode === "new") {
                await create_agent(team._id, agent.agent_name, agent.config, agent.prompt, token);
                showNotification("Agent created successfully", "success");
            }

            if (mode === "edit") {
                await edit_agent(agent._id, agent.agent_name, agent.config, agent.prompt, token);
                showNotification("Agent updated successfully", "success");
            }

            const refreshed = await get_agent_by_team(team._id, token);
            setAgents(refreshed ?? []);
            setOpenDialog(false);
        } catch (err) {
            console.error("save agent failed:", err);
            showNotification("Failed to save agent", "error");
        } finally {
            setSaving(false); // ✅ ADD
        }
    };

    const handleDelete = async (agent: Agent) => {
        if (!team?._id) return;

        try {
            setDeletingId(agent._id); // ✅ ADD
            const token = await getToken(instance);
            if (!token) return;

            await delete_agent(team._id, agent._id, token);
            setAgents(prev => prev.filter(a => a._id !== agent._id));
            showNotification("Agent deleted successfully", "success");
        } catch (err) {
            console.error("delete agent failed:", err);
            showNotification("Failed to delete agent", "error");
        } finally {
            setDeletingId(null); // ✅ ADD
        }
    };

    /* =========================
       FILTER
    ========================= */
    const filteredAgents = useMemo(() => {
        return agents.filter(agent => agent.agent_name.toLowerCase().includes(search.toLowerCase()));
    }, [agents, search]);

    /* =========================
       RENDER
    ========================= */
    return (
        <Stack spacing={2}>
            {/* HEADER */}
            <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                    <Typography variant="h6">Agent Management</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Manage agents for this team
                    </Typography>
                </Box>

                <Button variant="contained" startIcon={<AddIcon />} onClick={openNew} disabled={!team}>
                    New Agent
                </Button>
            </Box>

            <Divider />

            <TextField size="small" placeholder="Search agent..." value={search} onChange={e => setSearch(e.target.value)} sx={{ maxWidth: 300 }} />

            {/* AGENT LIST */}
            <Box sx={{ maxHeight: 420, overflowY: "auto" }}>
                {loading ? (
                    <AgentListSkeleton count={6} />
                ) : filteredAgents.length === 0 ? (
                    <Typography color="text.secondary">No agents found</Typography>
                ) : (
                    <Stack spacing={1}>
                        {filteredAgents.map(agent => (
                            <Paper
                                key={agent._id}
                                variant="outlined"
                                sx={{
                                    p: 2,
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "center"
                                }}
                            >
                                <Box>
                                    <Typography fontWeight={600}>{agent.agent_name}</Typography>
                                    <Box mt={0.5}>
                                        <Chip size="small" label={`Temp: ${agent.config.temperature}`} sx={{ mr: 1 }} />
                                        <Chip size="small" label={`Max tokens: ${agent.config.max_tokens}`} sx={{ mr: 1 }} />
                                        <Chip size="small" label={`Min Search Score: ${agent.config.min_search_score}`} sx={{ mr: 1 }} />
                                        <Chip size="small" label={`Max Search Results: ${agent.config.max_search_results}`} />
                                    </Box>
                                </Box>

                                <Box>
                                    <IconButton onClick={() => openView(agent)}>
                                        <VisibilityIcon />
                                    </IconButton>
                                    <IconButton onClick={() => openEdit(agent)}>
                                        <EditIcon />
                                    </IconButton>
                                    <IconButton
                                        color="error"
                                        onClick={() => {
                                            setAgentToDelete(agent);
                                            setConfirmOpen(true);
                                        }}
                                        disabled={deletingId === agent._id}
                                    >
                                        <DeleteIcon />
                                    </IconButton>
                                </Box>
                            </Paper>
                        ))}
                    </Stack>
                )}
            </Box>

            {/* DIALOG */}
            <AgentDialog
                open={openDialog}
                mode={mode}
                loading={saving}
                agent={selectedAgent}
                teamId={team?._id}
                onClose={() => setOpenDialog(false)}
                onSave={handleSave}
            />
            <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
                <DialogTitle>Confirm Delete</DialogTitle>
                <DialogContent>
                    <Typography>
                        Are you sure you want to delete agent
                        <strong> {agentToDelete?.agent_name}</strong> ?
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setConfirmOpen(false)} disabled={!!deletingId}>
                        Cancel
                    </Button>
                    <Button
                        color="error"
                        variant="contained"
                        disabled={!!deletingId}
                        onClick={async () => {
                            if (!agentToDelete) return;
                            await handleDelete(agentToDelete);
                            setConfirmOpen(false);
                        }}
                    >
                        {deletingId ? "Deleting..." : "Delete"}
                    </Button>
                </DialogActions>
            </Dialog>
        </Stack>
    );
}

/* =========================================================
   AGENT DIALOG — tabbed layout
========================================================= */
function AgentDialog({
    open,
    mode,
    agent,
    teamId,
    loading,
    onClose,
    onSave
}: {
    open: boolean;
    mode: AgentDialogMode;
    agent: Agent | null;
    teamId?: string;
    loading: boolean;
    onClose: () => void;
    onSave: (agent: Agent) => void;
}) {
    const { instance } = useMsal();
    const isViewMode = mode === "view";
    const isSaving = loading;
    const isFieldDisabled = isViewMode || isSaving;
    const isCreate = mode === "new";

    // Tab state — always reset to "info" when dialog opens
    const [activeTab, setActiveTab] = useState<"info" | "integrations">("info");

    useEffect(() => {
        if (open) setActiveTab("info");
    }, [open]);

    const [agentName, setAgentName] = useState("");

    const EMPTY_PROMPT: Prompt = {
        role: "",
        task: "",
        detail_context: "",
        output_format: "",
        constraints: ""
    };

    const [config, setConfig] = useState<AgentConfig>({
        temperature: 0.2,
        seed: null,
        min_search_score: 0,
        max_search_results: 2,
        max_tokens: 1024
    });

    const [prompt, setPrompt] = useState<Prompt>({
        role: "",
        task: "",
        detail_context: "",
        output_format: "",
        constraints: ""
    });

    const [bindings, setBindings] = useState<Binding[]>([]);
    const [databaseBindings, setDatabaseBindings] = useState<DatabaseBindingData[]>([]);
    const [mailBindings, setMailBindings] = useState<MailBindingData[]>([]);
    const [chartBindings, setChartBindings] = useState<ChartBindingData[]>([]); // ⭐ CHART CAPABILITY
    const [bindingDialogOpen, setBindingDialogOpen] = useState(false);
    const [databaseBindingDialogOpen, setDatabaseBindingDialogOpen] = useState(false);
    const [mailBindingDialogOpen, setMailBindingDialogOpen] = useState(false);
    const [chartBindingDialogOpen, setChartBindingDialogOpen] = useState(false); // ⭐ CHART CAPABILITY
    const [selectedChartBinding, setSelectedChartBinding] = useState<ChartBindingData | null>(null); // ⭐ CHART CAPABILITY
    const [bindingSaving, setBindingSaving] = useState(false);
    const [bindingsLoading, setBindingsLoading] = useState(false);
    const [deletingBindingId, setDeletingBindingId] = useState<string | null>(null);
    const [deletingDatabaseBindingId, setDeletingDatabaseBindingId] = useState<string | null>(null);
    const [deletingMailBindingId, setDeletingMailBindingId] = useState<string | null>(null);
    const [deletingChartBindingId, setDeletingChartBindingId] = useState<string | null>(null); // ⭐ CHART CAPABILITY
    const { showNotification } = useNotification();

    const [integrations, setIntegrations] = useState<Integration[]>([]);
    const [databaseConnections, setDatabaseConnections] = useState<DatabaseConnection[]>([]);
    const [mailConfigs, setMailConfigs] = useState<MailEmailConfig[]>([]);

    useEffect(() => {
        const loadIntegrations = async () => {
            if (open && teamId) {
                try {
                    const token = await getToken(instance);
                    if (!token) return;
                    const res = await get_integrations_by_team(teamId, token);
                    const integrData = res?.result || res?.data || res || [];
                    setIntegrations(Array.isArray(integrData) ? integrData : []);
                } catch (e) {
                    console.error("load integrations failed", e);
                }
            }
        };
        loadIntegrations();
    }, [open, teamId, instance]);

    useEffect(() => {
        const loadDatabaseConnections = async () => {
            if (open && teamId) {
                try {
                    const token = await getToken(instance);
                    if (!token) return;
                    const res = await get_db_connections(teamId, token);
                    setDatabaseConnections(Array.isArray(res) ? res : []);
                } catch (e) {
                    console.error("load database connections failed", e);
                }
            }
        };
        loadDatabaseConnections();
    }, [open, teamId, instance]);

    useEffect(() => {
        const loadMailConfigs = async () => {
            if (open && teamId) {
                try {
                    const token = await getToken(instance);
                    if (!token) return;
                    const res = await get_mail_configs(teamId, token);
                    setMailConfigs(Array.isArray(res) ? res : []);
                } catch (e) {
                    console.error("load mail configs failed", e);
                }
            }
        };
        loadMailConfigs();
    }, [open, teamId, instance]);

    const loadBindings = async () => {
        if (agent?._id && mode !== "new") {
            try {
                setBindingsLoading(true);
                const token = await getToken(instance);
                if (!token) return;

                // Load API bindings
                const res = await get_agent_bindings_by_agent(agent._id, token);
                const bindingData = res?.result || res?.data || res || [];
                setBindings(Array.isArray(bindingData) ? bindingData : []);

                // Load Database bindings
                try {
                    const dbRes = await get_database_bindings_by_agent(agent._id, token);
                    const dbData = dbRes?.result || dbRes?.data || dbRes || [];
                    setDatabaseBindings(Array.isArray(dbData) ? dbData : []);
                } catch (dbErr) {
                    console.error("load database bindings error", dbErr);
                    setDatabaseBindings([]);
                }

                // Load Mail bindings
                try {
                    const mailRes = await get_mail_bindings_by_agent(agent._id, token);
                    setMailBindings(Array.isArray(mailRes) ? mailRes : []);
                } catch (mailErr) {
                    console.error("load mail bindings error", mailErr);
                    setMailBindings([]);
                }

                // ⭐ CHART CAPABILITY: Load Chart bindings
                try {
                    const chartRes = await get_chart_bindings_by_agent(agent._id, token);
                    setChartBindings(Array.isArray(chartRes) ? chartRes : []);
                } catch (chartErr) {
                    console.error("load chart bindings error", chartErr);
                    setChartBindings([]);
                }
            } catch (e) {
                console.error("load bindings error", e);
            } finally {
                setBindingsLoading(false);
            }
        } else {
            setBindings([]);
            setDatabaseBindings([]);
            setMailBindings([]);
            setChartBindings([]); // ⭐ CHART CAPABILITY
        }
    };

    useEffect(() => {
        if (open) {
            loadBindings();
        }
    }, [agent, mode, instance, open]);

    useEffect(() => {
        if (agent) {
            setAgentName(agent.agent_name);
            setConfig(agent.config);
            setPrompt(agent.prompt ?? EMPTY_PROMPT); // ✅ FIX
        } else {
            setAgentName("");
            setConfig({
                temperature: 0.2,
                seed: null,
                min_search_score: 0,
                max_search_results: 2,
                max_tokens: 1024
            });
            setPrompt(EMPTY_PROMPT);
        }
    }, [agent, mode]);

    useEffect(() => {
        if (!open) {
            setBindingDialogOpen(false);
            setDatabaseBindingDialogOpen(false);
            setMailBindingDialogOpen(false);
            setChartBindingDialogOpen(false); // ⭐ CHART CAPABILITY
        }
    }, [open]);

    const apiBindings = bindings;

    /* ── Tab panel helpers ───────────────────────────────────── */
    const integrationsTabDisabled = isCreate;

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>
                {mode === "new" && "Create New Agent"}
                {mode === "view" && "View Agent"}
                {mode === "edit" && "Edit Agent"}
            </DialogTitle>

            {/* ── Tab bar ── */}
            <Box sx={{ borderBottom: 1, borderColor: "divider", px: 3 }}>
                <Tabs
                    value={activeTab}
                    onChange={(_, v) => setActiveTab(v)}
                    aria-label="agent dialog tabs"
                >
                    <Tab label="Agent Info" value="info" />
                    <Tab
                        label="Integrations"
                        value="integrations"
                        disabled={integrationsTabDisabled}
                        title={integrationsTabDisabled ? "Save the agent first to manage integrations" : undefined}
                    />
                </Tabs>
            </Box>

            <DialogContent dividers>
                {/* ══════════════════════════════════
                    TAB 1 — Agent Info
                ══════════════════════════════════ */}
                {activeTab === "info" && (
                    <Stack spacing={3}>
                        {/* Agent name */}
                        <TextField label="Agent Name" value={agentName} disabled={isFieldDisabled} onChange={e => setAgentName(e.target.value)} />

                        {/* CONFIG */}
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Typography fontWeight={600}>Configuration</Typography>
                            <Stack spacing={2} mt={2}>
                                <TextField
                                    label="Temperature"
                                    type="number"
                                    disabled={isFieldDisabled}
                                    value={config.temperature}
                                    onChange={e => setConfig({ ...config, temperature: Number(e.target.value) })}
                                />
                                <TextField
                                    label="Seed"
                                    type="number"
                                    disabled={isFieldDisabled}
                                    value={config.seed ?? ""}
                                    onChange={e => setConfig({ ...config, seed: e.target.value ? Number(e.target.value) : null })}
                                />
                                <TextField
                                    label="Min Search Score"
                                    type="number"
                                    disabled={isFieldDisabled}
                                    value={config.min_search_score}
                                    onChange={e => setConfig({ ...config, min_search_score: Number(e.target.value) })}
                                />
                                <TextField
                                    label="Max Search Results"
                                    type="number"
                                    disabled={isFieldDisabled}
                                    value={config.max_search_results}
                                    onChange={e => setConfig({ ...config, max_search_results: Number(e.target.value) })}
                                />
                                <TextField
                                    label="Max Tokens"
                                    type="number"
                                    disabled={isFieldDisabled}
                                    value={config.max_tokens}
                                    onChange={e => setConfig({ ...config, max_tokens: Number(e.target.value) })}
                                />
                            </Stack>
                        </Paper>

                        {/* PROMPT */}
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Typography fontWeight={600}>Prompt</Typography>
                            <Stack spacing={2} mt={2}>
                                <TextField
                                    label="Role"
                                    disabled={isFieldDisabled}
                                    value={prompt.role}
                                    onChange={e => setPrompt({ ...prompt, role: e.target.value })}
                                />
                                <TextField
                                    label="Task"
                                    disabled={isFieldDisabled}
                                    value={prompt.task}
                                    onChange={e => setPrompt({ ...prompt, task: e.target.value })}
                                />
                                <TextField
                                    label="Detail Context"
                                    multiline
                                    minRows={3}
                                    disabled={isFieldDisabled}
                                    value={prompt.detail_context}
                                    onChange={e => setPrompt({ ...prompt, detail_context: e.target.value })}
                                />
                                <TextField
                                    label="Output Format"
                                    disabled={isFieldDisabled}
                                    value={prompt.output_format}
                                    onChange={e => setPrompt({ ...prompt, output_format: e.target.value })}
                                />
                                <TextField
                                    label="Constraints"
                                    disabled={isFieldDisabled}
                                    value={prompt.constraints}
                                    onChange={e => setPrompt({ ...prompt, constraints: e.target.value })}
                                />
                            </Stack>
                        </Paper>
                    </Stack>
                )}

                {/* ══════════════════════════════════
                    TAB 2 — Integrations
                    Designed to be extensible: add new
                    integration sections here as needed.
                ══════════════════════════════════ */}
                {activeTab === "integrations" && !isCreate && (
                    <Stack spacing={3}>
                        {/* ── External API ── */}
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Stack direction="row" justifyContent="space-between" alignItems="center">
                                <Box>
                                    <Typography fontWeight={600}>External API Capabilities</Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        APIs that the agent can call automatically
                                    </Typography>
                                </Box>

                                {!isViewMode && (
                                    <Button size="small" onClick={() => setBindingDialogOpen(true)}>
                                        + Add Integration
                                    </Button>
                                )}
                            </Stack>

                            {bindingsLoading ? (
                                <AgentBindingListSkeleton count={2} />
                            ) : apiBindings.length === 0 ? (
                                <Typography variant="body2" color="text.secondary" mt={2}>
                                    No integrations linked
                                </Typography>
                            ) : (
                                <Box mt={2} sx={{ maxHeight: 460, overflowY: "auto", pr: 0.5 }}>
                                    <Stack spacing={2}>
                                    {apiBindings.map(b => {
                                        const integration = integrations.find(i => i._id === b.integration_id);
                                        const endpoint = integration?.endpoints.find(e => e.name === b.endpoint_name);

                                        return (
                                            <BindingCard
                                                key={b._id}
                                                binding={b}
                                                title={integration?.name ?? b.integration_id}
                                                subtitle={endpoint ? `${endpoint.method} ${endpoint.path}` : undefined}
                                                chips={[
                                                    endpoint?.method
                                                        ? { label: endpoint.method, color: endpoint.method === "GET" ? "success" : "primary" }
                                                        : null,
                                                    endpoint?.path ? { label: endpoint.path, sx: { fontFamily: "monospace" } } : null,
                                                    { label: b.async ? "Async" : "Sync", color: b.async ? "warning" : "default" }
                                                ]}
                                                detailLabel="Triggers"
                                                detailValues={b.trigger_keywords}
                                                deletingBindingId={deletingBindingId}
                                                isViewMode={isViewMode}
                                                instance={instance}
                                                setBindings={setBindings}
                                                setDeletingBindingId={setDeletingBindingId}
                                                showNotification={showNotification}
                                            >
                                                {b.request_fields?.length > 0 && (
                                                    <Box>
                                                        <Typography variant="caption" color="text.secondary">
                                                            Request
                                                        </Typography>
                                                        {b.request_fields.map((f, idx) => (
                                                            <Typography key={idx} variant="body2">
                                                                {f.field} ({f.location}) : {f.description}
                                                            </Typography>
                                                        ))}
                                                    </Box>
                                                )}
                                                {b.response_fields?.length > 0 && (
                                                    <Box>
                                                        <Typography variant="caption" color="text.secondary">
                                                            Response
                                                        </Typography>
                                                        {b.response_fields.map((f, idx) => (
                                                            <Typography key={idx} variant="body2">
                                                                {f.field} : {f.description}
                                                            </Typography>
                                                        ))}
                                                    </Box>
                                                )}
                                            </BindingCard>
                                        );
                                    })}
                                    </Stack>
                                </Box>
                            )}
                        </Paper>

                        {/* ── Database Connections ── */}
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Stack direction="row" justifyContent="space-between" alignItems="center">
                                <Box>
                                    <Typography fontWeight={600}>Database Connections</Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Databases that the agent can use for query generation
                                    </Typography>
                                </Box>

                                {!isViewMode && (
                                    <Button size="small" onClick={() => setDatabaseBindingDialogOpen(true)}>
                                        + Add Database
                                    </Button>
                                )}
                            </Stack>

                            {bindingsLoading ? (
                                <AgentBindingListSkeleton count={2} />
                            ) : databaseBindings.length === 0 ? (
                                <Typography variant="body2" color="text.secondary" mt={2}>
                                    No database connections linked
                                </Typography>
                            ) : (
                                <Box mt={2} sx={{ maxHeight: 460, overflowY: "auto", pr: 0.5 }}>
                                    <Stack spacing={2}>
                                    {databaseBindings.map(binding => {
                                        const databaseConnection = databaseConnections.find(
                                            connection => connection._id === binding.integration_id
                                        );
                                        const alias = binding.alias?.trim();
                                        const title = alias || databaseConnection?.name || binding.integration_id;
                                        const subtitle = databaseConnection
                                            ? `${databaseConnection.db_type} • ${databaseConnection.host}:${databaseConnection.port} • ${databaseConnection.database}`
                                            : undefined;

                                        return (
                                            <DatabaseBindingCard
                                                key={binding._id}
                                                binding={binding}
                                                title={title}
                                                subtitle={subtitle}
                                                chips={[
                                                    databaseConnection?.db_type ? { label: databaseConnection.db_type } : null,
                                                    databaseConnection?.database ? { label: databaseConnection.database } : null
                                                ]}
                                                deletingBindingId={deletingDatabaseBindingId}
                                                isViewMode={isViewMode}
                                                instance={instance}
                                                setBindings={setDatabaseBindings}
                                                setDeletingBindingId={setDeletingDatabaseBindingId}
                                                showNotification={showNotification}
                                            >
                                                {databaseConnection && (
                                                    <Typography variant="caption" color="text.secondary">
                                                        User: {databaseConnection.username}
                                                    </Typography>
                                                )}
                                            </DatabaseBindingCard>
                                        );
                                    })}
                                    </Stack>
                                </Box>
                            )}
                        </Paper>

                        {/* ── Mail Capabilities ── */}
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Stack direction="row" justifyContent="space-between" alignItems="center">
                                <Box>
                                    <Typography fontWeight={600}>Mail Capabilities</Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Email accounts the agent can send mail through
                                    </Typography>
                                </Box>
                                {!isViewMode && (
                                    <Button size="small" onClick={() => setMailBindingDialogOpen(true)}>
                                        + Add Mail
                                    </Button>
                                )}
                            </Stack>

                            {bindingsLoading ? (
                                <AgentBindingListSkeleton count={2} />
                            ) : mailBindings.length === 0 ? (
                                <Typography variant="body2" color="text.secondary" mt={2}>
                                    No mail accounts linked
                                </Typography>
                            ) : (
                                <Box mt={2} sx={{ maxHeight: 460, overflowY: "auto", pr: 0.5 }}>
                                    <Stack spacing={2}>
                                        {mailBindings.map(binding => {
                                            const cfg = mailConfigs.find(c => c._id === binding.email_id);
                                            const title = cfg?.name ?? binding.email_id;
                                            const subtitle = cfg ? `${cfg.email} — ${cfg.protocol}/${cfg.encryption}` : undefined;

                                            return (
                                                <Paper key={binding._id} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                                                    <Stack spacing={1.5}>
                                                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                                                            <Stack direction="row" spacing={1} alignItems="center">
                                                                {getIntegrationIcon("mail")}
                                                                <Typography fontWeight={600}>{title}</Typography>
                                                                <Chip size="small" label="mail" sx={{ ml: 1 }} />
                                                                <Chip
                                                                    size="small"
                                                                    label={binding.is_html ? "HTML" : "Plain text"}
                                                                    variant="outlined"
                                                                />
                                                            </Stack>

                                                            <Stack direction="row" spacing={1} alignItems="center">
                                                                <Typography variant="caption">Enabled</Typography>
                                                                <Switch
                                                                    size="small"
                                                                    checked={binding.enabled !== false}
                                                                    disabled={isViewMode}
                                                                    onChange={async () => {
                                                                        const newValue = !binding.enabled;
                                                                        setMailBindings(prev =>
                                                                            prev.map(x => (x._id === binding._id ? { ...x, enabled: newValue } : x))
                                                                        );
                                                                        try {
                                                                            const token = await getToken(instance);
                                                                            if (token) {
                                                                                await toggle_mail_binding_by_id(binding._id, newValue, token);
                                                                                showNotification(`Mail binding ${newValue ? "enabled" : "disabled"}`, "success");
                                                                            }
                                                                        } catch (err) {
                                                                            setMailBindings(prev =>
                                                                                prev.map(x => (x._id === binding._id ? { ...x, enabled: !newValue } : x))
                                                                            );
                                                                            showNotification("Failed to toggle mail binding", "error");
                                                                        }
                                                                    }}
                                                                />
                                                                {!isViewMode && (
                                                                    <IconButton
                                                                        size="small"
                                                                        color="error"
                                                                        disabled={deletingMailBindingId === binding._id}
                                                                        onClick={async () => {
                                                                            if (!window.confirm("Delete this mail binding?")) return;
                                                                            try {
                                                                                setDeletingMailBindingId(binding._id);
                                                                                const token = await getToken(instance);
                                                                                if (token) {
                                                                                    await delete_mail_binding_by_id(binding._id, token);
                                                                                    setMailBindings(prev => prev.filter(x => x._id !== binding._id));
                                                                                    showNotification("Mail binding deleted", "success");
                                                                                }
                                                                            } catch (err) {
                                                                                showNotification("Failed to delete mail binding", "error");
                                                                            } finally {
                                                                                setDeletingMailBindingId(null);
                                                                            }
                                                                        }}
                                                                    >
                                                                        {deletingMailBindingId === binding._id ? (
                                                                            <CircularProgress size={20} color="inherit" />
                                                                        ) : (
                                                                            <DeleteIcon fontSize="small" />
                                                                        )}
                                                                    </IconButton>
                                                                )}
                                                            </Stack>
                                                        </Stack>

                                                        {subtitle && (
                                                            <Typography variant="body2" color="text.secondary">
                                                                {subtitle}
                                                            </Typography>
                                                        )}
                                                    </Stack>
                                                </Paper>
                                            );
                                        })}
                                    </Stack>
                                </Box>
                            )}
                        </Paper>

                        {/* ⭐ CHART CAPABILITY: Chart Capabilities section */}
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Stack direction="row" justifyContent="space-between" alignItems="center">
                                <Box>
                                    <Typography fontWeight={600}>Chart Capabilities</Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Allow the agent to generate charts from data
                                    </Typography>
                                </Box>
                                {!isViewMode && chartBindings.length === 0 && (
                                    <Button
                                        size="small"
                                        onClick={() => {
                                            setSelectedChartBinding(null);
                                            setChartBindingDialogOpen(true);
                                        }}
                                    >
                                        + Add Chart Capability
                                    </Button>
                                )}
                            </Stack>

                            {bindingsLoading ? (
                                <AgentBindingListSkeleton count={1} />
                            ) : chartBindings.length === 0 ? (
                                <Typography variant="body2" color="text.secondary" mt={2}>
                                    No chart capability linked
                                </Typography>
                            ) : (
                                <Box mt={2} sx={{ maxHeight: 460, overflowY: "auto", pr: 0.5 }}>
                                    <Stack spacing={2}>
                                        {chartBindings.map(binding => (
                                            <Paper key={binding._id} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                                                <Stack spacing={1.5}>
                                                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                                                        <Stack direction="row" spacing={1} alignItems="center">
                                                            {getIntegrationIcon("chart")}
                                                            <Typography fontWeight={600}>
                                                                {binding.chart_selection_mode === "auto" ? "Auto" : "Manual"} Chart
                                                            </Typography>
                                                            <Chip size="small" label="chart" sx={{ ml: 1 }} />
                                                            <Chip
                                                                size="small"
                                                                label={`mode: ${binding.chart_selection_mode ?? "auto"}`}
                                                                variant="outlined"
                                                            />
                                                        </Stack>

                                                        <Stack direction="row" spacing={1} alignItems="center">
                                                            <Typography variant="caption">Enabled</Typography>
                                                            <Switch
                                                                size="small"
                                                                checked={binding.enabled !== false}
                                                                disabled={isViewMode}
                                                                onChange={async () => {
                                                                    const newValue = !binding.enabled;
                                                                    setChartBindings(prev =>
                                                                        prev.map(x => (x._id === binding._id ? { ...x, enabled: newValue } : x))
                                                                    );
                                                                    try {
                                                                        const token = await getToken(instance);
                                                                        if (token) {
                                                                            await toggle_chart_binding_by_id(binding._id, newValue, token);
                                                                            showNotification(`Chart capability ${newValue ? "enabled" : "disabled"}`, "success");
                                                                        }
                                                                    } catch (err) {
                                                                        setChartBindings(prev =>
                                                                            prev.map(x => (x._id === binding._id ? { ...x, enabled: !newValue } : x))
                                                                        );
                                                                        showNotification("Failed to toggle chart capability", "error");
                                                                    }
                                                                }}
                                                            />
                                                            {!isViewMode && (
                                                                <>
                                                                    <IconButton
                                                                        size="small"
                                                                        color="primary"
                                                                        onClick={() => {
                                                                            setSelectedChartBinding(binding);
                                                                            setChartBindingDialogOpen(true);
                                                                        }}
                                                                    >
                                                                        <EditIcon fontSize="small" />
                                                                    </IconButton>
                                                                    <IconButton
                                                                        size="small"
                                                                        color="error"
                                                                        disabled={deletingChartBindingId === binding._id}
                                                                        onClick={async () => {
                                                                            if (!window.confirm("Delete this chart capability?")) return;
                                                                            try {
                                                                                setDeletingChartBindingId(binding._id);
                                                                                const token = await getToken(instance);
                                                                                if (token) {
                                                                                    await delete_chart_binding_by_id(binding._id, token);
                                                                                    setChartBindings(prev => prev.filter(x => x._id !== binding._id));
                                                                                    showNotification("Chart capability deleted", "success");
                                                                                }
                                                                            } catch (err) {
                                                                                showNotification("Failed to delete chart capability", "error");
                                                                            } finally {
                                                                                setDeletingChartBindingId(null);
                                                                            }
                                                                        }}
                                                                    >
                                                                        {deletingChartBindingId === binding._id ? (
                                                                            <CircularProgress size={20} color="inherit" />
                                                                        ) : (
                                                                            <DeleteIcon fontSize="small" />
                                                                        )}
                                                                    </IconButton>
                                                                </>
                                                            )}
                                                        </Stack>
                                                    </Stack>

                                                    {/* Chart selection info */}
                                                    <Box>
                                                        <Typography variant="caption" color="text.secondary">
                                                            Selection Mode
                                                        </Typography>
                                                        <Box mt={0.5} display="flex" gap={0.5} flexWrap="wrap">
                                                            <Chip
                                                                label={binding.chart_selection_mode === "auto" ? "🤖 Auto — LLM เลือกเอง" : "🎛 Manual — กำหนด type เอง"}
                                                                size="small"
                                                                color={binding.chart_selection_mode === "auto" ? "primary" : "default"}
                                                                variant="outlined"
                                                            />
                                                            <Chip
                                                                label={binding.auto_generate ? "⚡ Auto-generate ON" : "👆 ต้องให้ user สั่ง"}
                                                                size="small"
                                                                color={binding.auto_generate ? "success" : "default"}
                                                                variant="outlined"
                                                            />
                                                        </Box>
                                                    </Box>

                                                    {/* Color palette */}
                                                    {binding.color_palette && binding.color_palette.length > 0 && (
                                                        <Box>
                                                            <Typography variant="caption" color="text.secondary">
                                                                Palette
                                                            </Typography>
                                                            <Stack direction="row" spacing={0.5} mt={0.5} alignItems="center">
                                                                {binding.color_palette.map((color, index) => (
                                                                    <Box
                                                                        key={`${binding._id}-color-${index}`}
                                                                        sx={{
                                                                            width: 18,
                                                                            height: 18,
                                                                            borderRadius: "4px",
                                                                            backgroundColor: color,
                                                                            border: "1px solid rgba(0,0,0,0.1)"
                                                                        }}
                                                                    />
                                                                ))}
                                                            </Stack>
                                                        </Box>
                                                    )}

                                                    {/* Trigger keywords */}
                                                    {binding.trigger_keywords && binding.trigger_keywords.length > 0 && (
                                                        <Box>
                                                            <Typography variant="caption" color="text.secondary">
                                                                Trigger keywords
                                                            </Typography>
                                                            <Box mt={0.5}>
                                                                {binding.trigger_keywords.map((keyword, index) => (
                                                                    <Chip
                                                                        key={`${binding._id}-kw-${index}`}
                                                                        label={keyword}
                                                                        size="small"
                                                                        sx={{ mr: 0.5, mb: 0.5 }}
                                                                    />
                                                                ))}
                                                            </Box>
                                                        </Box>
                                                    )}

                                                    {binding.title_template && (
                                                        <Typography variant="caption" color="text.secondary">
                                                            Title template: <code>{binding.title_template}</code>
                                                        </Typography>
                                                    )}
                                                </Stack>
                                            </Paper>
                                        ))}
                                    </Stack>
                                </Box>
                            )}
                        </Paper>

                        {/* Future: LINE, Google Sheet ฯลฯ เพิ่ม <Paper> block ตรงนี้ */}
                    </Stack>
                )}
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} disabled={isSaving}>
                    Close
                </Button>
                {/* Save button ปรากฏเฉพาะ tab "info" และ mode ที่ไม่ใช่ view */}
                {!isViewMode && activeTab === "info" && (
                    <Button
                        variant="contained"
                        disabled={!agentName || isSaving}
                        onClick={() =>
                            onSave({
                                _id: agent?._id ?? "",
                                agent_name: agentName,
                                config,
                                prompt
                            })
                        }
                    >
                        {loading ? "Saving..." : "Save"}
                    </Button>
                )}
            </DialogActions>
            <AgentBindingDialog
                open={bindingDialogOpen}
                saving={bindingSaving}
                integrations={integrations}
                onClose={() => setBindingDialogOpen(false)}
                onSave={async (binding: BindingInput) => {
                    const exists = bindings.some(b => b.integration_id === binding.integration_id && b.endpoint_name === binding.endpoint_name);
                    if (exists) {
                        showNotification("Binding already exists", "warning");
                        return;
                    }

                    try {
                        setBindingSaving(true);
                        const token = await getToken(instance);
                        if (!token || !agent?._id) return;

                        const payload = {
                            _id: Date.now().toString(),
                            agent_id: agent._id,
                            integration_id: binding.integration_id,
                            integration_type: binding.integration_type,
                            endpoint_name: binding.endpoint_name,
                            trigger_keywords: binding.trigger_keywords,
                            async: binding.async,
                            enabled: binding.enabled ?? true,
                            request_fields: binding.request_fields,
                            response_fields: binding.response_fields
                        };

                        await insert_agent_binding(payload, token);
                        await loadBindings(); // reload bindings from backend
                        showNotification("Binding added successfully", "success");
                        setBindingDialogOpen(false);
                    } catch (err) {
                        console.error("insert binding err", err);
                        showNotification("Failed to add binding", "error");
                    } finally {
                        setBindingSaving(false);
                    }
                }}
            />
            <DatabaseBindingDialog
                open={databaseBindingDialogOpen}
                saving={bindingSaving}
                connections={databaseConnections}
                onClose={() => setDatabaseBindingDialogOpen(false)}
                onSave={async (binding: DatabaseBindingInput) => {
                    const exists = databaseBindings.some(b => b.integration_id === binding.integration_id);
                    if (exists) {
                        showNotification("This database is already linked", "warning");
                        return;
                    }

                    try {
                        setBindingSaving(true);
                        const token = await getToken(instance);
                        if (!token || !agent?._id) return;

                        const selectedConnection = databaseConnections.find(connection => connection._id === binding.integration_id);
                        const payload = {
                            agent_id: agent._id,
                            integration_id: binding.integration_id,
                            alias: binding.alias.trim() || selectedConnection?.name || "",
                            trigger_keywords: binding.trigger_keywords,
                            enabled: binding.enabled
                        };

                        await insert_database_binding(payload, token);
                        await loadBindings();
                        showNotification("Database binding added successfully", "success");
                        setDatabaseBindingDialogOpen(false);
                    } catch (err) {
                        console.error("insert database binding err", err);
                        showNotification("Failed to add database binding", "error");
                    } finally {
                        setBindingSaving(false);
                    }
                }}
            />
            <MailBindingDialog
                open={mailBindingDialogOpen}
                saving={bindingSaving}
                mailConfigs={mailConfigs}
                onClose={() => setMailBindingDialogOpen(false)}
                onSave={async (binding: MailBindingInput) => {
                    const exists = mailBindings.some(b => b.email_id === binding.email_id);
                    if (exists) {
                        showNotification("This mail account is already linked", "warning");
                        return;
                    }
                    try {
                        setBindingSaving(true);
                        const token = await getToken(instance);
                        if (!token || !agent?._id) return;

                        await insert_mail_binding(
                            {
                                agent_id: agent._id,
                                email_id: binding.email_id,
                                is_html: binding.is_html,
                                enabled: binding.enabled,
                                subject: binding.subject,
                                body: binding.body,
                                default_to: binding.default_to,
                                default_cc: binding.default_cc,
                                default_bcc: binding.default_bcc
                            },
                            token
                        );
                        await loadBindings();
                        showNotification("Mail binding added successfully", "success");
                        setMailBindingDialogOpen(false);
                    } catch (err) {
                        console.error("insert mail binding err", err);
                        showNotification("Failed to add mail binding", "error");
                    } finally {
                        setBindingSaving(false);
                    }
                }}
            />
            {/* ⭐ CHART CAPABILITY: Chart binding dialog */}
            <ChartBindingDialog
                open={chartBindingDialogOpen}
                saving={bindingSaving}
                initialBinding={selectedChartBinding}
                onClose={() => setChartBindingDialogOpen(false)}
                onSave={async (binding: ChartBindingInput) => {
                    try {
                        setBindingSaving(true);
                        const token = await getToken(instance);
                        if (!token || !agent?._id) return;

                        if (binding._id) {
                            await update_chart_binding(
                                {
                                    _id: binding._id,
                                    agent_id: agent._id,
                                    enabled: binding.enabled,
                                    chart_selection_mode: "auto",
                                    auto_generate: binding.auto_generate,
                                    color_palette: binding.color_palette,
                                    title_template: binding.title_template,
                                    trigger_keywords: binding.trigger_keywords
                                },
                                token
                            );
                            showNotification("Chart capability updated successfully", "success");
                        } else {
                            await insert_chart_binding(
                                {
                                    agent_id: agent._id,
                                    enabled: binding.enabled,
                                    chart_selection_mode: "auto",
                                    auto_generate: binding.auto_generate,
                                    color_palette: binding.color_palette,
                                    title_template: binding.title_template,
                                    trigger_keywords: binding.trigger_keywords
                                },
                                token
                            );
                            showNotification("Chart capability added successfully", "success");
                        }
                        await loadBindings();
                        setChartBindingDialogOpen(false);
                    } catch (err) {
                        console.error("save chart binding err", err);
                        showNotification("Failed to save chart capability", "error");
                    } finally {
                        setBindingSaving(false);
                    }
                }}
            />
        </Dialog>
    );
}

function DatabaseBindingCard({
    binding,
    title,
    subtitle,
    chips,
    deletingBindingId,
    isViewMode,
    instance,
    setBindings,
    setDeletingBindingId,
    showNotification,
    children
}: {
    binding: DatabaseBindingData;
    title: string;
    subtitle?: string;
    chips: ({ label: string; color?: "default" | "primary" | "secondary" | "error" | "info" | "success" | "warning"; sx?: object } | null)[];
    deletingBindingId: string | null;
    isViewMode: boolean;
    instance: any;
    setBindings: React.Dispatch<React.SetStateAction<DatabaseBindingData[]>>;
    setDeletingBindingId: React.Dispatch<React.SetStateAction<string | null>>;
    showNotification: (message: string, severity?: any) => void;
    children?: React.ReactNode;
}) {
    return (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Stack spacing={1.5}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Stack direction="row" spacing={1} alignItems="center">
                        {getIntegrationIcon("database")}
                        <Typography fontWeight={600}>{title}</Typography>
                        <Chip size="small" label="database" sx={{ ml: 1 }} />
                    </Stack>

                    <Stack direction="row" spacing={1} alignItems="center">
                        <Typography variant="caption">Enabled</Typography>
                        <Switch
                            size="small"
                            checked={binding.enabled !== false}
                            disabled={isViewMode}
                            onChange={async () => {
                                const newValue = binding.enabled !== false ? false : true;
                                setBindings(prev => prev.map(x => (x._id === binding._id ? { ...x, enabled: newValue } : x)));
                                try {
                                    const token = await getToken(instance);
                                    if (token) {
                                        await toggle_database_binding_by_id(binding._id, newValue, token);
                                        showNotification(`Binding ${newValue ? "enabled" : "disabled"}`, "success");
                                    }
                                } catch (err) {
                                    console.error("toggle err", err);
                                    setBindings(prev => prev.map(x => (x._id === binding._id ? { ...x, enabled: !newValue } : x)));
                                    showNotification("Failed to toggle binding", "error");
                                }
                            }}
                        />

                        {!isViewMode && (
                            <IconButton
                                size="small"
                                color="error"
                                disabled={deletingBindingId === binding._id}
                                onClick={async () => {
                                    if (!window.confirm("Delete this database binding?")) return;
                                    try {
                                        setDeletingBindingId(binding._id);
                                        const token = await getToken(instance);
                                        if (token) {
                                            await delete_database_binding_by_id(binding._id, token);
                                            setBindings(prev => prev.filter(x => x._id !== binding._id));
                                            showNotification("Database binding deleted successfully", "success");
                                        }
                                    } catch (err) {
                                        console.error("del binding err", err);
                                        showNotification("Failed to delete database binding", "error");
                                    } finally {
                                        setDeletingBindingId(null);
                                    }
                                }}
                            >
                                {deletingBindingId === binding._id ? <CircularProgress size={20} color="inherit" /> : <DeleteIcon fontSize="small" />}
                            </IconButton>
                        )}
                    </Stack>
                </Stack>

                {subtitle && (
                    <Typography variant="body2" color="text.secondary">
                        {subtitle}
                    </Typography>
                )}

                {chips.filter(Boolean).length > 0 && (
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        {chips.filter(Boolean).map((chip, index) => (
                            <Chip key={`${binding._id}-${index}`} size="small" label={chip!.label} color={chip!.color} sx={chip!.sx} />
                        ))}
                    </Stack>
                )}

                {binding.trigger_keywords && binding.trigger_keywords.length > 0 && (
                    <Box>
                        <Typography variant="caption" color="text.secondary">
                            Trigger keywords
                        </Typography>
                        <Box mt={0.5}>
                            {binding.trigger_keywords.map((value, index) => (
                                <Chip key={`${binding._id}-detail-${index}`} label={value} size="small" sx={{ mr: 0.5, mb: 0.5 }} />
                            ))}
                        </Box>
                    </Box>
                )}

                {children}
            </Stack>
        </Paper>
    );
}

function BindingCard({
    binding,
    title,
    subtitle,
    chips,
    detailLabel,
    detailValues,
    deletingBindingId,
    isViewMode,
    instance,
    setBindings,
    setDeletingBindingId,
    showNotification,
    children
}: {
    binding: Binding;
    title: string;
    subtitle?: string;
    chips: ({ label: string; color?: "default" | "primary" | "secondary" | "error" | "info" | "success" | "warning"; sx?: object } | null)[];
    detailLabel?: string;
    detailValues?: string[];
    deletingBindingId: string | null;
    isViewMode: boolean;
    instance: any;
    setBindings: React.Dispatch<React.SetStateAction<Binding[]>>;
    setDeletingBindingId: React.Dispatch<React.SetStateAction<string | null>>;
    showNotification: (message: string, severity?: any) => void;
    children?: React.ReactNode;
}) {
    return (
        <Paper
            variant="outlined"
            sx={{
                p: 2,
                borderRadius: 2
            }}
        >
            <Stack spacing={1.5}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Stack direction="row" spacing={1} alignItems="center">
                        {getIntegrationIcon(binding.integration_type)}
                        <Typography fontWeight={600}>{title}</Typography>
                        <Chip size="small" label={binding.integration_type} sx={{ ml: 1 }} />
                    </Stack>

                    <Stack direction="row" spacing={1} alignItems="center">
                        <Typography variant="caption">Enabled</Typography>

                        <Switch
                            size="small"
                            checked={binding.enabled !== false}
                            disabled={isViewMode}
                            onChange={async () => {
                                const newValue = binding.enabled !== false ? false : true;
                                setBindings(prev => prev.map(x => (x._id === binding._id ? { ...x, enabled: newValue } : x)));
                                try {
                                    const token = await getToken(instance);
                                    if (token) {
                                        await toggle_agent_binding_by_id(binding._id, newValue, token);
                                        showNotification(`Binding ${newValue ? "enabled" : "disabled"}`, "success");
                                    }
                                } catch (err) {
                                    console.error("toggle err", err);
                                    setBindings(prev => prev.map(x => (x._id === binding._id ? { ...x, enabled: !newValue } : x)));
                                    showNotification("Failed to toggle binding", "error");
                                }
                            }}
                        />

                        {!isViewMode && (
                            <IconButton
                                size="small"
                                color="error"
                                disabled={deletingBindingId === binding._id}
                                onClick={async () => {
                                    if (!window.confirm("Delete this binding?")) return;
                                    try {
                                        setDeletingBindingId(binding._id);
                                        const token = await getToken(instance);
                                        if (token) {
                                            await delete_agent_binding_by_id(binding._id, token);
                                            setBindings(prev => prev.filter(x => x._id !== binding._id));
                                            showNotification("Binding deleted successfully", "success");
                                        }
                                    } catch (err) {
                                        console.error("del binding err", err);
                                        showNotification("Failed to delete binding", "error");
                                    } finally {
                                        setDeletingBindingId(null);
                                    }
                                }}
                            >
                                {deletingBindingId === binding._id ? <CircularProgress size={20} color="inherit" /> : <DeleteIcon fontSize="small" />}
                            </IconButton>
                        )}
                    </Stack>
                </Stack>

                {subtitle && (
                    <Typography variant="body2" color="text.secondary">
                        {subtitle}
                    </Typography>
                )}

                {chips.filter(Boolean).length > 0 && (
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        {chips.filter(Boolean).map((chip, index) => (
                            <Chip key={`${binding._id}-${index}`} size="small" label={chip!.label} color={chip!.color} sx={chip!.sx} />
                        ))}
                    </Stack>
                )}

                {detailValues && detailValues.length > 0 && (
                    <Box>
                        <Typography variant="caption" color="text.secondary">
                            {detailLabel}
                        </Typography>

                        <Box mt={0.5}>
                            {detailValues.map((value, index) => (
                                <Chip key={`${binding._id}-detail-${index}`} label={value} size="small" sx={{ mr: 0.5, mb: 0.5 }} />
                            ))}
                        </Box>
                    </Box>
                )}

                {children}
            </Stack>
        </Paper>
    );
}

function AgentListSkeleton({ count = 6 }: { count?: number }) {
    return (
        <Stack spacing={1}>
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
                        {/* title */}
                        <Skeleton variant="text" width="35%" height={26} />

                        {/* chips */}
                        <Box mt={1} display="flex" gap={1} flexWrap="wrap">
                            <Skeleton variant="rounded" width={90} height={24} />
                            <Skeleton variant="rounded" width={130} height={24} />
                            <Skeleton variant="rounded" width={150} height={24} />
                            <Skeleton variant="rounded" width={160} height={24} />
                        </Box>
                    </Box>

                    {/* action buttons */}
                    <Box sx={{ display: "flex", gap: 1 }}>
                        <Skeleton variant="circular" width={32} height={32} />
                        <Skeleton variant="circular" width={32} height={32} />
                        <Skeleton variant="circular" width={32} height={32} />
                    </Box>
                </Paper>
            ))}
        </Stack>
    );
}

function AgentBindingListSkeleton({ count = 2 }: { count?: number }) {
    return (
        <Stack spacing={2} mt={2}>
            {Array.from({ length: count }).map((_, idx) => (
                <Paper key={idx} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                    <Stack spacing={1.5}>
                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                            <Stack direction="row" spacing={1} alignItems="center">
                                <Skeleton variant="circular" width={24} height={24} />
                                <Skeleton variant="text" width={100} height={24} />
                                <Skeleton variant="rounded" width={50} height={20} />
                            </Stack>
                            <Box display="flex" gap={1}>
                                <Skeleton variant="rounded" width={40} height={20} />
                                <Skeleton variant="circular" width={24} height={24} />
                            </Box>
                        </Stack>
                        <Stack direction="row" spacing={1}>
                            <Skeleton variant="rounded" width={50} height={24} />
                            <Skeleton variant="rounded" width={120} height={24} />
                        </Stack>
                    </Stack>
                </Paper>
            ))}
        </Stack>
    );
}
