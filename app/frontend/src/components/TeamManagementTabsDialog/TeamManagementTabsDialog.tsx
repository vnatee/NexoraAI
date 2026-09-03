import React, { useEffect, useMemo, useState } from "react";
import {
    Box,
    Button,
    Chip,
    Collapse,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    List,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    MenuItem,
    TextField,
    Typography,
    useMediaQuery,
    useTheme
} from "@mui/material";
import AdminPanelSettingsOutlinedIcon from "@mui/icons-material/AdminPanelSettingsOutlined";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";
import PolicyOutlinedIcon from "@mui/icons-material/PolicyOutlined";
import SmartToyOutlinedIcon from "@mui/icons-material/SmartToyOutlined";

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
import { UsageQuotaPolicyPage } from "./Tabs/UsageQuotaPolicyPage";

interface Props {
    open: boolean;
    onClose: () => void;
    is_sys_admin: boolean;
    sys_permissions: string[] | null;
    selectTeamData: TeamProfile | null;
    onAgentsChanged?: () => void;
    onTeamChanged?: (team: TeamProfile) => void;
}

type MenuGroup = "people" | "workspace" | "governance" | "system";

interface SettingsPage {
    id: string;
    label: string;
    permission: string[];
    group: MenuGroup;
    teamScoped?: boolean;
    systemAdminOnly?: boolean;
    selfPadded?: boolean;
    element: React.ReactNode;
}

const GROUP_DETAILS: Record<MenuGroup, { label: string; icon: React.ReactNode }> = {
    people: { label: "People & access", icon: <GroupsOutlinedIcon fontSize="small" /> },
    workspace: { label: "AI workspace", icon: <SmartToyOutlinedIcon fontSize="small" /> },
    governance: { label: "Governance", icon: <PolicyOutlinedIcon fontSize="small" /> },
    system: { label: "System administration", icon: <AdminPanelSettingsOutlinedIcon fontSize="small" /> }
};

