import { AccountInfo, EventType, PublicClientApplication } from "@azure/msal-browser";
import { msalConfig, useLogin, requireLogin, getToken } from "./authConfig";
import { useEffect, useRef, useState } from "react";
import { MsalProvider } from "@azure/msal-react";
import { LoginContext } from "./loginContext";
import Layout from "./pages/layout/Layout";
import LoginPage from "./pages/login/LoginPage";
import { UserProfile } from "./api/models";
import { CircularProgress } from "@mui/material";
import { check_user_login } from "./api/api";
import { AuthStorage } from "./utill/authStorage";

const LayoutWrapper = () => {
    const [loggedIn, setLoggedIn] = useState(false);
    const [authInitialized, setAuthInitialized] = useState(false);
    const [userDetails, setUserDetails] = useState<UserProfile | null>(null);
    const [isUserLoading, setIsUserLoading] = useState(false);
    const [isWaitingApprove, setIsWaitingApprove] = useState(false);
    const [isSwitchTeam, setIsSwitchTeam] = useState(false);

    // ✅ useRef อยู่ top-level เสมอ (Rules of Hooks)
    const msalInstanceRef = useRef<PublicClientApplication | null>(null);

    if (useLogin) {
        // สร้าง instance เพียงครั้งเดียว
        if (!msalInstanceRef.current) {
            msalInstanceRef.current = new PublicClientApplication(msalConfig);
        }

        const msalInstance = msalInstanceRef.current;

        useEffect(() => {
            const fetchLoggedIn = async () => {
                let isLogged = false;
                try {
                    // ✅ ต้อง initialize ก่อนเสมอ — MSAL v2+ โหลด cache จาก storage แบบ async
                    // ถ้าข้ามขั้นตอนนี้ acquireTokenSilent จะหา account ไม่เจอ → token = undefined → login
                    await msalInstance.initialize();

                    // ตั้ง active account ถ้ายังไม่มี
                    if (!msalInstance.getActiveAccount() && msalInstance.getAllAccounts().length > 0) {
                        msalInstance.setActiveAccount(msalInstance.getAllAccounts()[0]);
                    }

                    // Listen login success เพื่อ set active account
                    msalInstance.addEventCallback(event => {
                        if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
                            const account = event.payload as AccountInfo;
                            msalInstance.setActiveAccount(account);
                        }
                    });

                    const token = await getToken(msalInstance);
                    if (token) {
                        const authProfile = await check_user_login(token);
                        const hasNoTeam = !authProfile.teams || authProfile.teams.length === 0;
                        const isSysAdmin = authProfile.user?.is_sys_admin;
                        if (!hasNoTeam || isSysAdmin) {
                            isLogged = true;
                            AuthStorage.set(authProfile);
                            setUserDetails(authProfile.user);
                        }
                    }
                } catch (err: any) {
                    console.error("fetchLoggedIn auth check failed:", err);
                }
                setLoggedIn(isLogged);
                setAuthInitialized(true);
            };

            fetchLoggedIn();
        }, []);

        if (!authInitialized) {
            return (
                <div
                    style={{
                        display: "flex",
                        justifyContent: "center",
                        alignItems: "center",
                        height: "100vh",
                        width: "100vw",
                        background: "linear-gradient(135deg, #0f172a 0%, #1e293b 40%, #0f172a 100%)",
                        color: "#6366f1"
                    }}
                >
                    <CircularProgress color="inherit" />
                </div>
            );
        }

        return (
            <MsalProvider instance={msalInstance}>
                <LoginContext.Provider
                    value={{
                        loggedIn,
                        setLoggedIn,
                        userDetails,
                        setUserDetails,
                        isUserLoading,
                        setIsUserLoading,
                        isWaitingApprove,
                        setIsWaitingApprove,
                        isSwitchTeam,
                        setIsSwitchTeam
                    }}
                >
                    {requireLogin && !loggedIn ? (
                        <LoginPage onLoginSuccess={() => setLoggedIn(true)} />
                    ) : (
                        <Layout />
                    )}
                </LoginContext.Provider>
            </MsalProvider>
        );
    } else {
        return (
            <LoginContext.Provider
                value={{
                    loggedIn,
                    setLoggedIn,
                    userDetails,
                    setUserDetails,
                    isUserLoading,
                    setIsUserLoading,
                    isWaitingApprove,
                    setIsWaitingApprove,
                    isSwitchTeam,
                    setIsSwitchTeam
                }}
            >
                <Layout />
            </LoginContext.Provider>
        );
    }
};

export default LayoutWrapper;
