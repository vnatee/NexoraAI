import { Stack, Typography, TextField, Switch, FormControlLabel, Divider, Button } from "@mui/material";
import { useEffect, useState } from "react";
import { User } from "../../../api/models";

type Props = {
    user: User;
    onSave: (u: User) => void;
    onClose: () => void;
    onDelete: () => void;
    isDelete: boolean;
};

export function UserDetailPanel({ user, onSave, onClose, onDelete, isDelete }: Props) {
    // 🆕 edit state
    const [isEditing, setIsEditing] = useState(false);

    // 🆕 draft user (ใช้แก้ไข)
    const [draft, setDraft] = useState<User>(user);

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
                            disabled={!isEditing} // 🔒
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

            <TextField label="Tel" value={draft.tel || ""} disabled={!isEditing} onChange={e => setDraft({ ...draft, tel: e.target.value })} />

            {/* Actions */}
            <Stack direction="row" spacing={2}>
                {!isEditing ? (
                    <Button variant="contained" onClick={() => setIsEditing(true)}>
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

                <Button color="error" disabled={isEditing || isDelete} onClick={onDelete}>
                    Delete
                </Button>
            </Stack>
        </Stack>
    );
}
