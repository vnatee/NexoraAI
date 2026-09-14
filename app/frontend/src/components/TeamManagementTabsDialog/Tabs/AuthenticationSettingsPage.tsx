import { Alert, Button, CircularProgress, Divider, FormControlLabel, Stack, Switch, TextField, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";

import { getAuthenticationSettings, resetAuthenticationSettings, updateAuthenticationSettings } from "../../../api";
import { AuthenticationSettings } from "../../../api/models";
import { getToken } from "../../../authConfig";
import { OIDCProviderManagement } from "../../OIDCProviderManagement/OIDCProviderManagement";
import { SAMLProviderManagement } from "../../SAMLProviderManagement/SAMLProviderManagement";

const emptySettings: AuthenticationSettings = {
    local_enabled: false, entra_enabled: false, tenant_id: "", server_app_id: "", client_app_id: "", has_client_secret: false,
    oidc_enabled: false, oidc_display_name: "Enterprise SSO", oidc_issuer: "", oidc_client_id: "",
    oidc_token_auth_method: "client_secret_basic", oidc_has_client_secret: false, oidc_jit_enabled: false, oidc_allowed_domains: []
};

export function AuthenticationSettingsPage() {
    const { instance } = useMsal();
    const [settings, setSettings] = useState<AuthenticationSettings>(emptySettings);
    const [clientSecret, setClientSecret] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    useEffect(() => {
        void (async () => {
            try {
                const token = await getToken(instance);
                if (!token) throw new Error("Authentication required");
                setSettings(await getAuthenticationSettings(token));
            } catch (reason: any) {
                setError(reason?.message || "Unable to load settings");
            } finally {
                setLoading(false);
            }
        })();
    }, [instance]);

    const save = async () => {
        setSaving(true); setError(""); setMessage("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            const updated = await updateAuthenticationSettings({ ...settings, client_secret: clientSecret || undefined }, token);
            setSettings({ ...updated, local_enabled: settings.local_enabled });
            setClientSecret("");
            setMessage("Microsoft Entra settings saved. Reload the page before testing sign-in.");
        } catch (reason: any) {
            setError(reason?.message || "Unable to save settings");
        } finally {
            setSaving(false);
        }
    };

    const restoreEnvironment = async () => {
        setSaving(true); setError("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            await resetAuthenticationSettings(token);
            setMessage("Managed Entra settings removed. Reload the page to use environment configuration.");
        } catch (reason: any) {
            setError(reason?.message || "Unable to restore environment settings");
        } finally {
            setSaving(false);
        }
    };

    const disableLegacyOidc = async () => {
        setSaving(true); setError(""); setMessage("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            const updated = await updateAuthenticationSettings({ ...settings, oidc_enabled: false }, token);
            setSettings({ ...updated, local_enabled: settings.local_enabled });
            setMessage("Legacy OIDC connection disabled. Existing managed connections are unchanged.");
        } catch (reason: any) {
            setError(reason?.message || "Unable to disable legacy OIDC connection");
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <CircularProgress />;

    return <Stack spacing={3} sx={{ maxWidth: 980 }}>
        <Typography variant="h6">Authentication</Typography>
        <Alert severity="info">Local authentication is controlled by deployment setting LOCAL_AUTH_ENABLED. Keep a tested Local administrator as the break-glass account before changing enterprise authentication.</Alert>
        {error && <Alert severity="error">{error}</Alert>}
        {message && <Alert severity="success">{message}</Alert>}

        <Stack spacing={2}>
            <Typography variant="h6">Microsoft Entra ID</Typography>
            <FormControlLabel control={<Switch checked={settings.entra_enabled} onChange={event => setSettings({ ...settings, entra_enabled: event.target.checked })} />} label="Enable Microsoft Entra ID" />
            <TextField label="Tenant ID" value={settings.tenant_id} onChange={event => setSettings({ ...settings, tenant_id: event.target.value })} disabled={!settings.entra_enabled} />
            <TextField label="API application (server) ID" value={settings.server_app_id} onChange={event => setSettings({ ...settings, server_app_id: event.target.value })} disabled={!settings.entra_enabled} />
            <TextField label="SPA application (client) ID" value={settings.client_app_id} onChange={event => setSettings({ ...settings, client_app_id: event.target.value })} disabled={!settings.entra_enabled} />
            <TextField label={settings.has_client_secret ? "API client secret (stored; enter to replace)" : "API client secret"} type="password" value={clientSecret} onChange={event => setClientSecret(event.target.value)} disabled={!settings.entra_enabled} autoComplete="new-password" />
            <Typography variant="body2" color="text.secondary">Configuration source: {settings.source || "managed"}. Client secrets are never returned to the browser.</Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                <Button variant="contained" onClick={() => void save()} disabled={saving}>{saving ? "Saving…" : "Save Entra settings"}</Button>
                {settings.source === "managed" && <Button onClick={() => void restoreEnvironment()} disabled={saving}>Use environment settings</Button>}
            </Stack>
        </Stack>

        {settings.oidc_issuer && <><Divider /><Alert severity="warning" action={settings.oidc_enabled ? <Button color="inherit" size="small" onClick={() => void disableLegacyOidc()} disabled={saving}>Disable legacy</Button> : undefined}>A legacy single-provider OIDC connection is configured as <strong>{settings.oidc_display_name}</strong> ({settings.oidc_enabled ? "enabled" : "disabled"}). Create a managed connection before retiring it; an enabled legacy domain cannot be reused.</Alert></>}
        <Divider />
        <OIDCProviderManagement callbackUrl={settings.oidc_callback_url || `${window.location.origin}/auth/oidc/callback`} />
        <Divider />
        <SAMLProviderManagement />
    </Stack>;
}
