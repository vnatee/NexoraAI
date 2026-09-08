import React, { useEffect, useState } from "react";
import { Alert, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, MenuItem, Stack, TextField } from "@mui/material";

import { BusinessDocumentBindingData, BusinessDocumentConnection } from "../../../api/models";


export function BusinessDocumentBindingDialog({ open, connections, binding, saving, onClose, onSave }: {
    open: boolean;
    connections: BusinessDocumentConnection[];
    binding?: BusinessDocumentBindingData | null;
    saving: boolean;
    onClose: () => void;
    onSave: (value: { connection_id: string; enabled: boolean; permissions: Array<"read" | "create"> }) => void;
}) {
    const [connectionId, setConnectionId] = useState("");
    const [read, setRead] = useState(true);
    const [create, setCreate] = useState(false);
    useEffect(() => {
        if (!open) return;
        setConnectionId(binding?.connection_id ?? "");
        setRead(binding?.permissions?.includes("read") ?? true);
        setCreate(binding?.permissions?.includes("create") ?? false);
    }, [open, binding]);
    const selected = connections.find(connection => connection._id === connectionId);
    const createAvailable = selected?.operation_mode === "read_write";
    useEffect(() => {
        if (!createAvailable) setCreate(false);
    }, [createAvailable]);
    return <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
        <DialogTitle>{binding ? "Edit" : "Add"} Business Documents Binding</DialogTitle>
        <DialogContent dividers><Stack spacing={2}>
            <TextField select label="Document Connection" value={connectionId} onChange={event => setConnectionId(event.target.value)} disabled={Boolean(binding)}>
                {connections.filter(connection => connection.enabled).map(connection => <MenuItem key={connection._id} value={connection._id}>{connection.name} — {connection.provider === "microsoft365" ? "Microsoft 365" : "Google Workspace"}</MenuItem>)}
            </TextField>
            <FormControlLabel control={<Checkbox checked={read} onChange={event => setRead(event.target.checked)} />} label="Search and read documents" />
            <FormControlLabel control={<Checkbox checked={create} disabled={!createAvailable} onChange={event => setCreate(event.target.checked)} />} label="Create Word/Docs, Excel/Sheets and PowerPoint/Slides files" />
            {create && <Alert severity="warning">Creating a cloud document is a write action. The Agent must only use it after an explicit user request.</Alert>}
        </Stack></DialogContent>
        <DialogActions><Button onClick={onClose}>Cancel</Button><Button variant="contained" disabled={saving || !connectionId || (!read && !create)} onClick={() => onSave({ connection_id: connectionId, enabled: true, permissions: [...(read ? ["read" as const] : []), ...(create ? ["create" as const] : [])] })}>{saving ? "Saving..." : "Save"}</Button></DialogActions>
    </Dialog>;
}
