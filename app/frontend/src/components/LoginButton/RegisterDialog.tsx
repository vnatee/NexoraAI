import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Stack,
    Typography,
    FormControlLabel,
    Checkbox,
    CircularProgress,
    Divider,
    Alert
} from "@mui/material";
import { useEffect, useState } from "react";
import { User, Team, RegisterUserPayload } from "../../api/models";
import { get_teams } from "../../api/api";
import { getToken } from "../../authConfig";
import { useMsal } from "@azure/msal-react";

interface RegisterDialogProps {
    open: boolean;
    /**
     * null  → new user (ยังไม่มีในระบบ) → แสดงฟอร์มเต็ม
     * User  → existing user (มีในระบบแล้วแต่ไม่มีทีม) → แสดงแค่ team picker
     */
    user?: User | null;
    onCancel: () => void;
    onSubmit: (data: { team_id: string[]; user: RegisterUserPayload }) => Promise<void> | void;
}

export const RegisterDialog = ({ open, onCancel, onSubmit, user }: RegisterDialogProps) => {
    const { instance } = useMsal();

    // mode: "new" = ยังไม่มีในระบบ, "assign" = มีแล้วแค่ขาดทีม
    const isExistingUser = Boolean(user?._id);

    const [form, setForm] = useState<RegisterUserPayload>({
        email: "",
        first_name: "",
        last_name: "",
        employee_id: "",
        tel: ""
    });

    const [teams, setTeams] = useState<Team[]>([]);
    const [selectedTeams, setSelectedTeams] = useState<string[]>([]);
    const [loadingTeams, setLoadingTeams] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    // Load teams เมื่อ dialog เปิด
    useEffect(() => {
        if (!open) return;
        const loadTeams = async () => {
            setLoadingTeams(true);
            try {
                const token = await getToken(instance);
                if (!token) return;
                const data = await get_teams(token);
                setTeams(data.result ?? []);
            } finally {
                setLoadingTeams(false);
            }
        };
        loadTeams();
    }, [open]);

    // Populate form จาก user prop
    useEffect(() => {
        if (user) {
            setForm({
                email: user.email ?? "",
                first_name: user.first_name ?? "",
                last_name: user.last_name ?? "",
                employee_id: user.employee_id ?? "",
                tel: user.tel ?? ""
            });
        } else {
            setForm({ email: "", first_name: "", last_name: "", employee_id: "", tel: "" });
        }
        setSelectedTeams([]);
    }, [user, open]);

    const handleChange = (key: keyof RegisterUserPayload) => (e: React.ChangeEvent<HTMLInputElement>) => {
        setForm(prev => ({ ...prev, [key]: e.target.value }));
    };

    const toggleTeam = (teamId: string) => {
        setSelectedTeams(prev => (prev.includes(teamId) ? prev.filter(id => id !== teamId) : [...prev, teamId]));
    };

    // existing user → เพียงแค่เลือก team ก็พอ
    // new user → ต้องกรอก email + first + last + team
    const isValid = isExistingUser
        ? selectedTeams.length > 0
        : Boolean(form.email.trim()) &&
          Boolean(form.first_name.trim()) &&
          Boolean(form.last_name.trim()) &&
          selectedTeams.length > 0;

    const resetForm = () => {
        setForm({ email: "", first_name: "", last_name: "", employee_id: "", tel: "" });
        setSelectedTeams([]);
    };

    const handleSubmit = async () => {
        if (!isValid) return;
        setSubmitting(true);
        try {
            await onSubmit({ team_id: selectedTeams, user: form });
            resetForm();
        } finally {
            setSubmitting(false);
        }
    };

    const handleCancel = () => {
        resetForm();
        onCancel();
    };

    return (
        <Dialog
            open={open}
            onClose={(_, reason) => { if (reason === "backdropClick") return; }}
            maxWidth="sm"
            fullWidth
            disableEscapeKeyDown
        >
            <DialogTitle>
                {isExistingUser ? "Assign Team" : "Register New User"}
            </DialogTitle>

            <DialogContent dividers>
                <Stack spacing={2}>
                    {/* ── Existing user: แค่บอก context ไม่แสดงฟอร์มเต็ม ── */}
                    {isExistingUser ? (
                        <Alert severity="info">
                            Your account <strong>{form.email}</strong> exists but has not been assigned to any team yet.
                            Please select a team to request access.
                        </Alert>
                    ) : (
                        /* ── New user: ฟอร์มเต็ม ── */
                        <>
                            <TextField
                                label="Email"
                                value={form.email}
                                onChange={handleChange("email")}
                                required
                                fullWidth
                            />
                            <TextField
                                label="First Name"
                                value={form.first_name}
                                onChange={handleChange("first_name")}
                                required
                                fullWidth
                            />
                            <TextField
                                label="Last Name"
                                value={form.last_name}
                                onChange={handleChange("last_name")}
                                required
                                fullWidth
                            />
                            <TextField
                                label="Employee ID"
                                value={form.employee_id}
                                onChange={handleChange("employee_id")}
                                fullWidth
                                placeholder="Optional"
                            />
                            <TextField
                                label="Telephone"
                                value={form.tel}
                                onChange={handleChange("tel")}
                                fullWidth
                            />
                            <Divider />
                        </>
                    )}

                    {/* ── Team picker (ทั้ง 2 mode) ── */}
                    <Typography fontWeight={600}>
                        {isExistingUser ? "Select Team" : "Assign Teams"}
                    </Typography>

                    {loadingTeams ? (
                        <CircularProgress size={24} />
                    ) : teams.length === 0 ? (
                        <Typography color="text.secondary">No teams available</Typography>
                    ) : (
                        <Stack>
                            {teams.map(team => (
                                <FormControlLabel
                                    key={team._id}
                                    control={
                                        <Checkbox
                                            checked={selectedTeams.includes(team._id)}
                                            onChange={() => toggleTeam(team._id)}
                                        />
                                    }
                                    label={team.name}
                                />
                            ))}
                        </Stack>
                    )}
                </Stack>
            </DialogContent>

            <DialogActions sx={{ px: 3, pb: 2 }}>
                <Button variant="outlined" onClick={handleCancel} disabled={submitting}>
                    Cancel
                </Button>
                <Button variant="contained" onClick={handleSubmit} disabled={!isValid || submitting}>
                    {submitting ? <CircularProgress size={20} /> : isExistingUser ? "Request Access" : "Register"}
                </Button>
            </DialogActions>
        </Dialog>
    );
};
