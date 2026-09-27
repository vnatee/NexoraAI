import React, { useEffect, useState } from "react";
import { Alert, Box, Typography, Card, CardContent, Stack, Chip, CircularProgress, IconButton, InputAdornment, Menu, MenuItem, Tab, Tabs, TextField } from "@mui/material";
import ApiIcon from "@mui/icons-material/Api";
import ChatIcon from "@mui/icons-material/Chat";
import EmailIcon from "@mui/icons-material/Email";
import TableChartIcon from "@mui/icons-material/TableChart";
import StorageIcon from "@mui/icons-material/Storage";
import DocumentScannerIcon from "@mui/icons-material/DocumentScanner";
import HubOutlinedIcon from "@mui/icons-material/HubOutlined";
import FolderSharedOutlinedIcon from "@mui/icons-material/FolderSharedOutlined";
import SearchIcon from "@mui/icons-material/Search";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import { useMsal } from "@azure/msal-react";

import { ExternalApiListPage } from "./ExternalApiListPage";
import { DatabaseQueryListPage } from "./DatabaseQueryListPage";
import { MailIntegrationListPage } from "./MailIntegrationListPage";
import { MessagingIntegrationListPage } from "./MessagingIntegrationListPage";
import { DocumentProcessingPage } from "./DocumentProcessingPage";
import { BusinessDocumentsIntegrationPage } from "./BusinessDocumentsIntegrationPage";
import { WebSearchIntegrationPage } from "./WebSearchIntegrationPage";
import { IntegrationConnectionSummary, TeamProfile } from "../../../api/models";
import { listIntegrationConnectionsApi } from "../../../api/api";
import { getToken } from "../../../authConfig";
import { MCPServerManagement } from "../../MCPServerManagement";

type ViewMode = "types" | "external_api" | "database" | "mail" | "messaging" | "mcp" | "document_processing" | "business_documents" | "web_search";

const connectionView = (kind: IntegrationConnectionSummary["kind"]): ViewMode => (kind === "rest_api" ? "external_api" : kind);

interface Props {
    team: TeamProfile | null;
    isSystemAdmin: boolean;
}

