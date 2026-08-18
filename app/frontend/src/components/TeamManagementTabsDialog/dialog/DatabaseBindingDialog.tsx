import React, { useEffect, useState } from "react";
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField } from "@mui/material";
import { DatabaseConnection } from "../../../api";

export interface DatabaseBindingInput {
    integration_id: string;
    alias: string;
    trigger_keywords: string[];
    enabled: boolean;
}

export function DatabaseBindingDialog({
    open,
    connections,
    saving,
    onClose,
    onSave
}: {
    open: boolean;
    connections: DatabaseConnection[];
    saving?: boolean;
    onClose: () => void;
    onSave: (binding: DatabaseBindingInput) => void;
}) {
    const [connectionId, setConnectionId] = useState("");
    const [alias, setAlias] = useState("");
    const [triggerKeywords, setTriggerKeywords] = useState("");
    const [enabled, setEnabled] = useState(true);
    const [isSubmitted, setIsSubmitted] = useState(false);

    useEffect(() => {
        if (!open) return;

        setConnectionId("");
        setAlias("");
        setTriggerKeywords("");
        setEnabled(true);
        setIsSubmitted(false);
    }, [open]);

    const handleSave = () => {
        setIsSubmitted(true);
        if (!connectionId) return;

        onSave({
            integration_id: connectionId,
            alias: alias.trim(),
            trigger_keywords: triggerKeywords
                .split(",")
                .map(keyword => keyword.trim())
                .filter(Boolean),
            enabled
        });
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle>Add Database Binding</DialogTitle>

            <DialogContent dividers>
                <Stack spacing={3}>
                    <TextField
                        select
                        required
                        label="Database Connection"
                        value={connectionId}
                        disabled={saving}
                        error={isSubmitted && !connectionId}
                        helperText={isSubmitted && !connectionId ? "Database connection is required" : ""}
                        onChange={e => setConnectionId(e.target.value)}
                    >
                        {connections.map(connection => (
                            <MenuItem key={connection._id} value={connection._id}>
                                {connection.name} - {connection.db_type} - {connection.database}
                            </MenuItem>
                        ))}
                    </TextField>

                    <TextField
                        label="Alias"
                        value={alias}
                        disabled={saving}
                        onChange={e => setAlias(e.target.value)}
                        helperText="Optional display name for this binding"
                    />

                    <TextField
                        label="Trigger Keywords"
                        value={triggerKeywords}
                        disabled={saving}
                        onChange={e => setTriggerKeywords(e.target.value)}
                        helperText="Optional, comma separated. Example: sales, revenue, orders"
                    />

                    <TextField
                        select
                        label="Status"
                        value={enabled ? "enabled" : "disabled"}
                        disabled={saving}
                        onChange={e => setEnabled(e.target.value === "enabled")}
                    >
                        <MenuItem value="enabled">Enabled</MenuItem>
                        <MenuItem value="disabled">Disabled</MenuItem>
                    </TextField>
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} disabled={saving}>
                    Cancel
                </Button>
                <Button variant="contained" onClick={handleSave} disabled={saving || connections.length === 0}>
                    {saving ? "Saving..." : "Save"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
