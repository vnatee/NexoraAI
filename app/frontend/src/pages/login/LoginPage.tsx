import { useState } from "react";
import { useMsal } from "@azure/msal-react";
import { getRedirectUri, loginRequest, getToken } from "../../authConfig";
import styles from "./LoginPage.module.css";
import appLogo from "../../../public/insight_sphere_new.png";
import { RegisterDialog } from "../../components/LoginButton/RegisterDialog";
import { check_user_login, check_waiting_approve, register } from "../../api/api";
import { AuthStorage } from "../../utill/authStorage";
import { User } from "../../api/models";

interface LoginPageProps {
    onLoginSuccess: () => void;
}

const LoginPage = ({ onLoginSuccess }: LoginPageProps) => {
    const { instance } = useMsal();

    // ── Username / Password (skeleton — ยังไม่ submit จริง) ──
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");

    // ── AD Login ──
    const [adLoading, setAdLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState("");
    const [successMsg, setSuccessMsg] = useState("");

    // ── Register Dialog ──
    const [openRegisterDialog, setOpenRegisterDialog] = useState(false);
    const [pendingUser, setPendingUser] = useState<User | null>(null);

    const clearMsalCacheAndActive = () => {
        try {
            AuthStorage.clear();
            instance.setActiveAccount(null);

            // Clear localStorage keys starting with msal
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && (key.startsWith("msal.") || key.includes("login.windows.net"))) {
                    localStorage.removeItem(key);
                    i--; // Adjust index since we removed an item
                }
            }
            // Clear sessionStorage keys starting with msal
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                if (key && (key.startsWith("msal.") || key.includes("login.windows.net"))) {
                    sessionStorage.removeItem(key);
                    i--;
                }
            }
        } catch (e) {
            console.error("Failed to clear MSAL cache:", e);
        }
    };

    const handleAdLogin = async () => {
        setAdLoading(true);
        setErrorMsg("");
        setSuccessMsg("");
        try {
            const result = await instance.loginPopup({
                ...loginRequest,
                redirectUri: getRedirectUri()
            });
            const account = result?.account || instance.getAllAccounts()[0];
            if (account) instance.setActiveAccount(account);

            const token = await getToken(instance);
            if (!token) {
                setErrorMsg("Failed to retrieve authentication token.");
                clearMsalCacheAndActive();
                return;
            }

            try {
                const authProfile = await check_user_login(token);
                const hasNoTeam = !authProfile.teams || authProfile.teams.length === 0;
                const isSysAdmin = authProfile.user?.is_sys_admin;

                if (hasNoTeam && !isSysAdmin) {
                    const waitingResp = await check_waiting_approve(token);
                    if (waitingResp?.is_waiting) {
                        setErrorMsg("Your registration is pending approval. Please wait for an administrator to approve your account.");
                        clearMsalCacheAndActive();
                    } else {
                        setPendingUser(authProfile.user || {
                            email: account.username,
                            first_name: account.name?.split(" ")[0] || "",
                            last_name: account.name?.split(" ").slice(1).join(" ") || "",
                            employee_id: "",
                            tel: ""
                        });
                        setOpenRegisterDialog(true);
                    }
                } else {
                    AuthStorage.set(authProfile);
                    onLoginSuccess();
                }
            } catch (err: any) {
                if (err?.status === 404) {
                    try {
                        const waitingResp = await check_waiting_approve(token);
                        if (waitingResp?.is_waiting) {
                            setErrorMsg("Your registration is pending approval. Please wait for an administrator to approve your account.");
                        } else {
                            setPendingUser({
                                email: account.username,
                                first_name: account.name?.split(" ")[0] || "",
                                last_name: account.name?.split(" ").slice(1).join(" ") || "",
                                employee_id: "",
                                tel: ""
                            } as User);
                            setOpenRegisterDialog(true);
                        }
                    } catch (e) {
                        console.error(e);
                        setPendingUser({
                            email: account.username,
                            first_name: account.name?.split(" ")[0] || "",
                            last_name: account.name?.split(" ").slice(1).join(" ") || "",
                            employee_id: "",
                            tel: ""
                        } as User);
                        setOpenRegisterDialog(true);
                    }
                } else {
                    console.error("check_user_login error:", err);
                    setErrorMsg("Authentication failed. Please contact your administrator.");
                    clearMsalCacheAndActive();
                }
            }
        } catch (err) {
            console.error("AD login failed:", err);
            clearMsalCacheAndActive();
        } finally {
            setAdLoading(false);
        }
    };

    return (
        <div className={styles.loginPageWrapper}>
            <div className={styles.loginCard}>
                {/* ── Logo ── */}
                <div className={styles.logoContainer}>
                    <img src={appLogo} alt="InsightSphere" className={styles.logo} />
                    <h1 className={styles.title}>InsightSphere</h1>
                    <p className={styles.subtitle}>Sign in to your account</p>
                </div>

                {/* ── Notifications ── */}
                {errorMsg && <div className={styles.alertBox}>{errorMsg}</div>}
                {successMsg && <div className={styles.successBox}>{successMsg}</div>}

                {/* ── Username / Password Form (skeleton) ── */}
                <form
                    className={styles.form}
                    onSubmit={(e) => {
                        e.preventDefault();
                        // ยังไม่ทำ logic submit จริง
                    }}
                >
                    <div className={styles.inputGroup}>
                        <label className={styles.inputLabel} htmlFor="login-username">
                            Username
                        </label>
                        <input
                            id="login-username"
                            className={styles.input}
                            type="text"
                            placeholder="Enter your username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            autoComplete="username"
                        />
                    </div>

                    <div className={styles.inputGroup}>
                        <label className={styles.inputLabel} htmlFor="login-password">
                            Password
                        </label>
                        <input
                            id="login-password"
                            className={styles.input}
                            type="password"
                            placeholder="Enter your password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            autoComplete="current-password"
                        />
                    </div>

                    <button type="submit" className={styles.loginBtn} disabled>
                        Sign In
                        <span className={styles.comingSoonBadge}>Coming Soon</span>
                    </button>
                </form>

                {/* ── Divider ── */}
                <div className={styles.divider}>
                    <span className={styles.dividerLine} />
                    <span className={styles.dividerText}>or</span>
                    <span className={styles.dividerLine} />
                </div>

                {/* ── AD Login Button ── */}
                <button
                    className={`${styles.adLoginBtn} ${adLoading ? styles.adLoginBtnLoading : ""}`}
                    onClick={handleAdLogin}
                    disabled={adLoading}
                    type="button"
                >
                    {adLoading ? (
                        <>
                            <span className={styles.spinner} aria-hidden="true" />
                            Signing in...
                        </>
                    ) : (
                        <>
                            {/* Microsoft icon */}
                            <svg className={styles.adIcon} viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg">
                                <rect x="1" y="1" width="9" height="9" fill="#f25022" />
                                <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
                                <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
                                <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
                            </svg>
                            Sign in with Azure AD
                        </>
                    )}
                </button>

                {/* ── Footer ── */}
                <p className={styles.footer}>
                    © {new Date().getFullYear()} InsightSphere. All rights reserved.
                </p>
            </div>

            <RegisterDialog
                open={openRegisterDialog}
                user={pendingUser}
                onCancel={() => {
                    setOpenRegisterDialog(false);
                    clearMsalCacheAndActive();
                }}
                onSubmit={async ({ team_id, user }) => {
                    const token = await getToken(instance);
                    if (!token) return;

                    try {
                        await register(team_id, user, token);
                        setOpenRegisterDialog(false);
                        setSuccessMsg("Registration successful! Your account is pending approval.");
                        setErrorMsg("");
                    } catch (err) {
                        console.error("Registration failed:", err);
                        setErrorMsg("Registration failed. Please try again.");
                        setSuccessMsg("");
                    } finally {
                        clearMsalCacheAndActive();
                    }
                }}
            />
        </div>
    );
};

export default LoginPage;
