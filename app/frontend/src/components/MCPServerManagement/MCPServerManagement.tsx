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
    Divider,
    IconButton,
    ListItemText,
    ListSubheader,
    Menu,
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
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import { useMsal } from "@azure/msal-react";

import { createMCPServerApi, deleteMCPServerApi, listMCPServersApi, testMCPServerApi, updateMCPServerApi } from "../../api/api";
import { ManagedMCPServer, MCPCategory, MCPServerPayload } from "../../api/models";
import { getToken } from "../../authConfig";

const emptyPayload = (): MCPServerPayload => ({
    name: "",
    url: "",
    vendor: "generic",
    category: "custom",
    auth_type: "headers",
    enabled: true,
    allowed_tools: [],
    timeout_seconds: 60
});

const DATADOG_SITES = {
    us1: "https://mcp.datadoghq.com/v1/mcp",
    eu: "https://mcp.datadoghq.eu/v1/mcp"
} as const;

const datadogPayload = (): MCPServerPayload => ({
    name: "Datadog",
    url: DATADOG_SITES.us1,
    vendor: "datadog",
    category: "observability",
    auth_type: "bearer",
    enabled: true,
    allowed_tools: [],
    timeout_seconds: 60
});

type MCPTemplateId = "datadog" | "custom" | "drawio" | "azure";

interface MCPTemplateDefinition {
    id: MCPTemplateId;
    group: "Observability" | "Diagram & Collaboration" | "Cloud & Platform" | "Custom";
    category: MCPCategory;
    name: string;
    description: string;
    available: boolean;
}

interface DiscoveredMCPTool {
    name: string;
    description?: string;
}

const MCP_TEMPLATE_GROUPS: MCPTemplateDefinition["group"][] = ["Observability", "Diagram & Collaboration", "Cloud & Platform", "Custom"];

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
        description: "Diagram creation and editing template",
        available: false
    },
    {
        id: "azure",
        group: "Cloud & Platform",
        category: "cloud_platform",
        name: "Microsoft Azure",
        description: "Azure resource and platform management template",
        available: false
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
    { id: "data_search", label: "Data & Search" },
    { id: "custom", label: "Custom" }
];

const categoryLabel = (category: MCPCategory) => MCP_CATEGORIES.find(item => item.id === category)?.label ?? category;

