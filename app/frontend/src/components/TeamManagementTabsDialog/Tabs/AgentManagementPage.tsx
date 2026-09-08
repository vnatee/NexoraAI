import React, { useEffect, useMemo, useState } from "react";
import {
    Alert,
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
    FormControlLabel,
    CircularProgress,
    MenuItem,
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
    configApi,
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
    BusinessDocumentBindingData,
    BusinessDocumentConnection,
    ChartBindingData,
    ManagedMCPServer,
    LLMProfile,
    MessagingConnection,
    MessagingBindingData
} from "../../../api";
import { getToken } from "../../../authConfig";
import { useNotification } from "../../../utill/NotificationProvider";
import { AgentBindingDialog } from "../dialog/AgentBindingDialog";
import { DatabaseBindingDialog, DatabaseBindingInput } from "../dialog/DatabaseBindingDialog";
import { MailBindingDialog, MailBindingInput } from "../dialog/MailBindingDialog";
import { BusinessDocumentBindingDialog } from "../dialog/BusinessDocumentBindingDialog";
import { MessagingBindingDialog } from "../dialog/MessagingBindingDialog";
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
    update_database_binding,
    get_mail_configs,
    get_mail_bindings_by_agent,
    insert_mail_binding,
    update_mail_binding,
    delete_mail_binding_by_id,
    toggle_mail_binding_by_id,
    // ⭐ CHART CAPABILITY
    get_chart_bindings_by_agent,
    insert_chart_binding,
    delete_chart_binding_by_id,
    toggle_chart_binding_by_id,
    update_chart_binding,
    listAvailableMCPServersApi,
    test_db_connection
    ,get_messaging_connections, get_messaging_bindings, save_messaging_binding, delete_messaging_binding,
    get_business_document_connections, get_business_document_bindings,
    save_business_document_binding, delete_business_document_binding
} from "../../../api/api";

const DEFAULT_TOOL_POLICY = {
    max_total_calls: 24,
    max_calls_per_tool: 8,
    max_argument_chars: 20000,
    max_output_chars: 100000,
    max_timeout_seconds: 90,
    blocked_tools: [] as string[],
    blocked_sources: [] as string[]
};

const DEFAULT_AGENT_TOOL_SETTINGS = {
    knowledge_search: "auto" as const,
    external_database: true,
    rest_integrations: true,
    mail: true,
    business_documents: true,
    messaging: true,
    mcp: true,
    mcp_execution: "auto" as const,
    subagents: false,
    mcp_server_ids: [] as string[],
    mcp_tool_allowlists: {} as Record<string, string[]>,
    mcp_timeout_seconds: 60,
    subagent_ids: [] as string[],
    subagent_max_depth: 2,
    tool_policy: { ...DEFAULT_TOOL_POLICY }
};

const DEFAULT_GUARDRAILS = {
    enabled: true,
    max_input_chars: 20000,
    prompt_injection_action: "block" as const,
    sensitive_input_action: "block" as const,
    sensitive_output_action: "redact" as const,
    pii_input_action: "block" as const,
    pii_output_action: "redact" as const,
    content_safety_input_action: "block" as const,
    content_safety_output_action: "block" as const,
    blocked_phrases: [] as string[]
};

