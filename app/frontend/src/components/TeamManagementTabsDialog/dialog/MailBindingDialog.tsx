import React, { useEffect, useState } from "react";
import {
    Alert,
    Box,
    Button,
    Chip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControlLabel,
    IconButton,
    InputAdornment,
    MenuItem,
    Stack,
    Switch,
    TextField,
    Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import { MailBindingData, MailEmailConfig } from "../../../api/models";

export interface MailBindingInput {
    email_id: string;
    is_html: boolean;
    enabled: boolean;
    permissions: Array<"read" | "send">;
    allowed_recipient_domains: string[];
    max_recipients: number;
    subject: string;
    body: string;
    default_to: string[];
    default_cc: string[];
    default_bcc: string[];
}

interface MailBindingDialogProps {
    open: boolean;
    mailConfigs: MailEmailConfig[];
    binding?: MailBindingData | null;
    saving?: boolean;
    onClose: () => void;
    onSave: (binding: MailBindingInput) => void;
}

// ── helper: comma-separated chip input ──────────────────────────────────────
function EmailChipInput({
    label,
    values,
    onChange,
    disabled,
    helperText
}: {
    label: string;
    values: string[];
    onChange: (v: string[]) => void;
    disabled?: boolean;
    helperText?: string;
}) {
    const [input, setInput] = useState("");

    const addEmail = () => {
        const trimmed = input.trim();
        if (!trimmed) return;
        // split by comma to allow pasting multiple
        const emails = trimmed
            .split(",")
            .map(e => e.trim())
            .filter(e => e && !values.includes(e));
        if (emails.length) onChange([...values, ...emails]);
        setInput("");
    };

    const removeEmail = (email: string) => onChange(values.filter(v => v !== email));

    return (
        <Box sx={{ pt: 1 }}>
            <TextField
                label={label}
                value={input}
                disabled={disabled}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                    if (e.key === "Enter" || e.key === ",") {
                        e.preventDefault();
                        addEmail();
                    }
                }}
                fullWidth
                size="small"
                helperText={helperText}
                InputProps={{
                    endAdornment: (
                        <InputAdornment position="end">
                            <IconButton size="small" onClick={addEmail} disabled={disabled || !input.trim()}>
                                <AddIcon fontSize="small" />
                            </IconButton>
                        </InputAdornment>
                    )
                }}
            />
            {values.length > 0 && (
                <Stack direction="row" flexWrap="wrap" gap={0.5} mt={1}>
                    {values.map(email => (
                        <Chip
                            key={email}
                            label={email}
                            size="small"
                            onDelete={disabled ? undefined : () => removeEmail(email)}
                            deleteIcon={<CloseIcon />}
                        />
                    ))}
                </Stack>
            )}
        </Box>
    );
}

