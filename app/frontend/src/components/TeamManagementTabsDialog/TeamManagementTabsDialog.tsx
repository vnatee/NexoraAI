import React, { useEffect, useState } from "react";
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Tabs, Tab } from "@mui/material";

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
            label: "Team Users",
            permission: ["Manage team users"],
            element: <TeamUserManagementPage team={selectTeamData} />
        },
        {
            label: "Agents",
            permission: ["Manage agents"],
            element: <AgentManagementPage onAgentsChanged={onAgentsChanged} />
        },
        {
            label: "Integrations",
            permission: ["Manage integrations"],
            element: <IntegrationManagementPage team={selectTeamData} />
        },
        {
            label: "Data Groups",
            permission: ["Manage team data groups"],
            element: <DataGroupManagementPage />
        },
        {
            label: "RBAC",
            permission: ["Manage team permissions"],
            element: <RBACManagementPage />
        },
        {
            label: "Manage User",
            permission: ["Manage users", "Manage teams"],
            element: <ManageUserTabs />
        },
        {
            label: "LLM Providers",
            permission: ["Manage users", "Manage teams"],
            systemAdminOnly: true,
            element: <LLMProviderManagement />
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
            <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ px: 2, borderBottom: 1, borderColor: "divider" }}>
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
