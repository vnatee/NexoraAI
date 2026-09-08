import { useEffect, useState } from "react";
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    InputAdornment,
    MenuItem,
    Paper,
    Snackbar,
    Stack,
    Switch,
    Tab,
    Tabs,
    TextField,
    Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import AppsIcon from "@mui/icons-material/Apps";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DnsOutlinedIcon from "@mui/icons-material/DnsOutlined";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import SearchIcon from "@mui/icons-material/Search";
import { useMsal } from "@azure/msal-react";

import { createMCPServerApi, deleteMCPServerApi, listMCPServersApi, testMCPServerApi, updateMCPServerApi } from "../../api/api";
import { ManagedMCPServer, MCPCategory, MCPServerPayload, TeamProfile } from "../../api/models";
import { getToken } from "../../authConfig";
import { AssignIntegrationTeamButton } from "../TeamManagementTabsDialog/Tabs/AssignIntegrationTeamButton";

const emptyPayload = (teamId = ""): MCPServerPayload => ({
    team_id: teamId,
    name: "",
    url: "",
    vendor: "generic",
    category: "custom",
    auth_type: "headers",
    deployment_mode: "external",
    operation_mode: "read_write",
    enabled: true,
    allowed_tools: [],
    timeout_seconds: 60
});

const DATADOG_SITES = {
    us1: "https://mcp.datadoghq.com/v1/mcp",
    eu: "https://mcp.datadoghq.eu/v1/mcp"
} as const;

const datadogPayload = (teamId = ""): MCPServerPayload => ({
    team_id: teamId,
    name: "Datadog",
    url: DATADOG_SITES.us1,
    vendor: "datadog",
    category: "observability",
    auth_type: "bearer",
    deployment_mode: "external",
    operation_mode: "read_write",
    enabled: true,
    allowed_tools: [],
    timeout_seconds: 60
});

type MCPTemplateId = "datadog" | "custom" | "drawio" | "azure" | "atlassian" | "servicenow";

interface MCPTemplateDefinition {
    id: MCPTemplateId;
    group: "Observability" | "Diagram & Collaboration" | "Cloud & Platform" | "Business Workflows" | "Custom";
    category: MCPCategory;
    name: string;
    description: string;
    available: boolean;
}

interface DiscoveredMCPTool {
    name: string;
    description?: string;
}

const MCP_TEMPLATES: MCPTemplateDefinition[] = [
    {
        id: "datadog",
        group: "Observability",
        category: "observability",
        name: "Datadog",
        description: "Logs, metrics, monitors, incidents and observability",
        available: true
    },
    {
        id: "drawio",
        group: "Diagram & Collaboration",
        category: "diagram_collaboration",
        name: "Draw.io",
        description: "Create diagrams with the official hosted Draw.io MCP server",
        available: true
    },
    {
        id: "azure",
        group: "Cloud & Platform",
        category: "cloud_platform",
        name: "Microsoft Azure",
        description: "Read-only Azure resource inventory for architecture discovery",
        available: true
    },
    {
        id: "atlassian",
        group: "Business Workflows",
        category: "business_workflows",
        name: "Atlassian Jira & Confluence",
        description: "Connect directly to Atlassian's hosted Rovo MCP server",
        available: true
    },
    {
        id: "servicenow",
        group: "Business Workflows",
        category: "business_workflows",
        name: "ServiceNow",
        description: "Connect to the MCP server enabled in your ServiceNow instance",
        available: true
    },
    {
        id: "custom",
        group: "Custom",
        category: "custom",
        name: "Custom Streamable HTTP",
        description: "Connect another MCP server using its URL and headers",
        available: true
    }
];

const MCP_CATEGORIES: Array<{ id: "all" | MCPCategory; label: string }> = [
    { id: "all", label: "All" },
    { id: "observability", label: "Observability" },
    { id: "diagram_collaboration", label: "Diagram & Collaboration" },
    { id: "cloud_platform", label: "Cloud & Platform" },
    { id: "developer_tools", label: "Developer Tools" },
    { id: "business_workflows", label: "Business Workflows" },
    { id: "data_search", label: "Data & Search" },
    { id: "custom", label: "Custom" }
];

const categoryLabel = (category: MCPCategory) => MCP_CATEGORIES.find(item => item.id === category)?.label ?? category;

