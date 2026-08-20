import React, { useState } from "react";
import { Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, MenuItem, Paper, Stack, Switch, TextField, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import AltRouteIcon from "@mui/icons-material/AltRoute";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import { useMsal } from "@azure/msal-react";

import { delete_document_processing_routing_rule, explain_document_processing_route, save_document_processing_routing_rule } from "../../../api/api";
import { DocumentProcessingProfile, DocumentProcessingRoutingRule } from "../../../api/models";
import { getToken } from "../../../authConfig";
import { useNotification } from "../../../utill/NotificationProvider";

interface Props {
    rules: DocumentProcessingRoutingRule[];
    profiles: DocumentProcessingProfile[];
    onReload: (token?: string) => Promise<void>;
}

export function DocumentProcessingRoutingRules({ rules, profiles, onReload }: Props) {
    const client = useMsal().instance;
    const { showNotification } = useNotification();
    const [editing, setEditing] = useState<DocumentProcessingRoutingRule | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [filename, setFilename] = useState("invoice.pdf");
    const [scope, setScope] = useState("personal");
    const [teamId, setTeamId] = useState("");
    const [explanation, setExplanation] = useState<Record<string, any> | null>(null);
    const [explaining, setExplaining] = useState(false);

    const sortedRules = [...rules].sort((left, right) =>
        Number(right.enabled) - Number(left.enabled)
        || right.priority - left.priority
        || left.name.localeCompare(right.name)
    );

    const remove = async (ruleId: string) => {
        try {
            const token = await getToken(client); if (!token) return;
            await delete_document_processing_routing_rule(ruleId, token);
            await onReload(token);
        } catch (error) {
            showNotification(error instanceof Error ? error.message : "Delete failed", "error");
        }
    };
    const explain = async () => {
        if (explaining) return;
        setExplaining(true);
        setExplanation(null);
        try {
            const token = await getToken(client); if (!token) return;
            setExplanation(await explain_document_processing_route({ filename, scope, team_id: scope === "team" ? teamId : "" }, token));
        } catch (error) {
            showNotification(error instanceof Error ? error.message : "Explain route failed", "error");
        } finally {
            setExplaining(false);
        }
    };

    return <Box mt={2}>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditing(null); setDialogOpen(true); }}>Add Routing Rule</Button>
        <Stack spacing={2} mt={2}>{sortedRules.map(rule => <Paper key={rule._id} variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Box><Stack direction="row" spacing={1} alignItems="center"><Typography fontWeight={700}>{rule.name}</Typography><Chip size="small" label={rule.scope === "team" ? `team:${rule.team_id}` : rule.scope} /><Chip size="small" label={`Priority ${rule.priority}`} /><Chip size="small" color={rule.enabled ? "success" : "default"} label={rule.enabled ? "Enabled" : "Disabled"} /></Stack><Typography variant="body2" color="text.secondary" mt={1}>{rule.file_types.join(", ")} → {profiles.find(profile => profile._id === rule.profile_id)?.name ?? rule.profile_id} · unavailable: {rule.fallback_behavior}</Typography></Box>
                <Box><IconButton onClick={() => { setEditing(rule); setDialogOpen(true); }}><EditIcon /></IconButton><IconButton color="error" onClick={() => remove(rule._id)}><DeleteIcon /></IconButton></Box>
            </Stack>
        </Paper>)}</Stack>
        <Paper variant="outlined" sx={{ p: 2, mt: 3 }}><Typography variant="subtitle1" fontWeight={700}>Explain Route</Typography><Typography variant="body2" color="text.secondary" mb={2}>Preview the rule decision before activating or troubleshooting an upload.</Typography><Stack direction={{ xs: "column", md: "row" }} spacing={2}><TextField disabled={explaining} fullWidth label="Filename or extension" value={filename} onChange={event => setFilename(event.target.value)} /><TextField disabled={explaining} select fullWidth label="Scope" value={scope} onChange={event => setScope(event.target.value)}><MenuItem value="personal">Personal</MenuItem><MenuItem value="team">Team</MenuItem><MenuItem value="global">Global</MenuItem></TextField>{scope === "team" && <TextField disabled={explaining} fullWidth label="Team ID" value={teamId} onChange={event => setTeamId(event.target.value)} />}<Button variant="contained" size="large" startIcon={explaining ? <CircularProgress color="inherit" size={18} /> : <AltRouteIcon />} disabled={explaining || !filename.trim() || (scope === "team" && !teamId.trim())} onClick={explain} sx={{ minWidth: 170, height: 56, whiteSpace: "nowrap" }}>{explaining ? "Checking…" : "Explain Route"}</Button></Stack>{explaining && <Alert icon={<CircularProgress size={20} />} severity="info" sx={{ mt: 2 }} role="status">Checking the routing rules and selected processing profile…</Alert>}{explanation && <Alert severity={explanation.status === "error" ? "error" : "info"} sx={{ mt: 2 }}><Typography fontWeight={700}>{String(explanation.source)}: {String(explanation.reason)}</Typography><Typography variant="body2">Profile: {explanation.profile?.name ?? "startup system fallback"}{explanation.rule?.name ? ` · Rule: ${explanation.rule.name}` : ""}</Typography></Alert>}</Paper>
        <RoutingRuleDialog open={dialogOpen} value={editing} profiles={profiles} onClose={() => setDialogOpen(false)} onSave={async payload => { try { const token = await getToken(client); if (!token) return; await save_document_processing_routing_rule(payload, token); await onReload(token); setDialogOpen(false); } catch (error) { showNotification(error instanceof Error ? error.message : "Save failed", "error"); } }} />
    </Box>;
}

