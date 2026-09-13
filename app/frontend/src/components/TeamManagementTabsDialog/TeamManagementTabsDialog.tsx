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
    IconButton,
    List,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    MenuItem,
    Stack,
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
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import CloseIcon from "@mui/icons-material/Close";
import { useMsal } from "@azure/msal-react";

import { TeamUserManagementPage } from "./Tabs/TeamUserManagementPage";
import { AgentManagementPage } from "./Tabs/AgentManagementPage";
import { DataGroupManagementPage } from "./Tabs/DataGroupManagementPage";
import { RBACManagementPage } from "./Tabs/RBACManagementPage";
import { UserManagementPage } from "./Tabs/UserManagementPage";
import { UserPermissionPanel } from "./Tabs/UserPermissionPanel";
import { AuthenticationSettingsPage } from "./Tabs/AuthenticationSettingsPage";
import { hasPermission } from "../../utill/hasPermission";
import { TeamProfile } from "../../api/models";
import { edit_team_name } from "../../api";
import { getToken } from "../../authConfig";
import { useNotification } from "../../utill/NotificationProvider";
import { TeamManagement } from "../TeamManagement/TeamManagement";
import { IntegrationManagementPage } from "./Tabs/IntegrationManagementPage";
import { LLMProviderManagement } from "../LLMProviderManagement";
import { EmbeddingProfileManagement } from "../EmbeddingProfileManagement/EmbeddingProfileManagement";
import { AgentAuditManagement } from "../AgentAuditManagement";
import { GuardrailPolicyPage } from "./Tabs/GuardrailPolicyPage";
import { UsageQuotaPolicyPage } from "./Tabs/UsageQuotaPolicyPage";
import { ChatHistoryPolicyPage } from "./Tabs/ChatHistoryPolicyPage";
import { SystemHealthManagement } from "../SystemHealthManagement/SystemHealthManagement";
import { LicenseSettingsPage } from "./Tabs/LicenseSettingsPage";

interface Props {
    open: boolean;
    onClose: () => void;
    is_sys_admin: boolean;
    sys_permissions: string[] | null;
    selectTeamData: TeamProfile | null;
    onAgentsChanged?: () => void;
    onTeamChanged?: (team: TeamProfile) => void;
}

type MenuGroup = "people" | "workspace" | "governance" | "user-team" | "system";

interface SettingsPage {
    id: string;
    label: string;
    permission: string[];
    group: MenuGroup;
    scope: "team" | "system" | "both";
    teamScoped?: boolean;
    systemAdminOnly?: boolean;
    selfPadded?: boolean;
    element: React.ReactNode;
}

const GROUP_DETAILS: Record<MenuGroup, { label: string; icon: React.ReactNode }> = {
    people: { label: "Current team", icon: <GroupsOutlinedIcon fontSize="small" /> },
    workspace: { label: "AI workspace", icon: <SmartToyOutlinedIcon fontSize="small" /> },
    governance: { label: "Governance", icon: <PolicyOutlinedIcon fontSize="small" /> },
    "user-team": { label: "Organization", icon: <GroupsOutlinedIcon fontSize="small" /> },
    system: { label: "System administration", icon: <AdminPanelSettingsOutlinedIcon fontSize="small" /> }
};

const COLLAPSED_GROUPS: Record<MenuGroup, boolean> = {
    people: false,
    workspace: false,
    governance: false,
    "user-team": false,
    system: false
};

