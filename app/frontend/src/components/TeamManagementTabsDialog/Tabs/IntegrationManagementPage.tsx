import React, { useEffect, useState } from "react";
import { Box, Typography, Card, CardContent, Stack, Chip } from "@mui/material";
import ApiIcon from "@mui/icons-material/Api";
import ChatIcon from "@mui/icons-material/Chat";
import EmailIcon from "@mui/icons-material/Email";
import TableChartIcon from "@mui/icons-material/TableChart";
import StorageIcon from "@mui/icons-material/Storage";
import DocumentScannerIcon from "@mui/icons-material/DocumentScanner";

import { ExternalApiListPage } from "./ExternalApiListPage";
import { DatabaseQueryListPage } from "./DatabaseQueryListPage";
import { MailIntegrationListPage } from "./MailIntegrationListPage";
import { MessagingIntegrationListPage } from "./MessagingIntegrationListPage";
import { DocumentProcessingPage } from "./DocumentProcessingPage";
import { TeamProfile } from "../../../api/models";

type ViewMode = "types" | "external_api" | "database" | "mail" | "messaging" | "document_processing";

interface Props {
    team: TeamProfile | null;
    isSystemAdmin: boolean;
}

export function IntegrationManagementPage({ team, isSystemAdmin }: Props) {
    const [view, setView] = useState<ViewMode>("types");

    // ✅ reset view ถ้า team เปลี่ยน
    useEffect(() => {
        setView("types");
    }, [team?._id]);

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
    if (view === "document_processing") return <DocumentProcessingPage onBack={() => setView("types")} />;

    // ✅ scalable integration type config
    const integrationTypes = [
        {
            key: "external_api",
            title: "REST APIs",
            description: "Manage REST connections, authentication and endpoints",
            icon: <ApiIcon fontSize="large" />,
            enabled: true,
            badges: [
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
                { label: "Read-only", color: "success" as const },
                { label: "Connection catalog", color: "default" as const }
            ]
        },
        {
            key: "mail",
            title: "Mail",
            description: "Manage Microsoft 365, Gmail and IMAP/POP3 + SMTP connections",
            icon: <EmailIcon fontSize="large" />,
            enabled: true,
            badges: [
                { label: "Read / Write", color: "warning" as const },
                { label: "Connection catalog", color: "default" as const }
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
            badges: [{ label: "LINE", color: "success" as const }, { label: "Slack", color: "primary" as const }, { label: "Discord", color: "info" as const }]
        },
        {
            key: "google_sheet",
            title: "Google Sheet",
            description: "Connect Google Sheets",
            icon: <TableChartIcon fontSize="large" />,
            enabled: false,
            badges: []
        }
    ];

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