export function TeamManagementTabsDialog({ open, onClose, is_sys_admin, selectTeamData, sys_permissions, onAgentsChanged, onTeamChanged }: Props) {
    const theme = useTheme();
    const compactNavigation = useMediaQuery(theme.breakpoints.down("md"));
    const [selectedPageId, setSelectedPageId] = useState("members");
    const [managedTeam, setManagedTeam] = useState<TeamProfile | null>(selectTeamData);
    const [expandedGroups, setExpandedGroups] = useState<Record<MenuGroup, boolean>>({
        people: true,
        workspace: true,
        governance: true,
        system: false
    });

    useEffect(() => {
        setManagedTeam(selectTeamData);
    }, [selectTeamData]);

    const handleTeamCreated = (team: TeamProfile) => {
        setManagedTeam(team);
        onTeamChanged?.(team);
        setSelectedPageId("data-access");
    };

    const pages: SettingsPage[] = [
        {
            id: "members",
            label: "Members",
            permission: ["Manage team users"],
            group: "people",
            teamScoped: true,
            element: <TeamUserManagementPage team={managedTeam} />
        },
        {
            id: "data-access",
            label: "Data access",
            permission: ["Manage team data groups"],
            group: "people",
            teamScoped: true,
            element: <DataGroupManagementPage team={managedTeam} />
        },
        {
            id: "roles",
            label: "Roles & permissions",
            permission: ["Manage team permissions"],
            group: "people",
            teamScoped: true,
            element: <RBACManagementPage team={managedTeam} />
        },
        {
            id: "agents",
            label: "Agents",
            permission: ["Manage agents"],
            group: "workspace",
            teamScoped: true,
            element: <AgentManagementPage team={managedTeam} onAgentsChanged={onAgentsChanged} />
        },
        {
            id: "integrations",
            label: managedTeam ? "Team integrations" : "Integration catalog",
            permission: ["Manage integrations"],
            group: managedTeam ? "workspace" : "system",
            selfPadded: true,
            element: <IntegrationManagementPage team={managedTeam} isSystemAdmin={is_sys_admin} />
        },
        {
            id: "user-directory",
            label: "User directory",
            permission: ["Manage users", "Manage teams"],
            group: "system",
            element: <ManageUserTabs selectedTeam={managedTeam} onTeamCreated={handleTeamCreated} />
        },
        {
            id: "llm-providers",
            label: "LLM providers",
            permission: ["Manage users", "Manage teams"],
            group: "system",
            systemAdminOnly: true,
            element: <LLMProviderManagement />
        },
        {
            id: "mcp-servers",
            label: "MCP servers",
            permission: ["Manage users", "Manage teams"],
            group: "system",
            systemAdminOnly: true,
            element: <MCPServerManagement />
        },
        {
            id: "agent-audit",
            label: "Agent audit",
            permission: ["Manage users", "Manage teams"],
            group: managedTeam ? "system" : "governance",
            systemAdminOnly: true,
            element: <AgentAuditManagement />
        },
        {
            id: "guardrails",
            label: "Guardrail policy",
            permission: ["Manage agents"],
            group: "governance",
            systemAdminOnly: !managedTeam,
            selfPadded: true,
            element: <GuardrailPolicyPage team={managedTeam} />
        },
        {
            id: "usage-quotas",
            label: "Usage quotas",
            permission: ["Manage team permissions", "Manage users"],
            group: "governance",
            systemAdminOnly: !managedTeam,
            selfPadded: true,
            element: <UsageQuotaPolicyPage team={managedTeam} isSystemAdmin={is_sys_admin} />
        }
    ];

    const allowedPages = pages.filter(
        page =>
            (!page.teamScoped || Boolean(managedTeam)) &&
            (page.id !== "integrations" || Boolean(managedTeam) || is_sys_admin) &&
            (!page.systemAdminOnly || is_sys_admin) &&
            hasPermission({
                is_sys_admin,
                permissions: managedTeam?.permissions ?? [],
                sys_permissions: sys_permissions ?? [],
                requiredPermissions: page.permission
            })
    );
    const groupOrder: MenuGroup[] = managedTeam
        ? ["people", "workspace", "governance", "system"]
        : ["system", "governance"];
    const groupedPages = useMemo(
        () => groupOrder
            .map(group => ({ group, pages: allowedPages.filter(page => page.group === group) }))
            .filter(section => section.pages.length > 0),
        [allowedPages, managedTeam]
    );
    const selectedPage = allowedPages.find(page => page.id === selectedPageId) ?? allowedPages[0];

    useEffect(() => {
        if (!allowedPages.some(page => page.id === selectedPageId) && allowedPages[0]) {
            setSelectedPageId(allowedPages[0].id);
        }
    }, [allowedPages, selectedPageId]);

    useEffect(() => {
        if (selectedPage) {
            setExpandedGroups(current => current[selectedPage.group]
                ? current
                : { ...current, [selectedPage.group]: true });
        }
    }, [selectedPage?.group]);

    const selectPage = (page: SettingsPage) => {
        setSelectedPageId(page.id);
        setExpandedGroups(current => ({ ...current, [page.group]: true }));
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="xl" fullWidth>
            <DialogTitle sx={{ pb: 2 }}>
                <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
                    <Typography variant="h6">{managedTeam ? `Team settings · ${managedTeam.name}` : "Administration"}</Typography>
                    <Chip size="small" variant="outlined" color={managedTeam ? "primary" : "default"} label={managedTeam ? "Team" : "System"} />
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {managedTeam
                        ? "Manage people, AI workspace, governance, and authorized system settings."
                        : "Manage platform identity, providers, integrations, governance, and operational policy."}
                </Typography>
            </DialogTitle>

            <DialogContent dividers sx={{ height: "72vh", p: 0, overflow: "hidden" }}>
                {compactNavigation ? (
                    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
                        <Box sx={{ p: 2, borderBottom: 1, borderColor: "divider" }}>
                            <TextField
                                select
                                fullWidth
                                size="small"
                                label="Settings section"
                                value={selectedPage?.id ?? ""}
                                onChange={event => {
                                    const page = allowedPages.find(item => item.id === event.target.value);
                                    if (page) selectPage(page);
                                }}
                            >
                                {groupedPages.map(section => [
                                    <MenuItem key={`${section.group}-heading`} disabled>{GROUP_DETAILS[section.group].label}</MenuItem>,
                                    ...section.pages.map(page => <MenuItem key={page.id} value={page.id}>{page.label}</MenuItem>)
                                ])}
                            </TextField>
                        </Box>
                        <Box sx={{
                            flex: 1,
                            minHeight: 0,
                            overflow: "auto",
                            boxSizing: "border-box",
                            p: selectedPage?.selfPadded ? 0 : 2
                        }}>{selectedPage?.element}</Box>
                    </Box>
                ) : (
                    <Box sx={{ height: "100%", display: "flex" }}>
                        <Box component="nav" aria-label="Settings navigation" sx={{ width: 280, flexShrink: 0, overflowY: "auto", bgcolor: "grey.50", borderRight: 1, borderColor: "divider", py: 1 }}>
                            {groupedPages.map((section, index) => <React.Fragment key={section.group}>
                                {index > 0 && <Divider sx={{ my: 1 }} />}
                                <List disablePadding>
                                    <ListItemButton onClick={() => setExpandedGroups(current => ({ ...current, [section.group]: !current[section.group] }))} sx={{ px: 2, py: 1 }}>
                                        <ListItemIcon sx={{ minWidth: 36, color: "text.secondary" }}>{GROUP_DETAILS[section.group].icon}</ListItemIcon>
                                        <ListItemText primary={GROUP_DETAILS[section.group].label} primaryTypographyProps={{ variant: "overline", fontWeight: 700, color: "text.secondary" }} />
                                        {expandedGroups[section.group] ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                                    </ListItemButton>
                                    <Collapse in={expandedGroups[section.group]} timeout="auto" unmountOnExit>
                                        <List disablePadding>
                                            {section.pages.map(page => <ListItemButton key={page.id} selected={selectedPage?.id === page.id} onClick={() => selectPage(page)} sx={{ pl: 6, pr: 2, py: 1 }}>
                                                <ListItemText primary={page.label} primaryTypographyProps={{ fontWeight: selectedPage?.id === page.id ? 700 : 400 }} />
                                            </ListItemButton>)}
                                        </List>
                                    </Collapse>
                                </List>
                            </React.Fragment>)}
                        </Box>
                        <Box sx={{
                            flex: 1,
                            minWidth: 0,
                            height: "100%",
                            overflow: "auto",
                            boxSizing: "border-box",
                            p: selectedPage?.selfPadded ? 0 : 3
                        }}>{selectedPage?.element}</Box>
                    </Box>
                )}
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
}
