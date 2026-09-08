import ContentCopyOutlinedIcon from "@mui/icons-material/ContentCopyOutlined";
import KeyOutlinedIcon from "@mui/icons-material/KeyOutlined";
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Divider, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";

import { getLicenseStatusApi, importLicenseApi, startLicenseTrialApi } from "../../../api";
import { LicenseStatus, LicenseStatusResponse } from "../../../api/models";
import { getToken } from "../../../authConfig";

const statusColor = (status: LicenseStatus) => {
    if (status === "active") return "success" as const;
    if (status === "grace") return "warning" as const;
    if (status === "unlicensed") return "default" as const;
    return "error" as const;
};

const formatDate = (value?: string) => value ? new Date(value).toLocaleString() : "—";

export function LicenseSettingsPage() {
    const { instance } = useMsal();
    const [status, setStatus] = useState<LicenseStatusResponse | null>(null);
    const [licenseKey, setLicenseKey] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");

    const load = async () => {
        setError("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            setStatus(await getLicenseStatusApi(token));
        } catch (reason: any) {
            setError(reason?.message || "Unable to load license status");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void load();
    }, []);

    const startTrial = async () => {
        if (!window.confirm("Start the one-time 14-day trial now? It cannot be restarted for this installation.")) return;
        setSaving(true);
        setError("");
        setMessage("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            setStatus(await startLicenseTrialApi(token));
            setMessage("The 14-day trial has started.");
        } catch (reason: any) {
            setError(reason?.message || "Unable to start trial");
        } finally {
            setSaving(false);
        }
    };

    const importLicense = async () => {
        if (!licenseKey.trim()) return;
        setSaving(true);
        setError("");
        setMessage("");
        try {
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication required");
            setStatus(await importLicenseApi(licenseKey.trim(), token));
            setLicenseKey("");
            setMessage("License verified and activated.");
        } catch (reason: any) {
            setError(reason?.message || "Unable to import license");
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <CircularProgress />;

    return (
        <Stack spacing={2} sx={{ maxWidth: 900 }}>
            <Box>
                <Typography variant="h6">License</Typography>
                <Typography variant="body2" color="text.secondary">
                    Activate a 14-day trial or import an offline license issued for this installation.
                </Typography>
            </Box>
            {status?.audit_mode && <Alert severity="info">License audit mode is active. Entitlements are visible but are not blocking features yet.</Alert>}
            {error && <Alert severity="error">{error}</Alert>}
            {message && <Alert severity="success">{message}</Alert>}

            {status && (
                <Card variant="outlined">
                    <CardContent>
                        <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
                            <Typography variant="h6">Current status</Typography>
                            <Chip color={statusColor(status.status)} label={status.status} sx={{ textTransform: "capitalize" }} />
                            <Typography variant="body2" color="text.secondary">Source: {status.source}</Typography>
                        </Stack>
                        <Divider sx={{ my: 2 }} />
                        <Typography variant="caption" color="text.secondary">Installation ID</Typography>
                        <Stack direction="row" spacing={1} alignItems="center">
                            <Typography sx={{ overflowWrap: "anywhere" }}>{status.installation_id}</Typography>
                            <Button size="small" startIcon={<ContentCopyOutlinedIcon />} onClick={() => void navigator.clipboard.writeText(status.installation_id)}>Copy</Button>
                        </Stack>
                        {status.trial && (
                            <Stack mt={2} spacing={0.5}>
                                <Typography fontWeight={700}>14-day Trial</Typography>
                                <Typography variant="body2">Started: {formatDate(status.trial.started_at)}</Typography>
                                <Typography variant="body2">Expires: {formatDate(status.trial.expires_at)}</Typography>
                            </Stack>
                        )}
                        {status.license && <LicenseDetails value={status.license} />}
                    </CardContent>
                </Card>
            )}

            {status?.trial_available && (
                <Card variant="outlined">
                    <CardContent>
                        <Typography fontWeight={700}>Start evaluation</Typography>
                        <Typography variant="body2" color="text.secondary" mb={1.5}>
                            Trial activation is recorded once for this installation and cannot be restarted.
                        </Typography>
                        <Button variant="contained" onClick={() => void startTrial()} disabled={saving}>Start 14-day trial</Button>
                    </CardContent>
                </Card>
            )}

            <Card variant="outlined">
                <CardContent>
                    <Stack direction="row" spacing={1} alignItems="center" mb={1}>
                        <KeyOutlinedIcon color="primary" />
                        <Typography fontWeight={700}>Activate offline license</Typography>
                    </Stack>
                    <TextField
                        fullWidth
                        type="password"
                        label="License key"
                        value={licenseKey}
                        onChange={event => setLicenseKey(event.target.value)}
                        autoComplete="off"
                        helperText="The raw key is encrypted at rest and is never returned after import."
                    />
                    <Button sx={{ mt: 2 }} variant="contained" onClick={() => void importLicense()} disabled={saving || !licenseKey.trim()}>
                        {saving ? "Verifying…" : "Verify and activate"}
                    </Button>
                </CardContent>
            </Card>
        </Stack>
    );
}

function LicenseDetails({ value }: { value: NonNullable<LicenseStatusResponse["license"]> }) {
    return (
        <Stack mt={2} spacing={1.5}>
            <Typography fontWeight={700}>{value.edition} · {value.customer_id}</Typography>
            <Typography variant="body2">License ID: {value.license_id}</Typography>
            <Typography variant="body2">Valid: {formatDate(value.not_before)} – {formatDate(value.expires_at)}</Typography>
            <Typography variant="body2">Grace period: {value.grace_days} days</Typography>
            <Box>
                <Typography variant="caption" color="text.secondary">Features</Typography>
                <Stack direction="row" gap={1} flexWrap="wrap" mt={0.5}>
                    {Object.entries(value.features).map(([name, enabled]) => <Chip key={name} size="small" color={enabled ? "success" : "default"} label={`${name}: ${enabled ? "On" : "Off"}`} />)}
                </Stack>
            </Box>
            <Box>
                <Typography variant="caption" color="text.secondary">Capacity</Typography>
                <Stack direction="row" gap={1} flexWrap="wrap" mt={0.5}>
                    {Object.entries(value.capacities).map(([name, capacity]) => <Chip key={name} size="small" label={`${name}: ${capacity === null ? "Unlimited" : capacity}`} />)}
                </Stack>
            </Box>
        </Stack>
    );
}
