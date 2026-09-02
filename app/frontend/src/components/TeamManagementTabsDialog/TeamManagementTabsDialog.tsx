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
import { GuardrailPolicyPage } from "./Tabs/GuardrailPolicyPage";

interface Props {
    open: boolean;
    onClose: () => void;
    is_sys_admin: boolean;
    sys_permissions: string[] | null;
    selectTeamData: TeamProfile | null;
    onAgentsChanged?: () => void;
    onTeamChanged?: (team: TeamProfile) => void;
}

export function TeamManagementTabsDialog({ open, onClose, is_sys_admin, selectTeamData, sys_permissions, onAgentsChanged, onTeamChanged }: Props) {
    const [tab, setTab] = useState(0);
    const [managedTeam, setManagedTeam] = useState<TeamProfile | null>(selectTeamData);

    useEffect(() => {
        setManagedTeam(selectTeamData);
    }, [selectTeamData]);

    const handleTeamCreated = (team: TeamProfile) => {
        setManagedTeam(team);
        onTeamChanged?.(team);
        if (is_sys_admin) setTab(1);
    };

    const tabs = [
        {
            label: "Members",
            permission: ["Manage team users"],
            teamScoped: true,
            element: <TeamUserManagementPage team={managedTeam} />
        },
        {
            label: "Data access",
            permission: ["Manage team data groups"],
            teamScoped: true,
            element: <DataGroupManagementPage team={managedTeam} />
        },
        {
            label: "Roles & permissions",
            permission: ["Manage team permissions"],
            teamScoped: true,
            element: <RBACManagementPage team={managedTeam} />
        },
        {
            label: "Agents",
            permission: ["Manage agents"],
            teamScoped: true,
            element: <AgentManagementPage team={managedTeam} onAgentsChanged={onAgentsChanged} />
        },
        {
            label: "Integrations",
            permission: ["Manage integrations"],
            element: <IntegrationManagementPage team={managedTeam} isSystemAdmin={is_sys_admin} />
        },
        {
            label: "User directory",
            permission: ["Manage users", "Manage teams"],
            element: <ManageUserTabs selectedTeam={managedTeam} onTeamCreated={handleTeamCreated} />
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
        },
        {
            label: "Guardrail Policy",
            permission: ["Manage agents"],
            systemAdminOnly: !managedTeam,
            element: <GuardrailPolicyPage team={managedTeam} />
        }
    ];

    const allowedTabs = tabs.filter(
        t =>
            (!("teamScoped" in t) || !t.teamScoped || Boolean(managedTeam)) &&
            (t.label !== "Integrations" || Boolean(managedTeam) || is_sys_admin) &&
            (!("systemAdminOnly" in t) || !t.systemAdminOnly || is_sys_admin) &&
            hasPermission({
                is_sys_admin,
                permissions: managedTeam?.permissions ?? [],
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
                    <Typography variant="h6">{managedTeam ? `Team settings · ${managedTeam.name}` : "Administration"}</Typography>
                    <Typography variant="body2" color="text.secondary">
                        {managedTeam
                            ? "Manage membership, document access, roles, agents, and integrations for this team."
                            : "Manage the unassigned integration catalog or create and select a team for team-scoped settings."}
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
