import { Dialog, DialogTitle, DialogContent, DialogActions, TextField, Button, Stack } from "@mui/material";
import { useEffect, useState } from "react";
import { User } from "../../../api/models";
import { useMsal } from "@azure/msal-react";
import { getUsername } from "../../../authConfig";

type Props = {
    open: boolean;
    onClose: () => void;
    onCreate: (u: User) => void;
};

export function CreateUserDialog({ open, onClose, onCreate }: Props) {
    const [form, setForm] = useState({
        employee_id: "",
        first_name: "",
        last_name: "",
        email: "",
        ad_email: "",
        tel: ""
    });

    const handleCreate = () => {
        const newUser: User = {
            _id: Date.now().toString(),
            active: true,
            ...form
        };
        onCreate(newUser);
        onClose();
    };

    useEffect(() => {
        if (open) {
            setForm({
                employee_id: "",
                first_name: "",
                last_name: "",
                email: "",
                ad_email: "",
                tel: ""
            });
        }
    }, [open]);

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle>Create User</DialogTitle>

            <DialogContent>
                <Stack spacing={2} mt={1}>
                    <TextField label="Employee ID" value={form.employee_id} onChange={e => setForm({ ...form, employee_id: e.target.value })} />
                    <TextField label="First Name" value={form.first_name} onChange={e => setForm({ ...form, first_name: e.target.value })} />
                    <TextField label="Last Name" value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} />
                    <TextField label="Email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
                    <TextField label="Entra ID" value={form.ad_email} onChange={e => setForm({ ...form, ad_email: e.target.value })} />
                    <TextField label="Tel" value={form.tel} onChange={e => setForm({ ...form, tel: e.target.value })} />
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button variant="contained" onClick={handleCreate}>
                    Create
                </Button>
            </DialogActions>
        </Dialog>
    );
}
