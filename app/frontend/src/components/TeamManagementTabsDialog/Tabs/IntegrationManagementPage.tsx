import React, { useEffect, useState } from "react";
import { Alert, Box, Typography, Card, CardContent, Stack, Chip, CircularProgress, InputAdornment, MenuItem, TextField } from "@mui/material";
import ApiIcon from "@mui/icons-material/Api";
import ChatIcon from "@mui/icons-material/Chat";
import EmailIcon from "@mui/icons-material/Email";
import TableChartIcon from "@mui/icons-material/TableChart";
import StorageIcon from "@mui/icons-material/Storage";
import DocumentScannerIcon from "@mui/icons-material/DocumentScanner";
import HubOutlinedIcon from "@mui/icons-material/HubOutlined";
import FolderSharedOutlinedIcon from "@mui/icons-material/FolderSharedOutlined";
import SearchIcon from "@mui/icons-material/Search";
import { useMsal } from "@azure/msal-react";

import { ExternalApiListPage } from "./ExternalApiListPage";
import { DatabaseQueryListPage } from "./DatabaseQueryListPage";
import { MailIntegrationListPage } from "./MailIntegrationListPage";
import { MessagingIntegrationListPage } from "./MessagingIntegrationListPage";
import { DocumentProcessingPage } from "./DocumentProcessingPage";
import { BusinessDocumentsIntegrationPage } from "./BusinessDocumentsIntegrationPage";
import { IntegrationConnectionSummary, TeamProfile } from "../../../api/models";
import { listIntegrationConnectionsApi } from "../../../api/api";
import { getToken } from "../../../authConfig";
import { MCPServerManagement } from "../../MCPServerManagement";

type ViewMode = "types" | "external_api" | "database" | "mail" | "messaging" | "mcp" | "document_processing" | "business_documents";

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

    // ✅ reset view ถ้า team เปลี่ยน
    useEffect(() => {
        setView("types");
        setConnectionSearch("");
        setConnectionType("all");
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
    if (view === "mcp") return <MCPServerManagement key={team?._id || "unassigned"} team={team} onBack={() => setView("types")} />;
    if (view === "document_processing") return <DocumentProcessingPage onBack={() => setView("types")} />;
    if (view === "business_documents") return <BusinessDocumentsIntegrationPage key={team?._id || "unassigned"} team={team} onBack={() => setView("types")} />;

    // ✅ scalable integration type config
    const integrationTypes = [
        {
            key: "external_api",
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
            key: "business_documents",
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
            title: "Visualization",
            description: "Chart output capabilities are configured per Agent",
            icon: <TableChartIcon fontSize="large" />,
            enabled: false,
            statusLabel: "Managed per Agent",
            badges: [{ label: "Output capability", color: "info" as const }]
        },
        {
            key: "messaging",
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

    return (
        <Box
            p={3}
            sx={{
                height: "100%",
                overflowY: "auto"
            }}
        >
            <Typography variant="h6" mb={1}>
                {team ? `${team.name} integrations` : "Platform integration catalog"}
            </Typography>

            <Typography variant="body2" color="text.secondary" mb={3}>
                {team
                    ? "Manage connections assigned to this team."
                    : "Create and test connections before assigning them to a team. Unassigned connections cannot be used by Agents."}
            </Typography>

            <Typography fontWeight={700} mb={1.5}>
                Connections ({connections.length})
            </Typography>
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
                <Stack spacing={1.25} mb={4}>
                    {visibleConnections.map(connection => (
                        <ConnectionCard
                            key={`${connection.kind}:${connection.id}`}
                            connection={connection}
                            onClick={() => setView(connectionView(connection.kind))}
                        />
                    ))}
                    {!visibleConnections.length && (
                        <Card variant="outlined"><CardContent><Typography color="text.secondary">
                            {connections.length ? "No connections match these filters." : "No connections have been configured yet."}
                        </Typography></CardContent></Card>
                    )}
                </Stack>
            )}

            <Typography fontWeight={700} mb={1.5}>Add integration</Typography>

            <Stack spacing={2}>
                {integrationTypes.filter(type => !("systemAdminOnly" in type) || !type.systemAdminOnly || isSystemAdmin).map(type => (
                    <IntegrationCard
                        key={type.key}
                        icon={type.icon}
                        title={type.title}
                        description={type.description}
                        disabled={!type.enabled}
                        statusLabel={type.statusLabel}
                        badges={type.badges}
                        onClick={type.enabled ? () => setView(type.key as ViewMode) : undefined}
                    />
                ))}
            </Stack>
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
    onClick,
    disabled,
    statusLabel,
    badges
}: {
    icon: React.ReactNode;
    title: string;
    description: string;
    onClick?: () => void;
    disabled?: boolean;
    statusLabel?: string;
    badges?: Array<{ label: string; color: "default" | "primary" | "secondary" | "error" | "info" | "success" | "warning" }>;
}) {
    return (
        <Card
            onClick={disabled ? undefined : onClick}
            sx={{
                cursor: disabled ? "not-allowed" : "pointer",
                opacity: disabled ? 0.5 : 1,
                transition: "0.2s",
                borderRadius: 2,
                "&:hover": {
                    transform: disabled ? "none" : "translateY(-2px)",
                    boxShadow: disabled ? undefined : 4
                }
            }}
        >
            <CardContent>
                <Stack direction="row" spacing={3} alignItems="center">
                    <Box>{icon}</Box>

                    <Box flex={1}>
                        <Typography fontWeight={600}>{title}</Typography>
                        <Typography variant="body2" color="text.secondary">
                            {description}
                        </Typography>
                        {badges && badges.length > 0 && (
                            <Stack direction="row" spacing={0.75} mt={1} flexWrap="wrap" useFlexGap>
                                {badges.map(badge => (
                                    <Chip key={badge.label} size="small" variant="outlined" label={badge.label} color={badge.color} />
                                ))}
                            </Stack>
                        )}
                    </Box>

                    <Chip
                        size="small"
                        label={disabled ? statusLabel || "Coming soon" : "Manage"}
                        color={disabled ? "default" : "primary"}
                        variant={disabled ? "outlined" : "filled"}
                    />
                </Stack>
            </CardContent>
        </Card>
    );
}
