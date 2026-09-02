import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";
import {
    Alert,
    Button,
    CircularProgress,
    FormControlLabel,
    MenuItem,
    Paper,
    Stack,
    Switch,
    TextField,
    Typography
} from "@mui/material";

import { getGuardrailSettings, updateGuardrailSettings } from "../../../api";
import { AgentGuardrailPolicy, TeamProfile } from "../../../api/models";
import { getToken } from "../../../authConfig";

const DEFAULT_POLICY: AgentGuardrailPolicy = {
    enabled: true,
    max_input_chars: 20000,
    prompt_injection_action: "block",
    sensitive_input_action: "block",
    sensitive_output_action: "redact",
    pii_input_action: "block",
    pii_output_action: "redact",
    content_safety_input_action: "block",
    content_safety_output_action: "block",
    blocked_phrases: []
};

interface Props {
    team: TeamProfile | null;
}

export function GuardrailPolicyPage({ team }: Props) {
    const { instance } = useMsal();
    const [policy, setPolicy] = useState<AgentGuardrailPolicy>(DEFAULT_POLICY);
    const [configured, setConfigured] = useState(false);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    useEffect(() => {
        setLoading(true);
        setError("");
        void (async () => {
            try {
                const token = await getToken(instance);
                if (!token) throw new Error("Authentication required");
                const result = await getGuardrailSettings(token, team?._id);
                setPolicy({ ...DEFAULT_POLICY, ...result.policy });
                setConfigured(result.configured);
            } catch (reason: any) {
                setError(reason?.message || "Unable to load guardrail settings");
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
            const result = await updateGuardrailSettings(policy, token, team?._id);
            setPolicy({ ...DEFAULT_POLICY, ...result.policy });
            setConfigured(true);
            setMessage(`${team ? "Team" : "System"} guardrail policy saved.`);
        } catch (reason: any) {
            setError(reason?.message || "Unable to save guardrail settings");
        } finally {
            setSaving(false);
        }
    };

    const inputSelect = (
        label: string,
        key: "prompt_injection_action" | "sensitive_input_action" | "pii_input_action" | "content_safety_input_action"
    ) => (
        <TextField
            select
            fullWidth
            size="small"
            label={label}
            disabled={!policy.enabled}
            value={policy[key]}
            onChange={event => setPolicy({ ...policy, [key]: event.target.value })}
        >
            <MenuItem value="block">Block</MenuItem>
            <MenuItem value="warn">Audit only</MenuItem>
            <MenuItem value="allow">Allow</MenuItem>
        </TextField>
    );

    const outputSelect = (
        label: string,
        key: "sensitive_output_action" | "pii_output_action"
    ) => (
        <TextField
            select
            fullWidth
            size="small"
            label={label}
            disabled={!policy.enabled}
            value={policy[key]}
            onChange={event => setPolicy({ ...policy, [key]: event.target.value })}
        >
            <MenuItem value="redact">Redact</MenuItem>
            <MenuItem value="block">Block response</MenuItem>
            <MenuItem value="warn">Audit only</MenuItem>
            <MenuItem value="allow">Allow</MenuItem>
        </TextField>
    );

    if (loading) return <CircularProgress size={28} />;

    return (
        <Stack spacing={2} sx={{ p: 3, overflow: "auto", height: "100%" }}>
            <Typography variant="h6">{team ? `${team.name} guardrail policy` : "System guardrail policy"}</Typography>
            <Alert severity="info">
                {team
                    ? "This Team policy is combined with the System policy. Agents may make controls stricter, but cannot weaken either policy."
                    : "This policy becomes the minimum protection for every Team and Agent. Team and Agent policies may only make it stricter."}
            </Alert>
            {!configured && <Alert severity="warning">No policy has been saved at this level yet. Agent settings currently apply.</Alert>}
            {error && <Alert severity="error">{error}</Alert>}
            {message && <Alert severity="success">{message}</Alert>}
            <Paper variant="outlined" sx={{ p: 2 }}>
                <Stack spacing={2}>
                    <FormControlLabel
                        control={<Switch checked={policy.enabled} onChange={event => setPolicy({ ...policy, enabled: event.target.checked })} />}
                        label={policy.enabled ? "Policy enabled" : "Policy disabled at this level"}
                    />
                    <TextField
                        size="small"
                        type="number"
                        label="Maximum Input Characters"
                        disabled={!policy.enabled}
                        value={policy.max_input_chars}
                        inputProps={{ min: 256, max: 200000 }}
                        onChange={event => setPolicy({ ...policy, max_input_chars: Number(event.target.value) })}
                    />
                    <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                        {inputSelect("Prompt Injection", "prompt_injection_action")}
                        {inputSelect("Secrets in Input", "sensitive_input_action")}
                        {outputSelect("Secrets in Output", "sensitive_output_action")}
                    </Stack>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                        {inputSelect("PII in Input", "pii_input_action")}
                        {outputSelect("PII in Output", "pii_output_action")}
                        {inputSelect("Unsafe Content in Input", "content_safety_input_action")}
                        <TextField
                            select
                            fullWidth
                            size="small"
                            label="Unsafe Content in Output"
                            disabled={!policy.enabled}
                            value={policy.content_safety_output_action}
                            onChange={event =>
                                setPolicy({
                                    ...policy,
                                    content_safety_output_action: event.target.value as "allow" | "warn" | "block"
                                })
                            }
                        >
                            <MenuItem value="block">Block response</MenuItem>
                            <MenuItem value="warn">Audit only</MenuItem>
                            <MenuItem value="allow">Allow</MenuItem>
                        </TextField>
                    </Stack>
                    <TextField
                        size="small"
                        label="Blocked Phrases"
                        disabled={!policy.enabled}
                        value={policy.blocked_phrases.join(", ")}
                        helperText="Optional literal phrases separated by commas. Matching is case-insensitive."
                        onChange={event =>
                            setPolicy({
                                ...policy,
                                blocked_phrases: event.target.value.split(",").map(value => value.trim()).filter(Boolean)
                            })
                        }
                    />
                </Stack>
            </Paper>
            <Stack direction="row" justifyContent="flex-end">
                <Button variant="contained" disabled={saving} onClick={() => void save()}>
                    {saving ? "Saving…" : "Save policy"}
                </Button>
            </Stack>
        </Stack>
    );
}