export function MCPServerManagement() {
    const { instance } = useMsal();
    const [servers, setServers] = useState<ManagedMCPServer[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [testingId, setTestingId] = useState<string | null>(null);
    const [testStatus, setTestStatus] = useState<Record<string, { status: "success" | "error"; tools?: DiscoveredMCPTool[] }>>({});
    const [toolDialogServer, setToolDialogServer] = useState<ManagedMCPServer | null>(null);
    const [toolSearch, setToolSearch] = useState("");
    const [categoryFilter, setCategoryFilter] = useState<"all" | MCPCategory>("all");
    const [editing, setEditing] = useState<ManagedMCPServer | null>(null);
    const [form, setForm] = useState<MCPServerPayload>(emptyPayload());
    const [headersText, setHeadersText] = useState("");
    const [allowedToolsText, setAllowedToolsText] = useState("");
    const [datadogSite, setDatadogSite] = useState<"us1" | "eu" | "custom">("us1");
    const [datadogToolsets, setDatadogToolsets] = useState("core");
    const [datadogToken, setDatadogToken] = useState("");
    const [datadogApiKey, setDatadogApiKey] = useState("");
    const [datadogApplicationKey, setDatadogApplicationKey] = useState("");
    const [dialogOpen, setDialogOpen] = useState(false);
    const [addMenuAnchor, setAddMenuAnchor] = useState<HTMLElement | null>(null);
    const [notice, setNotice] = useState<{ severity: "success" | "error"; text: string } | null>(null);

    const load = async () => {
        setLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            setServers(await listMCPServersApi(token));
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Failed to load MCP servers" });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, [instance]);

    const openCreate = () => {
        setEditing(null);
        setForm(emptyPayload());
        setHeadersText("");
        setAllowedToolsText("");
        setDialogOpen(true);
    };

    const resetDatadogSecrets = () => {
        setDatadogToken("");
        setDatadogApiKey("");
        setDatadogApplicationKey("");
    };

    const openDatadog = () => {
        setEditing(null);
        setForm(datadogPayload());
        setDatadogSite("us1");
        setDatadogToolsets("core");
        resetDatadogSecrets();
        setHeadersText("");
        setAllowedToolsText("");
        setDialogOpen(true);
    };

    const openTemplate = (template: MCPTemplateDefinition) => {
        setAddMenuAnchor(null);
        if (!template.available) return;
        if (template.id === "datadog") openDatadog();
        else if (template.id === "custom") {
            openCreate();
            setForm({ ...emptyPayload(), category: template.category });
        }
    };

    const openEdit = (server: ManagedMCPServer) => {
        setEditing(server);
        setForm({
            name: server.name,
            url: server.url,
            vendor: server.vendor ?? "generic",
            category: server.category ?? (server.vendor === "datadog" ? "observability" : "custom"),
            auth_type: server.auth_type ?? "headers",
            enabled: server.enabled,
            allowed_tools: server.allowed_tools,
            timeout_seconds: server.timeout_seconds
        });
        setHeadersText("");
        const parsedUrl = new URL(server.url);
        setDatadogSite(parsedUrl.hostname === "mcp.datadoghq.com" ? "us1" : parsedUrl.hostname === "mcp.datadoghq.eu" ? "eu" : "custom");
        setDatadogToolsets(parsedUrl.searchParams.get("toolsets") ?? "core");
        resetDatadogSecrets();
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
            } else if (headersText.trim()) {
                const parsed = JSON.parse(headersText);
                if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Headers must be a JSON object");
                headers = Object.fromEntries(Object.entries(parsed).map(([key, value]) => [key, String(value)]));
            }
            const payload: MCPServerPayload = {
                ...form,
                url,
                ...(headers !== undefined ? { headers } : {}),
                allowed_tools: allowedToolsText
                    .split(",")
                    .map(item => item.trim())
                    .filter(Boolean)
            };
            const token = await getToken(instance);
            if (!token) throw new Error("No authentication token");
            if (editing) await updateMCPServerApi(editing._id, payload, token);
            else await createMCPServerApi(payload, token);
            setDialogOpen(false);
            setNotice({ severity: "success", text: `MCP server ${editing ? "updated" : "created"}` });
            await load();
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Failed to save MCP server" });
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
            setNotice({ severity: "success", text: `${server.name}: discovered ${result.tools.length} tool(s)` });
        } catch (error) {
            setTestStatus(previous => ({ ...previous, [server._id]: { status: "error" } }));
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "MCP connection failed" });
        } finally {
            setTestingId(null);
        }
    };

    const filteredServers = categoryFilter === "all" ? servers : servers.filter(server => server.category === categoryFilter);
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
        <Stack spacing={2} sx={{ pt: 1 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                    <Typography variant="h6">MCP Servers</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Manage Streamable HTTP MCP connections. Header values are encrypted and never returned.
                    </Typography>
                </Box>
                <Box>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        endIcon={<KeyboardArrowDownIcon />}
                        onClick={event => setAddMenuAnchor(event.currentTarget)}
                        aria-haspopup="menu"
                        aria-expanded={Boolean(addMenuAnchor)}
                    >
                        Add MCP Server
                    </Button>
                    <Menu
                        anchorEl={addMenuAnchor}
                        open={Boolean(addMenuAnchor)}
                        onClose={() => setAddMenuAnchor(null)}
                        slotProps={{ paper: { sx: { width: 390, maxWidth: "calc(100vw - 32px)", mt: 0.5 } } }}
                    >
                        {MCP_TEMPLATE_GROUPS.map((group, groupIndex) => {
                            const templates = MCP_TEMPLATES.filter(template => template.group === group);
                            return [
                                groupIndex > 0 ? <Divider key={`${group}-divider`} /> : null,
                                <ListSubheader key={`${group}-header`} disableSticky sx={{ lineHeight: "32px", fontWeight: 700 }}>
                                    {group}
                                </ListSubheader>,
                                ...templates.map(template => (
                                    <MenuItem key={template.id} disabled={!template.available} onClick={() => openTemplate(template)} sx={{ py: 1 }}>
                                        <ListItemText
                                            primary={
                                                <Stack direction="row" spacing={1} alignItems="center">
                                                    <Typography variant="body2" fontWeight={600}>
                                                        {template.name}
                                                    </Typography>
                                                    {!template.available && <Chip label="Coming soon" size="small" variant="outlined" />}
                                                </Stack>
                                            }
                                            secondary={template.description}
                                            secondaryTypographyProps={{ variant: "caption", sx: { whiteSpace: "normal" } }}
                                        />
                                    </MenuItem>
                                ))
                            ];
                        })}
                    </Menu>
                </Box>
            </Box>

            <Paper variant="outlined">
                <Tabs
                    value={categoryFilter}
                    onChange={(_, value) => setCategoryFilter(value)}
                    variant="scrollable"
                    scrollButtons="auto"
                    aria-label="MCP server categories"
                >
                    {MCP_CATEGORIES.map(category => {
                        const count = category.id === "all" ? servers.length : servers.filter(server => server.category === category.id).length;
                        return <Tab key={category.id} value={category.id} label={`${category.label} (${count})`} />;
                    })}
                </Tabs>
            </Paper>

            {loading ? (
                <Box textAlign="center" py={6}>
                    <CircularProgress />
                </Box>
            ) : (
                <Stack spacing={1}>
                    {filteredServers.map(server => (
                        <Paper key={server._id} variant="outlined" sx={{ p: 2 }}>
                            <Box display="flex" justifyContent="space-between" alignItems="center" gap={2}>
                                <Box minWidth={0}>
                                    <Stack direction="row" spacing={1} alignItems="center">
                                        <Typography fontWeight={600}>{server.name}</Typography>
                                        {server.vendor === "datadog" && <Chip size="small" color="primary" variant="outlined" label="Datadog" />}
                                        <Chip size="small" variant="outlined" label={categoryLabel(server.category)} />
                                        <Chip size="small" color={server.enabled ? "success" : "default"} label={server.enabled ? "Enabled" : "Disabled"} />
                                        {server.has_headers && <Chip size="small" variant="outlined" label="Headers stored" />}
                                        <Chip size="small" color="primary" variant="outlined" label={`${server.agent_usage_count ?? 0} Agent(s)`} />
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
                            <Typography color="text.secondary">
                                {servers.length ? `No MCP servers in ${categoryLabel(categoryFilter as MCPCategory)}.` : "No managed MCP servers."}
                            </Typography>
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
                        <TextField
                            select
                            label="Category"
                            value={form.category}
                            disabled={form.vendor === "datadog"}
                            onChange={event => setForm({ ...form, category: event.target.value as MCPCategory })}
                            helperText={
                                form.vendor === "datadog" ? "Datadog is categorized as Observability by its template" : "Used to group and filter MCP servers"
                            }
                        >
                            {MCP_CATEGORIES.filter(category => category.id !== "all").map(category => (
                                <MenuItem key={category.id} value={category.id}>
                                    {category.label}
                                </MenuItem>
                            ))}
                        </TextField>
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
                        <TextField
                            label="Streamable HTTP URL"
                            value={form.url}
                            onChange={event => setForm({ ...form, url: event.target.value })}
                            placeholder={form.vendor === "datadog" ? "https://mcp.datadoghq.com/v1/mcp" : "https://mcp.example.com/mcp"}
                            disabled={form.vendor === "datadog" && datadogSite !== "custom"}
                            required
                        />
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
                        <TextField
                            label="Allowed Tools"
                            value={allowedToolsText}
                            onChange={event => setAllowedToolsText(event.target.value)}
                            helperText="Comma-separated allowlist; blank allows all discovered tools"
                        />
                        {form.vendor === "generic" && (
                            <TextField
                                label={editing?.has_headers ? "Replace Headers JSON (blank keeps current)" : "Headers JSON"}
                                value={headersText}
                                onChange={event => setHeadersText(event.target.value)}
                                multiline
                                minRows={3}
                                placeholder='{"Authorization":"Bearer ..."}'
                            />
                        )}
                        <TextField
                            label="Timeout (seconds)"
                            type="number"
                            value={form.timeout_seconds}
                            onChange={event => setForm({ ...form, timeout_seconds: Number(event.target.value) })}
                        />
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
                    <Button variant="contained" onClick={save} disabled={saving || !form.name || !form.url}>
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
