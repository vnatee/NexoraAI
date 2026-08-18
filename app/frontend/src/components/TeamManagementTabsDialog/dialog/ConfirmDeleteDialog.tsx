import { Dialog, DialogTitle, DialogActions, Button, Typography } from "@mui/material";

type Props = {
    open: boolean;
    onClose: () => void;
    onConfirm: () => void;
};

export function ConfirmDeleteDialog({ open, onClose, onConfirm }: Props) {
    return (
        <Dialog open={open} onClose={onClose}>
            <DialogTitle>Delete User</DialogTitle>

            <Typography sx={{ px: 3 }}>Are you sure you want to delete this user?</Typography>

            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button color="error" variant="contained" onClick={onConfirm}>
                    Delete
                </Button>
            </DialogActions>
        </Dialog>
    );
}
