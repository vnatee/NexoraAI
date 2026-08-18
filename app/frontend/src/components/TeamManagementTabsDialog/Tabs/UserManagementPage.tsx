import { Stack, Paper, Typography, Box, CircularProgress } from "@mui/material";
import { useEffect, useState } from "react";
import { UserListPanel } from "../common/UserListPanel";
import { UserDetailPanel } from "../common/UserDetailPanel";
import { CreateUserDialog } from "../dialog/CreateUserDialog";
import { ConfirmDeleteDialog } from "../dialog/ConfirmDeleteDialog";
import { User } from "../../../api/models";
import { useMsal } from "@azure/msal-react";
import { getToken } from "../../../authConfig";
import { add_users, get_all_users, update_user, delete_user } from "../../../api";
import { useNotification } from "../../../utill/NotificationProvider";

export function UserManagementPage() {
    const { instance: msalInstance } = useMsal();
    const [users, setUsers] = useState<User[]>([]);
    const [selectedUser, setSelectedUser] = useState<User | null>(null);
    const [createOpen, setCreateOpen] = useState(false);
    const [deleteOpen, setDeleteOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [deleteUserId, setDeleteUserId] = useState<string | null>(null);
    const { showNotification } = useNotification();
    const [isDelete, setIsDelete] = useState<boolean>(false);

    const fetchUsers = async () => {
        try {
            setLoading(true);
            const token = await getToken(msalInstance);
            if (!token) return;

            const users = await get_all_users(token);
            setUsers(users.result);
        } catch (error) {
            console.error("Failed to fetch users:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async (updated: User) => {
        try {
            setLoading(true);
            const token = await getToken(msalInstance);
            if (!token) return;

            await update_user(updated, token);
            fetchUsers();
            showNotification("User updated successfully", "success");
        } catch (error) {
            console.error("Failed to update users:", error);
            showNotification("Failed to update user", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleCreate = async (u: User) => {
        try {
            setLoading(true);
            const token = await getToken(msalInstance);
            if (!token) return;

            await add_users(u, token);
            fetchUsers();
            showNotification("Create user successfully", "success");
        } catch (error) {
            console.error("Failed to fetch users:", error);
            showNotification("Failed to create user", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async () => {
        try {
            setLoading(true);
            setDeleteOpen(false);
            setIsDelete(true);
            if (!selectedUser) return;

            const token = await getToken(msalInstance);
            if (!token) return;

            await delete_user(deleteUserId!, token);
            fetchUsers();
            showNotification("Delete user successfully", "success");
        } catch (error) {
            setIsDelete(false);

            console.error("Failed to delete users:", error);
            showNotification("Failed to delete user", "error");
        } finally {
            setSelectedUser(null);
            setIsDelete(false);
            setDeleteOpen(false);
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    return (
        <Stack spacing={2}>
            <Typography variant="h6">User Management</Typography>

            {selectedUser === null && (
                <Paper sx={{ p: 2 }}>
                    {loading ? (
                        <Box sx={{ display: "flex", justifyContent: "center", mt: 4 }}>
                            <CircularProgress />
                        </Box>
                    ) : (
                        <UserListPanel users={users} selected={null} onSelect={setSelectedUser} fullWidth onCreate={() => setCreateOpen(true)} />
                    )}
                </Paper>
            )}

            {selectedUser !== null && (
                <Stack direction="row" spacing={2}>
                    <Paper sx={{ width: 280, p: 2 }}>
                        <UserListPanel users={users} selected={selectedUser} onSelect={setSelectedUser} onCreate={() => setCreateOpen(true)} />
                    </Paper>

                    <Paper sx={{ flex: 1, p: 3 }}>
                        <UserDetailPanel
                            user={selectedUser}
                            onSave={handleSave}
                            onClose={() => setSelectedUser(null)}
                            onDelete={() => {
                                setDeleteUserId(selectedUser._id);
                                setDeleteOpen(true);
                            }}
                            isDelete={isDelete}
                        />
                    </Paper>
                </Stack>
            )}
            <CreateUserDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreate={handleCreate} />
            <ConfirmDeleteDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={handleDelete} />
        </Stack>
    );
}