export function TeamManagementTabsDialog({ open, onClose, is_sys_admin, selectTeamData, sys_permissions, onAgentsChanged, onTeamChanged }: Props) {
    const { instance } = useMsal();
    const { showNotification } = useNotification();
    const theme = useTheme();
    const compactNavigation = useMediaQuery(theme.breakpoints.down("md"));
    const [selectedPageId, setSelectedPageId] = useState("members");
    const [managedTeam, setManagedTeam] = useState<TeamProfile | null>(selectTeamData);
    const [renameOpen, setRenameOpen] = useState(false);
    const [teamNameDraft, setTeamNameDraft] = useState("");
    const [renaming, setRenaming] = useState(false);
    const [expandedGroups, setExpandedGroups] = useState<Record<MenuGroup, boolean>>(() => ({ ...COLLAPSED_GROUPS }));

    useEffect(() => {
        if (open) setExpandedGroups({ ...COLLAPSED_GROUPS });
    }, [open]);

    useEffect(() => {
        setManagedTeam(selectTeamData);
    }, [selectTeamData]);

    const handleTeamCreated = (team: TeamProfile) => {
        setManagedTeam(team);
        onTeamChanged?.(team);
        setSelectedPageId("data-access");
    };

    const handleTeamManage = (team: TeamProfile) => {
        setManagedTeam(team);
        setSelectedPageId("members");
    };

    const canManageTeams = hasPermission({
        is_sys_admin,
        permissions: managedTeam?.permissions ?? [],
        sys_permissions: sys_permissions ?? [],
        requiredPermissions: ["Manage teams"]
    });

    const canManageUsers = hasPermission({
        is_sys_admin,
        permissions: managedTeam?.permissions ?? [],
        sys_permissions: sys_permissions ?? [],
        requiredPermissions: ["Manage users"]
    });

    const saveTeamName = async () => {
        const normalizedName = teamNameDraft.trim();
        if (!managedTeam || !normalizedName) return;
        try {
            setRenaming(true);
            const token = await getToken(instance);
            if (!token) return;
            await edit_team_name(managedTeam._id, normalizedName, token);
            const updatedTeam = { ...managedTeam, name: normalizedName };
            setManagedTeam(updatedTeam);
            onTeamChanged?.(updatedTeam);
            setRenameOpen(false);
            showNotification("Team name updated successfully", "success");
        } catch (error) {
            console.error("Failed to rename team", error);
            showNotification("Failed to update team name", "error");
        } finally {
            setRenaming(false);
        }
    };

    const pages: SettingsPage[] = [
        {
            id: "members",
            label: "Members",
            permission: ["Manage team users"],
            group: "people",
            scope: "team",
            teamScoped: true,
            element: <TeamUserManagementPage team={managedTeam} />
        },
        {
            id: "roles",
            label: "Roles & permissions",
            permission: ["Manage team permissions"],
            group: "people",
            scope: "team",
            teamScoped: true,
            element: <RBACManagementPage team={managedTeam} />
        },
        {
            id: "data-access",
            label: "Data access",
            permission: ["Manage team data groups"],
            group: "people",
            scope: "team",
            teamScoped: true,
            element: <DataGroupManagementPage team={managedTeam} />
        },
        {
            id: "agents",
            label: "Agents",
            permission: ["Manage agents"],
            group: "workspace",
            scope: "team",
            teamScoped: true,
            element: <AgentManagementPage team={managedTeam} onAgentsChanged={onAgentsChanged} />
        },
        {
            id: "integrations",
            label: managedTeam ? "Team integrations" : "Integration catalog",
            permission: ["Manage integrations"],
            group: managedTeam ? "workspace" : "system",
            scope: "both",
            selfPadded: true,
            element: <IntegrationManagementPage team={managedTeam} isSystemAdmin={is_sys_admin} />
        },
        {
            id: "teams",
            label: "Teams",
            permission: ["Manage teams"],
            group: "user-team",
            scope: "system",
            element: <TeamManagement onTeamCreated={handleTeamCreated} onTeamManage={handleTeamManage} />
        },
        {
            id: "users",
            label: "Users",
            permission: ["Manage users"],
            group: "user-team",
            scope: "system",
            element: <UserManagementPage />
        },
        {
            id: "system-permissions",
            label: "User permissions",
            permission: ["Manage users"],
            group: "user-team",
            scope: "system",
            element: <UserPermissionPanel />
        },
        {
            id: "system-health",
            label: "System health",
            permission: [],
            group: "system",
            scope: "system",
            systemAdminOnly: true,
            element: <SystemHealthManagement />
        },
        {
            id: "llm-providers",
            label: "LLM providers",
            permission: ["Manage users", "Manage teams"],
            group: "system",
            scope: "system",
            systemAdminOnly: true,
            element: <LLMProviderManagement />
        },
        {
            id: "embedding-profiles",
            label: "Embedding profiles",
            permission: [],
            group: "system",
            scope: "system",
            systemAdminOnly: true,
            element: <EmbeddingProfileManagement />
        },
        {
            id: "agent-audit",
            label: "Agent audit",
            permission: ["Manage users", "Manage teams"],
            group: managedTeam ? "system" : "governance",
            scope: "system",
            systemAdminOnly: true,
            element: <AgentAuditManagement />
        },
        {
            id: "guardrails",
            label: "Guardrail policy",
            permission: ["Manage agents"],
            group: "governance",
            scope: "both",
            systemAdminOnly: !managedTeam,
            selfPadded: true,
            element: <GuardrailPolicyPage team={managedTeam} />
        },
        {
            id: "usage-quotas",
            label: "Usage quotas",
            permission: ["Manage team permissions", "Manage users"],
            group: "governance",
            scope: "both",
            systemAdminOnly: !managedTeam,
            selfPadded: true,
            element: <UsageQuotaPolicyPage team={managedTeam} isSystemAdmin={is_sys_admin} />
        },
        {
            id: "team-chat-history",
            label: "Team chat history",
            permission: ["Manage agents"],
            group: "governance",
            scope: "team",
            teamScoped: true,
            selfPadded: true,
            element: <ChatHistoryPolicyPage team={managedTeam} />
        },
        {
            id: "system-chat-history",
            label: "System chat history",
            permission: [],
            group: "governance",
            scope: "system",
            systemAdminOnly: true,
            selfPadded: true,
            element: <ChatHistoryPolicyPage team={null} />
        },
        {
            id: "license",
            label: "License",
            permission: [],
            group: "system",
            scope: "system",
            systemAdminOnly: true,
            element: <LicenseSettingsPage />
        },
        {
            id: "authentication",
            label: "Sign-in & authentication",
            permission: [],
            group: "system",
            scope: "system",
            systemAdminOnly: true,
            element: <AuthenticationSettingsPage />
        }
    ];

    const allowedPages = pages.filter(
        page =>
            (page.scope === "both" || page.scope === (managedTeam ? "team" : "system")) &&
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
        ? ["people", "workspace", "governance"]
        : ["user-team", "governance", "system"];
    const groupDetails: Record<MenuGroup, { label: string; icon: React.ReactNode }> = {
        ...GROUP_DETAILS,
        people: {
            ...GROUP_DETAILS.people,
            label: managedTeam ? `Team · ${managedTeam.name}` : GROUP_DETAILS.people.label
        },
        governance: {
            ...GROUP_DETAILS.governance,
            label: managedTeam ? "Team governance" : "Platform governance"
        }
    };
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

    const selectPage = (page: SettingsPage) => {
        setSelectedPageId(page.id);
        setExpandedGroups(current => ({ ...current, [page.group]: true }));
    };

    const keepOpenUnlessCloseButton = (_event: object, reason: "backdropClick" | "escapeKeyDown") => {
        if (reason === "backdropClick" || reason === "escapeKeyDown") return;
    };

    return (
        <Dialog
            open={open}
            onClose={keepOpenUnlessCloseButton}
            disableEscapeKeyDown
            maxWidth="xl"
            fullWidth
        >
            <DialogTitle
                sx={{
                    px: 3,
                    py: 2,
                    bgcolor: managedTeam ? "rgba(25, 118, 210, 0.06)" : "grey.100",
                    borderTop: 4,
                    borderColor: managedTeam ? "primary.main" : "text.secondary"
                }}
            >
                <Box display="flex" alignItems="center" justifyContent="space-between" gap={2} flexWrap="wrap">
                    <Box>
                        <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
                            {managedTeam ? <GroupsOutlinedIcon color="primary" /> : <AdminPanelSettingsOutlinedIcon color="action" />}
                            <Box>
                                <Typography variant="overline" color={managedTeam ? "primary.main" : "text.secondary"} fontWeight={800} lineHeight={1.2}>
                                    {managedTeam ? "TEAM WORKSPACE" : "SYSTEM ADMINISTRATION"}
                                </Typography>
                                <Typography variant="h6" lineHeight={1.3}>{managedTeam ? managedTeam.name : "Administration"}</Typography>
                            </Box>
                            {managedTeam && canManageTeams && (
                                <IconButton
                                    size="small"
                                    aria-label={`Rename ${managedTeam.name}`}
                                    title="Rename team"
                                    onClick={() => {
                                        setTeamNameDraft(managedTeam.name);
                                        setRenameOpen(true);
                                    }}
                                >
                                    <EditOutlinedIcon fontSize="small" />
                                </IconButton>
                            )}
                            <Chip
                                size="small"
                                variant={managedTeam ? "filled" : "outlined"}
                                color={managedTeam ? "primary" : "default"}
                                label={managedTeam ? `Team scope · ${managedTeam.name}` : "System-wide scope"}
                            />
                        </Box>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {managedTeam
                                ? `All pages in this workspace apply only to ${managedTeam.name}. Use System administration for platform-wide settings.`
                                : "Changes on this screen apply across the platform or to unassigned catalog resources."}
                        </Typography>
                    </Box>
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                        {managedTeam && (canManageUsers || canManageTeams) && (
                            <Button
                                size="small"
                                variant="outlined"
                                startIcon={<AdminPanelSettingsOutlinedIcon />}
                                onClick={() => {
                                    setManagedTeam(null);
                                    setSelectedPageId(canManageUsers ? "users" : "teams");
                                    setExpandedGroups({ ...COLLAPSED_GROUPS });
                                }}
                            >
                                Open system administration
                            </Button>
                        )}
                        {!managedTeam && selectTeamData && (
                            <Button
                                size="small"
                                variant="outlined"
                                startIcon={<GroupsOutlinedIcon />}
                                onClick={() => {
                                    setManagedTeam(selectTeamData);
                                    setSelectedPageId("members");
                                }}
                            >
                                Return to {selectTeamData.name} team
                            </Button>
                        )}
                        <Button size="small" variant="contained" startIcon={<CloseIcon />} onClick={onClose}>
                            Close
                        </Button>
                    </Stack>
                </Box>
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
                                    <MenuItem key={`${section.group}-heading`} disabled>{groupDetails[section.group].label}</MenuItem>,
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
                                    <ListItemButton
                                        title={section.group === "people" ? groupDetails[section.group].label : undefined}
                                        onClick={() => setExpandedGroups(current => ({ ...current, [section.group]: !current[section.group] }))}
                                        sx={{ px: 2, py: 1 }}
                                    >
                                        <ListItemIcon sx={{ minWidth: 36, color: "text.secondary" }}>{groupDetails[section.group].icon}</ListItemIcon>
                                        <ListItemText
                                            primary={groupDetails[section.group].label}
                                            primaryTypographyProps={{ variant: "overline", fontWeight: 700, color: "text.secondary", noWrap: true }}
                                        />
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

            <Dialog open={renameOpen} onClose={() => !renaming && setRenameOpen(false)} maxWidth="xs" fullWidth>
                <DialogTitle>Rename team</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        fullWidth
                        label="Team name"
                        value={teamNameDraft}
                        onChange={event => setTeamNameDraft(event.target.value)}
                        sx={{ mt: 1 }}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setRenameOpen(false)} disabled={renaming}>Cancel</Button>
                    <Button
                        variant="contained"
                        disabled={!teamNameDraft.trim() || teamNameDraft.trim() === managedTeam?.name || renaming}
                        onClick={() => void saveTeamName()}
                    >
                        {renaming ? "Saving..." : "Save"}
                    </Button>
                </DialogActions>
            </Dialog>
        </Dialog>
    );
}
