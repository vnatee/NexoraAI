// Refactored from https://github.com/Azure-Samples/ms-identity-javascript-react-tutorial/blob/main/1-Authentication/1-sign-in/SPA/src/authConfig.js

import { AccountInfo, InteractionRequiredAuthError, IPublicClientApplication } from "@azure/msal-browser";

const appServicesAuthTokenUrl = ".auth/me";
const appServicesAuthTokenRefreshUrl = ".auth/refresh";
const appServicesAuthLogoutUrl = ".auth/logout?post_logout_redirect_uri=/";

interface AppServicesToken {
    id_token: string;
    access_token: string;
    user_claims: Record<string, any>;
    expires_on: string;
}

interface AuthSetup {
    // Set to true if login elements should be shown in the UI
    useLogin: boolean;
    // Set to true if access control is enforced by the application
    requireAccessControl: boolean;
    // Set to true if the application allows unauthenticated access (only applies for documents without access control)
    enableUnauthenticatedAccess: boolean;
    localAuthenticationEnabled: boolean;
    entraAuthenticationEnabled: boolean;
    oidcAuthenticationEnabled: boolean;
    oidcDisplayName: string;
    oidcProviders: Array<{ id: string; display_name: string }>;
    samlAuthenticationEnabled: boolean;
    samlProviders: Array<{ id: string; display_name: string }>;
    localBootstrapRequired: boolean;
    /**
     * Configuration object to be passed to MSAL instance on creation.
     * For a full list of MSAL.js configuration parameters, visit:
     * https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-browser/docs/configuration.md
     */
    msalConfig: {
        auth: {
            clientId: string; // Client app id used for login
            authority: string; // Directory to use for login https://learn.microsoft.com/entra/identity-platform/msal-client-application-configuration#authority
            redirectUri: string; // Points to window.location.origin. You must register this URI on Azure Portal/App Registration.
            postLogoutRedirectUri: string; // Indicates the page to navigate after logout.
            navigateToLoginRequestUrl: boolean; // If "true", will navigate back to the original request location before processing the auth code response.
        };
        cache: {
            cacheLocation: string; // Configures cache location. "sessionStorage" is more secure, but "localStorage" gives you SSO between tabs.
            storeAuthStateInCookie: boolean; // Set this to "true" if you are having issues on IE11 or Edge
        };
    };
    loginRequest: {
        /**
         * Scopes you add here will be prompted for user consent during sign-in.
         * By default, MSAL.js will add OIDC scopes (openid, profile, email) to any login request.
         * For more information about OIDC scopes, visit:
         * https://learn.microsoft.com/entra/identity-platform/permissions-consent-overview#openid-connect-scopes
         */
        scopes: Array<string>;
    };
    tokenRequest: {
        scopes: Array<string>;
    };
}

// Default config for no-auth mode
const defaultAuthSetup: AuthSetup = {
    useLogin: true,
    requireAccessControl: false,
    enableUnauthenticatedAccess: true,
    localAuthenticationEnabled: false,
    entraAuthenticationEnabled: true,
    oidcAuthenticationEnabled: false,
    oidcDisplayName: "Enterprise SSO",
    oidcProviders: [],
    samlAuthenticationEnabled: false,
    samlProviders: [],
    localBootstrapRequired: false,
    msalConfig: {
        auth: {
            clientId: "",
            authority: "",
            redirectUri: "/",
            postLogoutRedirectUri: "/",
            navigateToLoginRequestUrl: false
        },
        cache: {
            cacheLocation: "localStorage", // localStorage คงข้าม refresh/tab ได้ / sessionStorage หายทุก refresh
            storeAuthStateInCookie: false
        }
    },
    loginRequest: {
        scopes: []
    },
    tokenRequest: {
        scopes: []
    }
};

// Fetch the auth setup JSON data from the API if not already cached
async function fetchAuthSetup(): Promise<AuthSetup> {
    try {
        const response = await fetch("/auth_setup");
        if (!response.ok) {
            throw new Error(`auth setup response was not ok: ${response.status}`);
        }
        return await response.json();
    } catch {
        return defaultAuthSetup;
    }
}

const authSetup = await fetchAuthSetup();

export const useLogin = authSetup.useLogin;

export const requireAccessControl = authSetup.requireAccessControl;

