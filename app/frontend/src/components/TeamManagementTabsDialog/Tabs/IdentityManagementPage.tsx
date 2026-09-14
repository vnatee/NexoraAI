import LinkOffOutlinedIcon from "@mui/icons-material/LinkOffOutlined";
import {
    Alert,
    Button,
    Card,
    CardActions,
    CardContent,
    Chip,
    CircularProgress,
    Divider,
    MenuItem,
    Stack,
    TextField,
    Typography
} from "@mui/material";
import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";

import {
    approveIdentityLink,
    get_all_users,
    getIdentityManagement,
    rejectIdentityLink,
    unlinkOidcIdentity
} from "../../../api";
import { IdentityManagementResponse, User } from "../../../api/models";
import { getToken } from "../../../authConfig";

const emptyResult: IdentityManagementResponse = { pending: [], links: [], audit_events: [] };

export function IdentityManagementPage() {
    const { instance } = useMsal();
    const [result, setResult] = useState<IdentityManagementResponse>(emptyResult);
    const [users, setUsers] = useState<User[]>([]);
    const [targets, setTargets] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);
    const [busyId, setBusyId] = useState("");
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");

    const load = async () => {
        const token = await getToken(instance);
        if (!token) throw new Error("Authentication required");
        const [identityResult, userResult] = await Promise.all([
            getIdentityManagement(token),
            get_all_users(token)
        ]);
        setResult(identityResult);
        const eligibleUsers = (userResult.result || []).filter((user: User) => user.active && !user.is_sys_admin);
        const eligibleUserIds = new Set(eligibleUsers.map((user: User) => user._id));
        setUsers(eligibleUsers);
        setTargets(current => {
            const next = { ...current };
            identityResult.pending.forEach(item => {
                if (!next[item.id] && eligibleUserIds.has(item.suggested_user_id)) next[item.id] = item.suggested_user_id;
            });
            return next;
        });
    };

    useEffect(() => {
        void load().catch(reason => setError(reason?.message || "Unable to load identity links")).finally(() => setLoading(false));
    }, [instance]);

    const run = async (id: string, action: (token: string) => Promise<void>, success: string) => {
        setBusyId(id); setError(""); setMessage("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            await action(token);
            await load();
            setMessage(success);
        } catch (reason: any) {
            setError(reason?.message || "Identity operation failed");
        } finally {
            setBusyId("");
        }
    };

    if (loading) return <CircularProgress />;

    return <Stack spacing={3}>
        <div>
            <Typography variant="h6">Federated identity links</Typography>
            <Typography variant="body2" color="text.secondary">Review OIDC and SAML identities before linking them to existing NexoraAI users. Email is a suggestion only and never authorizes an automatic link.</Typography>
        </div>
        <Alert severity="info">A request appears after a user completes a cryptographically verified federated sign-in whose email already belongs to an internal account. Requests expire after seven days.</Alert>
        {error && <Alert severity="error">{error}</Alert>}
        {message && <Alert severity="success" onClose={() => setMessage("")}>{message}</Alert>}

        <Typography variant="subtitle1" fontWeight={700}>Pending approval ({result.pending.length})</Typography>
        {result.pending.length === 0 ? <Alert severity="info">No identity links are waiting for review.</Alert> : <Stack direction="row" flexWrap="wrap" gap={2}>
            {result.pending.map(item => <Card key={item.id} variant="outlined" sx={{ width: { xs: "100%", lg: 430 } }}>
                <CardContent>
                    <Stack direction="row" justifyContent="space-between" gap={1}>
                        <Typography variant="subtitle1" fontWeight={700}>{item.email}</Typography>
                        <Chip size="small" label="Pending" color="warning" />
                    </Stack>
                    <Typography variant="body2" color="text.secondary">{item.provider_name}</Typography>
                    <TextField select fullWidth size="small" label="Link to internal user" sx={{ mt: 2 }} value={targets[item.id] || ""} onChange={event => setTargets({ ...targets, [item.id]: event.target.value })}>
                        {users.map(user => <MenuItem key={user._id} value={user._id}>{`${user.first_name} ${user.last_name} — ${user.ad_email || user.email}`}</MenuItem>)}
                    </TextField>
                    {item.suggested_user_name && <Typography variant="caption" color="text.secondary">Suggested match: {item.suggested_user_name}. Verify independently before approval.</Typography>}
                </CardContent>
                <CardActions>
                    <Button variant="contained" disabled={busyId === item.id || !targets[item.id]} onClick={() => void run(item.id, token => approveIdentityLink(item.id, targets[item.id], token), "Identity link approved.")}>Approve link</Button>
                    <Button color="error" disabled={busyId === item.id} onClick={() => void run(item.id, token => rejectIdentityLink(item.id, token), "Identity link rejected.")}>Reject</Button>
                </CardActions>
            </Card>)}
        </Stack>}

        <Divider />
        <Typography variant="subtitle1" fontWeight={700}>Linked federated identities ({result.links.length})</Typography>
        {result.links.length === 0 ? <Alert severity="info">No federated identities are linked.</Alert> : <Stack direction="row" flexWrap="wrap" gap={2}>
            {result.links.map(item => <Card key={item.id} variant="outlined" sx={{ width: { xs: "100%", lg: 360 } }}>
                <CardContent>
                    <Stack direction="row" justifyContent="space-between" gap={1}>
                        <Typography variant="subtitle1" fontWeight={700}>{item.user_name || item.user_id}</Typography>
                        <Chip size="small" color={item.active ? "success" : "default"} label={item.active ? "Active" : "Disabled"} />
                    </Stack>
                    <Typography variant="body2">{item.username}</Typography>
                    <Typography variant="body2" color="text.secondary">{item.provider_name}</Typography>
                </CardContent>
                <CardActions>
                    <Button color="error" startIcon={<LinkOffOutlinedIcon />} disabled={busyId === item.id} onClick={() => {
                        if (window.confirm(`Unlink ${item.username} from ${item.user_name || item.user_id}? Active sessions for this identity will be revoked.`)) {
                            void run(item.id, token => unlinkOidcIdentity(item.id, token), "Federated identity unlinked.");
                        }
                    }}>Unlink</Button>
                </CardActions>
            </Card>)}
        </Stack>}

        {result.audit_events.length > 0 && <><Divider /><Typography variant="subtitle1" fontWeight={700}>Recent identity activity</Typography><Stack spacing={1}>
            {result.audit_events.slice(0, 10).map(event => <Typography key={event.id} variant="body2" color="text.secondary">{event.action} · target {event.target_user_id || "not linked"} · {event.created_at ? new Date(event.created_at).toLocaleString() : ""}</Typography>)}
        </Stack></>}
    </Stack>;
}
