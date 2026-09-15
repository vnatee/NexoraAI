import React, { useEffect, useState } from "react";
import { Tabs, Tab, Box } from "@mui/material";
import { TabPanel } from "../common/TabPanel";
import { UserManagementPage } from "./UserManagementPage";
import { UserPermissionPanel } from "./UserPermissionPanel";
import { TeamManagement } from "../../TeamManagement/TeamManagement";
import { hasPermission } from "../../../utill/hasPermission";
import { TeamProfile, User } from "../../../api/models";
import { AuthStorage } from "../../../utill/authStorage";
import { AuthenticationSettingsPage } from "./AuthenticationSettingsPage";

interface ManageUserTabsProps {
    selectedTeam: TeamProfile | null;
    onTeamCreated?: (team: TeamProfile) => void;
}

export function ManageUserTabs({ selectedTeam, onTeamCreated }: ManageUserTabsProps) {
    const [tab, setTab] = useState(0);
    const [userData, setUserData] = useState<User | null>(null);
    const [sysPers, setSysPers] = useState<string[] | null>(null);

    const getUserData = () => {
        let user = AuthStorage.get()?.user ?? null;
        const sys_permissions = AuthStorage.get()?.sys_permissions ?? null;
        setUserData(user);
        setSysPers(sys_permissions);
    };

    useEffect(() => {
        getUserData();
    }, []);

    const tabs = [];

    if (
        hasPermission({
            is_sys_admin: userData?.is_sys_admin ?? false,
            permissions: selectedTeam?.permissions ?? [],
            sys_permissions: sysPers ? sysPers : [],
            requiredPermissions: ["Manage users"]
        })
    ) {
        tabs.push({
            label: "User Management",
            content: <UserManagementPage />
        });

        tabs.push({
            label: "User Permission",
            content: <UserPermissionPanel />
        });
    }

    if (userData?.is_sys_admin) {
        tabs.push({
            label: "Authentication",
            content: <AuthenticationSettingsPage />
        });
    }

    if (
        hasPermission({
            is_sys_admin: userData?.is_sys_admin ?? false,
            permissions: selectedTeam?.permissions ?? [],
            sys_permissions: sysPers ? sysPers : [],
            requiredPermissions: ["Manage teams"]
        })
    ) {
        tabs.push({
            label: "Team Management",
            content: <TeamManagement onTeamCreated={onTeamCreated} />
        });
    }

    return (
        <Box sx={{ height: "100%" }}>
            <Tabs value={tab} onChange={(_, v) => setTab(v)}>
                {tabs.map((t, i) => (
                    <Tab key={i} label={t.label} />
                ))}
            </Tabs>

            {tabs.map((t, i) => (
                <TabPanel key={i} value={tab} index={i}>
                    {t.content}
                </TabPanel>
            ))}
        </Box>
    );
}