// ── main dialog ──────────────────────────────────────────────────────────────
export function MailBindingDialog({ open, mailConfigs, binding, saving, onClose, onSave }: MailBindingDialogProps) {
    const [emailId, setEmailId] = useState("");
    const [isHtml, setIsHtml] = useState(false);
    const [enabled, setEnabled] = useState(true);
    const [canRead, setCanRead] = useState(true);
    const [canSend, setCanSend] = useState(false);
    const [allowedDomains, setAllowedDomains] = useState("");
    const [maxRecipients, setMaxRecipients] = useState(10);
    const [subject, setSubject] = useState("");
    const [body, setBody] = useState("");
    const [defaultTo, setDefaultTo] = useState<string[]>([]);
    const [defaultCc, setDefaultCc] = useState<string[]>([]);
    const [defaultBcc, setDefaultBcc] = useState<string[]>([]);
    const [isSubmitted, setIsSubmitted] = useState(false);

    useEffect(() => {
        if (!open) return;
        setEmailId(binding?.email_id ?? "");
        setIsHtml(binding?.is_html ?? false);
        setEnabled(binding?.enabled ?? true);
        const permissions = binding?.permissions ?? ["read"];
        setCanRead(permissions.includes("read"));
        setCanSend(permissions.includes("send"));
        setAllowedDomains((binding?.allowed_recipient_domains ?? []).join(", "));
        setMaxRecipients(binding?.max_recipients ?? 10);
        setSubject(binding?.subject ?? "");
        setBody(binding?.body ?? "");
        setDefaultTo(binding?.default_to ?? []);
        setDefaultCc(binding?.default_cc ?? []);
        setDefaultBcc(binding?.default_bcc ?? []);
        setIsSubmitted(false);
    }, [binding, open]);

    const handleSave = () => {
        setIsSubmitted(true);
        if (!emailId) return;
        onSave({
            email_id: emailId,
            is_html: isHtml,
            enabled,
            permissions: [...(canRead ? ["read" as const] : []), ...(canSend ? ["send" as const] : [])],
            allowed_recipient_domains: allowedDomains.split(",").map(v => v.trim().toLowerCase()).filter(Boolean),
            max_recipients: maxRecipients,
            subject,
            body,
            default_to: defaultTo,
            default_cc: defaultCc,
            default_bcc: defaultBcc
        });
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle>{binding ? "Edit Mail Binding" : "Add Mail Binding"}</DialogTitle>

            <DialogContent dividers>
                <Stack spacing={3}>
                    {/* ── Account ── */}
                    <Typography variant="subtitle2" color="text.secondary">
                        Account
                    </Typography>

                    <TextField
                        select
                        required
                        label="Email Account"
                        value={emailId}
                        disabled={saving}
                        error={isSubmitted && !emailId}
                        helperText={
                            isSubmitted && !emailId
                                ? "Email account is required"
                                : "Select the mail configuration to bind to this agent"
                        }
                        onChange={e => setEmailId(e.target.value)}
                    >
                        {mailConfigs.length === 0 ? (
                            <MenuItem disabled value="">
                                No mail configurations available
                            </MenuItem>
                        ) : (
                            mailConfigs.map(cfg => (
                                <MenuItem key={cfg._id} value={cfg._id}>
                                    {cfg.name} — {cfg.email_address} ({cfg.provider})
                                </MenuItem>
                            ))
                        )}
                    </TextField>

                    <Stack direction="row" spacing={2}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={isHtml}
                                    disabled={saving}
                                    onChange={e => setIsHtml(e.target.checked)}
                                />
                            }
                            label={isHtml ? "HTML email" : "Plain text email"}
                        />

                        <TextField
                            select
                            label="Status"
                            value={enabled ? "enabled" : "disabled"}
                            disabled={saving}
                            size="small"
                            sx={{ minWidth: 130 }}
                            onChange={e => setEnabled(e.target.value === "enabled")}
                        >
                            <MenuItem value="enabled">Enabled</MenuItem>
                            <MenuItem value="disabled">Disabled</MenuItem>
                        </TextField>
                    </Stack>

                    <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                        <FormControlLabel control={<Switch checked={canRead} onChange={e => setCanRead(e.target.checked)} />} label="Read / search mailbox" />
                        <FormControlLabel control={<Switch checked={canSend} onChange={e => setCanSend(e.target.checked)} />} label="Send mail" />
                    </Stack>
                    {canSend && <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                        <TextField label="Allowed recipient domains" value={allowedDomains} onChange={e => setAllowedDomains(e.target.value)} helperText="Comma-separated; blank allows any domain" fullWidth />
                        <TextField label="Max recipients" type="number" value={maxRecipients} onChange={e => setMaxRecipients(Math.max(1, Number(e.target.value)))} inputProps={{ min: 1, max: 100 }} sx={{ minWidth: 160 }} />
                    </Stack>}

                    <Divider />

                    {/* ── Recipients ── */}
                    <Typography variant="subtitle2" color="text.secondary">
                        Default Recipients{" "}
                        <Typography component="span" variant="caption" color="text.disabled">
                            (agent can override at runtime)
                        </Typography>
                    </Typography>

                    <EmailChipInput
                        label="To"
                        values={defaultTo}
                        onChange={setDefaultTo}
                        disabled={saving}
                        helperText="Press Enter or comma to add. Agent can override at runtime."
                    />

                    <EmailChipInput
                        label="CC"
                        values={defaultCc}
                        onChange={setDefaultCc}
                        disabled={saving}
                        helperText="Optional"
                    />

                    <EmailChipInput
                        label="BCC"
                        values={defaultBcc}
                        onChange={setDefaultBcc}
                        disabled={saving}
                        helperText="Optional"
                    />

                    <Divider />

                    {/* ── Template ── */}
                    <Typography variant="subtitle2" color="text.secondary">
                        Template{" "}
                        <Typography component="span" variant="caption" color="text.disabled">
                            (use {"{{variable}}"} for placeholders the agent will fill)
                        </Typography>
                    </Typography>

                    <Alert severity="info">
                        When a template is configured, the Agent supplies values for each {"{{variable}}"} and the runtime renders the final email.
                        Leave Subject or Body blank only when you want the Agent to generate that entire field.
                    </Alert>

                    <TextField
                        label="Subject"
                        value={subject}
                        disabled={saving}
                        onChange={e => setSubject(e.target.value)}
                        fullWidth
                        placeholder='e.g. "Order {{order_id}} has been confirmed"'
                        helperText="Leave blank to let the agent generate the subject"
                    />

                    <TextField
                        label="Body"
                        value={body}
                        disabled={saving}
                        onChange={e => setBody(e.target.value)}
                        fullWidth
                        multiline
                        minRows={6}
                        placeholder={
                            isHtml
                                ? "<p>Dear {{name}},</p>\n<p>Your order {{order_id}} is confirmed.</p>"
                                : "Dear {{name}},\n\nYour order {{order_id}} is confirmed."
                        }
                        helperText={
                            isHtml
                                ? "HTML body — use {{variable}} for dynamic values"
                                : "Plain text body — use {{variable}} for dynamic values"
                        }
                        sx={{ fontFamily: body ? "monospace" : undefined }}
                    />
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} disabled={saving}>
                    Cancel
                </Button>
                <Button
                    variant="contained"
                    onClick={handleSave}
                    disabled={saving || mailConfigs.length === 0 || (!canRead && !canSend)}
                >
                    {saving ? "Saving..." : "Save"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
