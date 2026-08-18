import React, { useEffect, useState } from "react";
import { Tabs, Tab, Box } from "@mui/material";
import { TabPanel } from "../common/TabPanel";
import { UserManagementPage } from "./UserManagementPage";
import { UserPermissionPanel } from "./UserPermissionPanel";
import { TeamManagement } from "../../TeamManagement/TeamManagement";
import { hasPermission } from "../../../utill/hasPermission";
import { TeamProfile, User } from "../../../api/models";
import { AuthStorage } from "../../../utill/authStorage";
import { STORAGE_KEYS } from "../../../utill/storageKeys";
import { Storage } from "../../../utill/storage";

export function ManageUserTabs() {
    const [tab, setTab] = useState(0);
    const [userData, setUserData] = useState<User | null>(null);
    const [selectTeamData, setSelectTeamData] = useState<TeamProfile | null>(null);
    const [sysPers, setSysPers] = useState<string[] | null>(null);

    const getUserData = () => {
        let user = AuthStorage.get()?.user ?? null;
        const sys_permissions = AuthStorage.get()?.sys_permissions ?? null;
        setUserData(user);
        setSysPers(sys_permissions);
    };

    const getCurrentTeam = () => {
        let selectTeam = Storage.get<TeamProfile>(STORAGE_KEYS.SELECT_TEAM) ?? null;
        setSelectTeamData(selectTeam);
    };

    useEffect(() => {
        getUserData();
        getCurrentTeam();
    }, []);

    const tabs = [];

    if (
        hasPermission({
            is_sys_admin: userData?.is_sys_admin ?? false,
            permissions: selectTeamData?.permissions ?? [],
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

    if (
        hasPermission({
            is_sys_admin: userData?.is_sys_admin ?? false,
            permissions: selectTeamData?.permissions ?? [],
            sys_permissions: sysPers ? sysPers : [],
            requiredPermissions: ["Manage teams"]
        })
    ) {
        tabs.push({
            label: "Team Management",
            content: <TeamManagement />
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
