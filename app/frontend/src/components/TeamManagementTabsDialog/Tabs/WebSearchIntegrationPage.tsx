import React, { useEffect, useState } from "react";
import {
    Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
    DialogContent, DialogTitle, FormControlLabel, IconButton, MenuItem,
    Paper, Stack, Switch, TextField, Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import TravelExploreIcon from "@mui/icons-material/TravelExplore";
import { useMsal } from "@azure/msal-react";

import { TeamProfile, WebSearchConnection, WebSearchProvider } from "../../../api/models";
import {
    delete_web_search_connection, get_web_search_connections,
    save_web_search_connection, test_web_search_connection
} from "../../../api/api";
import { getToken } from "../../../authConfig";
import { useNotification } from "../../../utill/NotificationProvider";
import { AssignIntegrationTeamButton } from "./AssignIntegrationTeamButton";

const PROVIDERS: Record<WebSearchProvider, string> = {
    brave: "Brave Search API",
    searxng: "SearXNG"
};

export function WebSearchIntegrationPage({ team, onBack }: { team: TeamProfile | null; onBack: () => void }) {
    const [items, setItems] = useState<WebSearchConnection[]>([]);
    const [loading, setLoading] = useState(true);
    const [testing, setTesting] = useState("");
    const [editing, setEditing] = useState<WebSearchConnection | null>(null);
    const [open, setOpen] = useState(false);
    const client = useMsal().instance;
    const { showNotification } = useNotification();
    const teamId = team?._id ?? "";

    const load = async (token?: string) => {
        const accessToken = token ?? await getToken(client);
        if (!accessToken) throw new Error("No authentication token");
        setItems(await get_web_search_connections(teamId, accessToken));
    };
    useEffect(() => {
        setLoading(true);
        load().catch(error => showNotification(error.message, "error")).finally(() => setLoading(false));
    }, [teamId]);

    const remove = async (item: WebSearchConnection) => {
        if (!confirm(`Delete Web Search connection "${item.name}"?`)) return;
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            await delete_web_search_connection(item._id, token);
            await load(token);
            showNotification("Web Search connection deleted", "success");
        } catch (error) {
            showNotification(error instanceof Error ? error.message : "Delete failed", "error");
        }
    };

    return <Box p={3} sx={{ height: "100%", overflowY: "auto" }}>
        <Stack direction="row" alignItems="center" spacing={2} mb={2}>
            <IconButton onClick={onBack}><ArrowBackIcon /></IconButton>
            <Box>
                <Typography variant="h6">Web Search</Typography>
                <Typography variant="body2" color="text.secondary">
                    Manage governed Brave Search or SearXNG connections. Domain access remains restricted per Agent.
                </Typography>
            </Box>
        </Stack>
        {!team && <Alert severity="info" sx={{ mb: 2 }}>New connections remain unavailable to Agents until assigned to a team.</Alert>}
        <Alert severity="warning" sx={{ mb: 2 }}>Search snippets are external, untrusted evidence. Agents must cite the source URL and search date.</Alert>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditing(null); setOpen(true); }} sx={{ mb: 2 }}>
            Add Web Search Connection
        </Button>
        {loading ? <CircularProgress /> : items.length === 0 ? (
            <Stack alignItems="center" py={6}><TravelExploreIcon sx={{ fontSize: 48, opacity: .3 }} /><Typography color="text.secondary">No Web Search connections yet</Typography></Stack>
        ) : <Stack spacing={2}>{items.map(item => <Paper key={item._id} variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
            <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={2}>
                <Box>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
                        <Typography fontWeight={700}>{item.name}</Typography>
                        <Chip size="small" label={PROVIDERS[item.provider]} />
                        <Chip size="small" color={item.enabled ? "success" : "default"} variant="outlined" label={item.enabled ? "Enabled" : "Disabled"} />
                        <Chip size="small" variant="outlined" label={`${item.agent_usage_count ?? 0} Agents`} />
                        {!team && <Chip size="small" color="warning" variant="outlined" label="Unassigned" />}
                    </Stack>
                    <Typography variant="body2" color="text.secondary" mt={.75}>
                        {item.provider === "brave" ? "Managed Brave Search API" : item.base_url}
                    </Typography>
                </Box>
                <Stack direction="row" spacing={1} alignItems="center">
                    {!team && <AssignIntegrationTeamButton integrationId={item._id} integrationType="web_search" onAssigned={load} />}
                    <Button size="small" disabled={testing === item._id} onClick={async () => {
                        try {
                            setTesting(item._id);
                            const token = await getToken(client);
                            if (!token) throw new Error("No authentication token");
                            const result = await test_web_search_connection(item._id, token);
                            showNotification(result.message, "success");
                        } catch (error) {
                            showNotification(error instanceof Error ? error.message : "Connection test failed", "error");
                        } finally { setTesting(""); }
                    }}>{testing === item._id ? "Testing..." : "Test"}</Button>
                    <IconButton onClick={() => { setEditing(item); setOpen(true); }}><EditIcon /></IconButton>
                    <IconButton color="error" onClick={() => remove(item)}><DeleteIcon /></IconButton>
                </Stack>
            </Stack>
        </Paper>)}</Stack>}
        <WebSearchDialog
            open={open}
            value={editing}
            teamId={teamId}
            onClose={() => { setOpen(false); setEditing(null); }}
            onSaved={async token => { await load(token); setOpen(false); setEditing(null); }}
        />
    </Box>;
}