function RoutingRuleDialog({ open, value, profiles, onClose, onSave }: { open: boolean; value: DocumentProcessingRoutingRule | null; profiles: DocumentProcessingProfile[]; onClose: () => void; onSave: (payload: any) => void }) {
    const [name, setName] = useState(""); const [scope, setScope] = useState("all"); const [teamId, setTeamId] = useState(""); const [types, setTypes] = useState("*"); const [profileId, setProfileId] = useState(""); const [priority, setPriority] = useState(100); const [fallback, setFallback] = useState("continue"); const [enabled, setEnabled] = useState(true);
    React.useEffect(() => { if (!open) return; setName(value?.name ?? ""); setScope(value?.scope ?? "all"); setTeamId(value?.team_id ?? ""); setTypes((value?.file_types ?? ["*"]).join(",")); setProfileId(value?.profile_id ?? ""); setPriority(value?.priority ?? 100); setFallback(value?.fallback_behavior ?? "continue"); setEnabled(value?.enabled ?? true); }, [open, value]);
    const invalid = !name.trim() || !profileId || (scope === "team" && !teamId.trim()) || !types.trim();
    return <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm"><DialogTitle>{value ? "Edit" : "Add"} Routing Rule</DialogTitle><DialogContent dividers><Stack spacing={2}><TextField label="Rule Name" value={name} onChange={event => setName(event.target.value)} /><TextField select label="Scope" value={scope} onChange={event => setScope(event.target.value)}><MenuItem value="all">All scopes</MenuItem><MenuItem value="personal">Personal</MenuItem><MenuItem value="team">Specific team</MenuItem><MenuItem value="global">Global</MenuItem></TextField>{scope === "team" && <TextField label="Team ID" value={teamId} onChange={event => setTeamId(event.target.value)} />}<TextField label="File Types" value={types} onChange={event => setTypes(event.target.value)} helperText="Comma-separated extensions or *" /><TextField select label="Processing Profile" value={profileId} onChange={event => setProfileId(event.target.value)}>{profiles.filter(profile => profile.enabled).map(profile => <MenuItem key={profile._id} value={profile._id}>{profile.name}</MenuItem>)}</TextField><TextField type="number" label="Priority" value={priority} onChange={event => setPriority(Number(event.target.value))} /><TextField select label="If profile is unavailable" value={fallback} onChange={event => setFallback(event.target.value)}><MenuItem value="continue">Continue to next matching rule</MenuItem><MenuItem value="system">Use legacy/system fallback</MenuItem><MenuItem value="error">Fail the upload</MenuItem></TextField><Stack direction="row" alignItems="center" spacing={1}><Switch checked={enabled} onChange={event => setEnabled(event.target.checked)} /><Typography>Enabled</Typography></Stack></Stack></DialogContent><DialogActions><Button onClick={onClose}>Cancel</Button><Button variant="contained" disabled={invalid} onClick={() => onSave({ rule_id: value?._id, name: name.trim(), scope, team_id: scope === "team" ? teamId.trim() : "", file_types: types.split(",").map(item => item.trim()).filter(Boolean), profile_id: profileId, priority, fallback_behavior: fallback, enabled })}>Save</Button></DialogActions></Dialog>;
}
