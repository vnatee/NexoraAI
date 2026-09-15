import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import {
    Alert,
    Button,
    Card,
    CardActions,
    CardContent,
    Chip,
    Dialog,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    IconButton,
    MenuItem,
    Stack,
    Switch,
    TextField,
    Typography
} from "@mui/material";
import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";

import {
    createOidcProvider,
    deleteOidcProvider,
    listOidcProviders,
    testOidcAuthenticationSettings,
    updateOidcProvider
} from "../../api";
import { OIDCProvider, OIDCProviderPayload } from "../../api/models";
import { getToken } from "../../authConfig";

const emptyProvider: OIDCProviderPayload = {
    enabled: false,
    display_name: "",
    issuer: "",
    client_id: "",
    client_secret: "",
    token_auth_method: "client_secret_basic",
    jit_enabled: true,
    allowed_domains: []
};

export function OIDCProviderManagement({ callbackUrl }: { callbackUrl: string }) {
    const { instance } = useMsal();
    const [providers, setProviders] = useState<OIDCProvider[]>([]);
    const [editing, setEditing] = useState<OIDCProvider | null>(null);
    const [form, setForm] = useState<OIDCProviderPayload>(emptyProvider);
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");

    const load = async () => {
        const token = await getToken(instance);
        if (!token) throw new Error("Authentication required");
        setProviders(await listOidcProviders(token));
    };

    useEffect(() => {
        void load().catch(reason => setError(reason?.message || "Unable to load OIDC connections"));
    }, [instance]);

    const beginCreate = () => {
        setEditing(null);
        setForm({ ...emptyProvider, allowed_domains: [] });
        setError("");
        setOpen(true);
    };

    const beginEdit = (provider: OIDCProvider) => {
        setEditing(provider);
        setForm({
            enabled: provider.enabled,
            display_name: provider.display_name,
            issuer: provider.issuer,
            client_id: provider.client_id,
            client_secret: "",
            token_auth_method: provider.token_auth_method,
            jit_enabled: provider.jit_enabled,
            allowed_domains: [...provider.allowed_domains]
        });
        setError("");
        setOpen(true);
    };

    const save = async () => {
        setBusy(true);
        setError("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            if (editing) await updateOidcProvider(editing.id, form, token);
            else await createOidcProvider(form, token);
            await load();
            setOpen(false);
            setMessage(editing ? "OIDC connection updated." : "OIDC connection created.");
        } catch (reason: any) {
            setError(reason?.message || "Unable to save OIDC connection");
        } finally {
            setBusy(false);
        }
    };

    const testDiscovery = async () => {
        setBusy(true);
        setError("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            await testOidcAuthenticationSettings(form.issuer, token);
            setMessage("OIDC discovery succeeded.");
        } catch (reason: any) {
            setError(reason?.message || "OIDC discovery failed");
        } finally {
            setBusy(false);
        }
    };

    const remove = async (provider: OIDCProvider) => {
        if (!window.confirm(`Delete OIDC connection “${provider.display_name}”? Active sessions from this provider will be revoked.`)) return;
        setBusy(true);
        setError("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            await deleteOidcProvider(provider.id, token);
            await load();
            setMessage("OIDC connection deleted and its active sessions revoked.");
        } catch (reason: any) {
            setError(reason?.message || "Unable to delete OIDC connection");
        } finally {
            setBusy(false);
        }
    };

    const managedProviders = providers.filter(provider => !provider.legacy);
    return <Stack spacing={2}>
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "stretch", sm: "center" }} gap={1}>
            <div>
                <Typography variant="h6">OpenID Connect connections</Typography>
                <Typography variant="body2" color="text.secondary">Add one connection per identity provider or tenant. Email domains route users to the correct provider.</Typography>
            </div>
            <Button variant="contained" startIcon={<AddIcon />} onClick={beginCreate}>Add OIDC connection</Button>
        </Stack>
        <Alert severity="info">Supported examples include Okta, Keycloak, Auth0, Google Workspace and Ping Identity. Local authentication must remain available as the break-glass administrator path.</Alert>
        {error && !open && <Alert severity="error">{error}</Alert>}
        {message && <Alert severity="success" onClose={() => setMessage("")}>{message}</Alert>}
        {managedProviders.length === 0 ? <Alert severity="info">No managed OIDC connections have been added.</Alert> : <Stack direction="row" flexWrap="wrap" gap={2}>
            {managedProviders.map(provider => <Card key={provider.id} variant="outlined" sx={{ width: { xs: "100%", md: 360 } }}>
                <CardContent>
                    <Stack direction="row" justifyContent="space-between" alignItems="center" gap={1}>
                        <Typography variant="subtitle1" fontWeight={700}>{provider.display_name}</Typography>
                        <Chip size="small" color={provider.enabled ? "success" : "default"} label={provider.enabled ? "Enabled" : "Disabled"} />
                    </Stack>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1, wordBreak: "break-all" }}>{provider.issuer}</Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>{provider.allowed_domains.length ? provider.allowed_domains.join(", ") : "No routing domains"}</Typography>
                    <Typography variant="caption" color="text.secondary">{provider.jit_enabled ? "JIT provisioning enabled" : "Pre-provisioned users only"}</Typography>
                </CardContent>
                <CardActions>
                    <Button startIcon={<EditOutlinedIcon />} onClick={() => beginEdit(provider)}>Edit</Button>
                    <Button color="error" startIcon={<DeleteOutlineIcon />} onClick={() => void remove(provider)} disabled={busy}>Delete</Button>
                </CardActions>
            </Card>)}
        </Stack>}

        <Dialog open={open} fullWidth maxWidth="md" disableEscapeKeyDown onClose={(_event, reason) => { if (reason !== "backdropClick") setOpen(false); }}>
            <DialogTitle sx={{ pr: 7 }}>{editing ? "Edit OIDC connection" : "Add OIDC connection"}
                <IconButton aria-label="Close" onClick={() => setOpen(false)} sx={{ position: "absolute", right: 12, top: 12 }}><CloseIcon /></IconButton>
            </DialogTitle>
            <DialogContent dividers>
                <Stack spacing={2} sx={{ pt: 1 }}>
                    {error && <Alert severity="error">{error}</Alert>}
                    <FormControlLabel control={<Switch checked={form.enabled} onChange={event => setForm({ ...form, enabled: event.target.checked })} />} label="Enable this connection" />
                    <TextField label="Connection / sign-in name" value={form.display_name} onChange={event => setForm({ ...form, display_name: event.target.value })} helperText="Example: Acme Workforce SSO" required />
                    <TextField label="Issuer URL" value={form.issuer} onChange={event => setForm({ ...form, issuer: event.target.value })} placeholder="https://id.example.com/realms/company" required />
                    <TextField label="Client ID" value={form.client_id} onChange={event => setForm({ ...form, client_id: event.target.value })} required />
                    <TextField label={editing?.has_client_secret ? "Client secret (stored; enter to replace)" : "Client secret"} type="password" value={form.client_secret || ""} onChange={event => setForm({ ...form, client_secret: event.target.value })} autoComplete="new-password" />
                    <TextField select label="Token endpoint authentication" value={form.token_auth_method} onChange={event => setForm({ ...form, token_auth_method: event.target.value as OIDCProviderPayload["token_auth_method"] })}>
                        <MenuItem value="client_secret_basic">Client secret basic (recommended)</MenuItem>
                        <MenuItem value="client_secret_post">Client secret post</MenuItem>
                    </TextField>
                    <TextField label="Redirect / callback URI" value={callbackUrl} InputProps={{ readOnly: true }} helperText="Register this exact URI in the identity provider." />
                    <TextField label="Allowed email domains" value={form.allowed_domains.join(", ")} onChange={event => setForm({ ...form, allowed_domains: event.target.value.split(",").map(item => item.trim()).filter(Boolean) })} placeholder="example.com, subsidiary.example" helperText="Also used to route work-email sign-in. A domain can belong to only one enabled connection." />
                    <FormControlLabel control={<Switch checked={form.jit_enabled} onChange={event => setForm({ ...form, jit_enabled: event.target.checked })} />} label="Create new users on first sign-in (JIT)" />
                    {form.jit_enabled && <Alert severity="warning">JIT users are created without System Admin rights and must be approved into a Team. Existing accounts are never linked by matching email automatically.</Alert>}
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        <Button variant="outlined" onClick={() => void testDiscovery()} disabled={busy || !form.issuer}>Test discovery</Button>
                        <Button variant="contained" onClick={() => void save()} disabled={busy}>{busy ? "Saving…" : editing ? "Save changes" : "Add connection"}</Button>
                    </Stack>
                </Stack>
            </DialogContent>
        </Dialog>
    </Stack>;
}