export const enableUnauthenticatedAccess = authSetup.enableUnauthenticatedAccess;
export const localAuthenticationEnabled = authSetup.localAuthenticationEnabled;
export const entraAuthenticationEnabled = authSetup.entraAuthenticationEnabled;
export const oidcAuthenticationEnabled = authSetup.oidcAuthenticationEnabled;
export const oidcDisplayName = authSetup.oidcDisplayName || "Enterprise SSO";
export const oidcProviders = authSetup.oidcProviders?.length
    ? authSetup.oidcProviders
    : authSetup.oidcAuthenticationEnabled
      ? [{ id: "legacy", display_name: authSetup.oidcDisplayName || "Enterprise SSO" }]
      : [];
export const samlAuthenticationEnabled = authSetup.samlAuthenticationEnabled;
export const samlProviders = authSetup.samlProviders || [];
export const localBootstrapRequired = authSetup.localBootstrapRequired;

export const requireLogin = true; // Always require login

const LOCAL_TOKEN_KEY = "nexora.localAccessToken";
const LOCAL_USERNAME_KEY = "nexora.localUsername";
const OIDC_TOKEN_KEY = "nexora.oidcAccessToken";
const OIDC_USERNAME_KEY = "nexora.oidcUsername";
const SAML_TOKEN_KEY = "nexora.samlAccessToken";
const SAML_USERNAME_KEY = "nexora.samlUsername";

export const getLocalToken = (): string | undefined => sessionStorage.getItem(LOCAL_TOKEN_KEY) || undefined;

export const isUsingLocalLogin = (): boolean => Boolean(getLocalToken());
export const getOidcToken = (): string | undefined => sessionStorage.getItem(OIDC_TOKEN_KEY) || undefined;
export const isUsingOidcLogin = (): boolean => Boolean(getOidcToken());
export const getSamlToken = (): string | undefined => sessionStorage.getItem(SAML_TOKEN_KEY) || undefined;
export const isUsingSamlLogin = (): boolean => Boolean(getSamlToken());

export const oidcLogin = async (providerId: string): Promise<void> => {
    const popup = window.open("about:blank", "nexora-oidc-login", "popup=yes,width=560,height=720");
    if (!popup) throw new Error("Allow pop-ups to sign in with Enterprise SSO.");
    const response = await fetch("/auth/oidc/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider_id: providerId })
    });
    const data = await response.json();
    if (!response.ok || !data.authorization_url) {
        popup.close();
        throw new Error(data.error || "Unable to start OIDC sign-in");
    }
    await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => finish(new Error("OIDC sign-in timed out.")), 120000);
        const finish = (error?: Error) => {
            window.clearTimeout(timeout);
            window.removeEventListener("message", receive);
            if (!popup.closed) popup.close();
            if (error) reject(error); else resolve();
        };
        const receive = (event: MessageEvent) => {
            if (event.origin !== window.location.origin || event.source !== popup || event.data?.type !== "nexora:oidc") return;
            if (event.data.error) return finish(new Error(String(event.data.error)));
            if (!event.data.access_token) return finish(new Error("OIDC sign-in did not return a session."));
            sessionStorage.removeItem(LOCAL_TOKEN_KEY);
            sessionStorage.removeItem(LOCAL_USERNAME_KEY);
            sessionStorage.removeItem(SAML_TOKEN_KEY);
            sessionStorage.removeItem(SAML_USERNAME_KEY);
            sessionStorage.setItem(OIDC_TOKEN_KEY, String(event.data.access_token));
            sessionStorage.setItem(OIDC_USERNAME_KEY, String(event.data.username || ""));
            finish();
        };
        window.addEventListener("message", receive);
        popup.location.href = String(data.authorization_url);
    });
};

export const routeOidcProvider = async (email: string): Promise<string> => {
    const response = await fetch("/auth/oidc/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email })
    });
    const data = await response.json();
    if (!response.ok || !data.provider_id) throw new Error(data.error || "No SSO provider matches this email.");
    return String(data.provider_id);
};

