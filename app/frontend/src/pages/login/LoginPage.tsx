import { useState } from "react";
import { useMsal } from "@azure/msal-react";
import {
    bootstrapLocalAdmin,
    entraAuthenticationEnabled,
    getRedirectUri,
    getToken,
    localAuthenticationEnabled,
    localBootstrapRequired,
    localLogin,
    loginRequest,
    oidcAuthenticationEnabled,
    oidcProviders,
    oidcLogin,
    oidcLogout,
    isUsingOidcLogin,
    routeOidcProvider,
    samlAuthenticationEnabled,
    samlProviders,
    samlLogin,
    samlLogout,
    isUsingSamlLogin
} from "../../authConfig";
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

    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [localLoading, setLocalLoading] = useState(false);
    const [bootstrapToken, setBootstrapToken] = useState("");
    const [email, setEmail] = useState("");
    const [firstName, setFirstName] = useState("");
    const [lastName, setLastName] = useState("");

    // ── AD Login ──
    const [adLoading, setAdLoading] = useState(false);
    const [oidcLoading, setOidcLoading] = useState(false);
    const [samlLoading, setSamlLoading] = useState(false);
    const [workEmail, setWorkEmail] = useState("");
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

    const handleLocalSubmit = async () => {
        setLocalLoading(true);
        setErrorMsg("");
        setSuccessMsg("");
        try {
            if (localBootstrapRequired) {
                await bootstrapLocalAdmin(
                    { username, password, email, first_name: firstName, last_name: lastName },
                    bootstrapToken
                );
                setSuccessMsg("Local administrator created. You can now sign in.");
                window.setTimeout(() => window.location.reload(), 800);
                return;
            }
            await localLogin(username, password);
            const token = await getToken(instance);
            if (!token) throw new Error("Local session was not created");
            const authProfile = await check_user_login(token);
            AuthStorage.set(authProfile);
            onLoginSuccess();
        } catch (error: any) {
            setErrorMsg(error?.message || "Local sign-in failed.");
        } finally {
            setLocalLoading(false);
        }
    };

    const handleOidcLogin = async (providerId: string) => {
        setOidcLoading(true);
        setErrorMsg("");
        setSuccessMsg("");
        try {
            await oidcLogin(providerId);
            const token = await getToken(instance);
            if (!token) throw new Error("OIDC session was not created.");
            const authProfile = await check_user_login(token);
            const hasNoTeam = !authProfile.teams || authProfile.teams.length === 0;
            if (hasNoTeam && !authProfile.user?.is_sys_admin) {
                const waitingResp = await check_waiting_approve(token);
                if (waitingResp?.is_waiting) {
                    setErrorMsg("Your registration is pending approval. Please wait for an administrator to approve your account.");
                    await oidcLogout();
                } else {
                    setPendingUser(authProfile.user);
                    setOpenRegisterDialog(true);
                }
            } else {
                AuthStorage.set(authProfile);
                onLoginSuccess();
            }
        } catch (error: any) {
            setErrorMsg(error?.message || "Enterprise SSO sign-in failed.");
            await oidcLogout();
        } finally {
            setOidcLoading(false);
        }
    };

    const handleRoutedOidcLogin = async () => {
        setOidcLoading(true);
        setErrorMsg("");
        try {
            const providerId = await routeOidcProvider(workEmail);
            setOidcLoading(false);
            await handleOidcLogin(providerId);
        } catch (error: any) {
            setErrorMsg(error?.message || "No SSO provider matches this email.");
            setOidcLoading(false);
        }
    };

    const handleSamlLogin = async (providerId: string) => {
        setSamlLoading(true);
        setErrorMsg("");
        setSuccessMsg("");
        try {
            await samlLogin(providerId);
            const token = await getToken(instance);
            if (!token) throw new Error("SAML session was not created.");
            const authProfile = await check_user_login(token);
            const hasNoTeam = !authProfile.teams || authProfile.teams.length === 0;
            if (hasNoTeam && !authProfile.user?.is_sys_admin) {
                const waitingResp = await check_waiting_approve(token);
                if (waitingResp?.is_waiting) {
                    setErrorMsg("Your registration is pending approval. Please wait for an administrator to approve your account.");
                    await samlLogout();
                } else {
                    setPendingUser(authProfile.user);
                    setOpenRegisterDialog(true);
                }
            } else {
                AuthStorage.set(authProfile);
                onLoginSuccess();
            }
        } catch (error: any) {
            setErrorMsg(error?.message || "SAML SSO sign-in failed.");
            await samlLogout();
        } finally {
            setSamlLoading(false);
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

                {localAuthenticationEnabled && <form
                    className={styles.form}
                    onSubmit={(e) => {
                        e.preventDefault();
                        void handleLocalSubmit();
                    }}
                >
                    {localBootstrapRequired && (
                        <>
                            <p className={styles.setupHint}>Create the first local system administrator.</p>
                            <div className={styles.inputGroup}>
                                <label className={styles.inputLabel} htmlFor="bootstrap-token">Bootstrap token</label>
                                <input id="bootstrap-token" className={styles.input} type="password" value={bootstrapToken} onChange={e => setBootstrapToken(e.target.value)} autoComplete="off" />
                            </div>
                            <div className={styles.inputGroup}>
                                <label className={styles.inputLabel} htmlFor="local-email">Email</label>
                                <input id="local-email" className={styles.input} type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" />
                            </div>
                            <div className={styles.nameRow}>
                                <input className={styles.input} placeholder="First name" value={firstName} onChange={e => setFirstName(e.target.value)} />
                                <input className={styles.input} placeholder="Last name" value={lastName} onChange={e => setLastName(e.target.value)} />
                            </div>
                        </>
                    )}
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

                    <button type="submit" className={styles.loginBtn} disabled={localLoading || !username || password.length < 12 || (localBootstrapRequired && !bootstrapToken)}>
                        {localLoading ? "Working…" : localBootstrapRequired ? "Create administrator" : "Sign In"}
                    </button>
                </form>}

                {/* ── Divider ── */}
                {localAuthenticationEnabled && (entraAuthenticationEnabled || oidcAuthenticationEnabled || samlAuthenticationEnabled) && <div className={styles.divider}>
                    <span className={styles.dividerLine} />
                    <span className={styles.dividerText}>or</span>
                    <span className={styles.dividerLine} />
                </div>}

                {/* ── AD Login Button ── */}
                {entraAuthenticationEnabled && <button
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
                </button>}

                {oidcProviders.length > 1 && <div className={styles.form}>
                    <div className={styles.inputGroup}>
                        <label className={styles.inputLabel} htmlFor="sso-email">Work email</label>
                        <input id="sso-email" className={styles.input} type="email" value={workEmail} onChange={event => setWorkEmail(event.target.value)} autoComplete="email" placeholder="name@company.com" />
                    </div>
                    <button className={styles.adLoginBtn} onClick={() => void handleRoutedOidcLogin()} disabled={oidcLoading || !workEmail} type="button">Continue with company SSO</button>
                </div>}

                {oidcAuthenticationEnabled && oidcProviders.map(provider => <button
                    key={provider.id}
                    className={`${styles.adLoginBtn} ${oidcLoading ? styles.adLoginBtnLoading : ""}`}
                    onClick={() => void handleOidcLogin(provider.id)}
                    disabled={oidcLoading}
                    type="button"
                >
                    {oidcLoading ? (
                        <><span className={styles.spinner} aria-hidden="true" />Signing in...</>
                    ) : (
                        <>{`Sign in with ${provider.display_name}`}</>
                    )}
                </button>)}

                {samlAuthenticationEnabled && samlProviders.map(provider => <button
                    key={provider.id}
                    className={`${styles.adLoginBtn} ${samlLoading ? styles.adLoginBtnLoading : ""}`}
                    onClick={() => void handleSamlLogin(provider.id)}
                    disabled={samlLoading}
                    type="button"
                >
                    {samlLoading ? (
                        <><span className={styles.spinner} aria-hidden="true" />Signing in...</>
                    ) : (
                        <>{`Sign in with ${provider.display_name}`}</>
                    )}
                </button>)}

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
                    if (isUsingOidcLogin()) void oidcLogout();
                    if (isUsingSamlLogin()) void samlLogout();
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
                        if (isUsingOidcLogin()) await oidcLogout();
                        if (isUsingSamlLogin()) await samlLogout();
                        clearMsalCacheAndActive();
                    }
                }}
            />
        </div>
    );
};

export default LoginPage;
