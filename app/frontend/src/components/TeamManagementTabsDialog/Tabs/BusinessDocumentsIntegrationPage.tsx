import React, { useEffect, useState } from "react";
import {
    Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
    DialogTitle, FormControlLabel, IconButton, MenuItem, Paper, Stack, Switch,
    TextField, Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import FolderSharedOutlinedIcon from "@mui/icons-material/FolderSharedOutlined";
import { useMsal } from "@azure/msal-react";

import {
    BusinessDocumentConnection, BusinessDocumentProvider, BusinessDocumentPublicConfig, TeamProfile
} from "../../../api/models";
import {
    delete_business_document_connection, get_business_document_connections,
    save_business_document_connection, test_business_document_connection
} from "../../../api/api";
import { getToken } from "../../../authConfig";
import { useNotification } from "../../../utill/NotificationProvider";
import { AssignIntegrationTeamButton } from "./AssignIntegrationTeamButton";


const PROVIDER_LABELS: Record<BusinessDocumentProvider, string> = {
    microsoft365: "Microsoft 365 Documents",
    google_workspace: "Google Workspace"
};

type Draft = Omit<BusinessDocumentConnection, "agent_usage_count" | "has_credentials"> & {
    secrets?: Record<string, string>;
};

export function BusinessDocumentsIntegrationPage({ team, onBack }: { team: TeamProfile | null; onBack: () => void }) {
    const [items, setItems] = useState<BusinessDocumentConnection[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState<string | null>(null);
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState<BusinessDocumentConnection | null>(null);
    const client = useMsal().instance;
    const { showNotification } = useNotification();
    const teamId = team?._id ?? "";

    const load = async (token?: string) => {
        const accessToken = token ?? await getToken(client);
        if (!accessToken) throw new Error("No authentication token");
        setItems(await get_business_document_connections(teamId, accessToken));
    };
    useEffect(() => {
        setLoading(true);
        load().catch(error => showNotification(error.message, "error")).finally(() => setLoading(false));
    }, [teamId]);

    const save = async (draft: Draft) => {
        try {
            setSaving(true);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            await save_business_document_connection({ ...draft, team_id: teamId, connection_id: editing?._id }, token);
            await load(token);
            setOpen(false);
            setEditing(null);
            showNotification("Document connection saved", "success");
        } catch (error) {
            showNotification(error instanceof Error ? error.message : "Save failed", "error");
        } finally {
            setSaving(false);
        }
    };

    return <Box p={3} sx={{ height: "100%", overflowY: "auto" }}>
        <Stack direction="row" alignItems="center" spacing={2} mb={2}>
            <IconButton onClick={onBack}><ArrowBackIcon /></IconButton>
            <Box>
                <Typography variant="h6">Business Documents</Typography>
                <Typography variant="body2" color="text.secondary">Connect Microsoft 365 or Google Workspace document libraries to Agents.</Typography>
            </Box>
        </Stack>
        {!team && <Alert severity="info" sx={{ mb: 2 }}>New connections remain unavailable to Agents until assigned to a team.</Alert>}
        <Alert severity="warning" sx={{ mb: 2 }}>Read-only is recommended. Creating cloud documents is exposed only when both the connection and Agent binding allow it.</Alert>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditing(null); setOpen(true); }} sx={{ mb: 2 }}>Add Document Connection</Button>
        {loading ? <CircularProgress /> : items.length === 0 ? (
            <Stack alignItems="center" py={6}><FolderSharedOutlinedIcon sx={{ fontSize: 48, opacity: .3 }} /><Typography color="text.secondary">No document connections yet</Typography></Stack>
        ) : <Stack spacing={2}>{items.map(item => <Paper key={item._id} variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
            <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={2}>
                <Box>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
                        <Typography fontWeight={700}>{item.name}</Typography>
                        <Chip size="small" label={PROVIDER_LABELS[item.provider]} />
                        <Chip size="small" color={item.operation_mode === "read_only" ? "success" : "warning"} label={item.operation_mode === "read_only" ? "Read-only" : "Read & create"} />
                        <Chip size="small" color={item.enabled ? "success" : "default"} variant="outlined" label={item.enabled ? "Enabled" : "Disabled"} />
                        <Chip size="small" variant="outlined" label={`${item.agent_usage_count ?? 0} Agents`} />
                        {!team && <Chip size="small" color="warning" variant="outlined" label="Unassigned" />}
                    </Stack>
                    <Typography variant="body2" color="text.secondary" mt={.75}>
                        {item.provider === "microsoft365" ? `Drive ID: ${item.public_config.drive_id}` : `Root folder: ${item.public_config.root_folder_id || "My Drive"}`}
                    </Typography>
                </Box>
                <Stack direction="row" spacing={1} alignItems="center">
                    {!team && <AssignIntegrationTeamButton integrationId={item._id} integrationType="business_documents" onAssigned={load} />}
                    <Button size="small" disabled={testing === item._id} onClick={async () => {
                        try {
                            setTesting(item._id);
                            const token = await getToken(client);
                            if (!token) return;
                            const result = await test_business_document_connection(item._id, token);
                            showNotification(result.message, "success");
                        } catch (error) {
                            showNotification(error instanceof Error ? error.message : "Connection test failed", "error");
                        } finally { setTesting(null); }
                    }}>{testing === item._id ? "Testing..." : "Test"}</Button>
                    <IconButton onClick={() => { setEditing(item); setOpen(true); }}><EditIcon /></IconButton>
                    <IconButton color="error" onClick={async () => {
                        if (!confirm("Delete this document connection?")) return;
                        try {
                            const token = await getToken(client);
                            if (!token) return;
                            await delete_business_document_connection(item._id, token);
                            await load(token);
                        } catch (error) { showNotification(error instanceof Error ? error.message : "Delete failed", "error"); }
                    }}><DeleteIcon /></IconButton>
                </Stack>
            </Stack>
        </Paper>)}</Stack>}
        <DocumentConnectionDialog open={open} value={editing} teamId={teamId} saving={saving} onClose={() => { setOpen(false); setEditing(null); }} onSave={save} />
    </Box>;
}