export const oidcLogout = async (): Promise<void> => {
    const token = getOidcToken();
    if (token) {
        await fetch("/auth/oidc/logout", { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => undefined);
    }
    sessionStorage.removeItem(OIDC_TOKEN_KEY);
    sessionStorage.removeItem(OIDC_USERNAME_KEY);
};

export const samlLogin = async (providerId: string): Promise<void> => {
    const popup = window.open("about:blank", "nexora-saml-login", "popup=yes,width=720,height=760");
    if (!popup) throw new Error("Allow pop-ups to sign in with SAML SSO.");
    const response = await fetch(`/auth/saml/${encodeURIComponent(providerId)}/start`, { method: "POST" });
    const data = await response.json();
    if (!response.ok || !data.authorization_url) {
        popup.close();
        throw new Error(data.error || "Unable to start SAML sign-in");
    }
    await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => finish(new Error("SAML sign-in timed out.")), 120000);
        const finish = (error?: Error) => {
            window.clearTimeout(timeout);
            window.removeEventListener("message", receive);
            if (!popup.closed) popup.close();
            if (error) reject(error); else resolve();
        };
        const receive = (event: MessageEvent) => {
            if (event.origin !== window.location.origin || event.source !== popup || event.data?.type !== "nexora:saml") return;
            if (event.data.error) return finish(new Error(String(event.data.error)));
            if (!event.data.access_token) return finish(new Error("SAML sign-in did not return a session."));
            sessionStorage.removeItem(LOCAL_TOKEN_KEY);
            sessionStorage.removeItem(LOCAL_USERNAME_KEY);
            sessionStorage.removeItem(OIDC_TOKEN_KEY);
            sessionStorage.removeItem(OIDC_USERNAME_KEY);
            sessionStorage.setItem(SAML_TOKEN_KEY, String(event.data.access_token));
            sessionStorage.setItem(SAML_USERNAME_KEY, String(event.data.username || ""));
            finish();
        };
        window.addEventListener("message", receive);
        popup.location.href = String(data.authorization_url);
    });
};

