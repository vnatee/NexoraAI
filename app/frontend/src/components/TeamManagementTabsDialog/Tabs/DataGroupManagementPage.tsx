import React, { useEffect, useMemo, useState } from "react";
import {
    Box,
    Typography,
    Divider,
    Paper,
    Stack,
    Button,
    IconButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Checkbox,
    Skeleton,
    Alert,
    Chip,
    FormControl,
    FormControlLabel,
    FormLabel,
    Radio,
    RadioGroup
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import VisibilityIcon from "@mui/icons-material/Visibility";
import GroupAddIcon from "@mui/icons-material/GroupAdd";
import DeleteIcon from "@mui/icons-material/Delete";
import { useMsal } from "@azure/msal-react";

import {
    get_data_group_by_team,
    create_data_group,
    edit_data_group,
    delete_data_group,
    get_users_by_team_id,
    DataGroupDisplay,
    TeamProfile,
    User
} from "../../../api";

import { getToken } from "../../../authConfig";
import { useNotification } from "../../../utill/NotificationProvider";

/* =========================================================
   PAGE
========================================================= */
export function DataGroupManagementPage({ team }: { team: TeamProfile | null }) {
    const { instance } = useMsal();
    const [dataGroups, setDataGroups] = useState<DataGroupDisplay[]>([]);
    const [users, setUsers] = useState<User[]>([]);
    const [search, setSearch] = useState("");
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [openNew, setOpenNew] = useState(false);
    const [viewGroup, setViewGroup] = useState<DataGroupDisplay | null>(null);
    const [assignGroup, setAssignGroup] = useState<DataGroupDisplay | null>(null);
    const [deleteGroup, setDeleteGroup] = useState<DataGroupDisplay | null>(null);
    const [usersLoading, setUsersLoading] = useState(false);
    const { showNotification } = useNotification();
    /* =========================
       LOAD DATA GROUP BY TEAM
    ========================= */
    useEffect(() => {
        const loadDataGroups = async () => {
            if (!team?._id) return;

            try {
                setLoading(true);
                const token = await getToken(instance);
                if (!token) return;

                const result = await get_data_group_by_team(team._id, token);
                setDataGroups(result ?? []);
            } catch (err) {
                console.error("load data group failed:", err);
                showNotification(err instanceof Error ? err.message : "Failed to load data groups", "error");
            } finally {
                setLoading(false);
            }
        };

        loadDataGroups();
    }, [team, instance]);

    /* =========================
       LOAD USERS FOR ASSIGN USER
       👉 Users มาจาก API get_users_by_team_id
       👉 Response: { users: User[] }
    ========================= */
    useEffect(() => {
        const loadUsers = async () => {
            if (!team?._id) return;

            try {
                setUsersLoading(true);
                const token = await getToken(instance);
                if (!token) return;

                const result = await get_users_by_team_id(team._id, token);

                // ✅ สำคัญ: API response เป็น { users: [] }
                setUsers(result?.users ?? []);
            } catch (err) {
                console.error("load users failed:", err);
                showNotification(err instanceof Error ? err.message : "Failed to load team members", "error");
            } finally {
                setUsersLoading(false);
            }
        };

        loadUsers();
    }, [team, instance]);

    const filteredGroups = useMemo(() => dataGroups.filter(d => d.name.toLowerCase().includes(search.toLowerCase())), [dataGroups, search]);

    /* =========================
       RENDER
    ========================= */
    return (
        <Stack spacing={2}>
            {/* HEADER */}
            <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                    <Typography variant="h6">Data Group Management</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Manage data group access
                    </Typography>
                </Box>

                <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpenNew(true)} disabled={!team}>
                    New Data Group
                </Button>
            </Box>

            <TextField size="small" placeholder="Search data group..." value={search} onChange={e => setSearch(e.target.value)} sx={{ maxWidth: 300 }} />

            <Divider />

            {/* LIST */}
            <Box sx={{ maxHeight: 400, overflowY: "auto" }}>
                {loading ? (
                    <DataGroupListSkeleton count={6} />
                ) : filteredGroups.length === 0 ? (
                    <Typography color="text.secondary">No data group found</Typography>
                ) : (
                    <Stack spacing={1}>
                        {/* LIST (Virtualized) */}
                        <Box>
                            {loading ? (
                                <Typography color="text.secondary">Loading...</Typography>
                            ) : filteredGroups.length === 0 ? (
                                <Typography color="text.secondary">No data group found</Typography>
                            ) : (
                                <VirtualizedDataGroupList
                                    items={filteredGroups}
                                    height={400}
                                    itemHeight={92} // ✅ ปรับตามความสูง Paper จริง
                                    overscan={6}
                                    renderItem={(dg: DataGroupDisplay) => (
                                        <Paper
                                            key={dg._id}
                                            variant="outlined"
                                            sx={{
                                                p: 2,
                                                width: "100%",
                                                display: "flex",
                                                justifyContent: "space-between",
                                                alignItems: "center"
                                            }}
                                        >
                                            <Box>
                                                <Typography fontWeight={600}>{dg.name}</Typography>
                                                <Stack direction="row" spacing={1} alignItems="center" mt={0.5}>
                                                    <Chip
                                                        size="small"
                                                        color={dg.access_mode === "team" ? "success" : "default"}
                                                        label={dg.access_mode === "team" ? "Entire team" : `Selected users (${dg.user_id?.length ?? 0})`}
                                                    />
                                                </Stack>
                                            </Box>

                                            <Box>
                                                <IconButton onClick={() => setViewGroup(dg)}>
                                                    <VisibilityIcon />
                                                </IconButton>
                                                <IconButton onClick={() => setAssignGroup(dg)}>
                                                    <GroupAddIcon />
                                                </IconButton>
                                                <IconButton color="error" disabled={deletingId === dg._id} onClick={() => setDeleteGroup(dg)}>
                                                    <DeleteIcon />
                                                </IconButton>
                                            </Box>
                                        </Paper>
                                    )}
                                />
                            )}
                        </Box>
                    </Stack>
                )}
            </Box>

            {/* CREATE */}
            <NewDataGroupDialog
                open={openNew}
                loading={saving}
                users={users}
                usersLoading={usersLoading}
                onClose={() => setOpenNew(false)}
                onCreate={async payload => {
                    if (!team?._id) return;

                    try {
                        setSaving(true);
                        const token = await getToken(instance);
                        if (!token) return;

                        await create_data_group(team._id, payload.name, payload.users_id, payload.access_mode, token);

                        const refreshed = await get_data_group_by_team(team._id, token);
                        setDataGroups(refreshed ?? []);
                        setOpenNew(false);
                        showNotification("Data group created successfully", "success");
                    } catch (err) {
                        console.error("create data group failed:", err);
                        showNotification(err instanceof Error ? err.message : "Failed to create data group", "error");
                    } finally {
                        setSaving(false);
                    }
                }}
            />

            {/* VIEW */}
            <ViewDataGroupDialog group={viewGroup} onClose={() => setViewGroup(null)} />

            {/* ASSIGN USERS + EDIT NAME */}
            <AssignUserDialog
                group={assignGroup}
                users={users}
                loading={saving}
                usersLoading={usersLoading}
                onCancel={() => setAssignGroup(null)}
                onConfirm={async (payload: DataGroupFormPayload) => {
                    if (!assignGroup || !team?._id) return;

                    try {
                        setSaving(true);
                        const token = await getToken(instance);
                        if (!token) return;

                        const dataGroupId = assignGroup._id;
                        await edit_data_group(dataGroupId, payload.name, payload.users_id, payload.access_mode, token);

                        const refreshed = await get_data_group_by_team(team._id, token);
                        setDataGroups(refreshed ?? []);
                        setAssignGroup(null);
                        showNotification("Data group updated successfully", "success");
                    } catch (err) {
                        console.error("edit data group failed:", err);
                        showNotification(err instanceof Error ? err.message : "Failed to update data group", "error");
                    } finally {
                        setSaving(false);
                    }
                }}
            />

            {/* DELETE */}
            <DeleteDataGroupDialog
                group={deleteGroup}
                loading={deletingId === deleteGroup?._id}
                onCancel={() => setDeleteGroup(null)}
                onConfirm={async () => {
                    if (!deleteGroup || !team?._id) return;

                    try {
                        setDeletingId(deleteGroup._id);

                        const token = await getToken(instance);
                        if (!token) return;

                        await delete_data_group(team._id, deleteGroup._id, token);

                        setDataGroups(prev => prev.filter(d => d._id !== deleteGroup._id));
                        setDeleteGroup(null);
                        showNotification("Data group deleted successfully", "success");
                    } catch (err) {
                        console.error("delete data group failed:", err);
                        showNotification("Failed to delete data group", "error");
                    } finally {
                        setDeletingId(null);
                    }
                }}
            />
        </Stack>
    );
}

