import React, { useMemo, useState, useEffect } from "react";
import {
    Box,
    Typography,
    Divider,
    Paper,
    Stack,
    Chip,
    IconButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    Checkbox,
    TextField,
    CircularProgress
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import VisibilityIcon from "@mui/icons-material/Visibility";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import PersonAddAltOutlinedIcon from "@mui/icons-material/PersonAddAltOutlined";
import { User, TeamProfile } from "../../../api/models";
import { useMsal } from "@azure/msal-react";
import { get_users_by_team_id, delete_team_user, approve_users, reject_users, get_available_team_users, insert_team_users } from "../../../api/api";
import { getToken } from "../../../authConfig";
import Skeleton from "@mui/material/Skeleton";
import { useNotification } from "../../../utill/NotificationProvider";

type WaitingUser = User & { __temp_id: string };

interface TeamUserManagementPageProps {
    team: TeamProfile | null;
}

/* =========================================================
   PAGE
========================================================= */
export function TeamUserManagementPage({ team }: TeamUserManagementPageProps) {
    const { instance: msalInstance } = useMsal();
    const { showNotification } = useNotification();

    const [users, setUsers] = useState<User[]>([]);
    const [waiting, setWaiting] = useState<WaitingUser[]>([]);

    const [searchUser, setSearchUser] = useState("");
    const [searchWaiting, setSearchWaiting] = useState("");

    const [selectedUser, setSelectedUser] = useState<User | null>(null);
    const [confirmRemove, setConfirmRemove] = useState<User | null>(null);

    const [selectedApprove, setSelectedApprove] = useState<string[]>([]);
    const [confirmApproveIds, setConfirmApproveIds] = useState<string[] | null>(null);
    const [confirmRejectIds, setConfirmRejectIds] = useState<string[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [teamId, setTeamId] = useState<string | null>(null);
    const [isApprove, setIsApprove] = useState<boolean>(false);
    const [isReject, setIsReject] = useState<boolean>(false);
    const [isRemove, setIsRemove] = useState<boolean>(false);
    const [addOpen, setAddOpen] = useState(false);
    const [availableUsers, setAvailableUsers] = useState<User[]>([]);
    const [selectedAddIds, setSelectedAddIds] = useState<string[]>([]);
    const [addSearch, setAddSearch] = useState("");
    const [loadingAvailable, setLoadingAvailable] = useState(false);
    const [adding, setAdding] = useState(false);

    /* =========================
       FILTER
    ========================= */
    const makeTempId = () => {
        // modern browser
        if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();

        // fallback
        return `tmp_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    };

    const getWaitingKey = (u: WaitingUser) => u.__temp_id;

    const filteredUsers = useMemo(
        () => users.filter(u => `${u.first_name} ${u.last_name} ${u.email}`.toLowerCase().includes(searchUser.toLowerCase())),
        [users, searchUser]
    );

    const filteredWaiting = useMemo(
        () => waiting.filter(u => `${u.first_name} ${u.last_name} ${u.email}`.toLowerCase().includes(searchWaiting.toLowerCase())),
        [waiting, searchWaiting]
    );

    const filteredAvailableUsers = useMemo(() => {
        const query = addSearch.trim().toLowerCase();
        if (!query) return availableUsers;
        return availableUsers.filter(user =>
            `${user.first_name} ${user.last_name} ${user.email} ${user.ad_email} ${user.local_username || ""}`
                .toLowerCase()
                .includes(query)
        );
    }, [availableUsers, addSearch]);

    /* =========================
       ACTIONS
    ========================= */
    const approveUsers = (ids: string[]) => {
        const approved = waiting.filter(u => ids.includes(getWaitingKey(u)));
        setUsers(prev => [...prev, ...approved]);
        setWaiting(prev => prev.filter(u => !ids.includes(getWaitingKey(u))));
        setSelectedApprove([]);
        setConfirmApproveIds(null);
    };

    const rejectUsers = (ids: string[]) => {
        setWaiting(prev => prev.filter(u => !ids.includes(getWaitingKey(u))));
        setSelectedApprove([]);
        setConfirmRejectIds(null);
    };

    const toggleSelectAll = () => {
        if (selectedApprove.length === filteredWaiting.length) {
            setSelectedApprove([]);
        } else {
            setSelectedApprove(filteredWaiting.map(u => getWaitingKey(u)));
        }
    };

    const loadUsers = async () => {
        try {
            setLoading(true);

            if (!team?._id) {
                setUsers([]);
                setWaiting([]);
                return;
            }

            setTeamId(team._id);
            const token = await getToken(msalInstance);
            if (!token) return;

            const result = await get_users_by_team_id(team._id, token);

            setUsers(result.users ?? []);
            const waitingList: WaitingUser[] = (result.waiting_approve ?? []).map((u: User) => ({
                ...u,
                __temp_id: makeTempId()
            }));

            setWaiting(waitingList);
        } catch (err) {
            console.error("loadUsers failed:", err);
            setUsers([]);
            setWaiting([]);
        } finally {
            setLoading(false);
        }
    };

    const openAddUsers = async () => {
        if (!team?._id) return;
        setAddOpen(true);
        setSelectedAddIds([]);
        setAddSearch("");
        setLoadingAvailable(true);
        try {
            const token = await getToken(msalInstance);
            if (!token) throw new Error("Your session has expired. Please sign in again.");
            setAvailableUsers(await get_available_team_users(team._id, token));
        } catch (err) {
            setAvailableUsers([]);
            showNotification(err instanceof Error ? err.message : "Failed to load available users", "error");
        } finally {
            setLoadingAvailable(false);
        }
    };

    const addSelectedUsers = async () => {
        if (!team?._id || selectedAddIds.length === 0) return;
        setAdding(true);
        try {
            const token = await getToken(msalInstance);
            if (!token) throw new Error("Your session has expired. Please sign in again.");
            await insert_team_users(team._id, selectedAddIds, token);
            setAddOpen(false);
            await loadUsers();
            showNotification(`${selectedAddIds.length} user(s) added to ${team.name}`, "success");
        } catch (err) {
            showNotification(err instanceof Error ? err.message : "Failed to add users", "error");
        } finally {
            setAdding(false);
        }
    };

    useEffect(() => {
        loadUsers();
    }, [team?._id]);

    return (
        <Stack spacing={3}>
            <Typography variant="h6">Team User Management</Typography>
            <Typography variant="body2" color="text.secondary">
                Manage users in this team and approve / reject pending users
            </Typography>

            <Divider />

            {/* ================= USERS IN TEAM ================= */}
            <Paper variant="outlined" sx={{ p: 2 }}>
                <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "stretch", sm: "center" }} gap={1}>
                    <Typography variant="subtitle1">Users in Team ({filteredUsers.length})</Typography>
                    <Button variant="contained" size="small" startIcon={<PersonAddAltOutlinedIcon />} onClick={() => void openAddUsers()}>
                        Add existing users
                    </Button>
                </Stack>

                <TextField
                    size="small"
                    placeholder="Search user..."
                    fullWidth
                    sx={{ my: 1 }}
                    value={searchUser}
                    onChange={e => setSearchUser(e.target.value)}
                />

                <Box sx={{ maxHeight: 260, overflowY: "auto" }}>
                    {loading ? (
                        <UserListSkeleton rows={5} />
                    ) : filteredUsers.length === 0 ? (
                        <Typography color="text.secondary">No users found</Typography>
                    ) : (
                        <Stack spacing={1}>
                            {filteredUsers.map(user => (
                                <UserRow key={user._id} user={user} onView={() => setSelectedUser(user)} onRemove={() => setConfirmRemove(user)} />
                            ))}
                        </Stack>
                    )}
                </Box>
            </Paper>

            {/* ================= WAITING APPROVE ================= */}
            <Paper variant="outlined" sx={{ p: 2 }}>
                <Box
                    sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 1
                    }}
                >
                    <Typography variant="subtitle1">Waiting Approve ({filteredWaiting.length})</Typography>

                    <Box sx={{ display: "flex", gap: 1 }}>
                        <Button
                            variant="contained"
                            color="success"
                            size="small"
                            startIcon={<CheckCircleIcon />}
                            disabled={loading || selectedApprove.length === 0}
                            onClick={() => setConfirmApproveIds(selectedApprove)}
                        >
                            Approve Selected
                        </Button>

                        <Button
                            variant="outlined"
                            color="error"
                            size="small"
                            startIcon={<CancelIcon />}
                            disabled={loading || selectedApprove.length === 0}
                            onClick={() => setConfirmRejectIds(selectedApprove)}
                        >
                            Reject Selected
                        </Button>
                    </Box>
                </Box>

                <TextField
                    size="small"
                    placeholder="Search waiting user..."
                    fullWidth
                    sx={{ my: 1 }}
                    value={searchWaiting}
                    onChange={e => setSearchWaiting(e.target.value)}
                />

                <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
                    <Checkbox
                        checked={filteredWaiting.length > 0 && selectedApprove.length === filteredWaiting.length}
                        indeterminate={selectedApprove.length > 0 && selectedApprove.length < filteredWaiting.length}
                        onChange={toggleSelectAll}
                    />
                    <Typography variant="caption">Select All</Typography>
                </Box>

                <Box sx={{ maxHeight: 300, overflowY: "auto" }}>
                    {loading ? (
                        <UserListSkeleton rows={6} />
                    ) : filteredWaiting.length === 0 ? (
                        <Typography color="text.secondary">No users waiting for approval</Typography>
                    ) : (
                        <Stack spacing={1}>
                            {filteredWaiting.map(user => {
                                const key = getWaitingKey(user);

                                return (
                                    <WaitingUserRow
                                        key={key} // ✅ ใช้ __temp_id (temporary unique id)
                                        user={user}
                                        checked={selectedApprove.includes(key)}
                                        onToggle={() => setSelectedApprove(prev => (prev.includes(key) ? prev.filter(id => id !== key) : [...prev, key]))}
                                        onView={() => setSelectedUser(user)}
                                    />
                                );
                            })}
                        </Stack>
                    )}
                </Box>
            </Paper>

            {/* ================= DIALOGS ================= */}
            <UserDetailDialog user={selectedUser} onClose={() => setSelectedUser(null)} />

            <Dialog open={addOpen} onClose={() => !adding && setAddOpen(false)} fullWidth maxWidth="sm">
                <DialogTitle>Add users to {team?.name}</DialogTitle>
                <DialogContent dividers>
                    <Stack spacing={2}>
                        <TextField
                            autoFocus
                            size="small"
                            label="Search users"
                            value={addSearch}
                            onChange={event => setAddSearch(event.target.value)}
                            placeholder="Name, email, or local username"
                        />
                        {loadingAvailable ? (
                            <Box textAlign="center" py={4}><CircularProgress size={28} /></Box>
                        ) : filteredAvailableUsers.length === 0 ? (
                            <Typography color="text.secondary">No active users are available to add.</Typography>
                        ) : (
                            <Stack spacing={0.5} sx={{ maxHeight: 360, overflowY: "auto" }}>
                                {filteredAvailableUsers.map(user => {
                                    const checked = selectedAddIds.includes(user._id);
                                    const provider = user.auth_providers?.includes("local") ? `Local · ${user.local_username || user.ad_email}` : "Microsoft Entra";
                                    return (
                                        <Paper
                                            key={user._id}
                                            variant="outlined"
                                            sx={{ p: 1, display: "flex", alignItems: "center", cursor: "pointer" }}
                                            onClick={() => setSelectedAddIds(current => checked ? current.filter(id => id !== user._id) : [...current, user._id])}
                                        >
                                            <Checkbox checked={checked} tabIndex={-1} />
                                            <Box minWidth={0}>
                                                <Typography fontWeight={600}>{user.first_name} {user.last_name}</Typography>
                                                <Typography variant="body2" color="text.secondary" noWrap>{user.email} · {provider}</Typography>
                                            </Box>
                                        </Paper>
                                    );
                                })}
                            </Stack>
                        )}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setAddOpen(false)} disabled={adding}>Cancel</Button>
                    <Button variant="contained" onClick={() => void addSelectedUsers()} disabled={adding || selectedAddIds.length === 0}>
                        {adding ? "Adding..." : `Add selected (${selectedAddIds.length})`}
                    </Button>
                </DialogActions>
            </Dialog>

            <ConfirmRemoveDialog
                user={confirmRemove}
                onCancel={() => setConfirmRemove(null)}
                isRemove={isRemove}
                onConfirm={async () => {
                    if (!confirmRemove || !teamId) return;

                    try {
                        setIsRemove(true);
                        const token = await getToken(msalInstance);
                        if (!token) return;

                        await delete_team_user(teamId, confirmRemove._id, token);

                        // update UI หลังลบสำเร็จ
                        setUsers(prev => prev.filter(u => u._id !== confirmRemove._id));

                        showNotification("User removed successfully", "success");
                    } catch (err) {
                        setIsRemove(false);
                        console.error("Delete user failed:", err);
                        showNotification("Failed to remove user", "error");
                    } finally {
                        setConfirmRemove(null);
                        setIsRemove(false);
                    }
                }}
            />

            <ConfirmApproveDialog
                users={waiting.filter(u => confirmApproveIds?.includes(getWaitingKey(u)))}
                isApprove={isApprove}
                onCancel={() => setConfirmApproveIds(null)}
                onConfirm={async () => {
                    if (!confirmApproveIds || !teamId) return;

                    try {
                        setIsApprove(true);
                        const token = await getToken(msalInstance);
                        if (!token) return;

                        const selectedUsers = waiting.filter(u => confirmApproveIds.includes(getWaitingKey(u)));
                        await approve_users(teamId, selectedUsers, token);

                        approveUsers(confirmApproveIds); // update UI
                        showNotification("Users approved successfully", "success");
                    } catch (err) {
                        setIsApprove(false);
                        console.error("Approve users failed:", err);
                        showNotification("Failed to approve users", "error");
                    } finally {
                        setIsApprove(false);
                    }
                }}
            />

            <ConfirmRejectDialog
                users={waiting.filter(u => confirmRejectIds?.includes(getWaitingKey(u)))}
                onCancel={() => setConfirmRejectIds(null)}
                isReject={isReject}
                onConfirm={async () => {
                    if (!confirmRejectIds || !teamId) return;

                    try {
                        setIsReject(true);
                        const token = await getToken(msalInstance);
                        if (!token) return;

                        const selectedUsers = waiting.filter(u => confirmRejectIds.includes(getWaitingKey(u)));
                        await reject_users(teamId, selectedUsers, token);

                        rejectUsers(confirmRejectIds); // update UI

                        showNotification("Users rejected successfully", "success");
                    } catch (err) {
                        setIsReject(false);
                        console.error("Reject users failed:", err);
                        showNotification("Failed to reject users", "error");
                    } finally {
                        setIsReject(false);
                    }
                }}
            />
        </Stack>
    );
}

function UserListSkeleton({ rows = 5 }: { rows?: number }) {
    return (
        <Stack spacing={1}>
            {Array.from({ length: rows }).map((_, i) => (
                <Box
                    key={i}
                    sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        p: 1,
                        border: "1px solid",
                        borderColor: "divider",
                        borderRadius: 1
                    }}
                >
                    <Box sx={{ flex: 1 }}>
                        <Skeleton width="60%" />
                        <Skeleton width="40%" />
                    </Box>
                    <Skeleton variant="circular" width={32} height={32} />
                </Box>
            ))}
        </Stack>
    );
}

/* =========================
   ROW COMPONENTS
========================= */
function UserRow({ user, onView, onRemove }: { user: User; onView: () => void; onRemove: () => void }) {
    return (
        <RowContainer>
            <UserInfo user={user} />
            <Box>
                <IconButton onClick={onView}>
                    <VisibilityIcon />
                </IconButton>
                <IconButton onClick={onRemove} color="error">
                    <DeleteIcon />
                </IconButton>
            </Box>
        </RowContainer>
    );
}

function WaitingUserRow({ user, checked, onToggle, onView }: { user: User; checked: boolean; onToggle: () => void; onView: () => void }) {
    return (
        <RowContainer>
            <Box sx={{ display: "flex", alignItems: "center" }}>
                <Checkbox checked={checked} onChange={onToggle} />
                <UserInfo user={user} />
            </Box>
            <IconButton onClick={onView}>
                <VisibilityIcon />
            </IconButton>
        </RowContainer>
    );
}

/* =========================
   DIALOGS
========================= */
function UserDetailDialog({ user, onClose }: { user: User | null; onClose: () => void }) {
    if (!user) return null;

    return (
        <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle sx={{ fontWeight: 600 }}>
                User: {user.first_name} {user.last_name}
            </DialogTitle>

            <DialogContent dividers>
                <Stack spacing={2}>
                    <DetailRow label="Email" value={user.email} />
                    <DetailRow label="Employee ID" value={user.employee_id} />
                    <DetailRow label="AD Email" value={user.ad_email} />
                    <DetailRow
                        label="Status"
                        value={<Chip label={user.active ? "Active" : "Inactive"} color={user.active ? "success" : "default"} size="small" />}
                    />
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
}

function ConfirmApproveDialog({
    users,
    onCancel,
    onConfirm,
    isApprove
}: {
    users: User[] | undefined;
    onCancel: () => void;
    onConfirm: () => void;
    isApprove: boolean;
}) {
    if (!users || users.length === 0) return null;

    return (
        <Dialog open onClose={onCancel} maxWidth="sm" fullWidth>
            <DialogTitle>Approve User(s)</DialogTitle>
            <DialogContent dividers>
                <Typography sx={{ mb: 1 }}>Approve the following user(s)?</Typography>
                {users.map(u => (
                    <Typography key={u.email ?? u.ad_email ?? `${u.first_name}-${u.last_name}`}>
                        • {u.first_name} {u.last_name} ({u.email})
                    </Typography>
                ))}
            </DialogContent>
            <DialogActions>
                <Button onClick={onCancel}>Cancel</Button>
                <Button variant="contained" color="success" disabled={isApprove} onClick={onConfirm}>
                    {isApprove ? "Approve..." : "Approve"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

function ConfirmRejectDialog({
    users,
    onCancel,
    onConfirm,
    isReject
}: {
    users: User[] | undefined;
    onCancel: () => void;
    onConfirm: () => void;
    isReject: boolean;
}) {
    if (!users || users.length === 0) return null;

    return (
        <Dialog open onClose={onCancel} maxWidth="sm" fullWidth>
            <DialogTitle>Reject User(s)</DialogTitle>
            <DialogContent dividers>
                <Typography sx={{ mb: 1 }}>Reject the following user(s)?</Typography>
                {users.map(u => (
                    <Typography key={u.email ?? u.ad_email ?? `${u.first_name}-${u.last_name}`}>
                        • {u.first_name} {u.last_name} ({u.email})
                    </Typography>
                ))}
            </DialogContent>
            <DialogActions>
                <Button onClick={onCancel}>Cancel</Button>
                <Button variant="contained" color="error" disabled={isReject} onClick={onConfirm}>
                    {isReject ? "Reject..." : "Reject"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

function ConfirmRemoveDialog({ user, onCancel, onConfirm, isRemove }: { user: User | null; onCancel: () => void; onConfirm: () => void; isRemove?: boolean }) {
    if (!user) return null;

    return (
        <Dialog open onClose={onCancel} maxWidth="xs" fullWidth>
            <DialogTitle>Remove User</DialogTitle>
            <DialogContent>
                <Typography>
                    Remove{" "}
                    <strong>
                        {user.first_name} {user.last_name}
                    </strong>{" "}
                    from this team?
                </Typography>
            </DialogContent>
            <DialogActions>
                <Button onClick={onCancel}>Cancel</Button>
                <Button color="error" variant="contained" disabled={isRemove} onClick={onConfirm}>
                    {isRemove ? "Removing..." : "Remove"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

/* =========================
   HELPERS
========================= */
function RowContainer({ children }: { children: React.ReactNode }) {
    return (
        <Box
            sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                p: 1,
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 1
            }}
        >
            {children}
        </Box>
    );
}

function UserInfo({ user }: { user: User }) {
    const email = user.email || user.ad_email || "No email";
    return (
        <Box>
            <Typography>
                {user.first_name} {user.last_name}
            </Typography>
            <Typography variant="caption" color="text.secondary">
                {email}{user.employee_id ? ` · Employee ID: ${user.employee_id}` : ""}
            </Typography>
        </Box>
    );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
    return (
        <Stack spacing={0.5}>
            <Typography variant="caption" color="text.secondary">
                {label}
            </Typography>
            <Typography variant="body2">{value}</Typography>
        </Stack>
    );
}
