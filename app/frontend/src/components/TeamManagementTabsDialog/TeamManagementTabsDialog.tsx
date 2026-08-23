import React, { useEffect, useState } from "react";
import { Box, Dialog, DialogTitle, DialogContent, DialogActions, Button, Tabs, Tab, Typography } from "@mui/material";

import { TabPanel } from "./common/TabPanel";
import { TeamUserManagementPage } from "./Tabs/TeamUserManagementPage";
import { AgentManagementPage } from "./Tabs/AgentManagementPage";
import { DataGroupManagementPage } from "./Tabs/DataGroupManagementPage";
import { RBACManagementPage } from "./Tabs/RBACManagementPage";
import { ManageUserTabs } from "./Tabs/ManageUserTabs";
import { hasPermission } from "../../utill/hasPermission";
import { TeamProfile } from "../../api/models";
import { IntegrationManagementPage } from "./Tabs/IntegrationManagementPage";
import { LLMProviderManagement } from "../LLMProviderManagement";
import { MCPServerManagement } from "../MCPServerManagement";
import { AgentAuditManagement } from "../AgentAuditManagement";

interface Props {
    open: boolean;
    teamName: string;
    onClose: () => void;
    is_sys_admin: boolean;
    sys_permissions: string[] | null;
    selectTeamData: TeamProfile | null;
    onAgentsChanged?: () => void;
}

export function TeamManagementTabsDialog({ open, teamName, onClose, is_sys_admin, selectTeamData, sys_permissions, onAgentsChanged }: Props) {
    const [tab, setTab] = useState(0);

    const tabs = [
        {
            label: "Members",
            permission: ["Manage team users"],
            element: <TeamUserManagementPage team={selectTeamData} />
        },
        {
            label: "Data access",
            permission: ["Manage team data groups"],
            element: <DataGroupManagementPage team={selectTeamData} />
        },
        {
            label: "Roles & permissions",
            permission: ["Manage team permissions"],
            element: <RBACManagementPage team={selectTeamData} />
        },
        {
            label: "Agents",
            permission: ["Manage agents"],
            element: <AgentManagementPage onAgentsChanged={onAgentsChanged} />
        },
        {
            label: "Integrations",
            permission: ["Manage integrations"],
            element: <IntegrationManagementPage team={selectTeamData} isSystemAdmin={is_sys_admin} />
        },
        {
            label: "User directory",
            permission: ["Manage users", "Manage teams"],
            element: <ManageUserTabs />
        },
        {
            label: "LLM Providers",
            permission: ["Manage users", "Manage teams"],
            systemAdminOnly: true,
            element: <LLMProviderManagement />
        },
        {
            label: "MCP Servers",
            permission: ["Manage users", "Manage teams"],
            systemAdminOnly: true,
            element: <MCPServerManagement />
        },
        {
            label: "Agent Audit",
            permission: ["Manage users", "Manage teams"],
            systemAdminOnly: true,
            element: <AgentAuditManagement />
        }
    ];

    const allowedTabs = tabs.filter(
        t =>
            (!("systemAdminOnly" in t) || !t.systemAdminOnly || is_sys_admin) &&
            hasPermission({
                is_sys_admin,
                permissions: selectTeamData?.permissions ?? [],
                sys_permissions: sys_permissions ?? [],
                requiredPermissions: t.permission
            })
    );

    useEffect(() => {
        if (tab >= allowedTabs.length) {
            setTab(0);
        }
    }, [allowedTabs.length, tab]);

    return (
        <Dialog open={open} onClose={onClose} maxWidth="xl" fullWidth>
            <DialogTitle>
                <Box>
                    <Typography variant="h6">Team settings · {teamName}</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Manage membership, document access, roles, agents, and integrations for this team.
                    </Typography>
                </Box>
            </DialogTitle>
            <Tabs
                value={tab}
                onChange={(_, v) => setTab(v)}
                variant="scrollable"
                scrollButtons="auto"
                allowScrollButtonsMobile
                sx={{ px: 2, borderBottom: 1, borderColor: "divider" }}
            >
                {allowedTabs.map(t => (
                    <Tab key={t.label} label={t.label} />
                ))}
            </Tabs>

            <DialogContent dividers sx={{ height: "70vh", p: 0, overflow: "hidden" }}>
                {allowedTabs.map((t, i) => (
                    <TabPanel key={t.label} value={tab} index={i}>
                        {t.element}
                    </TabPanel>
                ))}
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
}
