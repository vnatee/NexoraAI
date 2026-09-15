import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
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
    Stack,
    Switch,
    TextField,
    Typography
} from "@mui/material";
import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";

import { createSamlProvider, deleteSamlProvider, listSamlProviders, testSamlProvider, updateSamlProvider } from "../../api";
import { SAMLProvider, SAMLProviderPayload } from "../../api/models";
import { getToken } from "../../authConfig";

const newProvider = (): SAMLProviderPayload => ({
    id: crypto.randomUUID(),
    enabled: false,
    display_name: "",
    entity_id: "",
    sso_url: "",
    x509_cert: "",
    email_attribute: "email",
    first_name_attribute: "firstName",
    last_name_attribute: "lastName",
    jit_enabled: true,
    allowed_domains: []
});

export function SAMLProviderManagement() {
    const { instance } = useMsal();
    const [providers, setProviders] = useState<SAMLProvider[]>([]);
    const [editing, setEditing] = useState<SAMLProvider | null>(null);
    const [form, setForm] = useState<SAMLProviderPayload>(newProvider());
    const [open, setOpen] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");

    const acsUrl = `${window.location.origin}/auth/saml/${form.id}/acs`;
    const metadataUrl = `${window.location.origin}/auth/saml/${form.id}/metadata`;

    const load = async () => {
        const token = await getToken(instance);
        if (!token) throw new Error("Authentication required");
        setProviders(await listSamlProviders(token));
    };

    useEffect(() => {
        void load().catch(reason => setError(reason?.message || "Unable to load SAML connections"));
    }, [instance]);

    const beginCreate = () => {
        setEditing(null);
        setForm(newProvider());
        setError("");
        setOpen(true);
    };

    const beginEdit = (provider: SAMLProvider) => {
        setEditing(provider);
        setForm({
            id: provider.id,
            enabled: provider.enabled,
            display_name: provider.display_name,
            entity_id: provider.entity_id,
            sso_url: provider.sso_url,
            x509_cert: provider.x509_cert,
            email_attribute: provider.email_attribute,
            first_name_attribute: provider.first_name_attribute,
            last_name_attribute: provider.last_name_attribute,
            jit_enabled: provider.jit_enabled,
            allowed_domains: [...provider.allowed_domains]
        });
        setError("");
        setOpen(true);
    };

    const save = async () => {
        setBusy(true); setError("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            if (editing) await updateSamlProvider(editing.id, form, token);
            else await createSamlProvider(form, token);
            await load();
            setOpen(false);
            setMessage(editing ? "SAML connection updated." : "SAML connection created.");
        } catch (reason: any) {
            setError(reason?.message || "Unable to save SAML connection");
        } finally {
            setBusy(false);
        }
    };

    const test = async () => {
        setBusy(true); setError("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            await testSamlProvider(form, token);
            setMessage("SAML configuration and signing certificate are valid.");
        } catch (reason: any) {
            setError(reason?.message || "SAML configuration is invalid");
        } finally {
            setBusy(false);
        }
    };

    const remove = async (provider: SAMLProvider) => {
        if (!window.confirm(`Delete SAML connection “${provider.display_name}”? Active sessions from this provider will be revoked.`)) return;
        setBusy(true); setError("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            await deleteSamlProvider(provider.id, token);
            await load();
            setMessage("SAML connection deleted and its active sessions revoked.");
        } catch (reason: any) {
            setError(reason?.message || "Unable to delete SAML connection");
        } finally {
            setBusy(false);
        }
    };

    const copy = (value: string) => void navigator.clipboard.writeText(value);

    return <Stack spacing={2}>
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "stretch", sm: "center" }} gap={1}>
            <div>
                <Typography variant="h6">SAML 2.0 connections</Typography>
                <Typography variant="body2" color="text.secondary">Connect enterprise identity providers using signed SAML assertions.</Typography>
            </div>
            <Button variant="contained" startIcon={<AddIcon />} onClick={beginCreate}>Add SAML connection</Button>
        </Stack>
        <Alert severity="info">Create the connection disabled, register its ACS URL and Entity ID in the identity provider, test it, then enable it. Keep Local authentication as the break-glass path.</Alert>
        {error && !open && <Alert severity="error">{error}</Alert>}
        {message && <Alert severity="success" onClose={() => setMessage("")}>{message}</Alert>}
        {providers.length === 0 ? <Alert severity="info">No SAML connections have been added.</Alert> : <Stack direction="row" flexWrap="wrap" gap={2}>
            {providers.map(provider => <Card key={provider.id} variant="outlined" sx={{ width: { xs: "100%", md: 380 } }}>
                <CardContent>
                    <Stack direction="row" justifyContent="space-between" alignItems="center" gap={1}>
                        <Typography variant="subtitle1" fontWeight={700}>{provider.display_name}</Typography>
                        <Chip size="small" color={provider.enabled ? "success" : "default"} label={provider.enabled ? "Enabled" : "Disabled"} />
                    </Stack>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1, wordBreak: "break-all" }}>{provider.entity_id}</Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>{provider.allowed_domains.length ? provider.allowed_domains.join(", ") : "No domain restriction"}</Typography>
                    <Typography variant="caption" color="text.secondary">{provider.jit_enabled ? "JIT provisioning enabled" : "Pre-provisioned users only"}</Typography>
                </CardContent>
                <CardActions>
                    <Button startIcon={<EditOutlinedIcon />} onClick={() => beginEdit(provider)}>Edit</Button>
                    <Button color="error" startIcon={<DeleteOutlineIcon />} onClick={() => void remove(provider)} disabled={busy}>Delete</Button>
                </CardActions>
            </Card>)}
        </Stack>}

        <Dialog open={open} fullWidth maxWidth="md" disableEscapeKeyDown onClose={(_event, reason) => { if (reason !== "backdropClick") setOpen(false); }}>
            <DialogTitle sx={{ pr: 7 }}>{editing ? "Edit SAML connection" : "Add SAML connection"}
                <IconButton aria-label="Close" onClick={() => setOpen(false)} sx={{ position: "absolute", right: 12, top: 12 }}><CloseIcon /></IconButton>
            </DialogTitle>
            <DialogContent dividers>
                <Stack spacing={2} sx={{ pt: 1 }}>
                    {error && <Alert severity="error">{error}</Alert>}
                    <FormControlLabel control={<Switch checked={form.enabled} onChange={event => setForm({ ...form, enabled: event.target.checked })} />} label="Enable this connection" />
                    <TextField label="Connection / sign-in name" value={form.display_name} onChange={event => setForm({ ...form, display_name: event.target.value })} placeholder="Acme SAML SSO" required />
                    <TextField label="Identity provider Entity ID" value={form.entity_id} onChange={event => setForm({ ...form, entity_id: event.target.value })} required />
                    <TextField label="Identity provider SSO URL" value={form.sso_url} onChange={event => setForm({ ...form, sso_url: event.target.value })} placeholder="https://id.example.com/saml/sso" required />
                    <TextField label="Identity provider X.509 signing certificate" value={form.x509_cert} onChange={event => setForm({ ...form, x509_cert: event.target.value })} multiline minRows={5} placeholder="-----BEGIN CERTIFICATE-----" required />
                    <TextField label="ACS / Reply URL" value={acsUrl} InputProps={{ readOnly: true }} InputLabelProps={{ shrink: true }} helperText="Register this exact URL in the identity provider." />
                    <Button size="small" startIcon={<ContentCopyIcon />} onClick={() => copy(acsUrl)} sx={{ alignSelf: "flex-start" }}>Copy ACS URL</Button>
                    <TextField label="SP Entity ID / Audience" value={metadataUrl} InputProps={{ readOnly: true }} InputLabelProps={{ shrink: true }} helperText="Use this value as the Audience or Identifier." />
                    <Button size="small" startIcon={<ContentCopyIcon />} onClick={() => copy(metadataUrl)} sx={{ alignSelf: "flex-start" }}>Copy Entity ID</Button>
                    <TextField label="Email attribute" value={form.email_attribute} onChange={event => setForm({ ...form, email_attribute: event.target.value })} helperText="Falls back to NameID when NameID is an email address." />
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                        <TextField fullWidth label="First name attribute" value={form.first_name_attribute} onChange={event => setForm({ ...form, first_name_attribute: event.target.value })} />
                        <TextField fullWidth label="Last name attribute" value={form.last_name_attribute} onChange={event => setForm({ ...form, last_name_attribute: event.target.value })} />
                    </Stack>
                    <TextField label="Allowed email domains" value={form.allowed_domains.join(", ")} onChange={event => setForm({ ...form, allowed_domains: event.target.value.split(",").map(item => item.trim()).filter(Boolean) })} placeholder="example.com, subsidiary.example" />
                    <FormControlLabel control={<Switch checked={form.jit_enabled} onChange={event => setForm({ ...form, jit_enabled: event.target.checked })} />} label="Create new users on first sign-in (JIT)" />
                    {form.jit_enabled && <Alert severity="warning">JIT users never receive System Admin rights and must still be added to a Team. Existing accounts require explicit approval in Identity links.</Alert>}
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        <Button variant="outlined" onClick={() => void test()} disabled={busy || !form.entity_id || !form.sso_url || !form.x509_cert}>Validate configuration</Button>
                        <Button variant="contained" onClick={() => void save()} disabled={busy}>{busy ? "Saving…" : editing ? "Save changes" : "Add connection"}</Button>
                    </Stack>
                </Stack>
            </DialogContent>
        </Dialog>
    </Stack>;
}
