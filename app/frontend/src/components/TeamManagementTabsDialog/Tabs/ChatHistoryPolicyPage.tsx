import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";
import { Alert, Button, CircularProgress, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";

import { getChatHistoryRetentionSettings, updateChatHistoryRetentionSettings } from "../../../api";
import { TeamProfile } from "../../../api/models";
import { getToken } from "../../../authConfig";

interface Props {
    team: TeamProfile | null;
}

export function ChatHistoryPolicyPage({ team }: Props) {
    const { instance } = useMsal();
    const [days, setDays] = useState(90);
    const [systemDays, setSystemDays] = useState<number | null>(null);
    const [effectiveDays, setEffectiveDays] = useState(90);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    useEffect(() => {
        setLoading(true);
        setMessage("");
        setError("");
        void (async () => {
            try {
                const token = await getToken(instance);
                if (!token) throw new Error("Authentication required");
                const result = await getChatHistoryRetentionSettings(token, team?._id);
                setDays(result.configured_days ?? result.effective_days);
                setEffectiveDays(result.effective_days);
                setSystemDays(result.system_days ?? null);
            } catch (reason: any) {
                setError(reason?.message || "Unable to load chat history retention settings");
            } finally {
                setLoading(false);
            }
        })();
    }, [instance, team?._id]);

    const save = async () => {
        setSaving(true);
        setMessage("");
        setError("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            const result = await updateChatHistoryRetentionSettings(days, token, team?._id);
            setDays(result.configured_days ?? result.effective_days);
            setEffectiveDays(result.effective_days);
                setSystemDays(result.system_days ?? null);
            setMessage(`${team ? "Team" : "System"} retention policy saved.`);
        } catch (reason: any) {
            setError(reason?.message || "Unable to save chat history retention settings");
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <CircularProgress size={28} />;

    return (
        <Stack spacing={2} sx={{ p: 3, overflow: "auto", height: "100%", boxSizing: "border-box" }}>
            <Typography variant="h6">{team ? `${team.name} chat history` : "System chat history"}</Typography>
            <Alert severity="info">
                {team
                    ? `Team conversations expire after the stricter of this value and the System limit${systemDays === 0 ? " (no expiry)" : systemDays !== null ? ` (${systemDays} days)` : ""}.`
                    : "Server-side chat conversations are owner-isolated and automatically expire after this period."}
            </Alert>
            {error && <Alert severity="error">{error}</Alert>}
            {message && <Alert severity="success">{message}</Alert>}
            <Paper variant="outlined" sx={{ p: 2 }}>
                <Stack spacing={2}>
                    <TextField
                        select
                        size="small"
                        label="Retention period"
                        value={days}
                        helperText={`Effective retention: ${effectiveDays === 0 ? "No expiry" : `${effectiveDays} days`}.`}
                        onChange={event => setDays(Number(event.target.value))}
                    >
                        {[30, 90, 180, 365]
                            .filter(value => !team || systemDays === 0 || systemDays === null || value <= systemDays)
                            .map(value => <MenuItem key={value} value={value}>{value} days</MenuItem>)}
                        {(!team || systemDays === 0) && <MenuItem value={0}>No expiry</MenuItem>}
                    </TextField>
                    <Typography variant="body2" color="text.secondary">
                        Expiry is recalculated from each conversation's last update. MongoDB TTL removes expired records automatically; the application cleanup loop provides an additional safeguard.
                    </Typography>
                </Stack>
            </Paper>
            <Stack direction="row" justifyContent="flex-end">
                <Button
                    variant="contained"
                    disabled={saving}
                    onClick={() => void save()}
                >
                    {saving ? "Saving…" : "Save retention"}
                </Button>
            </Stack>
        </Stack>
    );
}