/* =========================================================
   DIALOG COMPONENTS
========================================================= */

type DataGroupAccessMode = "team" | "selected_users";

type DataGroupFormPayload = {
    name: string;
    access_mode: DataGroupAccessMode;
    users_id: string[];
};

function userIdentity(user: User): string {
    const email = user.email || user.ad_email || "No email";
    return user.employee_id ? `${email} · Employee ID: ${user.employee_id}` : email;
}

function DataGroupAccessEditor({
    accessMode,
    onAccessModeChange,
    selectedIds,
    onSelectedIdsChange,
    users,
    usersLoading,
    disabled
}: {
    accessMode: DataGroupAccessMode;
    onAccessModeChange: (mode: DataGroupAccessMode) => void;
    selectedIds: string[];
    onSelectedIdsChange: (ids: string[]) => void;
    users: User[];
    usersLoading: boolean;
    disabled: boolean;
}) {
    const [userSearch, setUserSearch] = useState("");
    const filteredUsers = useMemo(() => {
        const query = userSearch.trim().toLowerCase();
        if (!query) return users;
        return users.filter(user =>
            [user.first_name, user.last_name, user.email, user.ad_email, user.employee_id]
                .filter(Boolean)
                .some(value => String(value).toLowerCase().includes(query))
        );
    }, [userSearch, users]);

    return (
        <Stack spacing={2} mt={2}>
            <Divider />
            <FormControl disabled={disabled}>
                <FormLabel>Who can use this data group?</FormLabel>
                <RadioGroup value={accessMode} onChange={event => onAccessModeChange(event.target.value as DataGroupAccessMode)}>
                    <FormControlLabel value="team" control={<Radio />} label="Entire team" />
                    <FormControlLabel value="selected_users" control={<Radio />} label="Selected users only" />
                </RadioGroup>
            </FormControl>

            {accessMode === "team" ? (
                <Alert severity="info">All current and future members of this team can retrieve documents assigned to this data group.</Alert>
            ) : (
                <>
                    <Alert severity={selectedIds.length > 0 ? "info" : "warning"}>
                        {selectedIds.length > 0 ? `${selectedIds.length} user(s) selected.` : "Select at least one team member."}
                    </Alert>
                    <TextField
                        size="small"
                        fullWidth
                        placeholder="Search by name, email, or employee ID..."
                        value={userSearch}
                        disabled={disabled}
                        onChange={event => setUserSearch(event.target.value)}
                    />
                    <Typography variant="caption" color="text.secondary">
                        Showing {filteredUsers.length} of {users.length} team members
                    </Typography>
                    <Box sx={{ maxHeight: 300, overflowY: "auto", border: "1px solid", borderColor: "divider", borderRadius: 1, px: 1 }}>
                        {usersLoading ? (
                            <UserListSkeleton count={8} />
                        ) : filteredUsers.length === 0 ? (
                            <Typography color="text.secondary" sx={{ p: 2 }}>
                                No matching team members
                            </Typography>
                        ) : (
                            filteredUsers.map(user => (
                                <Box key={user._id} display="flex" alignItems="center" py={0.5}>
                                    <Checkbox
                                        disabled={disabled}
                                        checked={selectedIds.includes(user._id)}
                                        onChange={() =>
                                            onSelectedIdsChange(
                                                selectedIds.includes(user._id)
                                                    ? selectedIds.filter(id => id !== user._id)
                                                    : [...selectedIds, user._id]
                                            )
                                        }
                                    />
                                    <Box minWidth={0}>
                                        <Typography noWrap>
                                            {user.first_name} {user.last_name}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary" noWrap>
                                            {userIdentity(user)}
                                        </Typography>
                                    </Box>
                                </Box>
                            ))
                        )}
                    </Box>
                </>
            )}
        </Stack>
    );
}