export function MCPServerManagement({ team = null, onBack }: { team?: TeamProfile | null; onBack?: () => void }) {
    const { instance } = useMsal();
    const teamId = team?._id ?? "";
    const [servers, setServers] = useState<ManagedMCPServer[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [testingId, setTestingId] = useState<string | null>(null);
    const [testStatus, setTestStatus] = useState<Record<string, { status: "success" | "error"; tools?: DiscoveredMCPTool[] }>>({});
    const [toolDialogServer, setToolDialogServer] = useState<ManagedMCPServer | null>(null);
    const [toolSearch, setToolSearch] = useState("");
    const [view, setView] = useState<"configured" | "catalog">("configured");
    const [searchQuery, setSearchQuery] = useState("");
    const [categoryFilter, setCategoryFilter] = useState<"all" | MCPCategory>("all");
    const [statusFilter, setStatusFilter] = useState<"all" | "enabled" | "disabled">("all");
    const [usageFilter, setUsageFilter] = useState<"all" | "in_use" | "not_in_use">("all");
    const [editing, setEditing] = useState<ManagedMCPServer | null>(null);
    const [form, setForm] = useState<MCPServerPayload>(emptyPayload(teamId));
    const [headersText, setHeadersText] = useState("");
    const [allowedToolsText, setAllowedToolsText] = useState("");
    const [datadogSite, setDatadogSite] = useState<"us1" | "eu" | "custom">("us1");
    const [datadogToolsets, setDatadogToolsets] = useState("core");
    const [datadogToken, setDatadogToken] = useState("");
    const [datadogApiKey, setDatadogApiKey] = useState("");
    const [datadogApplicationKey, setDatadogApplicationKey] = useState("");
    const [remoteOAuthToken, setRemoteOAuthToken] = useState("");
    const [entraClientSecret, setEntraClientSecret] = useState("");
    const [azureClientSecret, setAzureClientSecret] = useState("");
    const [azureSubscriptionIdsText, setAzureSubscriptionIdsText] = useState("");
    const [dialogOpen, setDialogOpen] = useState(false);
    const [notice, setNotice] = useState<{ severity: "success" | "warning" | "error"; text: string } | null>(null);

    const load = async () => {
        setLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            setServers(await listMCPServersApi(teamId, token));
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Failed to load MCP servers" });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, [instance, teamId]);

    const openCreate = () => {
        setEditing(null);
        setForm(emptyPayload(teamId));
        setHeadersText("");
        setAllowedToolsText("");
        setEntraClientSecret("");
        setAzureClientSecret("");
        setAzureSubscriptionIdsText("");
        setRemoteOAuthToken("");
        setDialogOpen(true);
    };

    const resetDatadogSecrets = () => {
        setDatadogToken("");
        setDatadogApiKey("");
        setDatadogApplicationKey("");
    };

    const openDatadog = () => {
        setEditing(null);
        setForm(datadogPayload(teamId));
        setDatadogSite("us1");
        setDatadogToolsets("core");
        resetDatadogSecrets();
        setHeadersText("");
        setAllowedToolsText("");
        setDialogOpen(true);
    };

    const openTemplate = (template: MCPTemplateDefinition) => {
        if (!template.available) return;
        if (template.id === "datadog") openDatadog();
        else {
            setEditing(null);
            setForm({
                ...emptyPayload(teamId),
                name: template.id === "custom" ? "" : template.name,
                url:
                    template.id === "drawio"
                        ? "https://mcp.draw.io/mcp"
                        : template.id === "atlassian"
                          ? "https://mcp.atlassian.com/v1/mcp/authv2"
                          : "",
                vendor: template.id === "custom" ? "generic" : template.id,
                category: template.category,
                operation_mode: template.id === "azure" ? "read_only" : "read_write",
                deployment_mode: template.id === "azure" ? "managed" : "external",
                auth_type: template.id === "atlassian" || template.id === "servicenow" ? "bearer" : "headers"
            });
            resetDatadogSecrets();
            setEntraClientSecret("");
            setAzureClientSecret("");
            setAzureSubscriptionIdsText("");
            setRemoteOAuthToken("");
            setHeadersText("");
            setAllowedToolsText("");
            setDialogOpen(true);
        }
    };

    const openEdit = (server: ManagedMCPServer) => {
        setEditing(server);
        setForm({
            team_id: server.team_id,
            name: server.name,
            url: server.url,
            vendor: server.vendor ?? "generic",
            category: server.category ?? (server.vendor === "datadog" ? "observability" : "custom"),
            auth_type: server.auth_type ?? "headers",
            operation_mode: server.operation_mode ?? (server.vendor === "azure" ? "read_only" : "read_write"),
            enabled: server.enabled,
            allowed_tools: server.allowed_tools,
            timeout_seconds: server.timeout_seconds,
            deployment_mode: server.deployment_mode ?? "external",
            entra_tenant_id: server.entra_tenant_id,
            entra_client_id: server.entra_client_id,
            entra_scope: server.entra_scope,
            azure_tenant_id: server.azure_tenant_id ?? server.entra_tenant_id,
            azure_client_id: server.azure_client_id,
            azure_subscription_ids: server.azure_subscription_ids
        });
        setHeadersText("");
        if (server.vendor === "datadog") {
            const parsedUrl = new URL(server.url);
            setDatadogSite(parsedUrl.hostname === "mcp.datadoghq.com" ? "us1" : parsedUrl.hostname === "mcp.datadoghq.eu" ? "eu" : "custom");
            setDatadogToolsets(parsedUrl.searchParams.get("toolsets") ?? "core");
        }
        resetDatadogSecrets();
        setRemoteOAuthToken("");
        setEntraClientSecret("");
        setAzureClientSecret("");
        setAzureSubscriptionIdsText((server.azure_subscription_ids ?? []).join(", "));
        setAllowedToolsText(server.allowed_tools.join(", "));
        setDialogOpen(true);
    };

    const save = async () => {
        setSaving(true);
        try {
            let headers: Record<string, string> | undefined;
            let url = form.url;
            if (form.vendor === "datadog") {
                const parsedUrl = new URL(form.url);
                const toolsets = datadogToolsets
                    .split(",")
                    .map(value => value.trim())
                    .filter(Boolean)
                    .join(",");
                if (toolsets && toolsets !== "core") parsedUrl.searchParams.set("toolsets", toolsets);
                else parsedUrl.searchParams.delete("toolsets");
                url = parsedUrl.toString();
                if (form.auth_type === "bearer" && datadogToken.trim()) {
                    headers = { Authorization: `Bearer ${datadogToken.trim()}` };
                }
                if (form.auth_type === "datadog_keys" && (datadogApiKey.trim() || datadogApplicationKey.trim())) {
                    if (!datadogApiKey.trim() || !datadogApplicationKey.trim()) throw new Error("Both Datadog API Key and Application Key are required");
                    headers = {
                        DD_API_KEY: datadogApiKey.trim(),
                        DD_APPLICATION_KEY: datadogApplicationKey.trim()
                    };
                }
                if (!editing && !headers) throw new Error("Datadog credentials are required");
            } else if (form.vendor === "atlassian" || form.vendor === "servicenow") {
                if (remoteOAuthToken.trim()) headers = { Authorization: `Bearer ${remoteOAuthToken.trim()}` };
                if (!editing && !headers) throw new Error("OAuth access token is required");
            } else if (headersText.trim()) {
                const parsed = JSON.parse(headersText);
                if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Headers must be a JSON object");
                headers = Object.fromEntries(Object.entries(parsed).map(([key, value]) => [key, String(value)]));
            }
            const payload: MCPServerPayload = {
                ...form,
                url,
                ...(headers !== undefined ? { headers } : {}),
                ...(entraClientSecret.trim() ? { entra_client_secret: entraClientSecret.trim() } : {}),
                ...(azureClientSecret.trim() ? { azure_client_secret: azureClientSecret.trim() } : {}),
                azure_subscription_ids: azureSubscriptionIdsText
                    .split(",")
                    .map(item => item.trim())
                    .filter(Boolean),
                allowed_tools: allowedToolsText
                    .split(",")
                    .map(item => item.trim())
                    .filter(Boolean)
            };
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const saved = editing
                ? await updateMCPServerApi(editing._id, payload, token)
                : await createMCPServerApi(payload, token);
            setDialogOpen(false);
            if (!editing) {
                setView("configured");
                setSearchQuery("");
                setCategoryFilter("all");
                setStatusFilter("all");
                setUsageFilter("all");
            }
            setNotice(
                saved.provisioning_status === "failed" || saved.provisioning_status === "stop_pending"
                    ? {
                          severity: "warning",
                          text: "Azure MCP settings saved. Provisioning will retry when the Integration Controller is available."
                      }
                    : { severity: "success", text: `MCP server ${editing ? "updated" : "created"}` }
            );
            await load();
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Failed to save MCP server" });
            await load();
        } finally {
            setSaving(false);
        }
    };

    const test = async (server: ManagedMCPServer) => {
        setTestingId(server._id);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            const result = await testMCPServerApi(server._id, token);
            setTestStatus(previous => ({ ...previous, [server._id]: { status: "success", tools: result.tools } }));
            const filtered = result.blocked_tool_count ?? 0;
            setNotice({
                severity: "success",
                text: `${server.name}: ${result.tools.length} usable tool(s)${filtered ? `, ${filtered} blocked by read-only policy` : ""}`
            });
        } catch (error) {
            setTestStatus(previous => ({ ...previous, [server._id]: { status: "error" } }));
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "MCP connection failed" });
        } finally {
            setTestingId(null);
        }
    };

    const normalizedSearch = searchQuery.trim().toLocaleLowerCase();
    const filteredServers = servers.filter(server => {
        if (categoryFilter !== "all" && server.category !== categoryFilter) return false;
        if (statusFilter === "enabled" && !server.enabled) return false;
        if (statusFilter === "disabled" && server.enabled) return false;
        if (usageFilter === "in_use" && !(server.agent_usage_count ?? 0)) return false;
        if (usageFilter === "not_in_use" && (server.agent_usage_count ?? 0) > 0) return false;
        return (
            !normalizedSearch ||
            server.name.toLocaleLowerCase().includes(normalizedSearch) ||
            server.url.toLocaleLowerCase().includes(normalizedSearch) ||
            categoryLabel(server.category).toLocaleLowerCase().includes(normalizedSearch)
        );
    });
    const filteredTemplates = MCP_TEMPLATES.filter(template => {
        if (categoryFilter !== "all" && template.category !== categoryFilter) return false;
        return (
            !normalizedSearch ||
            template.name.toLocaleLowerCase().includes(normalizedSearch) ||
            template.description.toLocaleLowerCase().includes(normalizedSearch) ||
            template.group.toLocaleLowerCase().includes(normalizedSearch)
        );
    });
    const discoveredTools = toolDialogServer ? testStatus[toolDialogServer._id]?.tools ?? [] : [];
    const visibleTools = discoveredTools.filter(tool => {
        const query = toolSearch.trim().toLocaleLowerCase();
        return !query || tool.name.toLocaleLowerCase().includes(query) || (tool.description ?? "").toLocaleLowerCase().includes(query);
    });

    const remove = async (server: ManagedMCPServer) => {
        if (!window.confirm(`Remove MCP server ${server.name}?`)) return;
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            await deleteMCPServerApi(server._id, token);
            await load();
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Failed to remove MCP server" });
        }
    };

    return (
        <Stack spacing={2} sx={{ p: 3, height: "100%", overflowY: "auto", boxSizing: "border-box" }}>
            <Box display="flex" justifyContent="space-between" alignItems={{ xs: "flex-start", md: "center" }} gap={2} flexWrap="wrap">
                <Stack direction="row" spacing={1.5} alignItems="flex-start">
                    {onBack && <IconButton onClick={onBack} aria-label="Back to integrations"><ArrowBackIcon /></IconButton>}
                    <Box>
                        <Typography variant="h6">MCP Servers</Typography>
                        <Typography variant="body2" color="text.secondary">
                            {team
                                ? `Manage Streamable HTTP MCP connections assigned to ${team.name}.`
                                : "Create Streamable HTTP MCP connections, then assign them to a team."}
                        </Typography>
                    </Box>
                </Stack>
                {view === "configured" && (
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => {
                            setView("catalog");
                            setSearchQuery("");
                            setCategoryFilter("all");
                            setStatusFilter("all");
                            setUsageFilter("all");
                        }}
                    >
                        Add MCP Server
                    </Button>
                )}
            </Box>

            {!team && (
                <Alert severity="info">
                    New connections remain unavailable to Agents until assigned to a team.
                </Alert>
            )}

            <Paper variant="outlined">
                <Tabs
                    value={view}
                    onChange={(_, value) => {
                        setView(value);
                        setSearchQuery("");
                        setCategoryFilter("all");
                        setStatusFilter("all");
                        setUsageFilter("all");
                    }}
                    aria-label="MCP server management views"
                >
                    <Tab value="configured" icon={<DnsOutlinedIcon />} iconPosition="start" label={`Configured Servers (${servers.length})`} />
                    <Tab value="catalog" icon={<AppsIcon />} iconPosition="start" label="Browse Catalog" />
                </Tabs>
            </Paper>

            <Paper variant="outlined" sx={{ p: 2 }}>
                <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                    <TextField
                        fullWidth
                        size="small"
                        value={searchQuery}
                        onChange={event => setSearchQuery(event.target.value)}
                        placeholder={view === "configured" ? "Search servers by name, URL or category" : "Search MCP catalog"}
                        slotProps={{
                            input: {
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <SearchIcon fontSize="small" />
                                    </InputAdornment>
                                )
                            }
                        }}
                    />
                    <TextField
                        select
                        size="small"
                        label="Category"
                        value={categoryFilter}
                        onChange={event => setCategoryFilter(event.target.value as "all" | MCPCategory)}
                        sx={{ minWidth: { md: 220 } }}
                    >
                        {MCP_CATEGORIES.map(category => (
                            <MenuItem key={category.id} value={category.id}>
                                {category.label}
                            </MenuItem>
                        ))}
                    </TextField>
                    {view === "configured" && (
                        <>
                            <TextField
                                select
                                size="small"
                                label="Status"
                                value={statusFilter}
                                onChange={event => setStatusFilter(event.target.value as "all" | "enabled" | "disabled")}
                                sx={{ minWidth: { md: 150 } }}
                            >
                                <MenuItem value="all">All statuses</MenuItem>
                                <MenuItem value="enabled">Enabled</MenuItem>
                                <MenuItem value="disabled">Disabled</MenuItem>
                            </TextField>
                            <TextField
                                select
                                size="small"
                                label="Usage"
                                value={usageFilter}
                                onChange={event => setUsageFilter(event.target.value as "all" | "in_use" | "not_in_use")}
                                sx={{ minWidth: { md: 210 } }}
                            >
                                <MenuItem value="all">All usage</MenuItem>
                                <MenuItem value="in_use">In use by agents</MenuItem>
                                <MenuItem value="not_in_use">Not assigned to agents</MenuItem>
                            </TextField>
                        </>
                    )}
                </Stack>
            </Paper>

            {view === "configured" && loading ? (
                <Box textAlign="center" py={6}>
                    <CircularProgress />
                </Box>
            ) : view === "configured" ? (
                <Stack spacing={1}>
                    {filteredServers.map(server => (
                        <Paper key={server._id} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                            <Box display="flex" justifyContent="space-between" alignItems={{ xs: "flex-start", md: "center" }} gap={2} flexWrap="wrap">
                                <Box minWidth={0}>
                                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                                        <Typography fontWeight={600}>{server.name}</Typography>
                                        {server.vendor === "datadog" && <Chip size="small" color="primary" variant="outlined" label="Datadog" />}
                                        <Chip size="small" variant="outlined" label={categoryLabel(server.category)} />
                                        <Chip size="small" variant="outlined" label={server.operation_mode === "read_only" ? "Read only" : "Read / Write"} />
                                        <Chip size="small" color={server.enabled ? "success" : "default"} label={server.enabled ? "Enabled" : "Disabled"} />
                                        {server.has_headers && <Chip size="small" variant="outlined" label="Headers stored" />}
                                        {server.deployment_mode !== "managed" && server.has_entra_client_secret && <Chip size="small" variant="outlined" label="Entra OAuth" />}
                                        {server.deployment_mode === "managed" && (
                                            <Chip
                                                size="small"
                                                color={server.provisioning_status === "ready" ? "success" : server.provisioning_status === "failed" ? "error" : "warning"}
                                                variant="outlined"
                                                label={`Managed · ${server.provisioning_status ?? "pending"}`}
                                            />
                                        )}
                                        <Chip size="small" color="primary" variant="outlined" label={`${server.agent_usage_count ?? 0} Agent(s)`} />
                                        {!team && <Chip size="small" color="warning" variant="outlined" label="Unassigned" />}
                                        {testStatus[server._id]?.status === "success" && (
                                            <Chip
                                                size="small"
                                                color="success"
                                                clickable
                                                label={`Connected · ${testStatus[server._id].tools?.length ?? 0} tools`}
                                                onClick={() => {
                                                    setToolDialogServer(server);
                                                    setToolSearch("");
                                                }}
                                                aria-label={`View ${testStatus[server._id].tools?.length ?? 0} tools discovered from ${server.name}`}
                                            />
                                        )}
                                        {testStatus[server._id]?.status === "error" && <Chip size="small" color="error" label="Test failed" />}
                                    </Stack>
                                    <Typography variant="body2" color="text.secondary" noWrap>
                                        {server.url}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {server.allowed_tools.length ? `Allowed: ${server.allowed_tools.join(", ")}` : "All discovered tools"}
                                    </Typography>
                                </Box>
                                <Stack direction="row" spacing={0.5}>
                                    {!team && <AssignIntegrationTeamButton integrationId={server._id} integrationType="mcp" onAssigned={load} />}
                                    <Button
                                        size="small"
                                        disabled={testingId === server._id}
                                        startIcon={testingId === server._id ? <CircularProgress size={14} /> : <PlayArrowIcon />}
                                        onClick={() => test(server)}
                                    >
                                        Test
                                    </Button>
                                    <IconButton onClick={() => openEdit(server)}>
                                        <EditIcon />
                                    </IconButton>
                                    <IconButton color="error" onClick={() => remove(server)}>
                                        <DeleteIcon />
                                    </IconButton>
                                </Stack>
                            </Box>
                        </Paper>
                    ))}
                    {!filteredServers.length && (
                        <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
                            <DnsOutlinedIcon sx={{ fontSize: 44, color: "text.disabled", mb: 1 }} />
                            <Typography fontWeight={600}>{servers.length ? "No servers match these filters" : "No configured MCP servers"}</Typography>
                            <Typography variant="body2" color="text.secondary" mt={0.5}>
                                {servers.length ? "Try another search or clear the filters." : "Browse the catalog or add a custom Streamable HTTP server."}
                            </Typography>
                            <Button
                                sx={{ mt: 2 }}
                                onClick={() => {
                                    if (servers.length) {
                                        setSearchQuery("");
                                        setCategoryFilter("all");
                                        setStatusFilter("all");
                                        setUsageFilter("all");
                                    } else setView("catalog");
                                }}
                            >
                                {servers.length ? "Clear filters" : "Browse catalog"}
                            </Button>
                        </Paper>
                    )}
                </Stack>
            ) : (
                <Stack spacing={2}>
                    <Box>
                        <Typography variant="h6">MCP Catalog</Typography>
                        <Typography variant="body2" color="text.secondary">
                            Start from a supported template or connect another Streamable HTTP MCP server.
                        </Typography>
                    </Box>
                    {filteredTemplates.map(template => (
                        <Card
                            key={template.id}
                            variant="outlined"
                            onClick={template.available ? () => openTemplate(template) : undefined}
                            onKeyDown={event => {
                                if (!template.available || (event.key !== "Enter" && event.key !== " ")) return;
                                event.preventDefault();
                                openTemplate(template);
                            }}
                            role={template.available ? "button" : undefined}
                            tabIndex={template.available ? 0 : undefined}
                            aria-disabled={!template.available}
                            sx={{
                                cursor: template.available ? "pointer" : "not-allowed",
                                opacity: template.available ? 1 : 0.58,
                                borderRadius: 2,
                                transition: "transform 0.2s, box-shadow 0.2s",
                                "&:hover": template.available ? { transform: "translateY(-2px)", boxShadow: 3 } : undefined
                            }}
                        >
                            <CardContent>
                                <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ xs: "flex-start", sm: "center" }}>
                                    <Box
                                        sx={{
                                            width: 44,
                                            height: 44,
                                            borderRadius: 2,
                                            bgcolor: "action.hover",
                                            display: "grid",
                                            placeItems: "center",
                                            color: "primary.main"
                                        }}
                                    >
                                        <AppsIcon />
                                    </Box>
                                    <Box flex={1}>
                                        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                                            <Typography fontWeight={700}>{template.name}</Typography>
                                            <Chip size="small" variant="outlined" label={categoryLabel(template.category)} />
                                        </Stack>
                                        <Typography variant="body2" color="text.secondary" mt={0.5}>
                                            {template.description}
                                        </Typography>
                                    </Box>
                                    <Chip
                                        size="small"
                                        label={template.available ? "Add connection" : "Coming soon"}
                                        color={template.available ? "primary" : "default"}
                                        variant={template.available ? "filled" : "outlined"}
                                    />
                                </Stack>
                            </CardContent>
                        </Card>
                    ))}
                    {!filteredTemplates.length && (
                        <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
                            <Typography fontWeight={600}>No catalog items match these filters</Typography>
                            <Button
                                sx={{ mt: 1 }}
                                onClick={() => {
                                    setSearchQuery("");
                                    setCategoryFilter("all");
                                }}
                            >
                                Clear filters
                            </Button>
                        </Paper>
                    )}
                </Stack>
            )}

            <Dialog open={Boolean(toolDialogServer)} onClose={() => setToolDialogServer(null)} fullWidth maxWidth="md">
                <DialogTitle>
                    <Typography variant="h6" component="div">Tools available from {toolDialogServer?.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                        {discoveredTools.length} tool(s) returned by the latest connection test
                    </Typography>
                </DialogTitle>
                <DialogContent dividers>
                    <TextField
                        fullWidth
                        size="small"
                        label="Search tools"
                        placeholder="Search by name or description"
                        value={toolSearch}
                        onChange={event => setToolSearch(event.target.value)}
                        sx={{ mb: 2 }}
                    />
                    <Stack spacing={1}>
                        {visibleTools.map(tool => (
                            <Paper key={tool.name} variant="outlined" sx={{ p: 1.5 }}>
                                <Typography fontWeight={600} sx={{ overflowWrap: "anywhere" }}>{tool.name}</Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, whiteSpace: "pre-wrap" }}>
                                    {tool.description?.trim() || "No description provided by this MCP server."}
                                </Typography>
                            </Paper>
                        ))}
                        {!visibleTools.length && (
                            <Typography color="text.secondary" textAlign="center" py={3}>
                                {discoveredTools.length ? "No tools match this search." : "This server returned no tools."}
                            </Typography>
                        )}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setToolDialogServer(null)}>Close</Button>
                </DialogActions>
            </Dialog>

            <Dialog open={dialogOpen} onClose={() => !saving && setDialogOpen(false)} fullWidth maxWidth="md">
                <DialogTitle>{editing ? "Edit MCP Server" : "Add MCP Server"}</DialogTitle>
                <DialogContent dividers>
                    <Stack spacing={2}>
                        <TextField label="Server Name" value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} required />
                        {form.vendor === "generic" && (
                            <TextField
                                select
                                label="Category"
                                value={form.category}
                                onChange={event => setForm({ ...form, category: event.target.value as MCPCategory })}
                                helperText="Used to group and filter MCP servers"
                            >
                                {MCP_CATEGORIES.filter(category => category.id !== "all").map(category => (
                                    <MenuItem key={category.id} value={category.id}>
                                        {category.label}
                                    </MenuItem>
                                ))}
                            </TextField>
                        )}
                        {form.vendor === "datadog" && (
                            <>
                                <Alert severity="info">
                                    Use a Datadog PAT/SAT where possible. The account requires MCP Read and the underlying product permissions; write tools also
                                    require MCP Write.
                                </Alert>
                                <TextField
                                    select
                                    label="Datadog Site"
                                    value={datadogSite}
                                    onChange={event => {
                                        const site = event.target.value as "us1" | "eu" | "custom";
                                        setDatadogSite(site);
                                        if (site !== "custom") setForm({ ...form, url: DATADOG_SITES[site] });
                                    }}
                                >
                                    <MenuItem value="us1">US1 (datadoghq.com)</MenuItem>
                                    <MenuItem value="eu">EU (datadoghq.eu)</MenuItem>
                                    <MenuItem value="custom">Other official Datadog site</MenuItem>
                                </TextField>
                            </>
                        )}
                        {form.vendor === "azure" && (
                            <>
                                <Alert severity="info">
                                    Managed local mode needs only one Azure Service Principal with Reader access. NexoraAI starts the official MCP container on its private Docker network; no MCP URL or separate OAuth application is required.
                                </Alert>
                                <TextField
                                    select
                                    label="Deployment"
                                    value={form.deployment_mode}
                                    disabled={Boolean(editing)}
                                    onChange={event => {
                                        const mode = event.target.value as "external" | "managed";
                                        setForm({
                                            ...form,
                                            deployment_mode: mode,
                                            auth_type: mode === "managed" ? "headers" : "entra_client_credentials",
                                            url: mode === "managed" ? "" : form.url
                                        });
                                    }}
                                >
                                    <MenuItem value="managed">Managed on-prem container</MenuItem>
                                    <MenuItem value="external">Existing remote Azure MCP server (advanced)</MenuItem>
                                </TextField>
                            </>
                        )}
                        {(form.vendor !== "azure" || form.deployment_mode === "external") && (
                            <TextField
                                label="Streamable HTTP URL"
                                value={form.url}
                                onChange={event => setForm({ ...form, url: event.target.value })}
                                placeholder={
                                    form.vendor === "datadog"
                                        ? "https://mcp.datadoghq.com/v1/mcp"
                                        : form.vendor === "servicenow"
                                          ? "https://your-instance.service-now.com/.../mcp"
                                          : "https://mcp.example.com/mcp"
                                }
                                disabled={form.vendor === "atlassian" || (form.vendor === "datadog" && datadogSite !== "custom")}
                                helperText={
                                    form.vendor === "atlassian"
                                        ? "Official Atlassian hosted endpoint"
                                        : form.vendor === "servicenow"
                                          ? "Copy the Streamable HTTP endpoint configured by your ServiceNow administrator"
                                          : undefined
                                }
                                required
                            />
                        )}
                        {form.vendor === "drawio" && (
                            <Alert severity="info">
                                Use a trusted Draw.io MCP server. Diagram write tools may create or update files, so restrict its storage workspace to this Team.
                            </Alert>
                        )}
                        {form.vendor === "atlassian" && (
                            <Alert severity="info">
                                This connects directly to Atlassian's hosted Rovo MCP server; no local container is created. Use an OAuth 2.1 access token for the Atlassian user whose Jira and Confluence permissions should apply. Atlassian API tokens are not supported.
                            </Alert>
                        )}
                        {form.vendor === "servicenow" && (
                            <Alert severity="info">
                                This connects directly to the MCP endpoint exposed by your ServiceNow instance; no local container is created. A ServiceNow administrator must first activate and configure MCP Server access and OAuth permissions.
                            </Alert>
                        )}
                        {form.vendor === "datadog" && (
                            <>
                                <TextField
                                    label="Datadog Toolsets"
                                    value={datadogToolsets}
                                    onChange={event => setDatadogToolsets(event.target.value)}
                                    helperText="Comma-separated, for example: core,synthetics,software-delivery. Use all carefully because it increases model context."
                                />
                                <TextField
                                    select
                                    label="Authentication"
                                    value={form.auth_type}
                                    onChange={event => setForm({ ...form, auth_type: event.target.value as "bearer" | "datadog_keys" })}
                                >
                                    <MenuItem value="bearer">Personal / Service Access Token (recommended)</MenuItem>
                                    <MenuItem value="datadog_keys">API Key + Application Key</MenuItem>
                                </TextField>
                                {form.auth_type === "bearer" ? (
                                    <TextField
                                        label={editing?.has_headers ? "Replace PAT/SAT (blank keeps current)" : "PAT / SAT"}
                                        type="password"
                                        value={datadogToken}
                                        onChange={event => setDatadogToken(event.target.value)}
                                        autoComplete="new-password"
                                    />
                                ) : (
                                    <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                                        <TextField
                                            fullWidth
                                            label={editing?.has_headers ? "Replace API Key" : "API Key"}
                                            type="password"
                                            value={datadogApiKey}
                                            onChange={event => setDatadogApiKey(event.target.value)}
                                            autoComplete="new-password"
                                        />
                                        <TextField
                                            fullWidth
                                            label={editing?.has_headers ? "Replace Application Key" : "Application Key"}
                                            type="password"
                                            value={datadogApplicationKey}
                                            onChange={event => setDatadogApplicationKey(event.target.value)}
                                            autoComplete="new-password"
                                        />
                                    </Stack>
                                )}
                            </>
                        )}
                        {form.vendor === "azure" && (
                            <>
                                <TextField
                                    label="Azure Tenant ID"
                                    value={form.azure_tenant_id ?? form.entra_tenant_id ?? ""}
                                    onChange={event => setForm({ ...form, azure_tenant_id: event.target.value, entra_tenant_id: event.target.value })}
                                    helperText="Microsoft Entra ID → Overview → Tenant ID"
                                    required
                                />
                                {form.deployment_mode === "managed" && (
                                    <>
                                        <TextField
                                            label="Azure Client ID"
                                            value={form.azure_client_id ?? ""}
                                            onChange={event => setForm({ ...form, azure_client_id: event.target.value })}
                                            helperText="App registration → Overview → Application (client) ID; grant this Service Principal Reader access"
                                            required
                                        />
                                        <TextField
                                            label={editing?.has_azure_client_secret ? "Replace Azure Client Secret (blank keeps current)" : "Azure Client Secret"}
                                            type="password"
                                            value={azureClientSecret}
                                            onChange={event => setAzureClientSecret(event.target.value)}
                                            autoComplete="new-password"
                                            helperText="Use the secret Value, not the Secret ID"
                                            required={!editing?.has_azure_client_secret}
                                        />
                                        <TextField
                                            label="Subscription IDs"
                                            value={azureSubscriptionIdsText}
                                            onChange={event => setAzureSubscriptionIdsText(event.target.value)}
                                            helperText="Comma-separated subscriptions accessible to this Team connection"
                                            required
                                        />
                                    </>
                                )}
                                {form.deployment_mode === "external" && (
                                    <>
                                        <TextField
                                            label="Nexora OAuth Client ID"
                                            value={form.entra_client_id ?? ""}
                                            onChange={event => setForm({ ...form, entra_client_id: event.target.value })}
                                            helperText="Client application granted the remote MCP server's application role"
                                            required
                                        />
                                        <TextField
                                            label={editing?.has_entra_client_secret ? "Replace Nexora OAuth Client Secret (blank keeps current)" : "Nexora OAuth Client Secret"}
                                            type="password"
                                            value={entraClientSecret}
                                            onChange={event => setEntraClientSecret(event.target.value)}
                                            autoComplete="new-password"
                                            required={!editing?.has_entra_client_secret}
                                        />
                                        <TextField
                                            label="OAuth Scope"
                                            value={form.entra_scope ?? ""}
                                            onChange={event => setForm({ ...form, entra_scope: event.target.value })}
                                            placeholder="api://<remote-azure-mcp-app-id>/.default"
                                            required
                                        />
                                    </>
                                )}
                            </>
                        )}
                        {(form.vendor === "atlassian" || form.vendor === "servicenow") && (
                            <TextField
                                label={editing?.has_headers ? "Replace OAuth Access Token (blank keeps current)" : "OAuth Access Token"}
                                type="password"
                                value={remoteOAuthToken}
                                onChange={event => setRemoteOAuthToken(event.target.value)}
                                autoComplete="new-password"
                                required={!editing?.has_headers}
                                helperText={
                                    form.vendor === "atlassian"
                                        ? "OAuth 2.1 bearer token issued for the Atlassian Rovo MCP server"
                                        : "OAuth bearer token issued by this ServiceNow instance"
                                }
                            />
                        )}
                        {!(form.vendor === "azure" && form.deployment_mode === "managed") && (
                            <>
                                <TextField
                                    label="Allowed Tools"
                                    value={allowedToolsText}
                                    onChange={event => setAllowedToolsText(event.target.value)}
                                    helperText="Comma-separated allowlist; blank allows all discovered tools"
                                />
                                <TextField
                                    select
                                    label="Operation Mode"
                                    value={form.operation_mode}
                                    disabled={form.vendor === "azure"}
                                    onChange={event => setForm({ ...form, operation_mode: event.target.value as "read_only" | "read_write" })}
                                    helperText={form.vendor === "azure" ? "Azure inventory is locked to read-only tools" : "Read-only mode filters out tools that are not clearly read operations"}
                                >
                                    <MenuItem value="read_only">Read only</MenuItem>
                                    <MenuItem value="read_write">Read / Write</MenuItem>
                                </TextField>
                            </>
                        )}
                        {form.vendor !== "datadog" && form.vendor !== "azure" && form.vendor !== "atlassian" && form.vendor !== "servicenow" && (
                            <TextField
                                label={editing?.has_headers ? "Replace Headers JSON (blank keeps current)" : "Headers JSON"}
                                value={headersText}
                                onChange={event => setHeadersText(event.target.value)}
                                multiline
                                minRows={3}
                                placeholder='{"Authorization":"Bearer ..."}'
                            />
                        )}
                        {!(form.vendor === "azure" && form.deployment_mode === "managed") && (
                            <TextField
                                label="Timeout (seconds)"
                                type="number"
                                value={form.timeout_seconds}
                                onChange={event => setForm({ ...form, timeout_seconds: Number(event.target.value) })}
                            />
                        )}
                        <Stack direction="row" alignItems="center" spacing={1}>
                            <Switch checked={form.enabled} onChange={event => setForm({ ...form, enabled: event.target.checked })} />
                            <Typography>Enabled</Typography>
                        </Stack>
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDialogOpen(false)} disabled={saving}>
                        Cancel
                    </Button>
                    <Button
                        variant="contained"
                        onClick={save}
                        disabled={saving || !form.name || (form.deployment_mode !== "managed" && !form.url)}
                    >
                        {saving ? "Saving..." : "Save"}
                    </Button>
                </DialogActions>
            </Dialog>

            <Snackbar open={Boolean(notice)} autoHideDuration={5000} onClose={() => setNotice(null)} anchorOrigin={{ vertical: "top", horizontal: "right" }}>
                <Alert severity={notice?.severity ?? "success"} onClose={() => setNotice(null)}>
                    {notice?.text}
                </Alert>
            </Snackbar>
        </Stack>
    );
}
