import React, { useEffect, useState } from "react";
import { Box, Typography, Card, CardContent, Stack } from "@mui/material";
import ApiIcon from "@mui/icons-material/Api";
import ChatIcon from "@mui/icons-material/Chat";
import EmailIcon from "@mui/icons-material/Email";
import TableChartIcon from "@mui/icons-material/TableChart";
import StorageIcon from "@mui/icons-material/Storage";

import { ExternalApiListPage } from "./ExternalApiListPage";
import { DatabaseQueryListPage } from "./DatabaseQueryListPage";
import { MailIntegrationListPage } from "./MailIntegrationListPage";
import { TeamProfile } from "../../../api/models";

type ViewMode = "types" | "external_api" | "database" | "mail";

interface Props {
    team: TeamProfile | null;
}

export function IntegrationManagementPage({ team }: Props) {
    const [view, setView] = useState<ViewMode>("types");

    // ✅ reset view ถ้า team เปลี่ยน
    useEffect(() => {
        setView("types");
    }, [team?._id]);

    if (!team) {
        return (
            <Box p={3}>
                <Typography color="text.secondary">No active team selected</Typography>
            </Box>
        );
    }

    if (view === "external_api") {
        return <ExternalApiListPage key={team._id} team={team} onBack={() => setView("types")} />;
    }

    if (view === "database") {
        return <DatabaseQueryListPage key={team._id} team={team} onBack={() => setView("types")} />;
    }

    if (view === "mail") {
        return <MailIntegrationListPage key={team._id} team={team} onBack={() => setView("types")} />;
    }

    // ✅ scalable integration type config
    const integrationTypes = [
        {
            key: "external_api",
            title: "External API",
            description: "Connect REST services",
            icon: <ApiIcon fontSize="large" />,
            enabled: true
        },
        {
            key: "line",
            title: "LINE",
            description: "Connect LINE Bot",
            icon: <ChatIcon fontSize="large" />,
            enabled: false
        },
        {
            key: "google_sheet",
            title: "Google Sheet",
            description: "Connect Google Sheets",
            icon: <TableChartIcon fontSize="large" />,
            enabled: false
        },
        {
            key: "database",
            title: "Database Query",
            description: "Connect database queries",
            icon: <StorageIcon fontSize="large" />,
            enabled: true
        },
        {
            key: "mail",
            title: "Mail",
            description: "Configure SMTP/IMAP email connections",
            icon: <EmailIcon fontSize="large" />,
            enabled: false
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
                Integrations
            </Typography>

            <Typography variant="body2" color="text.secondary" mb={3}>
                Connect external services to this team
            </Typography>

            <Stack spacing={2}>
                {integrationTypes.map(type => (
                    <IntegrationCard
                        key={type.key}
                        icon={type.icon}
                        title={type.title}
                        description={type.description}
                        disabled={!type.enabled}
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
    disabled
}: {
    icon: React.ReactNode;
    title: string;
    description: string;
    onClick?: () => void;
    disabled?: boolean;
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
                    </Box>

                    {/* {!disabled && (
                        <Typography variant="body2" color="primary" fontWeight={500}>
                            Manage →
                        </Typography>
                    )} */}
                </Stack>
            </CardContent>
        </Card>
    );
}