const normalizeRuntimeToolName = (value: string) => {
    let normalized = value
        .trim()
        .toLowerCase()
        .replace(/[^\p{L}\p{N}_]/gu, "_")
        .split("_")
        .filter(Boolean)
        .join("_");
    if (!normalized || !/^\p{L}/u.test(normalized)) normalized = `tool_${normalized}`;
    return normalized.slice(0, 64);
};

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
export function AgentManagementPage({ team, onAgentsChanged }: { team: TeamProfile | null; onAgentsChanged?: () => void }) {
    const { instance } = useMsal();
    const [agents, setAgents] = useState<Agent[]>([]);
    const [llmProfiles, setLlmProfiles] = useState<LLMProfile[]>([]);
    const [loading, setLoading] = useState(false);
    const [openDialog, setOpenDialog] = useState(false);
    const [mode, setMode] = useState<AgentDialogMode>("new");
    const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
    const [search, setSearch] = useState("");
    const { showNotification } = useNotification();

    // ✅ ADD
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);

    // confirm delete
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [agentToDelete, setAgentToDelete] = useState<Agent | null>(null);

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

    useEffect(() => {
        configApi()
            .then(appConfig => setLlmProfiles(appConfig.llmProfiles ?? []))
            .catch(error => console.error("load LLM profiles failed", error));
    }, []);

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
                await edit_agent(team._id, agent._id, agent.agent_name, agent.config, agent.prompt, token);
                showNotification("Agent updated successfully", "success");
            }

            const refreshed = await get_agent_by_team(team._id, token);
            setAgents(refreshed ?? []);
            onAgentsChanged?.();
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
            onAgentsChanged?.();
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

    const llmProfilesById = useMemo(() => new Map(llmProfiles.map(profile => [profile.id, profile])), [llmProfiles]);

    const getAgentModelDisplay = (agent: Agent) => {
        const profileId = agent.config.llm_profile_id ?? "system";
        const profile = llmProfilesById.get(profileId);
        if (!profile) {
            return {
                label: profileId === "system" ? "System default" : "Unavailable profile",
                title: profileId === "system" ? "System default model" : "The configured LLM profile is no longer available"
            };
        }
        return {
            label: profile.label || profile.model,
            title: `${profile.model} (${profile.provider})`
        };
    };

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
                        {filteredAgents.map(agent => {
                            const modelDisplay = getAgentModelDisplay(agent);
                            return (
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
                                            <Chip size="small" label={`Model: ${modelDisplay.label}`} title={modelDisplay.title} sx={{ ml: 1 }} />
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
                            );
                        })}
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
                availableAgents={agents}
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
    onSave,
    availableAgents
}: {
    open: boolean;
    mode: AgentDialogMode;
    agent: Agent | null;
    teamId?: string;
    loading: boolean;
    onClose: () => void;
    onSave: (agent: Agent) => void;
    availableAgents: Agent[];
}) {
    const { instance } = useMsal();
    const isViewMode = mode === "view";
    const isSaving = loading;
    const isFieldDisabled = isViewMode || isSaving;
    const isCreate = mode === "new";

    // Tab state — always reset to "info" when dialog opens
    const [activeTab, setActiveTab] = useState<"info" | "integrations">("info");
    const [integrationSection, setIntegrationSection] = useState<"rest" | "database" | "mail" | "documents" | "messaging" | "mcp" | "visualization">("rest");

    useEffect(() => {
        if (open) {
            setActiveTab("info");
            setIntegrationSection("rest");
        }
    }, [open]);

    const [llmProfiles, setLlmProfiles] = useState<LLMProfile[]>([]);
    const [mcpServers, setMcpServers] = useState<ManagedMCPServer[]>([]);

    useEffect(() => {
        if (!open) return;
        configApi()
            .then(appConfig => setLlmProfiles(appConfig.llmProfiles ?? []))
            .catch(error => console.error("load LLM profiles failed", error));
    }, [open]);

    useEffect(() => {
        if (!open) return;
        getToken(instance)
            .then(token => (token && teamId ? listAvailableMCPServersApi(teamId, token, agent?._id) : []))
            .then(setMcpServers)
            .catch(error => console.error("load MCP servers failed", error));
    }, [open, instance, teamId, agent?._id]);

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
        max_tokens: 1024,
        llm_profile_id: "system",
        runtime: "legacy",
        image_input_enabled: false,
        document_attachments_enabled: true,
        tool_settings: { ...DEFAULT_AGENT_TOOL_SETTINGS },
        guardrails: { ...DEFAULT_GUARDRAILS }
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
    const [documentBindings, setDocumentBindings] = useState<BusinessDocumentBindingData[]>([]);
    const [messagingBindings, setMessagingBindings] = useState<MessagingBindingData[]>([]);
    const [chartBindings, setChartBindings] = useState<ChartBindingData[]>([]); // ⭐ CHART CAPABILITY
    const [bindingDialogOpen, setBindingDialogOpen] = useState(false);
    const [databaseBindingDialogOpen, setDatabaseBindingDialogOpen] = useState(false);
    const [selectedDatabaseBinding, setSelectedDatabaseBinding] = useState<DatabaseBindingData | null>(null);
    const [mailBindingDialogOpen, setMailBindingDialogOpen] = useState(false);
    const [documentBindingDialogOpen, setDocumentBindingDialogOpen] = useState(false);
    const [messagingBindingDialogOpen, setMessagingBindingDialogOpen] = useState(false);
    const [selectedMessagingBinding, setSelectedMessagingBinding] = useState<MessagingBindingData | null>(null);
    const [selectedMailBinding, setSelectedMailBinding] = useState<MailBindingData | null>(null);
    const [selectedDocumentBinding, setSelectedDocumentBinding] = useState<BusinessDocumentBindingData | null>(null);
    const [chartBindingDialogOpen, setChartBindingDialogOpen] = useState(false); // ⭐ CHART CAPABILITY
    const [selectedChartBinding, setSelectedChartBinding] = useState<ChartBindingData | null>(null); // ⭐ CHART CAPABILITY
    const [bindingSaving, setBindingSaving] = useState(false);
    const [bindingsLoading, setBindingsLoading] = useState(false);
    const [deletingBindingId, setDeletingBindingId] = useState<string | null>(null);
    const [deletingDatabaseBindingId, setDeletingDatabaseBindingId] = useState<string | null>(null);
    const [testingDatabaseConnectionId, setTestingDatabaseConnectionId] = useState<string | null>(null);
    const [deletingMailBindingId, setDeletingMailBindingId] = useState<string | null>(null);
    const [deletingDocumentBindingId, setDeletingDocumentBindingId] = useState<string | null>(null);
    const [deletingChartBindingId, setDeletingChartBindingId] = useState<string | null>(null); // ⭐ CHART CAPABILITY
    const { showNotification } = useNotification();

    const [integrations, setIntegrations] = useState<Integration[]>([]);
    const [databaseConnections, setDatabaseConnections] = useState<DatabaseConnection[]>([]);
    const [mailConfigs, setMailConfigs] = useState<MailEmailConfig[]>([]);
    const [documentConnections, setDocumentConnections] = useState<BusinessDocumentConnection[]>([]);
    const [messagingConnections, setMessagingConnections] = useState<MessagingConnection[]>([]);

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

    useEffect(() => {
        const loadDocumentConnections = async () => {
            if (open && teamId) {
                try {
                    const token = await getToken(instance);
                    if (!token) return;
                    setDocumentConnections(await get_business_document_connections(teamId, token));
                } catch (error) {
                    console.error("load business document connections failed", error);
                }
            }
        };
        loadDocumentConnections();
    }, [open, teamId, instance]);

    useEffect(() => {
        if (!open || !teamId) return;
        getToken(instance).then(token => token ? get_messaging_connections(teamId, token) : []).then(setMessagingConnections).catch(e => console.error("load messaging connections failed", e));
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
                try {
                    const documentRes = await get_business_document_bindings(agent._id, token);
                    setDocumentBindings(Array.isArray(documentRes) ? documentRes : []);
                } catch (documentError) {
                    console.error("load business document bindings error", documentError);
                    setDocumentBindings([]);
                }
                try {
                    const messageRes = await get_messaging_bindings(agent._id, token);
                    setMessagingBindings(Array.isArray(messageRes) ? messageRes : []);
                } catch (messageErr) {
                    console.error("load messaging bindings error", messageErr);
                    setMessagingBindings([]);
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
            setDocumentBindings([]);
            setMessagingBindings([]);
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
            setConfig({
                ...agent.config,
                llm_profile_id: agent.config.llm_profile_id ?? "system",
                runtime: agent.config.runtime ?? "legacy",
                image_input_enabled: agent.config.image_input_enabled ?? false,
                document_attachments_enabled: agent.config.document_attachments_enabled ?? true,
                tool_settings: {
                    ...DEFAULT_AGENT_TOOL_SETTINGS,
                    ...(agent.config.tool_settings ?? {}),
                    tool_policy: {
                        ...DEFAULT_TOOL_POLICY,
                        ...(agent.config.tool_settings?.tool_policy ?? {})
                    }
                },
                guardrails: { ...DEFAULT_GUARDRAILS, ...(agent.config.guardrails ?? {}) }
            });
            setPrompt(agent.prompt ?? EMPTY_PROMPT); // ✅ FIX
        } else {
            setAgentName("");
            setConfig({
                temperature: 0.2,
                seed: null,
                min_search_score: 0,
                max_search_results: 2,
                max_tokens: 1024,
                llm_profile_id: "system",
                runtime: "legacy",
                image_input_enabled: false,
                document_attachments_enabled: true,
                tool_settings: { ...DEFAULT_AGENT_TOOL_SETTINGS },
                guardrails: { ...DEFAULT_GUARDRAILS }
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
                <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} aria-label="agent dialog tabs">
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
                                    select
                                    label="LLM Profile"
                                    disabled={isFieldDisabled}
                                    value={config.llm_profile_id ?? "system"}
                                    onChange={e => {
                                        const profile = llmProfiles.find(item => item.id === e.target.value);
                                        setConfig({
                                            ...config,
                                            llm_profile_id: e.target.value,
                                            image_input_enabled: profile?.supportsVision ? config.image_input_enabled : false
                                        });
                                    }}
                                    helperText="Provider credentials are managed securely by the system"
                                >
                                    {llmProfiles.map(profile => (
                                        <MenuItem key={profile.id} value={profile.id}>
                                            {profile.label} — {profile.model} ({profile.provider})
                                            {profile.supportsVision ? " · Vision" : ""}
                                            {profile.supportsTools ? " · Tools" : ""}
                                        </MenuItem>
                                    ))}
                                </TextField>
                                <TextField
                                    select
                                    label="Agent Runtime"
                                    disabled={isFieldDisabled}
                                    value={config.runtime ?? "legacy"}
                                    onChange={e => {
                                        const runtime = e.target.value as "legacy" | "langgraph";
                                        setConfig({ ...config, runtime, image_input_enabled: runtime === "langgraph" ? false : config.image_input_enabled });
                                    }}
                                    helperText="LangGraph enables RAG, integrations and MCP as real tools; use Legacy for rollback"
                                >
                                    <MenuItem value="legacy">Legacy</MenuItem>
                                    <MenuItem value="langgraph">LangGraph (Tools / MCP)</MenuItem>
                                </TextField>
                                <Paper variant="outlined" sx={{ p: 2 }}>
                                    <Typography fontWeight={600}>Message attachments</Typography>
                                    <Stack mt={1}>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={config.image_input_enabled === true}
                                                    disabled={
                                                        isFieldDisabled ||
                                                        config.runtime === "langgraph" ||
                                                        !llmProfiles.find(profile => profile.id === (config.llm_profile_id ?? "system"))?.supportsVision
                                                    }
                                                    onChange={event => setConfig({ ...config, image_input_enabled: event.target.checked })}
                                                />
                                            }
                                            label="Enable image input"
                                        />
                                        <Typography variant="caption" color="text.secondary">
                                            Requires a tested Vision-capable LLM profile and the Legacy runtime.
                                        </Typography>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={config.document_attachments_enabled !== false}
                                                    disabled={isFieldDisabled}
                                                    onChange={event => setConfig({ ...config, document_attachments_enabled: event.target.checked })}
                                                />
                                            }
                                            label="Enable document attachments"
                                        />
                                        <Typography variant="caption" color="text.secondary">
                                            Allows private PDF, Office, text, CSV, and Markdown files when attachment storage is configured.
                                        </Typography>
                                    </Stack>
                                </Paper>
                                <Paper variant="outlined" sx={{ p: 2 }}>
                                    <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} spacing={1}>
                                        <Box>
                                            <Typography fontWeight={600}>AI Guardrails</Typography>
                                            <Typography variant="caption" color="text.secondary">
                                                Provider-independent checks applied to both Legacy and LangGraph requests.
                                            </Typography>
                                        </Box>
                                        <FormControlLabel
                                            control={
                                                <Switch
                                                    checked={config.guardrails?.enabled !== false}
                                                    disabled={isFieldDisabled}
                                                    onChange={event =>
                                                        setConfig({
                                                            ...config,
                                                            guardrails: {
                                                                ...DEFAULT_GUARDRAILS,
                                                                ...(config.guardrails ?? {}),
                                                                enabled: event.target.checked
                                                            }
                                                        })
                                                    }
                                                />
                                            }
                                            label={config.guardrails?.enabled === false ? "Disabled" : "Enabled"}
                                        />
                                    </Stack>
                                    <Stack spacing={2} mt={2}>
                                        <TextField
                                            size="small"
                                            type="number"
                                            label="Maximum Input Characters"
                                            disabled={isFieldDisabled || config.guardrails?.enabled === false}
                                            value={config.guardrails?.max_input_chars ?? DEFAULT_GUARDRAILS.max_input_chars}
                                            inputProps={{ min: 256, max: 200000 }}
                                            onChange={event =>
                                                setConfig({
                                                    ...config,
                                                    guardrails: {
                                                        ...DEFAULT_GUARDRAILS,
                                                        ...(config.guardrails ?? {}),
                                                        max_input_chars: Number(event.target.value)
                                                    }
                                                })
                                            }
                                        />
                                        <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                                            <TextField
                                                select
                                                fullWidth
                                                size="small"
                                                label="Prompt Injection"
                                                disabled={isFieldDisabled || config.guardrails?.enabled === false}
                                                value={config.guardrails?.prompt_injection_action ?? "block"}
                                                onChange={event =>
                                                    setConfig({
                                                        ...config,
                                                        guardrails: {
                                                            ...DEFAULT_GUARDRAILS,
                                                            ...(config.guardrails ?? {}),
                                                            prompt_injection_action: event.target.value as "allow" | "warn" | "block"
                                                        }
                                                    })
                                                }
                                            >
                                                <MenuItem value="block">Block</MenuItem>
                                                <MenuItem value="warn">Audit only</MenuItem>
                                                <MenuItem value="allow">Allow</MenuItem>
                                            </TextField>
                                            <TextField
                                                select
                                                fullWidth
                                                size="small"
                                                label="Secrets in Input"
                                                disabled={isFieldDisabled || config.guardrails?.enabled === false}
                                                value={config.guardrails?.sensitive_input_action ?? "block"}
                                                onChange={event =>
                                                    setConfig({
                                                        ...config,
                                                        guardrails: {
                                                            ...DEFAULT_GUARDRAILS,
                                                            ...(config.guardrails ?? {}),
                                                            sensitive_input_action: event.target.value as "allow" | "warn" | "block"
                                                        }
                                                    })
                                                }
                                            >
                                                <MenuItem value="block">Block</MenuItem>
                                                <MenuItem value="warn">Audit only</MenuItem>
                                                <MenuItem value="allow">Allow</MenuItem>
                                            </TextField>
                                            <TextField
                                                select
                                                fullWidth
                                                size="small"
                                                label="Secrets in Output"
                                                disabled={isFieldDisabled || config.guardrails?.enabled === false}
                                                value={config.guardrails?.sensitive_output_action ?? "redact"}
                                                onChange={event =>
                                                    setConfig({
                                                        ...config,
                                                        guardrails: {
                                                            ...DEFAULT_GUARDRAILS,
                                                            ...(config.guardrails ?? {}),
                                                            sensitive_output_action: event.target.value as "allow" | "warn" | "redact" | "block"
                                                        }
                                                    })
                                                }
                                            >
                                                <MenuItem value="redact">Redact</MenuItem>
                                                <MenuItem value="block">Block response</MenuItem>
                                                <MenuItem value="warn">Audit only</MenuItem>
                                                <MenuItem value="allow">Allow</MenuItem>
                                            </TextField>
                                        </Stack>
                                        <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                                            <TextField
                                                select
                                                fullWidth
                                                size="small"
                                                label="PII in Input"
                                                disabled={isFieldDisabled || config.guardrails?.enabled === false}
                                                value={config.guardrails?.pii_input_action ?? "block"}
                                                onChange={event =>
                                                    setConfig({
                                                        ...config,
                                                        guardrails: {
                                                            ...DEFAULT_GUARDRAILS,
                                                            ...(config.guardrails ?? {}),
                                                            pii_input_action: event.target.value as "allow" | "warn" | "block"
                                                        }
                                                    })
                                                }
                                            >
                                                <MenuItem value="block">Block</MenuItem>
                                                <MenuItem value="warn">Audit only</MenuItem>
                                                <MenuItem value="allow">Allow</MenuItem>
                                            </TextField>
                                            <TextField
                                                select
                                                fullWidth
                                                size="small"
                                                label="PII in Output"
                                                disabled={isFieldDisabled || config.guardrails?.enabled === false}
                                                value={config.guardrails?.pii_output_action ?? "redact"}
                                                onChange={event =>
                                                    setConfig({
                                                        ...config,
                                                        guardrails: {
                                                            ...DEFAULT_GUARDRAILS,
                                                            ...(config.guardrails ?? {}),
                                                            pii_output_action: event.target.value as "allow" | "warn" | "redact" | "block"
                                                        }
                                                    })
                                                }
                                            >
                                                <MenuItem value="redact">Redact</MenuItem>
                                                <MenuItem value="block">Block response</MenuItem>
                                                <MenuItem value="warn">Audit only</MenuItem>
                                                <MenuItem value="allow">Allow</MenuItem>
                                            </TextField>
                                            <TextField
                                                select
                                                fullWidth
                                                size="small"
                                                label="Unsafe Content in Input"
                                                disabled={isFieldDisabled || config.guardrails?.enabled === false}
                                                value={config.guardrails?.content_safety_input_action ?? "block"}
                                                onChange={event =>
                                                    setConfig({
                                                        ...config,
                                                        guardrails: {
                                                            ...DEFAULT_GUARDRAILS,
                                                            ...(config.guardrails ?? {}),
                                                            content_safety_input_action: event.target.value as "allow" | "warn" | "block"
                                                        }
                                                    })
                                                }
                                            >
                                                <MenuItem value="block">Block</MenuItem>
                                                <MenuItem value="warn">Audit only</MenuItem>
                                                <MenuItem value="allow">Allow</MenuItem>
                                            </TextField>
                                            <TextField
                                                select
                                                fullWidth
                                                size="small"
                                                label="Unsafe Content in Output"
                                                disabled={isFieldDisabled || config.guardrails?.enabled === false}
                                                value={config.guardrails?.content_safety_output_action ?? "block"}
                                                onChange={event =>
                                                    setConfig({
                                                        ...config,
                                                        guardrails: {
                                                            ...DEFAULT_GUARDRAILS,
                                                            ...(config.guardrails ?? {}),
                                                            content_safety_output_action: event.target.value as "allow" | "warn" | "block"
                                                        }
                                                    })
                                                }
                                            >
                                                <MenuItem value="block">Block response</MenuItem>
                                                <MenuItem value="warn">Audit only</MenuItem>
                                                <MenuItem value="allow">Allow</MenuItem>
                                            </TextField>
                                        </Stack>
                                        <TextField
                                            size="small"
                                            label="Blocked Phrases"
                                            disabled={isFieldDisabled || config.guardrails?.enabled === false}
                                            value={(config.guardrails?.blocked_phrases ?? []).join(", ")}
                                            onChange={event =>
                                                setConfig({
                                                    ...config,
                                                    guardrails: {
                                                        ...DEFAULT_GUARDRAILS,
                                                        ...(config.guardrails ?? {}),
                                                        blocked_phrases: event.target.value
                                                            .split(",")
                                                            .map(value => value.trim())
                                                            .filter(Boolean)
                                                    }
                                                })
                                            }
                                            helperText="Optional literal phrases to block, separated by commas. Matching is case-insensitive."
                                        />
                                        <Alert severity="info">
                                            Guardrail audit events store detector names and counts only—not prompts, secrets, or model output.
                                        </Alert>
                                    </Stack>
                                </Paper>
                                {config.runtime === "langgraph" && (
                                    <Paper variant="outlined" sx={{ p: 2 }}>
                                        <Typography fontWeight={600} mb={2}>
                                            Built-in Tools
                                        </Typography>
                                        <Stack spacing={1}>
                                            <TextField
                                                select
                                                size="small"
                                                label="Knowledge Search (RAG)"
                                                disabled={isFieldDisabled}
                                                value={config.tool_settings?.knowledge_search ?? "auto"}
                                                onChange={e =>
                                                    setConfig({
                                                        ...config,
                                                        tool_settings: {
                                                            ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                            ...(config.tool_settings ?? {}),
                                                            knowledge_search: e.target.value as "auto" | "always" | "disabled"
                                                        }
                                                    })
                                                }
                                                helperText="Auto: model decides, Always: search before every answer, Disabled: tool schema is not sent"
                                            >
                                                <MenuItem value="auto">Auto — model decides</MenuItem>
                                                <MenuItem value="always">Always search — Legacy-like</MenuItem>
                                                <MenuItem value="disabled">Disabled</MenuItem>
                                            </TextField>
                                            {[
                                                ["external_database", "External Database"],
                                                ["rest_integrations", "REST Integrations"],
                                                ["mail", "Mail"],
                                                ["business_documents", "Business Documents"],
                                                ["messaging", "Messaging & Chat"],
                                                ["mcp", "MCP Tools"],
                                                ["subagents", "Sub-agents"]
                                            ].map(([key, label]) => (
                                                <FormControlLabel
                                                    key={key}
                                                    control={
                                                        <Switch
                                                            disabled={isFieldDisabled}
                                                            checked={Boolean(
                                                                config.tool_settings?.[key as "external_database" | "rest_integrations" | "mail" | "business_documents" | "messaging" | "mcp" | "subagents"]
                                                            )}
                                                            onChange={(_, checked) =>
                                                                setConfig({
                                                                    ...config,
                                                                    tool_settings: {
                                                                        ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                                        ...(config.tool_settings ?? {}),
                                                                        [key]: checked
                                                                    }
                                                                })
                                                            }
                                                        />
                                                    }
                                                    label={label}
                                                />
                                            ))}
                                            {config.tool_settings?.subagents && (
                                                <Stack spacing={1}>
                                                    <TextField
                                                        select
                                                        SelectProps={{ multiple: true }}
                                                        size="small"
                                                        label="Allowed Sub-agents"
                                                        disabled={isFieldDisabled}
                                                        value={config.tool_settings.subagent_ids ?? []}
                                                        onChange={event => {
                                                            const value =
                                                                typeof event.target.value === "string" ? event.target.value.split(",") : event.target.value;
                                                            setConfig({
                                                                ...config,
                                                                tool_settings: {
                                                                    ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                                    ...(config.tool_settings ?? {}),
                                                                    subagent_ids: value as string[]
                                                                }
                                                            });
                                                        }}
                                                        helperText="Delegation is limited to selected agents in the same team"
                                                    >
                                                        {availableAgents
                                                            .filter(item => item._id !== agent?._id && item.config.runtime === "langgraph")
                                                            .map(item => (
                                                                <MenuItem key={item._id} value={item._id}>
                                                                    {item.agent_name}
                                                                </MenuItem>
                                                            ))}
                                                    </TextField>
                                                    <TextField
                                                        size="small"
                                                        label="Maximum Delegation Depth"
                                                        type="number"
                                                        disabled={isFieldDisabled}
                                                        value={config.tool_settings.subagent_max_depth ?? 2}
                                                        onChange={event =>
                                                            setConfig({
                                                                ...config,
                                                                tool_settings: {
                                                                    ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                                    ...(config.tool_settings ?? {}),
                                                                    subagent_max_depth: Number(event.target.value)
                                                                }
                                                            })
                                                        }
                                                        inputProps={{ min: 1, max: 5 }}
                                                    />
                                                </Stack>
                                            )}
                                            <Divider />
                                            <Typography variant="subtitle2">Tool Execution Policy</Typography>
                                            <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                                                {[
                                                    ["max_total_calls", "Total Calls", 1, 100],
                                                    ["max_calls_per_tool", "Calls / Tool", 1, 50],
                                                    ["max_timeout_seconds", "Timeout Seconds", 1, 300]
                                                ].map(([field, label, min, max]) => (
                                                    <TextField
                                                        key={field as string}
                                                        size="small"
                                                        type="number"
                                                        label={label as string}
                                                        disabled={isFieldDisabled}
                                                        value={
                                                            (config.tool_settings?.tool_policy as any)?.[field as string] ??
                                                            (DEFAULT_TOOL_POLICY as any)[field as string]
                                                        }
                                                        inputProps={{ min, max }}
                                                        onChange={event =>
                                                            setConfig({
                                                                ...config,
                                                                tool_settings: {
                                                                    ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                                    ...(config.tool_settings ?? {}),
                                                                    tool_policy: {
                                                                        ...DEFAULT_TOOL_POLICY,
                                                                        ...(config.tool_settings?.tool_policy ?? {}),
                                                                        [field as string]: Number(event.target.value)
                                                                    }
                                                                }
                                                            })
                                                        }
                                                    />
                                                ))}
                                            </Stack>
                                            <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                                                {[
                                                    ["max_argument_chars", "Max Argument Characters", 1000, 200000],
                                                    ["max_output_chars", "Max Output Characters", 1000, 1000000]
                                                ].map(([field, label, min, max]) => (
                                                    <TextField
                                                        key={field as string}
                                                        size="small"
                                                        type="number"
                                                        fullWidth
                                                        label={label as string}
                                                        disabled={isFieldDisabled}
                                                        value={
                                                            (config.tool_settings?.tool_policy as any)?.[field as string] ??
                                                            (DEFAULT_TOOL_POLICY as any)[field as string]
                                                        }
                                                        inputProps={{ min, max }}
                                                        onChange={event =>
                                                            setConfig({
                                                                ...config,
                                                                tool_settings: {
                                                                    ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                                    ...(config.tool_settings ?? {}),
                                                                    tool_policy: {
                                                                        ...DEFAULT_TOOL_POLICY,
                                                                        ...(config.tool_settings?.tool_policy ?? {}),
                                                                        [field as string]: Number(event.target.value)
                                                                    }
                                                                }
                                                            })
                                                        }
                                                    />
                                                ))}
                                            </Stack>
                                            <TextField
                                                size="small"
                                                label="Blocked Tool Names"
                                                disabled={isFieldDisabled}
                                                value={(config.tool_settings?.tool_policy?.blocked_tools ?? []).join(", ")}
                                                onChange={event =>
                                                    setConfig({
                                                        ...config,
                                                        tool_settings: {
                                                            ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                            ...(config.tool_settings ?? {}),
                                                            tool_policy: {
                                                                ...DEFAULT_TOOL_POLICY,
                                                                ...(config.tool_settings?.tool_policy ?? {}),
                                                                blocked_tools: event.target.value
                                                                    .split(",")
                                                                    .map(value => value.trim())
                                                                    .filter(Boolean)
                                                            }
                                                        }
                                                    })
                                                }
                                                helperText="Optional exact normalized tool names, separated by commas"
                                            />
                                            <TextField
                                                size="small"
                                                label="Blocked Tool Sources"
                                                disabled={isFieldDisabled}
                                                value={(config.tool_settings?.tool_policy?.blocked_sources ?? []).join(", ")}
                                                onChange={event =>
                                                    setConfig({
                                                        ...config,
                                                        tool_settings: {
                                                            ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                            ...(config.tool_settings ?? {}),
                                                            tool_policy: {
                                                                ...DEFAULT_TOOL_POLICY,
                                                                ...(config.tool_settings?.tool_policy ?? {}),
                                                                blocked_sources: event.target.value
                                                                    .split(",")
                                                                    .map(value => value.trim())
                                                                    .filter(Boolean)
                                                            }
                                                        }
                                                    })
                                                }
                                                helperText="Optional prefixes: rag, mcp, external_api, external_database, subagent, chart"
                                            />
                                        </Stack>
                                    </Paper>
                                )}
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

                {activeTab === "integrations" && !isCreate && (
                    <Paper variant="outlined" sx={{ mb: 3 }}>
                        <Tabs
                            value={integrationSection}
                            onChange={(_, value) => setIntegrationSection(value)}
                            variant="scrollable"
                            scrollButtons="auto"
                            aria-label="agent integration categories"
                        >
                            <Tab label={`REST APIs (${apiBindings.length})`} value="rest" />
                            <Tab label={`Databases (${databaseBindings.length})`} value="database" />
                            <Tab label={`Mail (${mailBindings.length})`} value="mail" />
                            <Tab label={`Documents (${documentBindings.length})`} value="documents" />
                            <Tab label={`Messaging (${messagingBindings.length})`} value="messaging" />
                            <Tab label={`MCP (${config.tool_settings?.mcp_server_ids?.length ?? 0})`} value="mcp" />
                            <Tab label={`Visualization (${chartBindings.length})`} value="visualization" />
                        </Tabs>
                    </Paper>
                )}

                {/* MCP remains a distinct runtime adapter but is managed in the same Integration context. */}
                {activeTab === "integrations" && integrationSection === "mcp" && !isCreate && (
                    <Stack spacing={3}>
                        {config.runtime !== "langgraph" && (
                            <Alert severity="warning">MCP tools require the LangGraph runtime. Change Agent Runtime in Agent Info before use.</Alert>
                        )}
                        {!config.tool_settings?.mcp && (
                            <Alert severity="info">
                                MCP Tools is currently disabled for this agent. Assignments below are saved but no MCP tool will be exposed until it is enabled
                                in Agent Info.
                            </Alert>
                        )}

                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Typography fontWeight={600}>MCP Execution</Typography>
                            <Typography variant="body2" color="text.secondary" mb={2}>
                                Control when this agent invokes MCP and cap the remote call timeout. Global execution limits remain in Agent Info.
                            </Typography>
                            <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                                <TextField
                                    select
                                    fullWidth
                                    label="Invocation Mode"
                                    disabled={isFieldDisabled}
                                    value={config.tool_settings?.mcp_execution ?? "auto"}
                                    onChange={event =>
                                        setConfig({
                                            ...config,
                                            tool_settings: {
                                                ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                ...(config.tool_settings ?? {}),
                                                mcp_execution: event.target.value as "auto" | "required"
                                            }
                                        })
                                    }
                                    helperText="Required is suitable for dedicated agents that must consult MCP before answering"
                                >
                                    <MenuItem value="auto">Auto — call when relevant or when the server is named</MenuItem>
                                    <MenuItem value="required">Required — always call an assigned MCP server first</MenuItem>
                                </TextField>
                                <TextField
                                    fullWidth
                                    type="number"
                                    label="Agent MCP Timeout (seconds)"
                                    disabled={isFieldDisabled}
                                    value={config.tool_settings?.mcp_timeout_seconds ?? 60}
                                    inputProps={{ min: 1, max: 300 }}
                                    onChange={event =>
                                        setConfig({
                                            ...config,
                                            tool_settings: {
                                                ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                ...(config.tool_settings ?? {}),
                                                mcp_timeout_seconds: Number(event.target.value)
                                            }
                                        })
                                    }
                                    helperText="The lower value between this setting and the server timeout is enforced"
                                />
                            </Stack>
                        </Paper>

                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
                                <Box>
                                    <Typography fontWeight={600}>Assigned MCP Servers</Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Select connections and optionally restrict the tools exposed to this agent
                                    </Typography>
                                </Box>
                                <Chip
                                    size="small"
                                    color={(config.tool_settings?.mcp_server_ids?.length ?? 0) > 0 ? "primary" : "default"}
                                    label={`${config.tool_settings?.mcp_server_ids?.length ?? 0} assigned`}
                                />
                            </Stack>

                            {mcpServers.length === 0 ? (
                                <Alert severity="info">No enabled MCP servers are available. Add one from Admin Management → MCP Servers.</Alert>
                            ) : (
                                <Stack spacing={1.5}>
                                    {mcpServers.map(server => {
                                        const assigned = (config.tool_settings?.mcp_server_ids ?? []).includes(server._id);
                                        const agentAllowlist = config.tool_settings?.mcp_tool_allowlists?.[server._id] ?? [];
                                        return (
                                            <Paper key={server._id} variant="outlined" sx={{ p: 2, bgcolor: assigned ? "action.hover" : "background.paper" }}>
                                                <Stack spacing={1.5}>
                                                    <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={2}>
                                                        <Box minWidth={0}>
                                                            <Stack direction="row" spacing={1} alignItems="center">
                                                                <Typography fontWeight={600}>{server.name}</Typography>
                                                                <Chip size="small" variant="outlined" label={server.vendor || "generic"} />
                                                            </Stack>
                                                            <Typography variant="caption" color="text.secondary" noWrap display="block">
                                                                {server.url}
                                                            </Typography>
                                                        </Box>
                                                        <FormControlLabel
                                                            label={assigned ? "Assigned" : "Not assigned"}
                                                            labelPlacement="start"
                                                            control={
                                                                <Switch
                                                                    checked={assigned}
                                                                    disabled={isFieldDisabled}
                                                                    onChange={(_, checked) => {
                                                                        const currentIds = config.tool_settings?.mcp_server_ids ?? [];
                                                                        const nextIds = checked
                                                                            ? [...currentIds.filter(id => id !== server._id), server._id]
                                                                            : currentIds.filter(id => id !== server._id);
                                                                        const nextAllowlists = {
                                                                            ...(config.tool_settings?.mcp_tool_allowlists ?? {})
                                                                        };
                                                                        if (!checked) delete nextAllowlists[server._id];
                                                                        setConfig({
                                                                            ...config,
                                                                            tool_settings: {
                                                                                ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                                                ...(config.tool_settings ?? {}),
                                                                                mcp_server_ids: nextIds,
                                                                                mcp_tool_allowlists: nextAllowlists
                                                                            }
                                                                        });
                                                                    }}
                                                                />
                                                            }
                                                        />
                                                    </Stack>

                                                    {assigned && (
                                                        <>
                                                            {server.allowed_tools.length > 0 && (
                                                                <Box>
                                                                    <Typography variant="caption" color="text.secondary">
                                                                        Admin allowlist
                                                                    </Typography>
                                                                    <Box mt={0.5} display="flex" gap={0.5} flexWrap="wrap">
                                                                        {server.allowed_tools.map(tool => (
                                                                            <Chip key={tool} size="small" label={tool} variant="outlined" />
                                                                        ))}
                                                                    </Box>
                                                                </Box>
                                                            )}
                                                            <TextField
                                                                fullWidth
                                                                size="small"
                                                                label="Agent Tool Allowlist"
                                                                disabled={isFieldDisabled}
                                                                value={agentAllowlist.join(", ")}
                                                                onChange={event => {
                                                                    const tools = event.target.value
                                                                        .split(",")
                                                                        .map(value => value.trim())
                                                                        .filter(Boolean);
                                                                    setConfig({
                                                                        ...config,
                                                                        tool_settings: {
                                                                            ...DEFAULT_AGENT_TOOL_SETTINGS,
                                                                            ...(config.tool_settings ?? {}),
                                                                            mcp_tool_allowlists: {
                                                                                ...(config.tool_settings?.mcp_tool_allowlists ?? {}),
                                                                                [server._id]: tools
                                                                            }
                                                                        }
                                                                    });
                                                                }}
                                                                placeholder="search_logs, search_monitors"
                                                                helperText={
                                                                    server.allowed_tools.length
                                                                        ? "Blank uses the Admin allowlist. Agent tools cannot exceed the Admin allowlist."
                                                                        : "Comma-separated exact tool names; blank exposes all tools discovered from this server."
                                                                }
                                                            />
                                                        </>
                                                    )}
                                                </Stack>
                                            </Paper>
                                        );
                                    })}
                                </Stack>
                            )}
                        </Paper>

                        <Alert severity="info">
                            Server URLs and credentials are read-only here. Administrators manage them centrally in Admin Management → MCP Servers.
                        </Alert>
                    </Stack>
                )}

                {/* ══════════════════════════════════
                    TAB 2 — Integrations
                    Designed to be extensible: add new
                    integration sections here as needed.
                ══════════════════════════════════ */}
                {activeTab === "integrations" && integrationSection !== "mcp" && !isCreate && (
                    <Stack spacing={3}>
                        <Alert severity="info">
                            Integration bindings are saved immediately. Credentials and connection definitions remain centrally managed and are not copied into
                            the Agent configuration.
                        </Alert>

                        {integrationSection === "rest" && !config.tool_settings?.rest_integrations && (
                            <Alert severity="warning">
                                REST Integrations is disabled in Agent Info. Existing bindings remain saved but are not exposed to the Agent runtime.
                            </Alert>
                        )}
                        {integrationSection === "database" && !config.tool_settings?.external_database && (
                            <Alert severity="warning">
                                External Database is disabled in Agent Info. Existing database bindings remain saved but are not exposed to the Agent runtime.
                            </Alert>
                        )}

                        {/* ── External API ── */}
                        {integrationSection === "rest" && (
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
                                                const runtimeToolName = normalizeRuntimeToolName(
                                                    `api_${integration?.name ?? b.integration_id}_${b.endpoint_name}_${String(b._id).slice(0, 8)}`
                                                );

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
                                                            endpoint?.method
                                                                ? {
                                                                      label: endpoint.method === "GET" ? "Read action" : "Write action",
                                                                      color: endpoint.method === "GET" ? ("success" as const) : ("warning" as const)
                                                                  }
                                                                : null,
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
                                                        <Typography variant="caption" color="text.secondary" sx={{ fontFamily: "monospace" }}>
                                                            Runtime tool: {runtimeToolName}
                                                        </Typography>
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
                        )}

                        {/* ── Database Connections ── */}
                        {integrationSection === "database" && (
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Stack direction="row" justifyContent="space-between" alignItems="center">
                                    <Box>
                                        <Typography fontWeight={600}>Database Connections</Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Databases that the agent can use for query generation
                                        </Typography>
                                    </Box>

                                    {!isViewMode && (
                                        <Button
                                            size="small"
                                            onClick={() => {
                                                setSelectedDatabaseBinding(null);
                                                setDatabaseBindingDialogOpen(true);
                                            }}
                                        >
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
                                                const databaseConnection = databaseConnections.find(connection => connection._id === binding.integration_id);
                                                const alias = binding.alias?.trim();
                                                const title = alias || databaseConnection?.name || binding.integration_id;
                                                const subtitle = databaseConnection
                                                    ? `${databaseConnection.db_type} • ${databaseConnection.host}:${databaseConnection.port} • ${databaseConnection.database}`
                                                    : undefined;
                                                const runtimeToolName = normalizeRuntimeToolName(
                                                    `database_${title}_${String(binding._id || binding.integration_id).slice(0, 8)}`
                                                );

                                                return (
                                                    <DatabaseBindingCard
                                                        key={binding._id}
                                                        binding={binding}
                                                        title={title}
                                                        subtitle={subtitle}
                                                        chips={[
                                                            databaseConnection?.db_type ? { label: databaseConnection.db_type } : null,
                                                            databaseConnection?.database ? { label: databaseConnection.database } : null,
                                                            { label: "Read-only", color: "success" as const },
                                                            binding.query_profile?.business_context || binding.query_profile?.allowed_objects?.length
                                                                ? { label: "Query profile configured", color: "success" as const }
                                                                : null
                                                        ]}
                                                        deletingBindingId={deletingDatabaseBindingId}
                                                        isViewMode={isViewMode}
                                                        instance={instance}
                                                        setBindings={setDatabaseBindings}
                                                        setDeletingBindingId={setDeletingDatabaseBindingId}
                                                        showNotification={showNotification}
                                                        onEdit={() => {
                                                            setSelectedDatabaseBinding(binding);
                                                            setDatabaseBindingDialogOpen(true);
                                                        }}
                                                    >
                                                        <Typography variant="caption" color="text.secondary" sx={{ fontFamily: "monospace" }}>
                                                            Runtime tool: {runtimeToolName}
                                                        </Typography>
                                                        {databaseConnection && (
                                                            <Stack spacing={0.5}>
                                                                <Typography variant="caption" color="text.secondary">
                                                                    User: {databaseConnection.username}
                                                                </Typography>
                                                                {binding.query_profile?.allowed_objects?.length ? (
                                                                    <Typography variant="caption" color="text.secondary">
                                                                        Allowed: {binding.query_profile.allowed_objects.join(", ")}
                                                                    </Typography>
                                                                ) : null}
                                                                <Typography variant="caption" color="text.secondary">
                                                                    Runtime actions: schema, query
                                                                    {databaseConnection.db_type !== "mongodb" ? ", chart_aggregate" : ""}
                                                                </Typography>
                                                                {!isViewMode && (
                                                                    <Box mt={0.5}>
                                                                        <Button
                                                                            size="small"
                                                                            variant="outlined"
                                                                            disabled={testingDatabaseConnectionId === databaseConnection._id}
                                                                            startIcon={
                                                                                testingDatabaseConnectionId === databaseConnection._id ? (
                                                                                    <CircularProgress size={14} />
                                                                                ) : undefined
                                                                            }
                                                                            onClick={async () => {
                                                                                try {
                                                                                    setTestingDatabaseConnectionId(databaseConnection._id);
                                                                                    const token = await getToken(instance);
                                                                                    if (!token) return;
                                                                                    const result = await test_db_connection(
                                                                                        { database_id: databaseConnection._id },
                                                                                        token
                                                                                    );
                                                                                    showNotification(result.message || "Connection succeeded", "success");
                                                                                } catch (error) {
                                                                                    showNotification(
                                                                                        error instanceof Error
                                                                                            ? error.message
                                                                                            : "Database connection test failed",
                                                                                        "error"
                                                                                    );
                                                                                } finally {
                                                                                    setTestingDatabaseConnectionId(null);
                                                                                }
                                                                            }}
                                                                        >
                                                                            {testingDatabaseConnectionId === databaseConnection._id
                                                                                ? "Testing..."
                                                                                : "Test Connection"}
                                                                        </Button>
                                                                    </Box>
                                                                )}
                                                            </Stack>
                                                        )}
                                                    </DatabaseBindingCard>
                                                );
                                            })}
                                        </Stack>
                                    </Box>
                                )}
                            </Paper>
                        )}

                        {/* ── Mail Capabilities ── */}
                        {integrationSection === "mail" && (
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Stack direction="row" justifyContent="space-between" alignItems="center">
                                    <Box>
                                        <Typography fontWeight={600}>Mail Capabilities</Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Email accounts the agent can read/search or send mail through
                                        </Typography>
                                    </Box>
                                    {!isViewMode && (
                                        <Button size="small" onClick={() => { setSelectedMailBinding(null); setMailBindingDialogOpen(true); }}>
                                            + Add Mail
                                        </Button>
                                    )}
                                </Stack>

                                {!config.tool_settings?.mail && <Alert severity="warning" sx={{ mt: 2 }}>Mail tools are disabled in Agent Info. Bindings remain saved but are not exposed at runtime.</Alert>}
                                <Alert severity="warning" sx={{ mt: 2 }}>
                                    Sending mail is a write action. Keep only the required account enabled and control automatic execution through the Agent
                                    tool policy.
                                </Alert>

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
                                                const subtitle = cfg ? `${cfg.email_address} — ${cfg.provider}` : undefined;

                                                return (
                                                    <Paper key={binding._id} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                                                        <Stack spacing={1.5}>
                                                            <Stack direction="row" justifyContent="space-between" alignItems="center">
                                                                <Stack direction="row" spacing={1} alignItems="center">
                                                                    {getIntegrationIcon("mail")}
                                                                    <Typography fontWeight={600}>{title}</Typography>
                                                                    <Chip size="small" label="mail" sx={{ ml: 1 }} />
                                                                    <Chip size="small" label={(binding.permissions ?? ["read", "send"]).join(" / ")} color={(binding.permissions ?? []).includes("send") ? "warning" : "success"} variant="outlined" />
                                                                    <Chip size="small" label={binding.is_html ? "HTML" : "Plain text"} variant="outlined" />
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
                                                                                    showNotification(
                                                                                        `Mail binding ${newValue ? "enabled" : "disabled"}`,
                                                                                        "success"
                                                                                    );
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
                                                                            aria-label="Edit mail binding"
                                                                            onClick={() => {
                                                                                setSelectedMailBinding(binding);
                                                                                setMailBindingDialogOpen(true);
                                                                            }}
                                                                        >
                                                                            <EditIcon fontSize="small" />
                                                                        </IconButton>
                                                                    )}
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
                        )}

                        {integrationSection === "documents" && (
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Stack direction="row" justifyContent="space-between" alignItems="center">
                                    <Box>
                                        <Typography fontWeight={600}>Business Documents</Typography>
                                        <Typography variant="body2" color="text.secondary">Microsoft 365 and Google Workspace libraries available to this Agent</Typography>
                                    </Box>
                                    {!isViewMode && <Button size="small" onClick={() => { setSelectedDocumentBinding(null); setDocumentBindingDialogOpen(true); }}>+ Add Documents</Button>}
                                </Stack>
                                {!config.tool_settings?.business_documents && <Alert severity="warning" sx={{ mt: 2 }}>Business Document tools are disabled in Agent Info.</Alert>}
                                {documentBindings.some(binding => binding.permissions.includes("create")) && <Alert severity="warning" sx={{ mt: 2 }}>At least one binding can create cloud documents. The Agent must act only on an explicit user request.</Alert>}
                                <Stack spacing={2} mt={2}>
                                    {documentBindings.length === 0 ? <Typography variant="body2" color="text.secondary">No document libraries linked</Typography> : documentBindings.map(binding => {
                                        const connection = documentConnections.find(item => item._id === binding.connection_id);
                                        return <Paper key={binding._id} variant="outlined" sx={{ p: 2 }}>
                                            <Stack direction="row" justifyContent="space-between" alignItems="center">
                                                <Box>
                                                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                                                        <Typography fontWeight={600}>{connection?.name ?? binding.connection_id}</Typography>
                                                        <Chip size="small" label={connection?.provider === "microsoft365" ? "Microsoft 365" : "Google Workspace"} color="primary" variant="outlined" />
                                                        <Chip size="small" label={binding.permissions.join(" / ")} color={binding.permissions.includes("create") ? "warning" : "success"} variant="outlined" />
                                                    </Stack>
                                                </Box>
                                                {!isViewMode && <Stack direction="row">
                                                    <IconButton size="small" onClick={() => { setSelectedDocumentBinding(binding); setDocumentBindingDialogOpen(true); }}><EditIcon fontSize="small" /></IconButton>
                                                    <IconButton size="small" color="error" disabled={deletingDocumentBindingId === binding._id} onClick={async () => {
                                                        if (!window.confirm("Delete this document binding?")) return;
                                                        try {
                                                            setDeletingDocumentBindingId(binding._id);
                                                            const token = await getToken(instance);
                                                            if (!token) return;
                                                            await delete_business_document_binding(binding._id, token);
                                                            await loadBindings();
                                                        } catch (error) {
                                                            showNotification(error instanceof Error ? error.message : "Delete failed", "error");
                                                        } finally { setDeletingDocumentBindingId(null); }
                                                    }}>{deletingDocumentBindingId === binding._id ? <CircularProgress size={20} /> : <DeleteIcon fontSize="small" />}</IconButton>
                                                </Stack>}
                                            </Stack>
                                        </Paper>;
                                    })}
                                </Stack>
                            </Paper>
                        )}

                        {integrationSection === "messaging" && (
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Stack direction="row" justifyContent="space-between" alignItems="center"><Box><Typography fontWeight={600}>Messaging & Chat</Typography><Typography variant="body2" color="text.secondary">LINE, Slack and Discord destinations the Agent may post to</Typography></Box>{!isViewMode && <Button size="small" onClick={() => { setSelectedMessagingBinding(null); setMessagingBindingDialogOpen(true); }}>+ Add Messaging</Button>}</Stack>
                                {!config.tool_settings?.messaging && <Alert severity="warning" sx={{ mt: 2 }}>Messaging tools are disabled in Agent Info.</Alert>}
                                <Alert severity="warning" sx={{ mt: 2 }}>Posting messages is a write action.</Alert>
                                <Stack spacing={2} mt={2}>{messagingBindings.length === 0 ? <Typography variant="body2" color="text.secondary">No messaging connections linked</Typography> : messagingBindings.map(binding => { const conn = messagingConnections.find(v => v._id === binding.connection_id); return <Paper key={binding._id} variant="outlined" sx={{ p: 2 }}><Stack direction="row" justifyContent="space-between" alignItems="center"><Box><Stack direction="row" spacing={1} alignItems="center"><Typography fontWeight={600}>{conn?.name ?? binding.connection_id}</Typography><Chip size="small" label={conn?.provider ?? "messaging"} color="primary" variant="outlined" /></Stack><Typography variant="body2" color="text.secondary" mt={.5}>Target: {binding.default_target || conn?.public_config.default_target || "Agent supplies at runtime"}</Typography></Box>{!isViewMode && <Box><IconButton size="small" onClick={() => { setSelectedMessagingBinding(binding); setMessagingBindingDialogOpen(true); }}><EditIcon fontSize="small" /></IconButton><IconButton size="small" color="error" onClick={async () => { try { const t = await getToken(instance); if (!t) return; await delete_messaging_binding(binding._id, t); await loadBindings(); } catch (e) { showNotification(e instanceof Error ? e.message : "Delete failed", "error"); } }}><DeleteIcon fontSize="small" /></IconButton></Box>}</Stack></Paper>; })}</Stack>
                            </Paper>
                        )}

                        {/* ⭐ CHART CAPABILITY: Chart Capabilities section */}
                        {integrationSection === "visualization" && (
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

                                <Alert severity="info" sx={{ mt: 2 }}>
                                    Visualization is an output capability. It can render exact numeric results returned by Database, REST, MCP, or Knowledge
                                    tools, but it does not provide source data by itself.
                                </Alert>

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
                                                                                showNotification(
                                                                                    `Chart capability ${newValue ? "enabled" : "disabled"}`,
                                                                                    "success"
                                                                                );
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
                                                                    label={
                                                                        binding.chart_selection_mode === "auto"
                                                                            ? "🤖 Auto — LLM เลือกเอง"
                                                                            : "🎛 Manual — กำหนด type เอง"
                                                                    }
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
                        )}

                        {/* Future: LINE, Google Sheet ฯลฯ เพิ่ม <Paper> block ตรงนี้ */}
                    </Stack>
                )}
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} disabled={isSaving}>
                    Close
                </Button>
                {/* Native bindings persist directly; Agent Info and MCP policy remain part of the Agent config. */}
                {!isViewMode && (activeTab !== "integrations" || integrationSection === "mcp") && (
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
                binding={selectedDatabaseBinding}
                saving={bindingSaving}
                connections={databaseConnections}
                onClose={() => {
                    setDatabaseBindingDialogOpen(false);
                    setSelectedDatabaseBinding(null);
                }}
                onSave={async (binding: DatabaseBindingInput) => {
                    const exists = databaseBindings.some(b => b.integration_id === binding.integration_id && b._id !== selectedDatabaseBinding?._id);
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
                            enabled: binding.enabled,
                            query_profile: binding.query_profile
                        };

                        if (selectedDatabaseBinding) {
                            await update_database_binding({ ...payload, database_binding_id: selectedDatabaseBinding._id }, token);
                        } else {
                            await insert_database_binding(payload, token);
                        }
                        await loadBindings();
                        showNotification(selectedDatabaseBinding ? "Database query profile updated" : "Database binding added successfully", "success");
                        setDatabaseBindingDialogOpen(false);
                        setSelectedDatabaseBinding(null);
                    } catch (err) {
                        console.error("save database binding err", err);
                        showNotification(err instanceof Error ? err.message : "Failed to save database binding", "error");
                    } finally {
                        setBindingSaving(false);
                    }
                }}
            />
            <MessagingBindingDialog
                open={messagingBindingDialogOpen}
                connections={messagingConnections}
                binding={selectedMessagingBinding}
                onClose={() => { setMessagingBindingDialogOpen(false); setSelectedMessagingBinding(null); }}
                onSave={async binding => {
                    try {
                        const token = await getToken(instance); if (!token || !agent?._id) return;
                        await save_messaging_binding({ ...binding, binding_id: selectedMessagingBinding?._id, agent_id: agent._id }, token);
                        await loadBindings(); setMessagingBindingDialogOpen(false); setSelectedMessagingBinding(null);
                        showNotification("Messaging binding saved", "success");
                    } catch (e) { showNotification(e instanceof Error ? e.message : "Save failed", "error"); }
                }}
            />
            <MailBindingDialog
                open={mailBindingDialogOpen}
                saving={bindingSaving}
                mailConfigs={mailConfigs}
                binding={selectedMailBinding}
                onClose={() => { setMailBindingDialogOpen(false); setSelectedMailBinding(null); }}
                onSave={async (binding: MailBindingInput) => {
                    const exists = mailBindings.some(b => b.email_id === binding.email_id && b._id !== selectedMailBinding?._id);
                    if (exists) {
                        showNotification("This mail account is already linked", "warning");
                        return;
                    }
                    try {
                        setBindingSaving(true);
                        const token = await getToken(instance);
                        if (!token || !agent?._id) return;

                        const payload = {
                                agent_id: agent._id,
                                email_id: binding.email_id,
                                is_html: binding.is_html,
                                enabled: binding.enabled,
                                permissions: binding.permissions,
                                allowed_recipient_domains: binding.allowed_recipient_domains,
                                max_recipients: binding.max_recipients,
                                subject: binding.subject,
                                body: binding.body,
                                default_to: binding.default_to,
                                default_cc: binding.default_cc,
                                default_bcc: binding.default_bcc
                            };
                        if (selectedMailBinding) {
                            await update_mail_binding(selectedMailBinding._id, payload, token);
                        } else {
                            await insert_mail_binding(payload, token);
                        }
                        await loadBindings();
                        showNotification(selectedMailBinding ? "Mail binding updated successfully" : "Mail binding added successfully", "success");
                        setMailBindingDialogOpen(false);
                        setSelectedMailBinding(null);
                    } catch (err) {
                        console.error("insert mail binding err", err);
                        showNotification("Failed to add mail binding", "error");
                    } finally {
                        setBindingSaving(false);
                    }
                }}
            />
            <BusinessDocumentBindingDialog
                open={documentBindingDialogOpen}
                saving={bindingSaving}
                connections={documentConnections}
                binding={selectedDocumentBinding}
                onClose={() => { setDocumentBindingDialogOpen(false); setSelectedDocumentBinding(null); }}
                onSave={async binding => {
                    try {
                        setBindingSaving(true);
                        const token = await getToken(instance);
                        if (!token || !agent?._id) return;
                        await save_business_document_binding({
                            ...binding,
                            binding_id: selectedDocumentBinding?._id,
                            agent_id: agent._id
                        }, token);
                        await loadBindings();
                        setDocumentBindingDialogOpen(false);
                        setSelectedDocumentBinding(null);
                        showNotification("Business document binding saved", "success");
                    } catch (error) {
                        showNotification(error instanceof Error ? error.message : "Save failed", "error");
                    } finally { setBindingSaving(false); }
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
                                    chart_selection_mode: binding.chart_selection_mode,
                                    default_chart_type: binding.default_chart_type,
                                    allowed_chart_types: binding.allowed_chart_types,
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
                                    chart_selection_mode: binding.chart_selection_mode,
                                    default_chart_type: binding.default_chart_type,
                                    allowed_chart_types: binding.allowed_chart_types,
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
                        showNotification(err instanceof Error ? err.message : "Failed to save chart capability", "error");
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
    onEdit,
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
    onEdit: () => void;
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
                            <IconButton size="small" onClick={onEdit} title="Edit database query profile">
                                <EditIcon fontSize="small" />
                            </IconButton>
                        )}

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