export const samlLogout = async (): Promise<void> => {
    const token = getSamlToken();
    if (token) {
        await fetch("/auth/saml/logout", { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => undefined);
    }
    sessionStorage.removeItem(SAML_TOKEN_KEY);
    sessionStorage.removeItem(SAML_USERNAME_KEY);
};

export const localLogin = async (username: string, password: string): Promise<void> => {
    const response = await fetch("/auth/local/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Local sign-in failed");
    sessionStorage.removeItem(OIDC_TOKEN_KEY);
    sessionStorage.removeItem(OIDC_USERNAME_KEY);
    sessionStorage.removeItem(SAML_TOKEN_KEY);
    sessionStorage.removeItem(SAML_USERNAME_KEY);
    sessionStorage.setItem(LOCAL_TOKEN_KEY, data.access_token);
    sessionStorage.setItem(LOCAL_USERNAME_KEY, data.username || username);
};

export const bootstrapLocalAdmin = async (payload: Record<string, string>, bootstrapToken: string): Promise<void> => {
    const response = await fetch("/auth/local/bootstrap", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Bootstrap-Token": bootstrapToken },
        body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Local administrator setup failed");
};

export const localLogout = async (): Promise<void> => {
    const token = getLocalToken();
    if (token) {
        await fetch("/auth/local/logout", { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => undefined);
    }
    sessionStorage.removeItem(LOCAL_TOKEN_KEY);
    sessionStorage.removeItem(LOCAL_USERNAME_KEY);
};

export const validateLocalSession = async (): Promise<boolean> => {
    const token = getLocalToken();
    if (!token) return false;
    const response = await fetch("/auth/local/me", { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) {
        sessionStorage.removeItem(LOCAL_TOKEN_KEY);
        sessionStorage.removeItem(LOCAL_USERNAME_KEY);
        return false;
    }
    return true;
};

/**
 * Configuration object to be passed to MSAL instance on creation.
 * For a full list of MSAL.js configuration parameters, visit:
 * https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-browser/docs/configuration.md
 */
export const msalConfig = authSetup.msalConfig;

/**
 * Scopes you add here will be prompted for user consent during sign-in.
 * By default, MSAL.js will add OIDC scopes (openid, profile, email) to any login request.
 * For more information about OIDC scopes, visit:
 * https://learn.microsoft.com/entra/identity-platform/permissions-consent-overview#openid-connect-scopes
 */
export const loginRequest = authSetup.loginRequest;

const tokenRequest = authSetup.tokenRequest;

// Build an absolute redirect URI using the current window's location and the relative redirect URI from auth setup
export const getRedirectUri = () => {
    return window.location.origin + authSetup.msalConfig.auth.redirectUri;
};

// Cache the app services token if it's available
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/this#global_context
declare global {
    var cachedAppServicesToken: AppServicesToken | null;
}
globalThis.cachedAppServicesToken = null;

/**
 * Retrieves an access token if the user is logged in using app services authentication.
 * Checks if the current token is expired and fetches a new token if necessary.
 * Returns null if the app doesn't support app services authentication.
 *
 * @returns {Promise<AppServicesToken | null>} A promise that resolves to an AppServicesToken if the user is authenticated, or null if authentication is not supported or fails.
 */
const getAppServicesToken = (): Promise<AppServicesToken | null> => {
    const checkNotExpired = (appServicesToken: AppServicesToken) => {
        const currentDate = new Date();
        const expiresOnDate = new Date(appServicesToken.expires_on);
        return expiresOnDate > currentDate;
    };

    if (globalThis.cachedAppServicesToken && checkNotExpired(globalThis.cachedAppServicesToken)) {
        return Promise.resolve(globalThis.cachedAppServicesToken);
    }

    const getAppServicesTokenFromMe: () => Promise<AppServicesToken | null> = () => {
        return fetch(appServicesAuthTokenUrl).then(r => {
            if (r.ok) {
                return r.json().then(json => {
                    if (json.length > 0) {
                        return {
                            id_token: json[0]["id_token"] as string,
                            access_token: json[0]["access_token"] as string,
                            user_claims: json[0]["user_claims"].reduce((acc: Record<string, any>, item: Record<string, any>) => {
                                acc[item.typ] = item.val;
                                return acc;
                            }, {}) as Record<string, any>,
                            expires_on: json[0]["expires_on"] as string
                        } as AppServicesToken;
                    }

                    return null;
                });
            }

            return null;
        });
    };

    return getAppServicesTokenFromMe().then(token => {
        if (token) {
            if (checkNotExpired(token)) {
                globalThis.cachedAppServicesToken = token;
                return token;
            }

            return fetch(appServicesAuthTokenRefreshUrl).then(r => {
                if (r.ok) {
                    return getAppServicesTokenFromMe();
                }
                return null;
            });
        }

        return null;
    });
};

export const isUsingAppServicesLogin = (await getAppServicesToken()) != null;

// Sign out of app services
// Learn more at https://learn.microsoft.com/azure/app-service/configure-authentication-customize-sign-in-out#sign-out-of-a-session
export const appServicesLogout = () => {
    window.location.href = appServicesAuthLogoutUrl;
};

/**
 * Determines if the user is logged in either via the MSAL public client application or the app services login.
 * @param {IPublicClientApplication | undefined} client - The MSAL public client application instance, or undefined if not available.
 * @returns {Promise<boolean>} A promise that resolves to true if the user is logged in, false otherwise.
 */
export const checkLoggedIn = async (client: IPublicClientApplication | undefined): Promise<boolean> => {
    if (getLocalToken() || getOidcToken() || getSamlToken()) return true;
    if (client) {
        const activeAccount = client.getActiveAccount();
        if (activeAccount) {
            return true;
        }
    }

    const appServicesToken = await getAppServicesToken();
    if (appServicesToken) {
        return true;
    }

    return false;
};

// Get an access token for use with the API server.
// ID token received when logging in may not be used for this purpose because it has the incorrect audience
// Use the access token from app services login if available
// export const getToken = async (client: IPublicClientApplication): Promise<string | undefined> => {
//     const appServicesToken = await getAppServicesToken();
//     if (appServicesToken) {
//         return Promise.resolve(appServicesToken.access_token);
//     }

//     return client
//         .acquireTokenSilent({
//             ...tokenRequest,
//             redirectUri: getRedirectUri()
//         })
//         .then(r => r.accessToken)
//         .catch(error => {
//             console.log(error);
//             return undefined;
//         });
// };

// export const getToken = async (client: IPublicClientApplication): Promise<string | undefined> => {
//     try {
//         // 1) ลองเอาจาก AppServices token ก่อน
//         const appServicesToken = await getAppServicesToken();
//         if (appServicesToken) {
//             return appServicesToken.access_token;
//         }

//         // 2) ขอ token แบบ silent
//         const response = await client.acquireTokenSilent({
//             ...tokenRequest,
//             redirectUri: getRedirectUri(),
//             account: client.getActiveAccount() ?? undefined
//         });

//         return response.accessToken;
//     } catch (error: any) {
//         console.error("getToken failed:", error);

//         // 👉 token หมดอายุ / ต้องให้ user re-login
//         if (error instanceof InteractionRequiredAuthError) {
//             // จะเลือก:
//             // 1. auto popup login → UX ดี
//             // 2. return undefined → ให้ component ไปจัดการ logout เอง
//             try {
//                 const response = await client.acquireTokenPopup({
//                     ...tokenRequest,
//                     redirectUri: getRedirectUri()
//                 });
//                 return response.accessToken;
//             } catch (popupError) {
//                 console.error("Silent & popup both failed:", popupError);
//                 return undefined;
//             }
//         }

//         // ❌ กรณีอื่น
//         return undefined;
//     }
// };

export const getToken = async (client: IPublicClientApplication): Promise<string | undefined> => {
    try {
        const localToken = getLocalToken();
        if (localToken) return localToken;
        const oidcToken = getOidcToken();
        if (oidcToken) return oidcToken;
        const samlToken = getSamlToken();
        if (samlToken) return samlToken;
        const appServicesToken = await getAppServicesToken();
        if (appServicesToken) {
            return appServicesToken.access_token;
        }

        const response = await client.acquireTokenSilent({
            ...tokenRequest,
            redirectUri: getRedirectUri(),
            account: client.getActiveAccount() ?? undefined
        });

        return response.accessToken;
    } catch (error: any) {
        // console.error("getToken failed:", error);

        if (error instanceof InteractionRequiredAuthError) {
            // 👉 ไม่ popup auto ตอน refresh
            return undefined;
        }

        return undefined;
    }
};

/**
 * Retrieves the username of the active account.
 * If no active account is found, attempts to retrieve the username from the app services login token if available.
 * @param {IPublicClientApplication} client - The MSAL public client application instance.
 * @returns {Promise<string | null>} The username of the active account, or null if no username is found.
 */
export const getUsername = async (client: IPublicClientApplication): Promise<string | null> => {
    const localUsername = sessionStorage.getItem(LOCAL_USERNAME_KEY);
    if (localUsername) return localUsername;
    const oidcUsername = sessionStorage.getItem(OIDC_USERNAME_KEY);
    if (oidcUsername) return oidcUsername;
    const samlUsername = sessionStorage.getItem(SAML_USERNAME_KEY);
    if (samlUsername) return samlUsername;
    const activeAccount = client.getActiveAccount();
    if (activeAccount) {
        return activeAccount.username;
    }

    const appServicesToken = await getAppServicesToken();
    if (appServicesToken?.user_claims) {
        return appServicesToken.user_claims.preferred_username;
    }

    return null;
};
export const getUsernameTest = async (client: IPublicClientApplication): Promise<AccountInfo | null> => {
    const activeAccount = client.getActiveAccount();
    if (activeAccount) {
        return activeAccount;
    }

    const appServicesToken = await getAppServicesToken();
    if (appServicesToken?.user_claims) {
        return appServicesToken.user_claims.preferred_username;
    }

    return null;
};
/**
 * Retrieves the token claims of the active account.
 * If no active account is found, attempts to retrieve the token claims from the app services login token if available.
 * @param {IPublicClientApplication} client - The MSAL public client application instance.
 * @returns {Promise<Record<string, unknown> | undefined>} A promise that resolves to the token claims of the active account, the user claims from the app services login token, or undefined if no claims are found.
 */
export const getTokenClaims = async (client: IPublicClientApplication): Promise<Record<string, unknown> | undefined> => {
    const activeAccount = client.getActiveAccount();
    if (activeAccount) {
        return activeAccount.idTokenClaims;
    }

    const appServicesToken = await getAppServicesToken();
    if (appServicesToken) {
        return appServicesToken.user_claims;
    }

    return undefined;
};
