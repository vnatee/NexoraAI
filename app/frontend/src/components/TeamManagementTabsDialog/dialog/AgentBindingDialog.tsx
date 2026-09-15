import React, { useEffect, useState } from "react";
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Stack,
    MenuItem,
    IconButton,
    Box,
    Typography,
    Divider,
    Paper,
    Chip
} from "@mui/material";

import DeleteIcon from "@mui/icons-material/Delete";
import AddIcon from "@mui/icons-material/Add";

import { BindingInput, Integration, FieldSchema } from "../../../api";
import ChatIcon from "@mui/icons-material/Chat";
import { getIntegrationIcon } from "../utils/integrationIcons";

export function AgentBindingDialog({
    open,
    integrations,
    saving,
    onClose,
    onSave
}: {
    open: boolean;
    integrations: Integration[];
    saving?: boolean;
    onClose: () => void;
    onSave: (binding: BindingInput) => void;
}) {
    const [integrationId, setIntegrationId] = useState("");
    const [endpointName, setEndpointName] = useState("");
    const [trigger, setTrigger] = useState("");
    const [asyncFlag, setAsyncFlag] = useState(false);
    const [enabled, setEnabled] = useState(true);
    const [isSubmitted, setIsSubmitted] = useState(false);

    const [requestFields, setRequestFields] = useState<FieldSchema[]>([{ field: "", description: "", location: "query" }]);

    const [responseFields, setResponseFields] = useState<FieldSchema[]>([{ field: "", description: "", location: "body" }]);

    const selectedIntegration = integrations.find(i => i._id === integrationId);

    const selectedEndpoint = selectedIntegration?.endpoints.find(e => e.name === endpointName);
    const FIELD_COL = 132;
    const LOCATION_COL = 274;
    const DELETE_COL = 40;

    const FIELD_COL_field = 180;
    const LOCATION_COL_field = 170;
    const DELETE_COL_field = 40;

    /* =========================
       REQUEST FIELD HANDLERS
    ========================= */

    const addField = () => {
        const defaultLocation = selectedEndpoint?.method === "GET" ? "query" : "body";

        setRequestFields(prev => [...prev, { field: "", description: "", location: defaultLocation }]);
    };

    const removeField = (index: number) => {
        setRequestFields(prev => prev.filter((_, i) => i !== index));
    };

    const updateField = (index: number, key: keyof FieldSchema, value: any) => {
        const updated = [...requestFields];
        updated[index][key] = value;
        setRequestFields(updated);
    };

    /* =========================
       RESPONSE FIELD HANDLERS
    ========================= */

    const addResponseField = () => {
        setResponseFields(prev => [...prev, { field: "", description: "", location: "body" }]);
    };

    const removeResponseField = (index: number) => {
        setResponseFields(prev => prev.filter((_, i) => i !== index));
    };

    const updateResponseField = (index: number, key: keyof FieldSchema, value: any) => {
        const updated = [...responseFields];
        updated[index][key] = value;
        setResponseFields(updated);
    };

    /* =========================
       SAVE
    ========================= */

    const handleSave = () => {
        setIsSubmitted(true);
        if (!integrationId || !endpointName) {
            return;
        }

        onSave({
            integration_id: integrationId,
            endpoint_name: endpointName,
            integration_type: selectedIntegration?.type ?? "rest",
            trigger_keywords: trigger
                .split(",")
                .map(s => s.trim())
                .filter(Boolean),

            async: asyncFlag,
            enabled: enabled,

            request_fields: requestFields.filter(f => f.field.trim() !== ""),
            response_fields: responseFields.filter(f => f.field.trim() !== "")
        });
    };

    /* =========================
       RESET FORM
    ========================= */

    useEffect(() => {
        if (!open) return;

        setIntegrationId("");
        setEndpointName("");
        setTrigger("");
        setAsyncFlag(false);
        setEnabled(true);
        setIsSubmitted(false);

        setRequestFields([{ field: "", description: "", location: "query" }]);

        setResponseFields([{ field: "", description: "", location: "body" }]);
    }, [open]);

    useEffect(() => {
        if (!selectedIntegration || !endpointName) return;

        const ep = selectedIntegration.endpoints.find(e => e.name === endpointName);

        if (!ep) return;

        if (ep.method === "GET") {
            setRequestFields([{ field: "", description: "", location: "query" }]);
        } else {
            setRequestFields([{ field: "", description: "", location: "body" }]);
        }
    }, [endpointName, selectedIntegration]);

    /* =========================
       UI
    ========================= */

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle>Add Integration Binding</DialogTitle>

            <DialogContent dividers>
                <Stack spacing={3}>
                    {/* Integration */}
                    <TextField
                        select
                        required
                        label="Integration"
                        value={integrationId}
                        error={isSubmitted && !integrationId}
                        helperText={isSubmitted && !integrationId ? "Integration is required" : ""}
                        onChange={e => {
                            setIntegrationId(e.target.value);
                            setEndpointName("");
                        }}
                    >
                        {integrations.map(i => (
                            <MenuItem key={i._id} value={i._id}>
                                <Stack direction="row" spacing={1} alignItems="center">
                                    {getIntegrationIcon(i.type)}
                                    <span>{i.name}</span>
                                </Stack>
                            </MenuItem>
                        ))}
                    </TextField>
                    {/* Endpoint */}
                    <TextField
                        select
                        required
                        label="Endpoint"
                        value={endpointName}
                        disabled={!selectedIntegration}
                        error={isSubmitted && !endpointName}
                        helperText={isSubmitted && !endpointName ? "Endpoint is required" : ""}
                        onChange={e => setEndpointName(e.target.value)}
                    >
                        {selectedIntegration ? (
                            selectedIntegration.endpoints.map(ep => (
                                <MenuItem key={ep.name} value={ep.name}>
                                    {ep.name} — {ep.method} {ep.path}
                                </MenuItem>
                            ))
                        ) : (
                            <MenuItem value="" disabled sx={{ display: "none" }}></MenuItem>
                        )}
                    </TextField>
                    {selectedEndpoint && (
                        <Paper
                            variant="outlined"
                            sx={{
                                p: 1.5,
                                bgcolor: "#fafafa"
                            }}
                        >
                            <Stack direction="row" spacing={1} alignItems="center">
                                <Typography
                                    fontWeight={700}
                                    sx={{
                                        color: selectedEndpoint.method === "GET" ? "#2e7d32" : "#1976d2"
                                    }}
                                >
                                    {selectedEndpoint.method}
                                </Typography>

                                <Box
                                    sx={{
                                        fontFamily: "monospace",
                                        bgcolor: "#f5f5f5",
                                        px: 1,
                                        py: 0.3,
                                        borderRadius: 1
                                    }}
                                >
                                    {selectedEndpoint.path}
                                </Box>

                                <Chip size="small" label={selectedIntegration?.type} sx={{ ml: 1 }} />
                            </Stack>
                        </Paper>
                    )}
                    {/* Trigger */}
                    <TextField
                        label="Trigger Keywords"
                        value={trigger}
                        onChange={e => setTrigger(e.target.value)}
                        helperText="Example: order, tracking, shipment"
                    />

                    <Stack direction="row" spacing={2} alignItems="center">
                        <Typography variant="body2">Enabled</Typography>

                        <Button
                            size="small"
                            variant={enabled ? "contained" : "outlined"}
                            color={enabled ? "success" : "inherit"}
                            onClick={() => setEnabled(!enabled)}
                        >
                            {enabled ? "Enabled" : "Disabled"}
                        </Button>
                    </Stack>
                    {/* ================= REQUEST FIELDS ================= */}

                    <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography fontWeight={700} sx={{ fontSize: 15 }}>
                            Request Parameters
                        </Typography>

                        <Typography variant="body2" color="text.secondary" mb={2}>
                            Parameters sent to the API endpoint
                        </Typography>

                        {/* Header */}
                        <Box
                            sx={{
                                display: "flex",
                                gap: 2,
                                px: 1,
                                pb: 1,
                                borderBottom: "1px solid #eee",
                                fontSize: 13,
                                color: "#666"
                            }}
                        >
                            <Box sx={{ width: 180 }}>Field</Box>
                            <Box sx={{ width: 140 }}>Location</Box>
                            <Box sx={{ flex: 1 }}>Description</Box>
                            <Box sx={{ width: 40 }} />
                        </Box>

                        {/* Rows */}
                        <Stack spacing={1.5} mt={1.5}>
                            {requestFields.length === 0 && (
                                <Typography variant="body2" color="text.secondary">
                                    No parameters required for this endpoint
                                </Typography>
                            )}

                            {requestFields.map((f, idx) => (
                                <Box
                                    key={idx}
                                    sx={{
                                        display: "flex",
                                        gap: 2,
                                        alignItems: "center"
                                    }}
                                >
                                    <TextField
                                        size="small"
                                        disabled={saving}
                                        value={f.field}
                                        placeholder="field name"
                                        onChange={e => updateField(idx, "field", e.target.value)}
                                        sx={{ width: 180 }}
                                    />

                                    <TextField
                                        size="small"
                                        disabled={saving}
                                        select
                                        value={f.location}
                                        onChange={e => updateField(idx, "location", e.target.value)}
                                        sx={{ width: 140 }}
                                    >
                                        <MenuItem value="query">Query</MenuItem>
                                        <MenuItem value="path">Path</MenuItem>

                                        {selectedEndpoint?.method !== "GET" && <MenuItem value="body">Body</MenuItem>}
                                    </TextField>

                                    <TextField
                                        size="small"
                                        disabled={saving}
                                        value={f.description}
                                        placeholder="description"
                                        onChange={e => updateField(idx, "description", e.target.value)}
                                        fullWidth
                                    />

                                    <IconButton size="small" disabled={saving} color="error" onClick={() => removeField(idx)}>
                                        <DeleteIcon fontSize="small" />
                                    </IconButton>
                                </Box>
                            ))}

                            {/* Buttons */}
                            <Stack direction="row" spacing={1} mt={1}>
                                <Button size="small" disabled={saving} startIcon={<AddIcon />} onClick={addField}>
                                    Add Parameter
                                </Button>

                                <Button size="small" disabled={saving} color="warning" onClick={() => setRequestFields([])}>
                                    No Parameters
                                </Button>
                            </Stack>
                        </Stack>
                    </Paper>
                    <Divider />
                    {/* ================= RESPONSE FIELDS ================= */}
                    <Paper variant="outlined" sx={{ p: 2 }}>
                        <Typography fontWeight={700} sx={{ fontSize: 15 }}>
                            Response Fields
                        </Typography>

                        <Typography variant="body2" color="text.secondary" mb={1}>
                            Fields extracted from API response
                        </Typography>

                        <Stack spacing={2}>
                            {responseFields.map((f, idx) => (
                                <Stack key={idx} direction="row" spacing={2} alignItems="center">
                                    <TextField
                                        size="small"
                                        value={f.field}
                                        disabled={saving}
                                        placeholder="field name"
                                        onChange={e => updateResponseField(idx, "field", e.target.value)}
                                        sx={{ width: 200 }}
                                    />

                                    <TextField
                                        size="small"
                                        value={f.description}
                                        disabled={saving}
                                        placeholder="description"
                                        onChange={e => updateResponseField(idx, "description", e.target.value)}
                                        fullWidth
                                    />

                                    <IconButton color="error" disabled={saving} onClick={() => removeResponseField(idx)}>
                                        <DeleteIcon />
                                    </IconButton>
                                </Stack>
                            ))}

                            <Button size="small" startIcon={<AddIcon />} onClick={addResponseField}>
                                Add Response Field
                            </Button>
                        </Stack>
                    </Paper>
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} disabled={saving}>
                    Cancel
                </Button>

                <Button variant="contained" disabled={saving} onClick={handleSave}>
                    {saving ? "Saving..." : "Save"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
