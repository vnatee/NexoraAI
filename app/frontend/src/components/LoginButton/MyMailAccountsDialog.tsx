import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Paper,
    Stack,
    TextField,
    Typography
} from "@mui/material";

import {
    disconnect_my_mail_account,
    get_my_mail_profiles,
    save_my_mail_account,
    test_my_mail_account
} from "../../api/api";
import { PersonalMailProfile } from "../../api/models";
import { getToken } from "../../authConfig";

interface Props {
    open: boolean;
    teamId: string;
    teamName: string;
    onClose: () => void;
}

export function MyMailAccountsDialog({ open, teamId, teamName, onClose }: Props) {
    const { instance } = useMsal();
    const [profiles, setProfiles] = useState<PersonalMailProfile[]>([]);
    const [loading, setLoading] = useState(false);
    const [busyId, setBusyId] = useState("");
    const [editing, setEditing] = useState<PersonalMailProfile | null>(null);
    const [email, setEmail] = useState("");
    const [username, setUsername] = useState("");
    const [credential, setCredential] = useState("");
    const [notice, setNotice] = useState<{ severity: "success" | "error" | "info"; text: string } | null>(null);

    const load = async () => {
        if (!teamId) return;
        setLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Your session has expired");
            setProfiles(await get_my_mail_profiles(teamId, token));
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to load mail profiles" });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (open) void load();
    }, [open, teamId]);

    const beginEdit = (item: PersonalMailProfile) => {
        setEditing(item);
        setEmail(item.account?.email_address ?? "");
        setUsername(item.account?.public_config?.username ?? "");
        setCredential("");
        setNotice(null);
    };

    const save = async () => {
        if (!editing) return;
        const provider = editing.profile.provider;
        setBusyId(editing.profile._id);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Your session has expired");
            await save_my_mail_account(
                editing.profile._id,
                {
                    email_address: email,
                    public_config: provider === "generic" ? { username: username || email } : {},
                    secrets: provider === "gmail"
                        ? { refresh_token: credential }
                        : provider === "generic"
                          ? { password: credential }
                          : {}
                },
                token
            );
            setEditing(null);
            setNotice({ severity: "info", text: "Account saved. Test it before the Agent can use it." });
            await load();
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to save mail account" });
        } finally {
            setBusyId("");
        }
    };

    const test = async (item: PersonalMailProfile) => {
        setBusyId(item.profile._id);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Your session has expired");
            const result = await test_my_mail_account(item.profile._id, token);
            setNotice({ severity: "success", text: result.message });
            await load();
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Mail account test failed" });
        } finally {
            setBusyId("");
        }
    };

    const disconnect = async (item: PersonalMailProfile) => {
        if (!window.confirm(`Disconnect ${item.profile.name}?`)) return;
        setBusyId(item.profile._id);
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Your session has expired");
            await disconnect_my_mail_account(item.profile._id, token);
            setNotice({ severity: "success", text: "Mail account disconnected." });
            await load();
        } catch (error) {
            setNotice({ severity: "error", text: error instanceof Error ? error.message : "Unable to disconnect mail account" });
        } finally {
            setBusyId("");
        }
    };

    return <>
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle>My email accounts</DialogTitle>
            <DialogContent dividers>
                <Stack spacing={2}>
                    <Typography variant="body2" color="text.secondary">
                        Team: {teamName || "No active Team"}. An Agent using a personal Team Mail Profile can access only your verified account.
                    </Typography>
                    {notice && <Alert severity={notice.severity} onClose={() => setNotice(null)}>{notice.text}</Alert>}
                    {loading ? <Box textAlign="center" py={4}><CircularProgress /></Box> : profiles.length === 0 ? (
                        <Alert severity="info">This Team has no personal Mail Profile. Ask a Team Admin to create one.</Alert>
                    ) : profiles.map(item => {
                        const verified = item.account?.verification_status === "verified";
                        return <Paper key={item.profile._id} variant="outlined" sx={{ p: 2 }}>
                            <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={2}>
                                <Box>
                                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
                                        <Typography fontWeight={700}>{item.profile.name}</Typography>
                                        <Chip size="small" label={item.profile.provider} />
                                        <Chip size="small" color={verified ? "success" : item.account ? "warning" : "default"} label={verified ? "Verified" : item.account ? "Test required" : "Not connected"} />
                                    </Stack>
                                    {item.account?.email_address && <Typography variant="body2" color="text.secondary" mt={.5}>{item.account.email_address}</Typography>}
                                </Box>
                                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                    <Button size="small" onClick={() => beginEdit(item)}>{item.account ? "Update" : "Connect"}</Button>
                                    {item.account && <Button size="small" disabled={busyId === item.profile._id} onClick={() => void test(item)}>Test</Button>}
                                    {item.account && <Button size="small" color="error" disabled={busyId === item.profile._id} onClick={() => void disconnect(item)}>Disconnect</Button>}
                                </Stack>
                            </Stack>
                        </Paper>;
                    })}
                </Stack>
            </DialogContent>
            <DialogActions><Button onClick={onClose}>Close</Button></DialogActions>
        </Dialog>

        <Dialog open={Boolean(editing)} onClose={() => !busyId && setEditing(null)} fullWidth maxWidth="sm">
            <DialogTitle>Connect {editing?.profile.name}</DialogTitle>
            <DialogContent dividers>
                {editing && <Stack spacing={2} pt={1}>
                    {editing.profile.provider === "microsoft365" ? (
                        <Alert severity="info">Your managed Microsoft identity email is selected by the server. You cannot enter another mailbox.</Alert>
                    ) : <TextField label="Mailbox email" type="email" value={email} onChange={event => setEmail(event.target.value)} required fullWidth />}
                    {editing.profile.provider === "gmail" && <TextField label="OAuth refresh token" type="password" value={credential} onChange={event => setCredential(event.target.value)} helperText={editing.account ? "Leave blank to keep the saved token." : "Use a token issued for this mailbox with the approved Gmail scopes."} required={!editing.account} fullWidth autoComplete="new-password" />}
                    {editing.profile.provider === "generic" && <>
                        <TextField label="Username" value={username} onChange={event => setUsername(event.target.value)} placeholder={email} fullWidth />
                        <TextField label="Password / app password" type="password" value={credential} onChange={event => setCredential(event.target.value)} helperText={editing.account ? "Leave blank to keep the saved password." : "Use an app password when required by your mail provider."} required={!editing.account} fullWidth autoComplete="new-password" />
                    </>}
                </Stack>}
            </DialogContent>
            <DialogActions>
                <Button onClick={() => setEditing(null)} disabled={Boolean(busyId)}>Cancel</Button>
                <Button variant="contained" onClick={() => void save()} disabled={Boolean(busyId) || Boolean(editing && editing.profile.provider !== "microsoft365" && !email.includes("@")) || Boolean(editing && !editing.account && editing.profile.provider !== "microsoft365" && !credential)}>{busyId ? "Saving…" : "Save"}</Button>
            </DialogActions>
        </Dialog>
    </>;
}
