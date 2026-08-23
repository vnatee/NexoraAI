import { Stack, Typography, TextField, Switch, FormControlLabel, Divider, Button } from "@mui/material";
import { useEffect, useState } from "react";
import { User } from "../../../api/models";

type Props = {
    user: User;
    onSave: (u: User) => void;
    onClose: () => void;
    onDelete: () => void;
    isDelete: boolean;
    onResetPassword?: (password: string) => Promise<void>;
    canEdit?: boolean;
    canDelete?: boolean;
    canResetPassword?: boolean;
};

export function UserDetailPanel({ user, onSave, onClose, onDelete, isDelete, onResetPassword, canEdit = true, canDelete = true, canResetPassword = true }: Props) {
    // 🆕 edit state
    const [isEditing, setIsEditing] = useState(false);

    // 🆕 draft user (ใช้แก้ไข)
    const [draft, setDraft] = useState<User>(user);
    const [newPassword, setNewPassword] = useState("");

    // 🆕 sync เมื่อเปลี่ยน user
    useEffect(() => {
        setDraft(user);
        setIsEditing(false);
    }, [user]);

    const handleCancel = () => {
        setDraft(user); // rollback
        setIsEditing(false);
    };

    const handleSave = () => {
        onSave(draft);
        setIsEditing(false);
    };

    const handleClose = () => {
        if (isEditing) {
            if (!window.confirm("Discard unsaved changes?")) {
                return;
            }
        }
        onClose();
    };

    return (
        <Stack spacing={3}>
            {/* Header */}
            <Stack direction="row" justifyContent="space-between">
                <Button onClick={handleClose} size="small">
                    ← Back
                </Button>
                <Typography variant="h6">User Detail</Typography>

                <FormControlLabel
                    label="Active"
                    control={
                        <Switch
                            checked={draft.active}
                            disabled={!isEditing || draft.is_sys_admin === true} // System-admin status uses the protected permission flow.
                            onChange={() => setDraft({ ...draft, active: !draft.active })}
                        />
                    }
                />
            </Stack>

            <Divider />

            {/* Fields */}
            <TextField label="Employee ID" value={draft.employee_id} disabled />

            <TextField
                label="First Name"
                value={draft.first_name}
                disabled={!isEditing} // 🔒
                onChange={e => setDraft({ ...draft, first_name: e.target.value })}
            />

            <TextField label="Last Name" value={draft.last_name} disabled={!isEditing} onChange={e => setDraft({ ...draft, last_name: e.target.value })} />

            <TextField label="Email" value={draft.email} disabled={!isEditing} />
            <TextField label="AD Email" value={draft.ad_email} disabled />
            <TextField label="Authentication" value={(draft.auth_providers || ["entra"]).join(", ")} disabled />

            <TextField label="Tel" value={draft.tel || ""} disabled={!isEditing} onChange={e => setDraft({ ...draft, tel: e.target.value })} />

            {draft.auth_providers?.includes("local") && onResetPassword && canResetPassword && (
                <Stack direction="row" spacing={2}>
                    <TextField fullWidth label={`New password for ${draft.local_username || "local user"}`} type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} helperText="At least 12 characters; all existing local sessions will be signed out." />
                    <Button disabled={newPassword.length < 12} onClick={async () => { await onResetPassword(newPassword); setNewPassword(""); }}>Reset password</Button>
                </Stack>
            )}

            {/* Actions */}
            <Stack direction="row" spacing={2}>
                {!isEditing ? (
                    <Button variant="contained" onClick={() => setIsEditing(true)} disabled={!canEdit}>
                        Edit
                    </Button>
                ) : (
                    <>
                        <Button variant="contained" onClick={handleSave}>
                            Save
                        </Button>
                        <Button onClick={handleCancel}>Cancel</Button>
                    </>
                )}

                <Button color="error" disabled={isEditing || isDelete || !canDelete} onClick={onDelete}>
                    Delete
                </Button>
            </Stack>
        </Stack>
    );
}