export function IntegrationManagementPage({ team, isSystemAdmin }: Props) {
    const { instance } = useMsal();
    const [view, setView] = useState<ViewMode>("types");
    const [connections, setConnections] = useState<IntegrationConnectionSummary[]>([]);
    const [loadingConnections, setLoadingConnections] = useState(false);
    const [connectionError, setConnectionError] = useState("");
    const [connectionSearch, setConnectionSearch] = useState("");
    const [connectionType, setConnectionType] = useState<"all" | "mcp" | "native">("all");
    const [landingTab, setLandingTab] = useState<"configured" | "catalog">("configured");
    const [catalogSearch, setCatalogSearch] = useState("");
    const [catalogCategory, setCatalogCategory] = useState("All");
    const [catalogMenuAnchor, setCatalogMenuAnchor] = useState<HTMLElement | null>(null);
    const [catalogMenuView, setCatalogMenuView] = useState<ViewMode | null>(null);

    // ✅ reset view ถ้า team เปลี่ยน
    useEffect(() => {
        setView("types");
        setConnectionSearch("");
        setConnectionType("all");
        setLandingTab("configured");
        setCatalogSearch("");
        setCatalogCategory("All");
    }, [team?._id]);

    useEffect(() => {
        if (view !== "types") return;
        let active = true;
        setLoadingConnections(true);
        setConnectionError("");
        getToken(instance)
            .then(token => {
                if (!token) throw new Error("No authentication token");
                return listIntegrationConnectionsApi(team?._id ?? "", token);
            })
            .then(items => active && setConnections(items))
            .catch(error => active && setConnectionError(error instanceof Error ? error.message : "Failed to load connections"))
            .finally(() => active && setLoadingConnections(false));
        return () => {
            active = false;
        };
    }, [instance, team?._id, view]);

    if (view === "external_api") {
        return <ExternalApiListPage key={team?._id || "unassigned"} team={team} onBack={() => setView("types")} />;
    }

    if (view === "database") {
        return <DatabaseQueryListPage key={team?._id || "unassigned"} team={team} onBack={() => setView("types")} />;
    }

    if (view === "mail") {
        return <MailIntegrationListPage key={team?._id || "unassigned"} team={team} onBack={() => setView("types")} />;
    }
    if (view === "messaging") return <MessagingIntegrationListPage key={team?._id || "unassigned"} team={team} onBack={() => setView("types")} />;
    if (view === "mcp") {
        return (
            <MCPServerManagement
                key={`${team?._id || "unassigned"}:${landingTab}`}
                team={team}
                initialView={landingTab}
                onBack={() => setView("types")}
            />
        );
    }
    if (view === "document_processing") return <DocumentProcessingPage onBack={() => setView("types")} />;
    if (view === "business_documents") return <BusinessDocumentsIntegrationPage key={team?._id || "unassigned"} team={team} onBack={() => setView("types")} />;
    if (view === "web_search") return <WebSearchIntegrationPage key={team?._id || "unassigned"} team={team} onBack={() => setView("types")} />;

    // ✅ scalable integration type config
    const integrationTypes = [
        {
            key: "external_api",
            category: "Developer Tools",
            title: "REST APIs",
            description: "Manage REST connections, authentication and endpoints",
            icon: <ApiIcon fontSize="large" />,
            enabled: true,
            badges: [
                { label: "Native", color: "secondary" as const },
                { label: "Read / Write", color: "warning" as const },
                { label: "Connection catalog", color: "default" as const }
            ]
        },
        {
            key: "database",
            category: "Data",
            title: "Databases",
            description: "Manage read-only database connections used by Agent query tools",
            icon: <StorageIcon fontSize="large" />,
            enabled: true,
            badges: [
                { label: "Native", color: "secondary" as const },
                { label: "Read-only", color: "success" as const },
                { label: "Connection catalog", color: "default" as const }
            ]
        },
        {
            key: "web_search",
            category: "Data & Search",
            title: "Web Search",
            description: "Connect Brave Search or SearXNG for governed, domain-restricted Agent research",
            icon: <SearchIcon fontSize="large" />,
            enabled: true,
            badges: [
                { label: "Native", color: "secondary" as const },
                { label: "Read-only", color: "success" as const },
                { label: "Governed", color: "info" as const }
            ]
        },
        {
            key: "business_documents",
            category: "Productivity",
            title: "Business Documents",
            description: "Connect Microsoft 365 and Google Workspace documents for Agent search, reading and controlled creation",
            icon: <FolderSharedOutlinedIcon fontSize="large" />,
            enabled: true,
            badges: [
                { label: "Native", color: "secondary" as const },
                { label: "Microsoft 365", color: "primary" as const },
                { label: "Google Workspace", color: "success" as const },
                { label: "Read / Create", color: "warning" as const }
            ]
        },
        {
            key: "mail",
            category: "Productivity",
            title: "Mail",
            description: "Manage Microsoft 365, Gmail and IMAP/POP3 + SMTP connections",
            icon: <EmailIcon fontSize="large" />,
            enabled: true,
            badges: [
                { label: "Native", color: "secondary" as const },
                { label: "Read / Write", color: "warning" as const },
                { label: "Connection catalog", color: "default" as const }
            ]
        },
        {
            key: "mcp",
            category: "Tool Providers",
            title: "Remote Tool Providers",
            description: "Connect Datadog, Azure, Draw.io, Atlassian, ServiceNow and other MCP providers",
            icon: <HubOutlinedIcon fontSize="large" />,
            enabled: true,
            badges: [
                { label: "MCP", color: "primary" as const },
                { label: "Hosted / Managed", color: "default" as const }
            ]
        },
        {
            key: "document_processing",
            category: "AI & Documents",
            title: "Document Processing & OCR",
            description: "Manage Azure and local extraction providers used by RAG ingestion",
            icon: <DocumentScannerIcon fontSize="large" />,
            enabled: true,
            systemAdminOnly: true,
            badges: [
                { label: "Azure DI", color: "primary" as const },
                { label: "Docling", color: "success" as const },
                { label: "PaddleOCR", color: "info" as const },
                { label: "Google Document AI", color: "warning" as const }
            ]
        },
        {
            key: "visualization",
            category: "Visualization",
            title: "Visualization",
            description: "Chart output capabilities are configured per Agent",
            icon: <TableChartIcon fontSize="large" />,
            enabled: false,
            statusLabel: "Managed per Agent",
            badges: [{ label: "Output capability", color: "info" as const }]
        },
        {
            key: "messaging",
            category: "Communication",
            title: "Messaging & Chat",
            description: "Manage LINE, Slack and Discord messaging channels",
            icon: <ChatIcon fontSize="large" />,
            enabled: true,
            badges: [
                { label: "Native", color: "secondary" as const },
                { label: "LINE", color: "success" as const },
                { label: "Slack", color: "primary" as const },
                { label: "Discord", color: "info" as const }
            ]
        },
    ];

    const normalizedSearch = connectionSearch.trim().toLocaleLowerCase();
    const visibleConnections = connections.filter(connection => {
        if (connectionType !== "all" && connection.connection_type !== connectionType) return false;
        return (
            !normalizedSearch ||
            connection.name.toLocaleLowerCase().includes(normalizedSearch) ||
            connection.provider.toLocaleLowerCase().includes(normalizedSearch) ||
            connection.detail.toLocaleLowerCase().includes(normalizedSearch)
        );
    });
    const availableIntegrationTypes = integrationTypes.filter(type => !type.systemAdminOnly || isSystemAdmin);
    const catalogCategories = ["All", ...Array.from(new Set(availableIntegrationTypes.map(type => type.category)))];
    const normalizedCatalogSearch = catalogSearch.trim().toLocaleLowerCase();
    const visibleIntegrationTypes = availableIntegrationTypes.filter(type =>
        (catalogCategory === "All" || type.category === catalogCategory) &&
        (!normalizedCatalogSearch || `${type.title} ${type.description} ${type.category}`.toLocaleLowerCase().includes(normalizedCatalogSearch))
    );

    return (
        <Box
            p={3}
            sx={{
                height: "100%",
                overflowY: "auto"
            }}
        >
            <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "center" }} gap={1} mb={1}>
                <Box>
                    <Typography variant="h6">Integrations</Typography>
                    <Typography variant="body2" color="text.secondary">
                        {team
                            ? `Team scope · ${team.name}. Connections and assignments here apply only to this team.`
                            : "System scope · Unassigned connections cannot be used by Agents until assigned to a team."}
                    </Typography>
                </Box>
                <Chip
                    color={team ? "primary" : "default"}
                    variant={team ? "filled" : "outlined"}
                    label={team ? `Team · ${team.name}` : "System · Unassigned"}
                />
            </Stack>

            <Tabs
                value={landingTab}
                onChange={(_, value) => setLandingTab(value)}
                sx={{ borderBottom: 1, borderColor: "divider", mb: 3 }}
                aria-label="integration catalog views"
            >
                <Tab value="configured" label={`Configured connections (${connections.length})`} />
                <Tab value="catalog" label="Browse catalog" />
            </Tabs>

            {landingTab === "configured" ? (
                <>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} mb={2}>
                        <TextField
                            fullWidth
                            size="small"
                            placeholder="Search connections"
                            value={connectionSearch}
                            onChange={event => setConnectionSearch(event.target.value)}
                            InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon /></InputAdornment> }}
                        />
                        <TextField
                            select
                            size="small"
                            label="Connection type"
                            value={connectionType}
                            onChange={event => setConnectionType(event.target.value as "all" | "mcp" | "native")}
                            sx={{ minWidth: 190 }}
                        >
                            <MenuItem value="all">All</MenuItem>
                            <MenuItem value="mcp">MCP</MenuItem>
                            <MenuItem value="native">Native</MenuItem>
                        </TextField>
                    </Stack>

                    {connectionError && <Alert severity="error" sx={{ mb: 2 }}>{connectionError}</Alert>}
                    {loadingConnections ? (
                        <Box display="flex" justifyContent="center" py={3}><CircularProgress size={28} /></Box>
                    ) : (
                        <Stack spacing={1.25}>
                            {visibleConnections.map(connection => (
                                <ConnectionCard
                                    key={`${connection.kind}:${connection.id}`}
                                    connection={connection}
                                    onClick={() => setView(connectionView(connection.kind))}
                                />
                            ))}
                            {!visibleConnections.length && (
                                <Card variant="outlined"><CardContent><Typography color="text.secondary">
                                    {connections.length ? "No connections match these filters." : "No connections have been configured yet. Open Browse catalog to add one."}
                                </Typography></CardContent></Card>
                            )}
                        </Stack>
                    )}
                </>
            ) : (
                <>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} mb={2}>
                        <TextField
                            fullWidth
                            size="small"
                            placeholder="Search integrations..."
                            value={catalogSearch}
                            onChange={event => setCatalogSearch(event.target.value)}
                            InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon color="action" /></InputAdornment> }}
                        />
                        <TextField
                            select
                            size="small"
                            label="Category"
                            value={catalogCategory}
                            onChange={event => setCatalogCategory(event.target.value)}
                            sx={{ minWidth: 210 }}
                        >
                            {catalogCategories.map(value => <MenuItem key={value} value={value}>{value}</MenuItem>)}
                        </TextField>
                    </Stack>
                    <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 240px), 1fr))", gap: 2 }}>
                    {visibleIntegrationTypes.map(type => (
                        <IntegrationCard
                            key={type.key}
                            icon={type.icon}
                            title={type.title}
                            description={type.description}
                            category={type.category}
                            disabled={!type.enabled}
                            statusLabel={type.statusLabel}
                            badges={type.badges}
                            onClick={type.enabled ? () => setView(type.key as ViewMode) : undefined}
                            onMenuClick={event => {
                                event.stopPropagation();
                                setCatalogMenuAnchor(event.currentTarget);
                                setCatalogMenuView(type.key as ViewMode);
                            }}
                        />
                    ))}
                    </Box>
                    {!visibleIntegrationTypes.length && <Alert severity="info">No integrations match these filters.</Alert>}
                    <Menu anchorEl={catalogMenuAnchor} open={Boolean(catalogMenuAnchor)} onClose={() => setCatalogMenuAnchor(null)}>
                        <MenuItem
                            disabled={!catalogMenuView || integrationTypes.find(type => type.key === catalogMenuView)?.enabled === false}
                            onClick={() => {
                                if (catalogMenuView) setView(catalogMenuView);
                                setCatalogMenuAnchor(null);
                            }}
                        >
                            Open integration
                        </MenuItem>
                    </Menu>
                </>
            )}
        </Box>
    );
}

