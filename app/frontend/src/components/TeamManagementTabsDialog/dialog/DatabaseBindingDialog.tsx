import React, { useEffect, useState } from "react";
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, MenuItem, Stack, TextField, Typography } from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import { DatabaseBindingData, DatabaseConnection, DatabaseQueryProfile } from "../../../api";

export interface DatabaseBindingInput {
    integration_id: string;
    alias: string;
    trigger_keywords: string[];
    enabled: boolean;
    query_profile: DatabaseQueryProfile;
}

export function DatabaseBindingDialog({
    open,
    binding,
    connections,
    saving,
    onClose,
    onSave
}: {
    open: boolean;
    binding?: DatabaseBindingData | null;
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
    const [businessContext, setBusinessContext] = useState("");
    const [businessRules, setBusinessRules] = useState("");
    const [glossary, setGlossary] = useState("");
    const [allowedObjects, setAllowedObjects] = useState("");
    const [queryExamples, setQueryExamples] = useState<{ question: string; query: string }[]>([]);

    useEffect(() => {
        if (!open) return;

        setConnectionId(binding?.integration_id ?? "");
        setAlias(binding?.alias ?? "");
        setTriggerKeywords((binding?.trigger_keywords ?? []).join(", "));
        setEnabled(binding?.enabled !== false);
        setBusinessContext(binding?.query_profile?.business_context ?? "");
        setBusinessRules(binding?.query_profile?.business_rules ?? "");
        setGlossary(binding?.query_profile?.glossary ?? "");
        setAllowedObjects((binding?.query_profile?.allowed_objects ?? []).join(", "));
        setQueryExamples(binding?.query_profile?.query_examples ?? []);
        setIsSubmitted(false);
    }, [binding, open]);

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
            enabled,
            query_profile: {
                business_context: businessContext.trim(),
                business_rules: businessRules.trim(),
                glossary: glossary.trim(),
                allowed_objects: allowedObjects
                    .split(",")
                    .map(value => value.trim())
                    .filter(Boolean),
                query_examples: queryExamples.filter(example => example.question.trim() && example.query.trim())
            }
        });
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle>{binding ? "Edit Database Query Profile" : "Add Database Binding"}</DialogTitle>

            <DialogContent dividers>
                <Stack spacing={3}>
                    <TextField
                        select
                        required
                        label="Database Connection"
                        value={connectionId}
                        disabled={saving || Boolean(binding)}
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

                    <Typography variant="subtitle2">Database Query Profile</Typography>

                    <TextField
                        label="Business Context"
                        value={businessContext}
                        disabled={saving}
                        onChange={e => setBusinessContext(e.target.value)}
                        multiline
                        minRows={3}
                        helperText="Explain what this database contains and what this agent should use it for."
                    />

                    <TextField
                        label="Allowed Tables / Collections"
                        value={allowedObjects}
                        disabled={saving}
                        onChange={e => setAllowedObjects(e.target.value)}
                        helperText="Comma separated. Qualified names are supported, e.g. purchasing.po_header, purchasing.po_line"
                    />

                    <TextField
                        label="Business Rules"
                        value={businessRules}
                        disabled={saving}
                        onChange={e => setBusinessRules(e.target.value)}
                        multiline
                        minRows={4}
                        helperText="Define filters, status meanings, calculations, joins, exclusions, and evaluation rules."
                    />

                    <TextField
                        label="Glossary"
                        value={glossary}
                        disabled={saving}
                        onChange={e => setGlossary(e.target.value)}
                        multiline
                        minRows={3}
                        helperText="Map user language to database concepts, e.g. ค้างส่ง = ordered_qty > received_qty."
                    />

                    <Stack spacing={1.5}>
                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                            <Typography variant="subtitle2">Verified Query Examples</Typography>
                            <Button
                                size="small"
                                disabled={saving || queryExamples.length >= 20}
                                onClick={() => setQueryExamples(previous => [...previous, { question: "", query: "" }])}
                            >
                                + Add Example
                            </Button>
                        </Stack>
                        {queryExamples.length === 0 && (
                            <Typography variant="caption" color="text.secondary">
                                Add reviewed question/SQL pairs to teach the agent the expected joins and calculations.
                            </Typography>
                        )}
                        {queryExamples.map((example, index) => (
                            <Stack key={index} direction="row" spacing={1} alignItems="flex-start">
                                <Stack spacing={1} flex={1}>
                                    <TextField
                                        label={`Example ${index + 1} Question`}
                                        value={example.question}
                                        disabled={saving}
                                        onChange={e =>
                                            setQueryExamples(previous =>
                                                previous.map((item, itemIndex) => (itemIndex === index ? { ...item, question: e.target.value } : item))
                                            )
                                        }
                                    />
                                    <TextField
                                        label={`Example ${index + 1} Read-only Query`}
                                        value={example.query}
                                        disabled={saving}
                                        onChange={e =>
                                            setQueryExamples(previous =>
                                                previous.map((item, itemIndex) => (itemIndex === index ? { ...item, query: e.target.value } : item))
                                            )
                                        }
                                        multiline
                                        minRows={3}
                                    />
                                </Stack>
                                <IconButton
                                    disabled={saving}
                                    color="error"
                                    onClick={() => setQueryExamples(previous => previous.filter((_, itemIndex) => itemIndex !== index))}
                                >
                                    <DeleteIcon fontSize="small" />
                                </IconButton>
                            </Stack>
                        ))}
                    </Stack>

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
