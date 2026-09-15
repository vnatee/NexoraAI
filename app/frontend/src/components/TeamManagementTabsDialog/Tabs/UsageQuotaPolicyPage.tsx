import { useEffect, useState } from "react";
import { Alert, Button, Chip, CircularProgress, Divider, FormControlLabel, LinearProgress, MenuItem, Paper, Stack, Switch, TextField, Typography } from "@mui/material";
import { useMsal } from "@azure/msal-react";

import { configApi, get_all_users, getQuotaSettings, getTeamUserQuotaSettings, getUserQuotaSettings, get_users_by_team_id, updateQuotaSettings, updateTeamUserQuotaSettings, updateUserQuotaSettings } from "../../../api";
import { LLMProfile, LLMTokenQuotaRule, TeamProfile, UsageQuotaPolicy, UsageQuotaSettingsResponse, User } from "../../../api/models";
import { getToken } from "../../../authConfig";

const DEFAULT_POLICY: UsageQuotaPolicy = {
    enabled: false,
    monthly_llm_tokens: 0,
    monthly_llm_tokens_per_user: 0,
    monthly_document_pages: 0,
    llm_requests_per_minute: 0,
    llm_token_rules: []
};

type QuotaLevel = "system" | "team" | "user";

export function UsageQuotaPolicyPage({ team, isSystemAdmin }: { team: TeamProfile | null; isSystemAdmin: boolean }) {
    const { instance } = useMsal();
    const [policy, setPolicy] = useState(DEFAULT_POLICY);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");
    const [usage, setUsage] = useState({ monthly_llm_tokens: 0, monthly_document_pages: 0 });
    const [ruleUsage, setRuleUsage] = useState<Record<string, number>>({});
    const [status, setStatus] = useState<NonNullable<UsageQuotaSettingsResponse["status"]>>([]);
    const [auditEvents, setAuditEvents] = useState<NonNullable<UsageQuotaSettingsResponse["audit_events"]>>([]);
    const [memberLimitSource, setMemberLimitSource] = useState<UsageQuotaSettingsResponse["member_limit_source"]>("");
    const [effectiveMemberLimit, setEffectiveMemberLimit] = useState(0);
    const [users, setUsers] = useState<User[]>([]);
    const [userId, setUserId] = useState("");
    const [level, setLevel] = useState<QuotaLevel>(team ? "team" : "system");
    const [profiles, setProfiles] = useState<LLMProfile[]>([]);

    useEffect(() => {
        void configApi().then(result => setProfiles(result.llmProfiles ?? [])).catch(() => setProfiles([]));
    }, []);

    useEffect(() => {
        setLevel(team ? "team" : "system");
        setUserId("");
    }, [team?._id]);

    useEffect(() => {
        setLoading(true);
        void (async () => {
            try {
                const token = await getToken(instance);
                if (!token) throw new Error("Authentication required");
                if (team?._id) {
                    const listed = await get_users_by_team_id(team._id, token);
                    setUsers(listed.users ?? []);
                } else if (isSystemAdmin) {
                    const listed = await get_all_users(token);
                    setUsers(listed.result ?? []);
                }
                if (level === "user" && !userId) {
                    setPolicy(DEFAULT_POLICY);
                    setUsage({ monthly_llm_tokens: 0, monthly_document_pages: 0 });
                    setRuleUsage({});
                    setStatus([]);
                    setAuditEvents([]);
                    setMemberLimitSource("");
                    setEffectiveMemberLimit(0);
                    return;
                }
                const result = level === "user"
                    ? team?._id
                        ? await getTeamUserQuotaSettings(token, team._id, userId)
                        : await getUserQuotaSettings(token, userId)
                    : await getQuotaSettings(token, level === "team" ? team?._id : undefined);
                setPolicy({ ...DEFAULT_POLICY, ...result.policy });
                setUsage(result.usage ?? usage);
                setRuleUsage(Object.fromEntries((result.rule_usage ?? []).map(item => [`${item.dimension}:${item.target_id}:${item.workload}`, item.monthly_tokens])));
                setStatus(result.status ?? []);
                setAuditEvents(result.audit_events ?? []);
                setMemberLimitSource(result.member_limit_source ?? "");
                setEffectiveMemberLimit(result.effective_member_limit ?? 0);
            } catch (reason) {
                setError(reason instanceof Error ? reason.message : "Unable to load quotas");
            } finally { setLoading(false); }
        })();
    }, [instance, team?._id, isSystemAdmin, level, userId]);

    const save = async () => {
        setSaving(true); setError(""); setMessage("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            if (level === "user" && !userId) throw new Error("Select a user first");
            const result = level === "user"
                ? team?._id
                    ? await updateTeamUserQuotaSettings(policy, token, team._id, userId)
                    : await updateUserQuotaSettings(policy, token, userId)
                : await updateQuotaSettings(policy, token, level === "team" ? team?._id : undefined);
            setPolicy({ ...DEFAULT_POLICY, ...result.policy });
            setUsage(result.usage ?? usage);
            setRuleUsage(Object.fromEntries((result.rule_usage ?? []).map(item => [`${item.dimension}:${item.target_id}:${item.workload}`, item.monthly_tokens])));
            setStatus(result.status ?? []);
            setAuditEvents(result.audit_events ?? []);
            setMemberLimitSource(result.member_limit_source ?? "");
            setEffectiveMemberLimit(result.effective_member_limit ?? 0);
            setMessage(`${level === "team" ? "Team" : level === "user" ? "User" : "System"} quota policy saved.`);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Unable to save quotas");
        } finally { setSaving(false); }
    };

    if (loading) return <CircularProgress size={28} />;
    const isMemberOverride = level === "user" && Boolean(team?._id);
    const field = (label: string, key: "monthly_llm_tokens" | "monthly_llm_tokens_per_user" | "monthly_document_pages" | "llm_requests_per_minute", helper: string) => (
        <TextField fullWidth type="number" label={label} value={policy[key]} disabled={!policy.enabled}
            inputProps={{ min: 0 }} helperText={helper}
            onChange={event => setPolicy({ ...policy, [key]: Math.max(0, Number(event.target.value) || 0) })} />
    );
    const providerOptions = Array.from(new Map(profiles.map(profile => {
        const id = profile.quotaProviderId ?? `configured:${profile.provider}`;
        const label = profile.managedProviderId ? profile.label.split(" — ")[0] : `Configured ${profile.provider}`;
        return [id, { id, label }] as const;
    })).values());
    const profileOptions = profiles.map(profile => ({ id: profile.id, label: `${profile.label} · ${profile.model}` }));
    const nextRuleTarget = [
        ...providerOptions.map(option => ({ ...option, dimension: "provider" as const })),
        ...profileOptions.map(option => ({ ...option, dimension: "profile" as const }))
    ].find(option => !policy.llm_token_rules.some(rule => rule.dimension === option.dimension && rule.target_id === option.id && rule.workload === "all"));
    const updateRule = (index: number, changes: Partial<LLMTokenQuotaRule>) => {
        setPolicy({ ...policy, llm_token_rules: policy.llm_token_rules.map((rule, ruleIndex) => ruleIndex === index ? { ...rule, ...changes } : rule) });
    };
    const addRule = () => {
        if (!nextRuleTarget) return;
        setPolicy({ ...policy, llm_token_rules: [...policy.llm_token_rules, {
            dimension: nextRuleTarget.dimension, target_id: nextRuleTarget.id, target_label: nextRuleTarget.label,
            workload: "all", monthly_tokens: 0, enabled: true
        }] });
    };
    return <Stack spacing={2} sx={{ p: 3, overflow: "auto", height: "100%" }}>
        <Typography variant="h6">
            {level === "team" ? `${team?.name ?? "Team"} usage quotas` : level === "user" ? "User usage quotas" : "System usage quotas"}
        </Typography>
        <Alert severity="info">{team
            ? "Every request must pass the System total, Team total, and member limit. A custom member value replaces the Team default for that member; it never bypasses the Team or System total."
            : "System and global user ceilings are combined with Team limits. The smallest applicable non-zero ceiling is enforced."}</Alert>
        {(isSystemAdmin || team) && <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField select fullWidth label="Configure level" value={level} onChange={event => { setLevel(event.target.value as QuotaLevel); setUserId(""); setMessage(""); }}>
                {isSystemAdmin && <MenuItem value="system">Entire system</MenuItem>}
                {team && <MenuItem value="team">Current team: {team.name}</MenuItem>}
                <MenuItem value="user">{team ? "Specific member override" : "Global user ceiling"}</MenuItem>
            </TextField>
            {level === "user" && <TextField select fullWidth label="User" value={userId} onChange={event => setUserId(event.target.value)}>
                <MenuItem value="" disabled>Select user</MenuItem>
                {users.map(user => <MenuItem key={user._id} value={user._id}>{`${user.first_name} ${user.last_name}`.trim() || user.email || user.ad_email}</MenuItem>)}
            </TextField>}
        </Stack>}
        {!isSystemAdmin && team && <Alert severity="info">You can configure this Team and its member overrides. System limits remain managed by a System Admin.</Alert>}
        {error && <Alert severity="error">{error}</Alert>}{message && <Alert severity="success">{message}</Alert>}
        {status.length > 0 && <Paper variant="outlined" sx={{ p: 2 }}><Stack spacing={1.5}>
            <Typography variant="subtitle1" fontWeight={600}>Current period</Typography>
            {status.map((item, index) => <Stack key={`${item.kind}:${item.label}:${index}`} spacing={0.5}>
                <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "center" }} spacing={1}>
                    <Typography variant="body2" sx={{ overflowWrap: "anywhere" }}>{item.label}</Typography>
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                        {item.reserved > 0 && <Chip size="small" label={`${item.reserved.toLocaleString()} reserved`} />}
                        <Typography variant="body2" color={item.severity === "normal" ? "text.secondary" : "warning.main"}>{`${item.used.toLocaleString()} / ${item.limit.toLocaleString()} (${item.percentage}%)`}</Typography>
                    </Stack>
                </Stack>
                <LinearProgress variant="determinate" color={item.severity === "exceeded" || item.severity === "critical" ? "error" : item.severity === "warning" ? "warning" : "primary"} value={Math.min(100, item.percentage)} />
            </Stack>)}
        </Stack></Paper>}
        <Paper variant="outlined" sx={{ p: 2 }}><Stack spacing={2}>
            <FormControlLabel control={<Switch checked={policy.enabled} onChange={event => setPolicy({ ...policy, enabled: event.target.checked })} />} label={isMemberOverride ? (policy.enabled ? "Custom member override enabled" : "Use Team default per-member limit") : (policy.enabled ? "Quota policy enabled" : "Quota policy disabled at this level")} />
            {isMemberOverride && memberLimitSource && <Alert severity="info">Effective member limit: {effectiveMemberLimit === 0 ? "Unlimited at member level" : `${effectiveMemberLimit.toLocaleString()} tokens/month`} ({memberLimitSource === "override" ? "custom override" : "Team default"}). Team and System totals still apply.</Alert>}
            <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                {field("Monthly LLM tokens", "monthly_llm_tokens", `Used this month: ${usage.monthly_llm_tokens.toLocaleString()}`)}
                {level === "team" && field("Default monthly tokens per member", "monthly_llm_tokens_per_user", "Used when a member has no custom override")}
                {!isMemberOverride && field("Monthly document pages", "monthly_document_pages", `Used this month: ${usage.monthly_document_pages.toLocaleString()}`)}
                {!isMemberOverride && field("LLM requests per minute", "llm_requests_per_minute", "Protects providers from request bursts")}
            </Stack>
            {!isMemberOverride && <Divider />}
            {!isMemberOverride && <>
            <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} spacing={1}>
                <div>
                    <Typography variant="subtitle1" fontWeight={600}>Provider and model limits</Typography>
                    <Typography variant="body2" color="text.secondary">Optional monthly limits. Every matching rule must pass; Overall remains the safety net.</Typography>
                </div>
                <Button variant="outlined" disabled={!policy.enabled || !nextRuleTarget} onClick={addRule}>Add limit</Button>
            </Stack>
            {policy.llm_token_rules.length === 0 && <Typography variant="body2" color="text.secondary">No provider or model-specific limits.</Typography>}
            {policy.llm_token_rules.map((rule, index) => {
                const options = rule.dimension === "provider" ? providerOptions : profileOptions;
                const available = options.some(option => option.id === rule.target_id);
                return <Paper key={`${rule.dimension}:${rule.target_id}:${rule.workload}:${index}`} variant="outlined" sx={{ p: 2 }}>
                    <Stack direction={{ xs: "column", lg: "row" }} spacing={1.5} alignItems={{ lg: "center" }}>
                        <FormControlLabel control={<Switch checked={rule.enabled} disabled={!policy.enabled} onChange={event => updateRule(index, { enabled: event.target.checked })} />} label="Active" />
                        <TextField select label="Limit by" value={rule.dimension} disabled={!policy.enabled} sx={{ minWidth: 150 }} onChange={event => {
                            const dimension = event.target.value as LLMTokenQuotaRule["dimension"];
                            const nextOptions = dimension === "provider" ? providerOptions : profileOptions;
                            updateRule(index, { dimension, target_id: nextOptions[0]?.id ?? "", target_label: nextOptions[0]?.label ?? "" });
                        }}>
                            <MenuItem value="provider">Provider</MenuItem><MenuItem value="profile">Model profile</MenuItem>
                        </TextField>
                        <TextField select fullWidth label={rule.dimension === "provider" ? "Provider" : "Model profile"} value={rule.target_id} disabled={!policy.enabled} onChange={event => {
                            const selected = options.find(option => option.id === event.target.value);
                            updateRule(index, { target_id: event.target.value, target_label: selected?.label ?? event.target.value });
                        }}>
                            {!available && <MenuItem value={rule.target_id}>{rule.target_label} (Unavailable)</MenuItem>}
                            {options.map(option => <MenuItem key={option.id} value={option.id}>{option.label}</MenuItem>)}
                        </TextField>
                        <TextField select label="Workload" value={rule.workload} disabled={!policy.enabled} sx={{ minWidth: 150 }} onChange={event => updateRule(index, { workload: event.target.value as LLMTokenQuotaRule["workload"] })}>
                            <MenuItem value="all">All requests</MenuItem><MenuItem value="chat">Chat</MenuItem><MenuItem value="ask">Ask</MenuItem>
                        </TextField>
                        <TextField type="number" label="Monthly tokens" value={rule.monthly_tokens} disabled={!policy.enabled} inputProps={{ min: 0 }} sx={{ minWidth: 190 }} helperText={`Used: ${(ruleUsage[`${rule.dimension}:${rule.target_id}:${rule.workload}`] ?? 0).toLocaleString()}`} onChange={event => updateRule(index, { monthly_tokens: Math.max(0, Number(event.target.value) || 0) })} />
                        <Button color="error" disabled={!policy.enabled} onClick={() => setPolicy({ ...policy, llm_token_rules: policy.llm_token_rules.filter((_, ruleIndex) => ruleIndex !== index) })}>Remove</Button>
                    </Stack>
                </Paper>;
            })}</>}
        </Stack></Paper>
        {auditEvents.length > 0 && <Paper variant="outlined" sx={{ p: 2 }}><Stack spacing={1}>
            <Typography variant="subtitle1" fontWeight={600}>Recent quota events</Typography>
            {auditEvents.slice(0, 10).map(event => <Stack key={event._id} direction={{ xs: "column", md: "row" }} spacing={1} alignItems={{ md: "center" }}>
                <Chip size="small" color={event.event_type === "quota_blocked" || event.event_type === "metering_failed" ? "error" : "warning"} label={event.event_type === "quota_blocked" ? "Blocked" : event.event_type === "metering_failed" ? "Metering failed" : `${event.threshold}% threshold`} />
                <Typography variant="body2">{`${event.projected.toLocaleString()} projected / ${event.limit.toLocaleString()} limit · ${event.workload || "all"}`}</Typography>
                <Typography variant="caption" color="text.secondary">{new Date(event.created_at).toLocaleString()}</Typography>
            </Stack>)}
        </Stack></Paper>}
        <Stack direction="row" justifyContent="flex-end"><Button variant="contained" disabled={saving || (level === "user" && !userId)} onClick={() => void save()}>{saving ? "Saving…" : "Save quotas"}</Button></Stack>
    </Stack>;
}
