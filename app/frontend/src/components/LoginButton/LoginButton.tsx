import { useMsal } from "@azure/msal-react";
import { useTranslation } from "react-i18next";
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    IconButton,
    Avatar,
    Menu,
    MenuItem,
    Typography,
    Box,
    Divider,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Radio
} from "@mui/material";
import CircularProgress from "@mui/material/CircularProgress";
import styles from "./LoginButton.module.css";
import { getRedirectUri, loginRequest, appServicesLogout, getUsername, getToken } from "../../authConfig";
import { useState, useEffect, useContext } from "react";
import { LoginContext } from "../../loginContext";
import { currentAgentConfig, check_user_login, register, check_waiting_approve } from "../../api/api";
import { GroupDetail, AuthProfile, TeamProfile, User } from "../../api/models";
import { RegisterDialog } from "./RegisterDialog";
import { Storage } from "../../utill/storage";
import { STORAGE_KEYS } from "../../utill/storageKeys";
import { AuthStorage } from "../../utill/authStorage";

export const LoginButton = () => {
    const { instance } = useMsal();
    const { instance: msalInstance } = useMsal();
    const { loggedIn, setLoggedIn, setUserDetails, setIsUserLoading, setIsWaitingApprove, isWaitingApprove, setIsSwitchTeam } = useContext(LoginContext);
    const { t } = useTranslation();

    const [username, setUsername] = useState("");

    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [openGroupDialog, setOpenGroupDialog] = useState(false);

    const [openRegisterDialog, setOpenRegisterDialog] = useState(false);
    const [pendingUsername, setPendingUsername] = useState<string | null>(null);

    const [refreshKey, setRefreshKey] = useState(0);
    const [teams, setTeams] = useState<TeamProfile[]>([]);
    const [activeTeam, setActiveTeam] = useState<TeamProfile | null>(null);
    const [selectedTeam, setSelectedTeam] = useState<TeamProfile | null>(null);
    const [haveUser, setHaveUser] = useState<User | null>(null);

    // ===============================
    // Restore session
    // ===============================
    useEffect(() => {
        const restore = async () => {
            const accounts = instance.getAllAccounts();
            if (accounts.length > 0) {
                instance.setActiveAccount(accounts[0]);
                setLoggedIn(true);

                const name = (await getUsername(instance)) ?? "";
                setUsername(name);
            }
        };
        restore();
    }, []);

    // ===============================
    // Init after login
    // ===============================
    useEffect(() => {
        const init = async () => {
            if (!loggedIn) return;

            setIsUserLoading(true);
            try {
                const token = await getToken(msalInstance);
                if (!token) {
                    setLoggedIn(false);
                    return;
                }

                const name = (await getUsername(instance)) ?? "";
                setUsername(name);

                try {
                    await initUserAfterLogin(token);
                } catch (err: any) {
                    if (err?.status === 404) {
                        const waitingResp = await check_waiting_approve(token);

                        if (waitingResp?.is_waiting) {
                            setIsWaitingApprove(true);
                        } else {
                            setIsWaitingApprove(false);
                            setLoggedIn(false);
                        }
                    } else {
                        console.error(err);
                    }
                }
            } finally {
                setIsUserLoading(false);
            }
        };

        init();
    }, [loggedIn]);

    // ===============================
    // Login
    // ===============================
    const handleLoginPopup = () => {
        instance
            .loginPopup({
                ...loginRequest,
                redirectUri: getRedirectUri()
            })
            .then(async result => {
                setLoggedIn(true);

                const account = result?.account || instance.getAllAccounts()[0];
                if (account) instance.setActiveAccount(account);

                const token = await getToken(msalInstance);
                if (!token) return;

                setIsUserLoading(true);

                const name = (await getUsername(instance)) ?? "";
                setUsername(name);

                try {
                    // ✅ ใช้ logic กลาง
                    await initUserAfterLogin(token);
                } catch (err: any) {
                    if (err?.status === 404) {
                        // ❌ ไม่มี user → register — populate ข้อมูลจาก MSAL account
                        const account = instance.getActiveAccount() || instance.getAllAccounts()[0];
                        setPendingUsername(name);
                        setHaveUser({
                            _id: "",
                            active: true,
                            ad_email: account?.username ?? name,
                            email: account?.username ?? name,
                            first_name: account?.name?.split(" ")[0] ?? "",
                            last_name: account?.name?.split(" ").slice(1).join(" ") ?? "",
                            employee_id: "",
                            tel: ""
                        } as User);
                        setOpenRegisterDialog(true);
                    } else {
                        console.error(err);
                    }
                } finally {
                    setIsUserLoading(false);
                }

                setRefreshKey(k => k + 1);
            })
            .catch(console.error);
    };

    // ===============================
    // Logout
    // ===============================
    const handleLogout = async () => {
        AuthStorage.clear();
        Storage.remove(STORAGE_KEYS.Active_Teams);

        setLoggedIn(false);
        setUsername("");

        const active = instance.getActiveAccount();
        if (active) {
            await instance.logoutPopup({
                account: active,
                mainWindowRedirectUri: "/"
            });
        } else {
            appServicesLogout();
        }
    };

    // ===============================
    // Switch Team
    // ===============================
    const handleSwitchTeam = async (team: TeamProfile) => {
        if (!team) return;

        Storage.remove(STORAGE_KEYS.ACTIVE_AGENT);
        setActiveTeam(team);
        persistActiveTeam(username, team);

        // ✅ Reload user profile to update sys_permissions for the new team
        try {
            const token = await getToken(msalInstance);
            if (token) {
                const authProfile = await check_user_login(token);
                Storage.set(STORAGE_KEYS.AUTH_PROFILE, authProfile as AuthProfile);
                AuthStorage.set(authProfile);
            }
        } catch (err) {
            console.error("Failed to reload profile after team switch:", err);
        }

        setIsSwitchTeam(true);
    };

    // ===============================
    // Avatar helpers
    // ===============================
    const stringToColor = (string: string) => {
        let hash = 0;
        for (let i = 0; i < string.length; i++) {
            hash = string.charCodeAt(i) + ((hash << 5) - hash);
        }
        return `#${((hash >> 24) & 0xff).toString(16).padStart(2, "0")}
                 ${((hash >> 16) & 0xff).toString(16).padStart(2, "0")}
                 ${((hash >> 8) & 0xff).toString(16).padStart(2, "0")}`.replace(/\s/g, "");
    };

    const stringAvatar = (name: string) => ({
        sx: { bgcolor: stringToColor(name) },
        children: name ? name[0].toUpperCase() : "?"
    });

    const persistActiveTeam = (username: string, team: TeamProfile) => {
        if (!username || !team) return;

        const savedTeams = (Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, TeamProfile>) || {};

        savedTeams[username] = team;

        Storage.set(STORAGE_KEYS.Active_Teams, savedTeams);
    };

    const handleCloseMenu = () => {
        setAnchorEl(null);
    };

    const resolveAndSetActiveTeam = async (teams: TeamProfile[]) => {
        if (teams.length > 0) {
            const username = (await getUsername(instance)) ?? "";

            const savedTeams = (Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, TeamProfile>) || {};
            const saved = savedTeams[username];

            const teamToUse = saved ? (teams.find((t: TeamProfile) => t._id === saved._id) ?? teams[0]) : teams[0];

            setActiveTeam(teamToUse);

            const shouldUpdate =
                !saved ||
                saved._id !== teamToUse._id ||
                JSON.stringify(saved.permissions ?? []) !== JSON.stringify(teamToUse.permissions ?? []) ||
                saved.name !== teamToUse.name;

            if (shouldUpdate) {
                persistActiveTeam(username, teamToUse);
            }
        } else {
            setActiveTeam(null);
        }
    };

    const initUserAfterLogin = async (token: string) => {
        const authProfile = await check_user_login(token);
        setHaveUser(authProfile ? authProfile.user : null);

        const hasNoTeam = !authProfile.teams || authProfile.teams.length === 0;
        const isSysAdmin = authProfile.user?.is_sys_admin;

        if (hasNoTeam && !isSysAdmin) {
            const waitingResp = await check_waiting_approve(token);

            if (waitingResp?.is_waiting) {
                setIsWaitingApprove(true);
            } else {
                setOpenRegisterDialog(true);
            }
        }

        Storage.set(STORAGE_KEYS.AUTH_PROFILE, authProfile as AuthProfile);

        const teams = authProfile.teams ?? [];
        setTeams(teams);

        await resolveAndSetActiveTeam(teams);
    };

    // useEffect(() => {
    //     const initAfterRefresh = async () => {
    //         const authProfile = Storage.get(STORAGE_KEYS.AUTH_PROFILE) as AuthProfile | null;

    //         if (!authProfile) return;

    //         // ✅ ดึง teams ใหม่ล่าสุดจาก backend เพื่อให้ทีม update เสมอ
    //         const token = await getToken(msalInstance);
    //         if (!token) return;
    //         const latestProfile = await check_user_login(token);

    //         Storage.set(STORAGE_KEYS.AUTH_PROFILE, latestProfile as AuthProfile);

    //         const teams = latestProfile.teams ?? [];
    //         setTeams(teams);

    //         // ✅ เรียกฟังก์ชันเดียวกับตอน login
    //         await resolveAndSetActiveTeam(teams);
    //     };

    //     initAfterRefresh();
    // }, [loggedIn, username]);

    useEffect(() => {
        if (!loggedIn || !username) return;

        const authProfile = Storage.get(STORAGE_KEYS.AUTH_PROFILE) as AuthProfile;
        const teams = authProfile?.teams ?? [];

        setTeams(teams);

        if (teams.length === 0) {
            setActiveTeam(null);
            return;
        }

        const savedTeams = (Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, TeamProfile>) || {};
        const saved = savedTeams[username];

        if (saved) {
            const stillExists = teams.find(t => t._id === saved._id);
            if (stillExists) {
                setActiveTeam(stillExists);
                return;
            }
        }

        // fallback → team แรก
        setActiveTeam(teams[0]);
    }, [loggedIn, username]);

    useEffect(() => {
        if (!isWaitingApprove) return;

        // console.log("▶ start polling approve");

        const interval = setInterval(async () => {
            try {
                // console.log("⏱ polling tick");

                const token = await getToken(msalInstance);
                if (!token) {
                    console.warn("no token");
                    return;
                }

                const resp = await check_waiting_approve(token);
                // console.log("approve resp:", resp);

                if (!resp?.is_waiting) {
                    // console.log("✅ approved");
                    setIsWaitingApprove(false);
                }
            } catch (err) {
                console.error("polling error:", err);
            }
        }, 5000);

        return () => {
            console.log("⏹ stop polling");
            clearInterval(interval);
        };
    }, [isWaitingApprove, loggedIn, msalInstance]);

    // ===============================
    // Render
    // ===============================
    return (
        <>
            <div key={refreshKey}>
                {!loggedIn ? (
                    <Button variant="contained" onClick={handleLoginPopup} className={styles.loginButton}>
                        {t("login")}
                    </Button>
                ) : (
                    <>
                        <IconButton onClick={e => setAnchorEl(e.currentTarget)}>
                            <Avatar {...stringAvatar(username)} />
                        </IconButton>

                        <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
                            <Box sx={{ px: 2, py: 1 }}>
                                <Typography variant="subtitle1" fontWeight={600}>
                                    {username || "Username"}
                                </Typography>

                                <Divider sx={{ my: 1 }} />

                                <Typography variant="body2" color="text.secondary">
                                    Current Team: <strong>{activeTeam ? activeTeam.name : "No team assigned"}</strong>
                                </Typography>
                            </Box>

                            <Divider />

                            <MenuItem
                                disabled={teams.length === 0}
                                onClick={() => {
                                    setSelectedTeam(activeTeam);
                                    setOpenGroupDialog(true);
                                    handleCloseMenu();
                                }}
                            >
                                Switch Team
                            </MenuItem>

                            <MenuItem onClick={handleLogout} sx={{ color: "#d32f2f" }}>
                                Logout
                            </MenuItem>
                        </Menu>

                        <Dialog open={openGroupDialog} onClose={() => setOpenGroupDialog(false)} fullWidth maxWidth="xs">
                            <DialogTitle>Switch Team</DialogTitle>

                            <DialogContent dividers>
                                {teams.length === 0 ? (
                                    <Typography>No teams available</Typography>
                                ) : (
                                    <List>
                                        {teams.map(team => (
                                            <ListItem key={team._id} disablePadding>
                                                <ListItemButton selected={selectedTeam?._id === team._id} onClick={() => setSelectedTeam(team)}>
                                                    <ListItemIcon>
                                                        <Radio checked={selectedTeam?._id === team._id} />
                                                    </ListItemIcon>
                                                    <ListItemText primary={team.name} />
                                                </ListItemButton>
                                            </ListItem>
                                        ))}
                                    </List>
                                )}
                            </DialogContent>

                            <DialogActions>
                                <Button onClick={() => setOpenGroupDialog(false)}>Cancel</Button>
                                <Button
                                    variant="contained"
                                    disabled={!selectedTeam || selectedTeam?._id === activeTeam?._id}
                                    onClick={async () => {
                                        if (selectedTeam) {
                                            await handleSwitchTeam(selectedTeam);
                                        }
                                        setOpenGroupDialog(false);
                                    }}
                                >
                                    Confirm
                                </Button>
                            </DialogActions>
                        </Dialog>
                    </>
                )}
            </div>

            <RegisterDialog
                open={openRegisterDialog}
                user={haveUser ? haveUser : null}
                onCancel={() => {
                    setOpenRegisterDialog(false);
                    setLoggedIn(false);
                }}
                onSubmit={async ({ team_id, user }) => {
                    const token = await getToken(msalInstance);
                    if (!token) return;

                    await register(team_id, user, token);
                    setOpenRegisterDialog(false);
                    setIsWaitingApprove(true);
                }}
            />
        </>
    );
};