function NewDataGroupDialog({
    open,
    loading,
    users,
    usersLoading,
    onClose,
    onCreate
}: {
    open: boolean;
    loading: boolean;
    users: User[];
    usersLoading: boolean;
    onClose: () => void;
    onCreate: (payload: DataGroupFormPayload) => Promise<void>;
}) {
    const [name, setName] = useState("");
    const [accessMode, setAccessMode] = useState<DataGroupAccessMode>("team");
    const [selectedIds, setSelectedIds] = useState<string[]>([]);

    useEffect(() => {
        if (!open) {
            setName("");
            setAccessMode("team");
            setSelectedIds([]);
        }
    }, [open]);

    return (
        <Dialog open={open} onClose={loading ? undefined : onClose} maxWidth="sm" fullWidth>
            <DialogTitle>New Data Group</DialogTitle>
            <DialogContent dividers>
                <TextField label="Data Group Name" fullWidth disabled={loading} value={name} onChange={e => setName(e.target.value)} />
                <DataGroupAccessEditor
                    accessMode={accessMode}
                    onAccessModeChange={setAccessMode}
                    selectedIds={selectedIds}
                    onSelectedIdsChange={setSelectedIds}
                    users={users}
                    usersLoading={usersLoading}
                    disabled={loading}
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={loading}>
                    Cancel
                </Button>
                <Button
                    variant="contained"
                    disabled={!name.trim() || loading || (accessMode === "selected_users" && selectedIds.length === 0)}
                    onClick={() => onCreate({ name: name.trim(), access_mode: accessMode, users_id: accessMode === "team" ? [] : selectedIds })}
                >
                    {loading ? "Creating..." : "Create"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

function VirtualizedDataGroupList({
    items,
    height = 400,
    itemHeight = 88,
    overscan = 5,
    renderItem
}: {
    items: any[];
    height?: number;
    itemHeight?: number;
    overscan?: number;
    renderItem: (item: any) => React.ReactNode;
}) {
    const [scrollTop, setScrollTop] = useState(0);

    const totalHeight = items.length * itemHeight;

    const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const endIndex = Math.min(items.length - 1, Math.floor((scrollTop + height) / itemHeight) + overscan);

    const visibleItems = items.slice(startIndex, endIndex + 1);

    const offsetY = startIndex * itemHeight;

    return (
        <Box sx={{ height, overflowY: "auto", position: "relative" }} onScroll={e => setScrollTop((e.target as HTMLDivElement).scrollTop)}>
            {/* spacer to create scroll height */}
            <Box sx={{ height: totalHeight, position: "relative" }}>
                {/* visible window */}
                <Box sx={{ position: "absolute", top: offsetY, left: 0, right: 0 }}>
                    {visibleItems.map((item, idx) => (
                        <Box key={item._id ?? `${startIndex}-${idx}`} sx={{ height: itemHeight, display: "flex", alignItems: "stretch" }}>
                            {renderItem(item)}
                        </Box>
                    ))}
                </Box>
            </Box>
        </Box>
    );
}

function ViewDataGroupDialog({ group, onClose }: { group: DataGroupDisplay | null; onClose: () => void }) {
    if (!group) return null;

    return (
        <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>{group.name}</DialogTitle>
            <DialogContent dividers>
                {group.access_mode === "team" ? (
                    <Alert severity="success">Everyone in this team can use this data group.</Alert>
                ) : (
                    <Stack spacing={1}>
                        <Typography variant="subtitle2">Selected users ({group.user_id?.length ?? 0})</Typography>
                        {group.user_id.map((u: User) => (
                        <Box key={u._id} mb={1}>
                            <Typography>
                                {u.first_name} {u.last_name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">{userIdentity(u)}</Typography>
                        </Box>
                        ))}
                    </Stack>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
}

function UserListSkeleton({ count = 8 }: { count?: number }) {
    return (
        <Box sx={{ px: 1 }}>
            {Array.from({ length: count }).map((_, idx) => (
                <Box key={idx} display="flex" alignItems="center" py={0.75}>
                    <Skeleton variant="rectangular" width={22} height={22} sx={{ borderRadius: 0.5, mr: 2 }} />
                    <Box sx={{ width: "100%" }}>
                        <Skeleton variant="text" width="40%" height={22} />
                        <Skeleton variant="text" width="55%" height={18} />
                    </Box>
                </Box>
            ))}
        </Box>
    );
}

function AssignUserDialog({
    group,
    users,
    loading,
    usersLoading,
    onCancel,
    onConfirm
}: {
    group: DataGroupDisplay | null;
    users: User[];
    loading: boolean;
    usersLoading: boolean;
    onCancel: () => void;
    onConfirm: (payload: DataGroupFormPayload) => Promise<void>;
}) {
    const [name, setName] = useState("");
    const [selectedIds, setSelectedIds] = useState<string[]>([]);
    const [accessMode, setAccessMode] = useState<DataGroupAccessMode>("team");

    useEffect(() => {
        if (!group) return;
        setName(group.name);
        setSelectedIds(group.user_id.map(u => u._id));
        setAccessMode(group.access_mode ?? (group.user_id.length === 0 ? "team" : "selected_users"));
    }, [group]);

    const originalIds = useMemo(() => (group?.user_id ?? []).map(u => u._id).sort(), [group]);

    const hasUserChange = JSON.stringify([...selectedIds].sort()) !== JSON.stringify(originalIds);
    const originalAccessMode = group?.access_mode ?? ((group?.user_id.length ?? 0) === 0 ? "team" : "selected_users");
    const hasNameChange = name.trim() !== (group?.name ?? "").trim();
    const hasChange = hasUserChange || hasNameChange || accessMode !== originalAccessMode;

    const isDisabled = loading;

    if (!group) return null;

    return (
        <Dialog open onClose={loading ? undefined : onCancel} maxWidth="sm" fullWidth>
            <DialogTitle>Edit Data Group – {group.name}</DialogTitle>

            <DialogContent dividers>
                {/* EDIT NAME */}
                <Box mb={2}>
                    <TextField label="Data Group Name" fullWidth disabled={isDisabled} value={name} onChange={e => setName(e.target.value)} />
                </Box>

                <DataGroupAccessEditor
                    accessMode={accessMode}
                    onAccessModeChange={setAccessMode}
                    selectedIds={selectedIds}
                    onSelectedIdsChange={setSelectedIds}
                    users={users}
                    usersLoading={usersLoading}
                    disabled={isDisabled}
                />
            </DialogContent>

            <DialogActions>
                <Button onClick={onCancel} disabled={isDisabled}>
                    Cancel
                </Button>

                <Button
                    variant="contained"
                    disabled={!hasChange || isDisabled || !name.trim() || (accessMode === "selected_users" && selectedIds.length === 0)}
                    onClick={() => onConfirm({ name: name.trim(), access_mode: accessMode, users_id: accessMode === "team" ? [] : selectedIds })}
                >
                    {loading ? "Saving..." : "Save"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

function DataGroupListSkeleton({ count = 6 }: { count?: number }) {
    return (
        <Stack spacing={1}>
            {Array.from({ length: count }).map((_, idx) => (
                <Paper
                    key={idx}
                    variant="outlined"
                    sx={{
                        p: 2,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center"
                    }}
                >
                    <Box sx={{ width: "70%" }}>
                        <Skeleton variant="text" width="40%" height={26} />
                        <Skeleton variant="text" width="25%" height={18} />
                    </Box>

                    <Box sx={{ display: "flex", gap: 1 }}>
                        <Skeleton variant="circular" width={32} height={32} />
                        <Skeleton variant="circular" width={32} height={32} />
                        <Skeleton variant="circular" width={32} height={32} />
                    </Box>
                </Paper>
            ))}
        </Stack>
    );
}

function DeleteDataGroupDialog({
    group,
    loading,
    onCancel,
    onConfirm
}: {
    group: DataGroupDisplay | null;
    loading: boolean;
    onCancel: () => void;
    onConfirm: () => Promise<void>;
}) {
    if (!group) return null;

    return (
        <Dialog open onClose={loading ? undefined : onCancel} maxWidth="xs" fullWidth>
            <DialogTitle>Delete Data Group</DialogTitle>
            <DialogContent>
                <Typography>
                    Delete <strong>{group.name}</strong> ?
                </Typography>
            </DialogContent>
            <DialogActions>
                <Button onClick={onCancel} disabled={loading}>
                    Cancel
                </Button>
                <Button color="error" variant="contained" disabled={loading} onClick={onConfirm}>
                    {loading ? "Deleting..." : "Delete"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
