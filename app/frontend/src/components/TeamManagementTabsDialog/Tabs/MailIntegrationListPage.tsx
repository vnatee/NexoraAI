import React, { useEffect, useState } from "react";
import { Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, IconButton, MenuItem, Paper, Stack, Switch, TextField, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import EmailIcon from "@mui/icons-material/Email";
import { MailEmailConfig, MailProvider, MailPublicConfig, MailSecurity, TeamProfile } from "../../../api/models";
import { delete_mail_config, edit_mail_config, get_mail_configs, insert_mail_config, test_mail_connection } from "../../../api/api";
import { getToken } from "../../../authConfig";
import { useMsal } from "@azure/msal-react";
import { useNotification } from "../../../utill/NotificationProvider";
import { AssignIntegrationTeamButton } from "./AssignIntegrationTeamButton";

interface Props { team: TeamProfile | null; onBack: () => void }
type Draft = MailEmailConfig & { secrets?: Record<string, string> };
const LABELS: Record<MailProvider, string> = { microsoft365: "Microsoft 365 (Graph)", gmail: "Gmail API", generic: "Generic IMAP/POP3 + SMTP" };

export function MailIntegrationListPage({ team, onBack }: Props) {
    const [configs, setConfigs] = useState<MailEmailConfig[]>([]); const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false); const [testing, setTesting] = useState<string | null>(null);
    const [open, setOpen] = useState(false); const [editing, setEditing] = useState<MailEmailConfig | null>(null);
    const client = useMsal().instance; const { showNotification } = useNotification();
    const teamId = team?._id ?? "";
    const load = async (token?: string) => { const t = token ?? await getToken(client); if (!t) throw new Error("No authentication token"); setConfigs(await get_mail_configs(teamId, t)); };
    useEffect(() => { setLoading(true); load().catch(e => showNotification(e.message, "error")).finally(() => setLoading(false)); }, [teamId]);
    const save = async (draft: Draft) => { try { setSaving(true); const token = await getToken(client); if (!token) throw new Error("No authentication token"); const payload = { ...draft, team_id: teamId, config_id: editing?._id }; if (editing) await edit_mail_config(payload, token); else await insert_mail_config(payload, token); await load(token); setOpen(false); setEditing(null); showNotification("Mail connection saved", "success"); } catch (e) { showNotification(e instanceof Error ? e.message : "Save failed", "error"); } finally { setSaving(false); } };
    return <Box p={3} sx={{ height: "100%", overflowY: "auto" }}>
        <Stack direction="row" alignItems="center" spacing={2} mb={2}><IconButton onClick={onBack}><ArrowBackIcon /></IconButton><Box><Typography variant="h6">Mail Integrations</Typography><Typography variant="body2" color="text.secondary">Central connections; assign Read and Send permissions per Agent.</Typography></Box></Stack>
        {!team && <Alert severity="info" sx={{ mb: 2 }}>New connections remain unavailable to Agents until assigned to a team.</Alert>}
        <Alert severity="info" sx={{ mb: 2 }}>Microsoft 365 and Gmail use their official APIs. Generic Mail uses IMAP/POP3 for reading and SMTP for sending.</Alert>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditing(null); setOpen(true); }} sx={{ mb: 2 }}>Add Connection</Button>
        {loading ? <CircularProgress /> : configs.length === 0 ? <Stack alignItems="center" py={6}><EmailIcon sx={{ fontSize: 48, opacity: .3 }} /><Typography color="text.secondary">No mail connections yet</Typography></Stack> : <Stack spacing={2}>{configs.map(conn => <Paper key={conn._id} variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}><Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={2}><Box><Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center"><Typography fontWeight={700}>{conn.name}</Typography><Chip size="small" label={LABELS[conn.provider]} /><Chip size="small" color={conn.enabled ? "success" : "default"} label={conn.enabled ? "Enabled" : "Disabled"} /><Chip size="small" variant="outlined" label={`${conn.agent_usage_count ?? 0} Agents`} />{!team && <Chip size="small" color="warning" variant="outlined" label="Unassigned" />}</Stack><Typography variant="body2" color="text.secondary" mt={.75}>{conn.email_address}</Typography></Box><Stack direction="row" spacing={1} alignItems="center">{!team && <AssignIntegrationTeamButton integrationId={conn._id} integrationType="mail" onAssigned={load} />}<Button size="small" disabled={testing === conn._id} onClick={async () => { try { setTesting(conn._id); const token = await getToken(client); if (!token) return; const result = await test_mail_connection(conn._id, token); showNotification(result.message, "success"); } catch (e) { showNotification(e instanceof Error ? e.message : "Connection test failed", "error"); } finally { setTesting(null); } }}>{testing === conn._id ? "Testing..." : "Test"}</Button><IconButton onClick={() => { setEditing(conn); setOpen(true); }}><EditIcon /></IconButton><IconButton color="error" onClick={async () => { if (!confirm("Delete this mail connection?")) return; try { const token = await getToken(client); if (!token) return; await delete_mail_config(conn._id, token); await load(token); } catch (e) { showNotification(e instanceof Error ? e.message : "Delete failed", "error"); } }}><DeleteIcon /></IconButton></Stack></Stack></Paper>)}</Stack>}
        <MailConfigDialog open={open} value={editing} saving={saving} teamId={teamId} onClose={() => { setOpen(false); setEditing(null); }} onSave={save} />
    </Box>;
}

function MailConfigDialog({ open, value, saving, teamId, onClose, onSave }: { open: boolean; value: MailEmailConfig | null; saving: boolean; teamId: string; onClose: () => void; onSave: (v: Draft) => void }) {
    const [provider, setProvider] = useState<MailProvider>("microsoft365"); const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [enabled, setEnabled] = useState(true);
    const [config, setConfig] = useState<MailPublicConfig>({}); const [secrets, setSecrets] = useState<Record<string, string>>({});
    useEffect(() => { if (!open) return; setProvider(value?.provider ?? "microsoft365"); setName(value?.name ?? ""); setEmail(value?.email_address ?? ""); setEnabled(value?.enabled ?? true); setConfig(value?.public_config ?? {}); setSecrets({}); }, [open, value]);
    const field = (key: keyof MailPublicConfig, label: string, type = "text") => <TextField label={label} type={type} value={config[key] ?? ""} onChange={e => setConfig(v => ({ ...v, [key]: type === "number" ? Number(e.target.value) : e.target.value }))} fullWidth />;
    const secret = (key: string, label: string) => <TextField label={label} type="password" value={secrets[key] ?? ""} onChange={e => setSecrets(v => ({ ...v, [key]: e.target.value }))} helperText={value ? "Leave blank to keep stored credential" : undefined} fullWidth autoComplete="new-password" />;
    const security = (key: "receive_security" | "smtp_security", label: string) => <TextField select label={label} value={config[key] ?? (key === "receive_security" ? "ssl" : "starttls")} onChange={e => setConfig(v => ({ ...v, [key]: e.target.value as MailSecurity }))} fullWidth><MenuItem value="ssl">SSL/TLS</MenuItem><MenuItem value="starttls">STARTTLS</MenuItem><MenuItem value="none">None</MenuItem></TextField>;
    const valid = Boolean(name.trim() && email.includes("@") && (value || Object.values(secrets).some(Boolean)));
    return <Dialog open={open} onClose={onClose} fullWidth maxWidth="md"><DialogTitle>{value ? "Edit" : "Add"} Mail Connection</DialogTitle><DialogContent dividers><Stack spacing={2.5}>
        <TextField select label="Provider" value={provider} disabled={Boolean(value)} onChange={e => { const p = e.target.value as MailProvider; setProvider(p); setConfig(p === "generic" ? { receive_protocol: "imap", receive_port: 993, receive_security: "ssl", smtp_port: 587, smtp_security: "starttls" } : {}); setSecrets({}); }}>{Object.entries(LABELS).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}</TextField>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}><TextField label="Connection Name" value={name} onChange={e => setName(e.target.value)} fullWidth required /><TextField label="Mailbox / Email Address" value={email} onChange={e => setEmail(e.target.value)} fullWidth required /></Stack>
        {provider === "microsoft365" && <><Alert severity="info">OAuth client credentials; Graph application permissions and admin consent are required.</Alert>{field("tenant_id", "Entra Tenant ID")}{field("client_id", "Application (Client) ID")}{secret("client_secret", "Client Secret")}</>}
        {provider === "gmail" && <><Alert severity="info">Enable Gmail API and obtain an offline OAuth refresh token with readonly/send scopes.</Alert>{field("client_id", "OAuth Client ID")}{secret("client_secret", "OAuth Client Secret")}{secret("refresh_token", "OAuth Refresh Token")}</>}
        {provider === "generic" && <><Alert severity="warning">Prefer IMAP. Use an app password when MFA is enabled.</Alert>{field("username", "Username")}{secret("password", "Password / App Password")}<TextField select label="Receive Protocol" value={config.receive_protocol ?? "imap"} onChange={e => setConfig(v => ({ ...v, receive_protocol: e.target.value as "imap" | "pop3" }))}><MenuItem value="imap">IMAP</MenuItem><MenuItem value="pop3">POP3</MenuItem></TextField><Stack direction={{ xs: "column", md: "row" }} spacing={2}>{field("receive_host", "Incoming Host")}{field("receive_port", "Incoming Port", "number")}{security("receive_security", "Incoming Security")}</Stack><Stack direction={{ xs: "column", md: "row" }} spacing={2}>{field("smtp_host", "SMTP Host")}{field("smtp_port", "SMTP Port", "number")}{security("smtp_security", "SMTP Security")}</Stack></>}
        <FormControlLabel control={<Switch checked={enabled} onChange={e => setEnabled(e.target.checked)} />} label="Enabled for Agent assignment" />
    </Stack></DialogContent><DialogActions><Button onClick={onClose}>Cancel</Button><Button variant="contained" disabled={!valid || saving} onClick={() => onSave({ _id: value?._id ?? "", team_id: teamId, name, provider, email_address: email, public_config: config, enabled, secrets })}>{saving ? "Saving..." : "Save"}</Button></DialogActions></Dialog>;
}
