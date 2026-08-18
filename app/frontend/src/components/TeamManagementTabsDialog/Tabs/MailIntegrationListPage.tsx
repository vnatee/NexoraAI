import React, { useEffect, useState } from "react";
import {
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    InputAdornment,
    MenuItem,
    Paper,
    Skeleton,
    Stack,
    TextField,
    Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import EmailIcon from "@mui/icons-material/Email";
import Visibility from "@mui/icons-material/Visibility";
import VisibilityOff from "@mui/icons-material/VisibilityOff";

import { MailEmailConfig, MailProtocol, MailEncryption, TeamProfile } from "../../../api/models";
import { get_mail_configs, insert_mail_config, edit_mail_config, delete_mail_config } from "../../../api/api";
import { getToken } from "../../../authConfig";
import { useMsal } from "@azure/msal-react";
import { useNotification } from "../../../utill/NotificationProvider";

interface MailIntegrationListPageProps {
    team: TeamProfile;
    onBack: () => void;
}

export function MailIntegrationListPage({ team, onBack }: MailIntegrationListPageProps) {
    const [configs, setConfigs] = useState<MailEmailConfig[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState<MailEmailConfig | null>(null);

    const client = useMsal().instance;
    const { showNotification } = useNotification();

    const loadConfigs = async (tokenOverride?: string) => {
        const token = tokenOverride ?? (await getToken(client));
        if (!token) throw new Error("No authentication token");

        const res = await get_mail_configs(team._id, token);
        setConfigs(Array.isArray(res) ? res : []);
    };

    useEffect(() => {
        async function load() {
            try {
                setLoading(true);
                await loadConfigs();
            } catch (err) {
                console.error("load mail configs failed", err);
                showNotification("Failed to load mail configurations", "error");
            } finally {
                setLoading(false);
            }
        }

        load();
    }, [client, team._id]);

    const handleSave = async (config: MailEmailConfig) => {
        try {
            setSaving(true);
            setLoading(true);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            const payload: any = {
                team_id: team._id,
                name: config.name,
                email: config.email,
                password: config.password,
                server: config.server,
                port: config.port,
                protocol: config.protocol,
                encryption: config.encryption
            };

            if (editing) {
                payload.config_id = config._id;
                await edit_mail_config(payload, token);
                showNotification("Mail configuration updated successfully", "success");
            } else {
                await insert_mail_config(payload, token);
                showNotification("Mail configuration created successfully", "success");
            }

            await loadConfigs(token);
            setOpen(false);
            setEditing(null);
        } catch (err) {
            console.error("save mail config failed", err);
            showNotification("Failed to save mail configuration", "error");
        } finally {
            setSaving(false);
            setLoading(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!window.confirm("Are you sure you want to delete this mail configuration?")) return;

        try {
            setDeletingId(id);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            await delete_mail_config(id, token);
            setConfigs(prev => prev.filter(item => item._id !== id));
            showNotification("Mail configuration deleted successfully", "success");
        } catch (err) {
            console.error("delete mail config failed", err);
            showNotification("Failed to delete mail configuration", "error");
        } finally {
            setDeletingId(null);
        }
    };

    return (
        <Box p={3} sx={{ height: "100%", overflowY: "auto" }}>
            {/* Header row */}
            <Stack direction="row" alignItems="center" spacing={2} mb={2}>
                <IconButton onClick={onBack}>
                    <ArrowBackIcon />
                </IconButton>
                <Box>
                    <Typography variant="h6">Mail Integrations</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Store SMTP/IMAP email server configurations here so backend services can send or receive email on behalf of the team.
                    </Typography>
                </Box>
            </Stack>

            {/* Summary card */}
            <Stack direction={{ xs: "column", md: "row" }} spacing={2} mb={3}>
                <SummaryCard title="Mail Connections" value={configs.length} subtitle="Configured email accounts" />
            </Stack>

            {/* Add Connection button */}
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)} sx={{ mb: 2 }}>
                Add Connection
            </Button>

            {/* Loading / empty state / list */}
            {loading ? (
                <MailConfigSkeleton count={3} />
            ) : configs.length === 0 ? (
                <EmptyState
                    icon={<EmailIcon sx={{ fontSize: 48, opacity: 0.3 }} />}
                    title="No mail configurations yet"
                    description="Add an email server configuration first so backend services can send or receive email on behalf of the team."
                />
            ) : (
                <Stack spacing={2}>
                    {configs.map(conn => (
                        <Paper
                            key={conn._id}
                            variant="outlined"
                            sx={{
                                p: 2.5,
                                borderRadius: 2
                            }}
                        >
                            <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={2}>
                                <Box>
                                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                                        <Typography fontWeight={700}>{conn.name}</Typography>
                                        <Chip size="small" label={conn.protocol} />
                                        <Chip size="small" label={conn.encryption} variant="outlined" />
                                    </Stack>

                                    <Typography variant="body2" color="text.secondary" mt={0.75}>
                                        {conn.email}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        {conn.server}:{conn.port}
                                    </Typography>
                                </Box>

                                <Stack direction="row" spacing={1} alignSelf={{ xs: "flex-start", md: "center" }}>
                                    <IconButton
                                        onClick={() => {
                                            setEditing(conn);
                                            setOpen(true);
                                        }}
                                    >
                                        <EditIcon />
                                    </IconButton>

                                    <IconButton color="error" disabled={deletingId === conn._id} onClick={() => handleDelete(conn._id)}>
                                        {deletingId === conn._id ? <CircularProgress size={20} color="inherit" /> : <DeleteIcon />}
                                    </IconButton>
                                </Stack>
                            </Stack>
                        </Paper>
                    ))}
                </Stack>
            )}

            <EmailConfigDialog
                open={open}
                config={editing}
                team={team}
                saving={saving}
                onClose={() => {
                    if (saving) return;
                    setOpen(false);
                    setEditing(null);
                }}
                onSave={handleSave}
            />
        </Box>
    );
}

// ─── Internal helper components ──────────────────────────────────────────────

function SummaryCard({ title, value, subtitle }: { title: string; value: number; subtitle: string }) {
    return (
        <Paper
            variant="outlined"
            sx={{
                p: 2,
                flex: 1,
                minWidth: 0,
                borderRadius: 2
            }}
        >
            <Typography variant="body2" color="text.secondary">
                {title}
            </Typography>
            <Typography variant="h5" fontWeight={700} mt={0.5}>
                {value}
            </Typography>
            <Typography variant="caption" color="text.secondary">
                {subtitle}
            </Typography>
        </Paper>
    );
}

function EmptyState({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
    return (
        <Box
            sx={{
                mt: 4,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                textAlign: "center",
                gap: 1.5,
                color: "text.secondary"
            }}
        >
            {icon}
            <Typography variant="body1">{title}</Typography>
            <Typography variant="body2" sx={{ maxWidth: 520 }}>
                {description}
            </Typography>
        </Box>
    );
}

function MailConfigSkeleton({ count = 3 }: { count?: number }) {
    return (
        <Stack spacing={2}>
            {Array.from({ length: count }).map((_, index) => (
                <Paper key={index} variant="outlined" sx={{ p: 2.5 }}>
                    <Skeleton variant="text" width="30%" height={28} />
                    <Skeleton variant="text" width="45%" height={22} />
                    <Skeleton variant="text" width="25%" height={18} />
                </Paper>
            ))}
        </Stack>
    );
}

// ─── EmailConfigDialog ────────────────────────────────────────────────────────

interface EmailConfigDialogProps {
    open: boolean;
    config: MailEmailConfig | null;
    team: TeamProfile;
    saving: boolean;
    onClose: () => void;
    onSave: (config: MailEmailConfig) => void;
}

const QUICK_PORTS: { label: string; port: number; protocol: MailProtocol; encryption: MailEncryption }[] = [
    { label: "587 SMTP", port: 587, protocol: "SMTP", encryption: "STARTTLS" },
    { label: "465 SSL", port: 465, protocol: "SMTP", encryption: "SSL" },
    { label: "993 IMAP", port: 993, protocol: "IMAP", encryption: "SSL" },
    { label: "143 IMAP", port: 143, protocol: "IMAP", encryption: "STARTTLS" }
];

function EmailConfigDialog({ open, config, team: _team, saving, onClose, onSave }: EmailConfigDialogProps) {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [server, setServer] = useState("");
    const [port, setPort] = useState(587);
    const [protocol, setProtocol] = useState<MailProtocol>("SMTP");
    const [encryption, setEncryption] = useState<MailEncryption>("STARTTLS");
    const [showPassword, setShowPassword] = useState(false);

    useEffect(() => {
        if (!open) return;

        if (config) {
            setName(config.name);
            setEmail(config.email);
            setPassword(config.password ?? "");
            setServer(config.server);
            setPort(config.port);
            setProtocol(config.protocol);
            setEncryption(config.encryption);
        } else {
            setName("");
            setEmail("");
            setPassword("");
            setServer("");
            setPort(587);
            setProtocol("SMTP");
            setEncryption("STARTTLS");
        }

        setShowPassword(false);
    }, [config, open]);

    const applyQuickPort = (preset: (typeof QUICK_PORTS)[number]) => {
        if (port && window.confirm(`Replace current port (${port}) with ${preset.port}?`)) {
            setPort(preset.port);
            setProtocol(preset.protocol);
            setEncryption(preset.encryption);
        } else if (!port) {
            setPort(preset.port);
            setProtocol(preset.protocol);
            setEncryption(preset.encryption);
        }
    };

    const isEditMode = config !== null;
    const isValid =
        name.trim() !== "" &&
        /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) &&
        server.trim() !== "" &&
        port >= 1 &&
        port <= 65535 &&
        (protocol === "SMTP" || protocol === "IMAP") &&
        (encryption === "STARTTLS" || encryption === "SSL" || encryption === "None") &&
        (isEditMode || password !== "");

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle>{config ? "Edit Mail Configuration" : "Add Mail Configuration"}</DialogTitle>

            <DialogContent dividers>
                <Stack spacing={3}>
                    {/* ── Identity ── */}
                    <Typography variant="subtitle2" color="text.secondary">
                        Identity
                    </Typography>

                    <TextField
                        label="Configuration Name"
                        disabled={saving}
                        value={name}
                        onChange={e => setName(e.target.value)}
                        fullWidth
                        placeholder="e.g. Marketing Support"
                    />

                    {/* ── Credentials ── */}
                    <Typography variant="subtitle2" color="text.secondary">
                        Credentials
                    </Typography>

                    <TextField
                        label="Email Address"
                        disabled={saving}
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        fullWidth
                        placeholder="user@domain.com"
                    />

                    <TextField
                        label="Password"
                        disabled={saving}
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        type={showPassword ? "text" : "password"}
                        fullWidth
                        helperText={isEditMode ? "Leave blank to keep existing password" : undefined}
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <IconButton size="small" onClick={() => setShowPassword(v => !v)} edge="end">
                                        {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                                    </IconButton>
                                </InputAdornment>
                            )
                        }}
                    />

                    {/* ── Server Configuration ── */}
                    <Typography variant="subtitle2" color="text.secondary">
                        Server Configuration
                    </Typography>

                    <TextField
                        label="Server"
                        disabled={saving}
                        value={server}
                        onChange={e => setServer(e.target.value)}
                        fullWidth
                        placeholder="e.g. mail.example.com"
                    />

                    <Stack direction="row" spacing={2} alignItems="flex-start">
                        <TextField
                            label="Port"
                            disabled={saving}
                            value={port}
                            onChange={e => setPort(Number(e.target.value))}
                            type="number"
                            sx={{ width: 120, flexShrink: 0 }}
                            inputProps={{ min: 1, max: 65535 }}
                        />

                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap pt={1}>
                            {QUICK_PORTS.map(p => (
                                <Button key={p.label} size="small" variant="outlined" onClick={() => applyQuickPort(p)} disabled={saving}>
                                    {p.label}
                                </Button>
                            ))}
                        </Stack>
                    </Stack>

                    <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                        <TextField
                            select
                            label="Protocol"
                            disabled={saving}
                            value={protocol}
                            onChange={e => setProtocol(e.target.value as MailProtocol)}
                            fullWidth
                        >
                            <MenuItem value="SMTP">SMTP</MenuItem>
                            <MenuItem value="IMAP">IMAP</MenuItem>
                        </TextField>

                        <TextField
                            select
                            label="Encryption"
                            disabled={saving}
                            value={encryption}
                            onChange={e => setEncryption(e.target.value as MailEncryption)}
                            fullWidth
                        >
                            <MenuItem value="STARTTLS">STARTTLS</MenuItem>
                            <MenuItem value="SSL">SSL</MenuItem>
                            <MenuItem value="None">None</MenuItem>
                        </TextField>
                    </Stack>
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} disabled={saving}>
                    Cancel
                </Button>

                <Button
                    variant="contained"
                    disabled={!isValid || saving}
                    onClick={() =>
                        onSave({
                            _id: config?._id ?? "",
                            team_id: _team._id,
                            name,
                            email,
                            password,
                            server,
                            port,
                            protocol,
                            encryption
                        })
                    }
                >
                    {saving ? "Saving..." : "Save"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