function ConnectionCard({ connection, onClick }: { connection: IntegrationConnectionSummary; onClick: () => void }) {
    const statusColor = connection.enabled && !["failed", "cleanup_pending", "stop_pending"].includes(connection.status) ? "success" : "default";
    return (
        <Card variant="outlined" onClick={onClick} sx={{ cursor: "pointer", borderRadius: 2, "&:hover": { boxShadow: 2 } }}>
            <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
                <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ xs: "flex-start", md: "center" }}>
                    <Box flex={1} minWidth={0}>
                        <Typography fontWeight={650}>{connection.name}</Typography>
                        <Typography variant="body2" color="text.secondary" noWrap>{connection.detail || connection.provider}</Typography>
                    </Box>
                    <Chip size="small" label={connection.provider} variant="outlined" />
                    <Chip size="small" label={connection.connection_type === "mcp" ? "MCP" : "Native"} color={connection.connection_type === "mcp" ? "primary" : "secondary"} variant="outlined" />
                    <Chip size="small" label={connection.status} color={statusColor} />
                    <Typography variant="body2" color="text.secondary">{connection.agent_usage_count} Agent(s)</Typography>
                </Stack>
            </CardContent>
        </Card>
    );
}

function IntegrationCard({
    icon,
    title,
    description,
    category,
    onClick,
    onMenuClick,
    disabled,
    statusLabel,
    badges
}: {
    icon: React.ReactNode;
    title: string;
    description: string;
    category: string;
    onClick?: () => void;
    onMenuClick: (event: React.MouseEvent<HTMLElement>) => void;
    disabled?: boolean;
    statusLabel?: string;
    badges?: Array<{ label: string; color: "default" | "primary" | "secondary" | "error" | "info" | "success" | "warning" }>;
}) {
    return (
        <Card
            onClick={disabled ? undefined : onClick}
            role={disabled ? undefined : "button"}
            tabIndex={disabled ? -1 : 0}
            onKeyDown={event => {
                if (!disabled && (event.key === "Enter" || event.key === " ")) onClick?.();
            }}
            sx={{
                cursor: disabled ? "not-allowed" : "pointer",
                opacity: disabled ? 0.5 : 1,
                minHeight: 300,
                position: "relative",
                transition: "transform 150ms ease, box-shadow 150ms ease, border-color 150ms ease",
                borderRadius: 2,
                "&:hover": {
                    transform: disabled ? "none" : "translateY(-2px)",
                    boxShadow: disabled ? undefined : 3,
                    borderColor: disabled ? undefined : "primary.light"
                },
                "&:focus-visible": { outline: "3px solid", outlineColor: "primary.light", outlineOffset: 2 }
            }}
            variant="outlined"
        >
            <CardContent sx={{ height: "100%", minHeight: 300, display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", p: 2 }}>
                <Chip size="small" label={disabled ? statusLabel || "Coming soon" : "Available"} color={disabled ? "default" : "success"} sx={{ position: "absolute", top: 12, left: 12 }} />
                <IconButton size="small" aria-label={`Actions for ${title}`} onClick={onMenuClick} sx={{ position: "absolute", top: 8, right: 8 }}>
                    <MoreHorizIcon />
                </IconButton>
                <Box sx={{ width: 72, height: 72, mt: 3, mb: 2, borderRadius: 2, bgcolor: "primary.50", color: "primary.main", display: "grid", placeItems: "center", boxShadow: 1 }}>
                    {icon}
                </Box>
                <Typography fontWeight={700} sx={{ lineHeight: 1.3, minHeight: 42 }}>{title}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                    {description}
                </Typography>
                <Box sx={{ flex: 1 }} />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 2 }}>{category}</Typography>
                {badges && badges.length > 0 && (
                    <Stack direction="row" spacing={0.5} mt={1} justifyContent="center" flexWrap="wrap" useFlexGap>
                        {badges.slice(0, 2).map(badge => (
                            <Chip key={badge.label} size="small" variant="outlined" label={badge.label} color={badge.color} />
                        ))}
                        {badges.length > 2 && <Chip size="small" variant="outlined" label={`+${badges.length - 2}`} />}
                    </Stack>
                )}
            </CardContent>
        </Card>
    );
}