function WebSearchDialog({ open, value, teamId, onClose, onSaved }: {
    open: boolean; value: WebSearchConnection | null; teamId: string;
    onClose: () => void; onSaved: (token: string) => Promise<void>;
}) {
    const [provider, setProvider] = useState<WebSearchProvider>("brave");
    const [name, setName] = useState("");
    const [baseUrl, setBaseUrl] = useState("");
    const [apiKey, setApiKey] = useState("");
    const [timeout, setTimeoutValue] = useState(10);
    const [enabled, setEnabled] = useState(true);
    const [saving, setSaving] = useState(false);
    const client = useMsal().instance;
    const { showNotification } = useNotification();
    useEffect(() => {
        if (!open) return;
        setProvider(value?.provider ?? "brave");
        setName(value?.name ?? "");
        setBaseUrl(value?.base_url ?? "");
        setApiKey("");
        setTimeoutValue(value?.timeout_seconds ?? 10);
        setEnabled(value?.enabled ?? true);
    }, [open, value]);

    const valid = Boolean(name.trim() && (provider === "brave" ? value?.has_api_key || apiKey.trim() : baseUrl.trim()));
    return <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
        <DialogTitle>{value ? "Edit" : "Add"} Web Search Connection</DialogTitle>
        <DialogContent dividers><Stack spacing={2.5}>
            <TextField select label="Provider" value={provider} disabled={Boolean(value)} onChange={event => setProvider(event.target.value as WebSearchProvider)}>
                {Object.entries(PROVIDERS).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}
            </TextField>
            <TextField label="Connection Name" value={name} onChange={event => setName(event.target.value)} required />
            {provider === "brave" ? <TextField
                label="Brave Search API Key" type="password" autoComplete="new-password"
                value={apiKey} onChange={event => setApiKey(event.target.value)}
                helperText={value?.has_api_key ? "Leave blank to keep the stored encrypted key" : "Stored encrypted; never returned by the API"}
                required={!value?.has_api_key}
            /> : <TextField
                label="SearXNG Base URL" value={baseUrl} onChange={event => setBaseUrl(event.target.value)}
                helperText="Example: https://search.example.com" required
            />}
            <TextField label="Provider Timeout (seconds)" type="number" value={timeout}
                inputProps={{ min: 1, max: 30 }}
                onChange={event => setTimeoutValue(Number(event.target.value))} />
            <FormControlLabel control={<Switch checked={enabled} onChange={event => setEnabled(event.target.checked)} />} label="Enabled for Agent assignment" />
        </Stack></DialogContent>
        <DialogActions>
            <Button onClick={onClose}>Cancel</Button>
            <Button variant="contained" disabled={!valid || saving} onClick={async () => {
                try {
                    setSaving(true);
                    const token = await getToken(client);
                    if (!token) throw new Error("No authentication token");
                    await save_web_search_connection({
                        connection_id: value?._id, team_id: teamId, provider, name,
                        base_url: baseUrl, api_key: apiKey, timeout_seconds: timeout, enabled
                    }, token);
                    await onSaved(token);
                    showNotification("Web Search connection saved", "success");
                } catch (error) {
                    showNotification(error instanceof Error ? error.message : "Save failed", "error");
                } finally { setSaving(false); }
            }}>{saving ? "Saving..." : "Save"}</Button>
        </DialogActions>
    </Dialog>;
}
