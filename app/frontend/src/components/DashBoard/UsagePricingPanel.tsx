import React, { useEffect, useMemo, useState } from "react";
import {
    Alert, Autocomplete, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle,
    FormControl, InputLabel, MenuItem, Paper, Select, Stack, TextField, Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { useMsal } from "@azure/msal-react";

import {
    createUsagePriceProfileApi, listUsagePriceProfilesApi, retireUsagePriceProfileApi
} from "../../api/api";
import { UsagePriceProfile, UsagePriceProfilePayload } from "../../api/models";
import { getToken } from "../../authConfig";

const today = () => new Date().toISOString().slice(0, 10);
const initialForm = {
    name: "", pricing_type: "token" as "token" | "local_tco", provider: "", provider_id: "",
    model: "", profile_id: "", route_type: "", effective_from: today(), effective_to: "",
    source_type: "manual", source_reference: "", input_usd_per_million: "",
    cached_input_usd_per_million: "", output_usd_per_million: "",
    hardware_purchase_usd: "", residual_value_usd: "", useful_life_years: "3",
    annual_maintenance_usd: "", annual_operations_usd: "", average_power_kw: "",
    pue: "1.4", electricity_usd_per_kwh: "", cloud_gpu_usd_per_hour: "",
    aggregate_tokens_per_second: "", utilization: "0.5"
};

type FormState = typeof initialForm;

const numeric = (value: string) => value === "" ? 0 : Number(value);

type Suggestion = { value: string; label: string };

export const UsagePricingPanel: React.FC<{
    visible: boolean;
    suggestions?: Record<string, Suggestion[]>;
}> = ({ visible, suggestions = {} }) => {
    const client = useMsal().instance;
    const [profiles, setProfiles] = useState<UsagePriceProfile[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [open, setOpen] = useState(false);
    const [form, setForm] = useState<FormState>(initialForm);

    const load = async () => {
        setLoading(true); setError("");
        try {
            const token = await getToken(client);
            if (!token) throw new Error("Authentication is required");
            setProfiles(await listUsagePriceProfilesApi(token));
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Unable to load price catalog");
        } finally { setLoading(false); }
    };

    useEffect(() => { if (visible) void load(); }, [visible]);

    const calculated = useMemo(() => {
        if (form.pricing_type !== "local_tco") return null;
        const life = Math.max(numeric(form.useful_life_years), 0.1);
        const hourly = (numeric(form.hardware_purchase_usd) - numeric(form.residual_value_usd)) / (life * 365 * 24)
            + (numeric(form.annual_maintenance_usd) + numeric(form.annual_operations_usd)) / (365 * 24)
            + numeric(form.average_power_kw) * numeric(form.pue) * numeric(form.electricity_usd_per_kwh)
            + numeric(form.cloud_gpu_usd_per_hour);
        const capacity = numeric(form.aggregate_tokens_per_second) * 3600 * numeric(form.utilization);
        return { hourly, perMillion: capacity > 0 ? hourly / capacity * 1_000_000 : 0 };
    }, [form]);

    const change = (key: keyof FormState, value: string) => setForm(current => ({ ...current, [key]: value }));
    const submit = async () => {
        setSaving(true); setError("");
        try {
            const token = await getToken(client);
            if (!token) throw new Error("Authentication is required");
            const payload: UsagePriceProfilePayload = {
                name: form.name, pricing_type: form.pricing_type,
                provider: form.provider, provider_id: form.provider_id, model: form.model,
                profile_id: form.profile_id, route_type: form.route_type,
                effective_from: form.effective_from, effective_to: form.effective_to || null,
                source_type: form.pricing_type === "local_tco" ? "local_tco" : form.source_type,
                source_reference: form.source_reference,
                input_usd_per_million: numeric(form.input_usd_per_million),
                cached_input_usd_per_million: numeric(form.cached_input_usd_per_million),
                output_usd_per_million: numeric(form.output_usd_per_million),
                ...(form.pricing_type === "local_tco" ? { local_tco: {
                    hardware_purchase_usd: numeric(form.hardware_purchase_usd),
                    residual_value_usd: numeric(form.residual_value_usd),
                    useful_life_years: numeric(form.useful_life_years),
                    annual_maintenance_usd: numeric(form.annual_maintenance_usd),
                    annual_operations_usd: numeric(form.annual_operations_usd),
                    average_power_kw: numeric(form.average_power_kw), pue: numeric(form.pue),
                    electricity_usd_per_kwh: numeric(form.electricity_usd_per_kwh),
                    cloud_gpu_usd_per_hour: numeric(form.cloud_gpu_usd_per_hour),
                    aggregate_tokens_per_second: numeric(form.aggregate_tokens_per_second),
                    utilization: numeric(form.utilization)
                }} : {})
            };
            await createUsagePriceProfileApi(payload, token);
            setOpen(false); setForm(initialForm); await load();
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Unable to create price profile");
        } finally { setSaving(false); }
    };

    const retire = async (profile: UsagePriceProfile) => {
        if (!window.confirm(`Retire price version “${profile.name}”? Historical usage will keep using its effective dates.`)) return;
        try {
            const token = await getToken(client);
            if (!token) throw new Error("Authentication is required");
            await retireUsagePriceProfileApi(profile._id, token); await load();
        } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to retire price profile"); }
    };

    const fields: Array<[keyof FormState, string]> = form.pricing_type === "local_tco" ? [
        ["hardware_purchase_usd", "Hardware purchase (USD)"], ["residual_value_usd", "Residual value (USD)"],
        ["useful_life_years", "Useful life (years)"], ["annual_maintenance_usd", "Annual maintenance (USD)"],
        ["annual_operations_usd", "Annual operations (USD)"], ["average_power_kw", "Average power (kW)"],
        ["pue", "PUE"], ["electricity_usd_per_kwh", "Electricity (USD/kWh)"],
        ["cloud_gpu_usd_per_hour", "Cloud GPU (USD/hour)"], ["aggregate_tokens_per_second", "Aggregate tokens/second"],
        ["utilization", "Utilization (0–1)"]
    ] : [
        ["input_usd_per_million", "Input USD / 1M tokens"],
        ["cached_input_usd_per_million", "Cached input USD / 1M tokens"],
        ["output_usd_per_million", "Output USD / 1M tokens"]
    ];

    return <Stack spacing={2}>
        <Alert severity="info">Prices are versioned estimates in USD. Empty matches act as wildcards; the most specific active version wins. Unknown usage remains Unpriced, never $0.</Alert>
        {error && <Alert severity="error">{error}</Alert>}
        <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Box><Typography variant="h6" fontWeight={800}>Price catalog</Typography><Typography variant="body2" color="text.secondary">Cloud token rates and Local AI total cost of ownership.</Typography></Box>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>Add price version</Button>
        </Stack>
        {profiles.length === 0 && !loading ? <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}><Typography color="text.secondary">No price versions yet. Usage will be shown as Unpriced.</Typography></Paper> : profiles.map(profile => <Paper key={profile._id} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Stack direction={{ xs: "column", md: "row" }} gap={2} alignItems={{ md: "center" }}>
                <Box flex={1}><Stack direction="row" gap={1} alignItems="center"><Typography fontWeight={800}>{profile.name}</Typography><Chip size="small" label={profile.enabled ? "Active" : "Retired"} color={profile.enabled ? "success" : "default"} /></Stack>
                    <Typography variant="body2" color="text.secondary">{[profile.provider, profile.provider_id, profile.model, profile.profile_id, profile.route_type].filter(Boolean).join(" · ")} · Effective {profile.effective_from.slice(0, 10)}{profile.effective_to ? ` to ${profile.effective_to.slice(0, 10)}` : " onward"}</Typography>
                </Box>
                <Typography fontWeight={700}>{profile.pricing_type === "local_tco" ? `$${profile.local_tco?.blended_usd_per_million_tokens.toFixed(4)} / 1M blended` : `$${profile.input_usd_per_million} in · $${profile.cached_input_usd_per_million} cached · $${profile.output_usd_per_million} out`}</Typography>
                {profile.enabled && <Button color="warning" onClick={() => void retire(profile)}>Retire</Button>}
            </Stack>
        </Paper>)}
        <Dialog open={open} onClose={() => !saving && setOpen(false)} maxWidth="md" fullWidth>
            <DialogTitle>Add immutable price version</DialogTitle>
            <DialogContent><Stack spacing={2} sx={{ pt: 1 }}>
                <TextField label="Name" required value={form.name} onChange={e => change("name", e.target.value)} />
                <FormControl><InputLabel>Pricing method</InputLabel><Select label="Pricing method" value={form.pricing_type} onChange={e => change("pricing_type", e.target.value)}><MenuItem value="token">Provider token rates</MenuItem><MenuItem value="local_tco">Local AI TCO</MenuItem></Select></FormControl>
                <Typography fontWeight={800}>Match usage</Typography>
                <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "1fr 1fr" }} gap={2}>
                    {([ ["provider", "Provider", "providers"], ["model", "Resolved model", "models"], ["route_type", "Route type", "routes"] ] as Array<[keyof FormState, string, string]>).map(([key, label, kind]) => <Autocomplete
                        key={key} freeSolo value={form[key]}
                        options={(suggestions[kind] ?? []).map(item => item.value)}
                        onInputChange={(_event, value) => change(key, value)}
                        renderInput={params => <TextField {...params} label={label} helperText="Choose observed usage or enter an exact value; blank means any" />}
                    />)}
                    <TextField label="Provider ID / gateway" value={form.provider_id} onChange={e => change("provider_id", e.target.value)} helperText="Leave blank for any" />
                    <TextField label="LLM profile ID" value={form.profile_id} onChange={e => change("profile_id", e.target.value)} helperText="Leave blank for any" />
                </Box>
                <Typography fontWeight={800}>{form.pricing_type === "local_tco" ? "Cost assumptions" : "Token rates"}</Typography>
                <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "1fr 1fr" }} gap={2}>{fields.map(([key, label]) => <TextField key={key} type="number" label={label} value={form[key]} onChange={e => change(key, e.target.value)} inputProps={{ min: 0, step: "any" }} />)}</Box>
                {calculated && <Alert severity="success">Preview: ${calculated.hourly.toFixed(4)}/hour loaded cost · ${calculated.perMillion.toFixed(4)}/1M tokens</Alert>}
                <Typography fontWeight={800}>Validity and source</Typography>
                <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "1fr 1fr" }} gap={2}><TextField type="date" label="Effective from" required value={form.effective_from} onChange={e => change("effective_from", e.target.value)} InputLabelProps={{ shrink: true }} /><TextField type="date" label="Effective to (optional)" value={form.effective_to} onChange={e => change("effective_to", e.target.value)} InputLabelProps={{ shrink: true }} /></Box>
                {form.pricing_type === "token" && <TextField label="Source type" value={form.source_type} onChange={e => change("source_type", e.target.value)} helperText="For example: manual, provider_price_list, contract" />}
                <TextField label="Source reference" value={form.source_reference} onChange={e => change("source_reference", e.target.value)} helperText="URL, contract/version reference, or assumption note. Do not enter credentials." />
            </Stack></DialogContent>
            <DialogActions><Button onClick={() => setOpen(false)} disabled={saving}>Cancel</Button><Button variant="contained" onClick={() => void submit()} disabled={saving || !form.name || !form.effective_from || ![form.provider, form.provider_id, form.model, form.profile_id, form.route_type].some(Boolean)}>{saving ? "Saving..." : "Create version"}</Button></DialogActions>
        </Dialog>
    </Stack>;
};