function DocumentConnectionDialog({ open, value, teamId, saving, onClose, onSave }: {
    open: boolean; value: BusinessDocumentConnection | null; teamId: string; saving: boolean;
    onClose: () => void; onSave: (draft: Draft) => void;
}) {
    const [provider, setProvider] = useState<BusinessDocumentProvider>("microsoft365");
    const [name, setName] = useState("");
    const [config, setConfig] = useState<BusinessDocumentPublicConfig>({});
    const [secrets, setSecrets] = useState<Record<string, string>>({});
    const [operationMode, setOperationMode] = useState<"read_only" | "read_write">("read_only");
    const [enabled, setEnabled] = useState(true);
    useEffect(() => {
        if (!open) return;
        setProvider(value?.provider ?? "microsoft365");
        setName(value?.name ?? "");
        setConfig(value?.public_config ?? {});
        setSecrets({});
        setOperationMode(value?.operation_mode ?? "read_only");
        setEnabled(value?.enabled ?? true);
    }, [open, value]);
    const field = (key: keyof BusinessDocumentPublicConfig, label: string, helperText?: string) => <TextField fullWidth label={label} value={config[key] ?? ""} helperText={helperText} onChange={event => setConfig(current => ({ ...current, [key]: event.target.value }))} />;
    const secret = (key: string, label: string) => <TextField fullWidth type="password" autoComplete="new-password" label={label} value={secrets[key] ?? ""} helperText={value ? "Leave blank to keep the stored credential" : undefined} onChange={event => setSecrets(current => ({ ...current, [key]: event.target.value }))} />;
    const valid = Boolean(name.trim() && config.client_id && (provider === "google_workspace" || (config.tenant_id && config.drive_id)) && (value || Object.values(secrets).some(Boolean)));
    return <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
        <DialogTitle>{value ? "Edit" : "Add"} Document Connection</DialogTitle>
        <DialogContent dividers><Stack spacing={2.5}>
            <TextField select label="Provider" value={provider} disabled={Boolean(value)} onChange={event => { setProvider(event.target.value as BusinessDocumentProvider); setConfig({}); setSecrets({}); }}>
                {Object.entries(PROVIDER_LABELS).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}
            </TextField>
            <TextField label="Connection Name" value={name} onChange={event => setName(event.target.value)} required />
            {provider === "microsoft365" ? <>
                <Alert severity="info">Create an Entra application with Microsoft Graph application permissions Files.Read.All and Sites.Read.All. Add Files.ReadWrite.All only for Read & create.</Alert>
                {field("tenant_id", "Entra Tenant ID")}
                {field("client_id", "Application (Client) ID")}
                {secret("client_secret", "Client Secret")}
                {field("drive_id", "Drive ID", "OneDrive or SharePoint document-library drive ID")}
                {field("root_folder_id", "Root Folder Item ID (optional)", "Restricts listing and document creation to this folder")}
            </> : <>
                <Alert severity="info">Enable Google Drive API and obtain an offline OAuth refresh token with Drive read-only or Drive file scope.</Alert>
                {field("client_id", "OAuth Client ID")}
                {secret("client_secret", "OAuth Client Secret")}
                {secret("refresh_token", "OAuth Refresh Token")}
                {field("root_folder_id", "Root Folder ID (optional)")}
                {field("shared_drive_id", "Shared Drive ID (optional)")}
            </>}
            <TextField select label="Operation Mode" value={operationMode} onChange={event => setOperationMode(event.target.value as "read_only" | "read_write")}>
                <MenuItem value="read_only">Read-only</MenuItem>
                <MenuItem value="read_write">Read & create documents</MenuItem>
            </TextField>
            {operationMode === "read_write" && <Alert severity="warning">Agents may create files in the configured folder when their binding also grants Create permission.</Alert>}
            <FormControlLabel control={<Switch checked={enabled} onChange={event => setEnabled(event.target.checked)} />} label="Enabled for Agent assignment" />
        </Stack></DialogContent>
        <DialogActions><Button onClick={onClose}>Cancel</Button><Button variant="contained" disabled={!valid || saving} onClick={() => onSave({ _id: value?._id ?? "", team_id: teamId, name, provider, public_config: config, operation_mode: operationMode, enabled, secrets })}>{saving ? "Saving..." : "Save"}</Button></DialogActions>
    </Dialog>;
}
