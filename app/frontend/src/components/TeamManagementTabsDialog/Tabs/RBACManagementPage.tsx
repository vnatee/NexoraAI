import React, { useEffect, useMemo, useState } from "react";
import {
    Stack,
    Typography,
    Divider,
    Tabs,
    Tab,
    Box,
    Paper,
    Button,
    TextField,
    Checkbox,
    Select,
    MenuItem,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Skeleton
} from "@mui/material";
import { useMsal } from "@azure/msal-react";

import {
    create_role,
    edit_role,
    delete_role,
    get_roles_by_team,
    get_all_permission,
    Role,
    Permission,
    get_team_users,
    create_edit_user_permissions,
    User,
    get_user_permissions,
    TeamProfile
} from "../../../api";

import { getToken } from "../../../authConfig";
import { useNotification } from "../../../utill/NotificationProvider";

/* =========================================================
   PAGE
========================================================= */

export function RBACManagementPage({ team }: { team: TeamProfile | null }) {
    const { instance } = useMsal();

    const [tab, setTab] = useState(0);
    const [userTabEnabled, setUserTabEnabled] = useState(false);

    // ✅ permissions from API
    const [permissions, setPermissions] = useState<Permission[]>([]);
    const [permLoading, setPermLoading] = useState(false);

    /* =========================
       LOAD PERMISSIONS
       GET /get_all_permissions
    ========================= */
    const normalizePermissionType = (type: string) => {
        const t = (type ?? "").toLowerCase().trim();

        if (t === "system permissions" || t === "system" || t.includes("system")) return "SYSTEM";
        if (t === "team permissions" || t === "team" || t.includes("team")) return "TEAM";

        return type; // fallback
    };
    useEffect(() => {
        const loadPermissions = async () => {
            try {
                setPermLoading(true);
                const token = await getToken(instance);
                if (!token) return;

                const perms = await get_all_permission(token);
                const normalized = (perms ?? []).map((p: any) => ({
                    ...p,
                    type: normalizePermissionType(p.type)
                }));

                setPermissions(normalized);
            } catch (err) {
                console.error("load permissions failed:", err);
            } finally {
                setPermLoading(false);
            }
        };

        loadPermissions();
    }, [instance]);

    return (
        <Stack spacing={2}>
            <Typography variant="h6">RBAC</Typography>
            <Typography variant="body2" color="text.secondary">
                Configure roles and permissions for this team
            </Typography>

            <Divider />

            <Tabs
                value={tab}
                onChange={(_, v) => {
                    setTab(v);

                    if (v === 1) setUserTabEnabled(true);
                }}
            >
                <Tab label="Role Preset" />
                <Tab label="User Permission" />
            </Tabs>

            {tab === 0 && <RolePresetPanel team={team} permissions={permissions} permissionsLoading={permLoading} />}

            {tab === 1 && <UserPermissionPanel team={team} permissions={permissions} permissionsLoading={permLoading} enabled={userTabEnabled} />}
        </Stack>
    );
}

/* =========================================================
   TAB 1: ROLE PRESET (CRUD) - API จริง
========================================================= */

function RolePresetPanel({ team, permissions, permissionsLoading }: { team: { _id: string } | null; permissions: Permission[]; permissionsLoading: boolean }) {
    const { instance } = useMsal();
    const [roles, setRoles] = useState<Role[]>([]);
    const [selectedRole, setSelectedRole] = useState<Role | null>(null);
    const [editing, setEditing] = useState(false);
    const [name, setName] = useState("");
    const [permissionIds, setPermissionIds] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [isNewDraft, setIsNewDraft] = useState(false);
    const [prevSelectedRoleId, setPrevSelectedRoleId] = useState<string | null>(null);
    const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
    const [hasSelectedOnce, setHasSelectedOnce] = useState(false);
    const [roleSearch, setRoleSearch] = useState("");
    const { showNotification } = useNotification();

    const filteredRoles = useMemo(() => {
        const q = roleSearch.trim().toLowerCase();
        if (!q) return roles;
        return roles.filter(r => (r.name ?? "").toLowerCase().includes(q));
    }, [roles, roleSearch]);

    /* =========================
       LOAD ROLES BY TEAM
    ========================= */
    useEffect(() => {
        const loadRoles = async () => {
            if (!team?._id) return;

            try {
                setLoading(true);
                const token = await getToken(instance);
                if (!token) return;

                const result = await get_roles_by_team(team._id, token); // returns roles[]
                const list: Role[] = result ?? [];

                setRoles(list);

                setSelectedRole(null);

                setEditing(false);
            } catch (err) {
                console.error("load roles failed:", err);
            } finally {
                setLoading(false);
            }
        };

        loadRoles();
    }, [team, instance]);

    /* =========================
       sync selectedRole -> form
    ========================= */
    useEffect(() => {
        if (!selectedRole) return;
        setName(selectedRole.name ?? "");
        setPermissionIds(selectedRole.permission_id ?? []);
    }, [selectedRole]);

    const togglePermission = (id: string) => {
        if (!editing) return;
        setPermissionIds(prev => (prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]));
    };

    const isBusy = loading || saving || deleting;
    const canEditPermissions = editing && !saving && !deleting && !permissionsLoading;

    /* =========================
       ACTIONS
    ========================= */
    const handleCreate = () => {
        // remember previous selected for back
        setPrevSelectedRoleId(selectedRole?._id ?? null);

        // local draft role (no api)
        const draft: Role = {
            _id: `draft-${Date.now()}`, // local id only
            name: "New Role",
            permission_id: [],
            team_id: team?._id
        };

        // IMPORTANT: don't append to roles list yet
        setSelectedRole(draft);

        // enter editing mode
        setName(draft.name);
        setPermissionIds([]);
        setEditing(true);

        // mark draft mode
        setIsNewDraft(true);
    };

    const handleSave = async () => {
        if (!team?._id) return;

        try {
            setSaving(true);
            const token = await getToken(instance);
            if (!token) return;

            if (isNewDraft) {
                // ✅ CREATE REAL ROLE
                await create_role(team._id, name.trim(), permissionIds, token);
                showNotification("Role created successfully", "success");
            } else {
                // ✅ EDIT ROLE
                if (!selectedRole?._id) return;
                await edit_role(team._id, selectedRole._id, name.trim(), permissionIds, token);
                showNotification("Role edited successfully", "success");
            }

            // refresh roles
            const refreshed = await get_roles_by_team(team._id, token);
            const list: Role[] = refreshed ?? [];
            setRoles(list);

            // select the saved role
            if (isNewDraft) {
                // best effort: find by name
                const created = [...list].reverse().find(r => r.name === name.trim()) ?? list[list.length - 1] ?? null;
                setSelectedRole(created);
            } else {
                const updated = list.find(r => r._id === selectedRole?._id) ?? null;
                setSelectedRole(updated);
            }

            setEditing(false);
            setIsNewDraft(false);
            setPrevSelectedRoleId(null);
        } catch (err) {
            console.error(isNewDraft ? "create role failed:" : "edit role failed:", err);
            showNotification("Failed to save role", "error");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!selectedRole?._id) return;

        try {
            setDeleting(true);
            const token = await getToken(instance);
            if (!token) return;

            await delete_role(selectedRole._id, token);

            setRoles(prev => prev.filter(r => r._id !== selectedRole._id));
            setSelectedRole(null);
            setEditing(false);
            showNotification("Role deleted successfully", "success");
        } catch (err) {
            console.error("delete role failed:", err);
            showNotification("Failed to delete role", "error");
        } finally {
            setDeleting(false);
        }
    };

    const isRoleSelected = !!selectedRole;

    return (
        <Stack direction="row" spacing={2}>
            {/* ROLE LIST */}
            <Paper
                variant="outlined"
                sx={{
                    width: isRoleSelected ? 320 : "100%",
                    p: 2,
                    borderRadius: 2,
                    transition: "width 200ms ease"
                }}
            >
                {/* Header */}
                <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Box>
                        <Typography fontWeight={700}>Roles</Typography>
                        <Typography variant="caption" color="text.secondary">
                            {roles.length} role(s)
                        </Typography>
                    </Box>

                    <Button variant="contained" onClick={handleCreate} disabled={!team || isBusy}>
                        + New Role
                    </Button>
                </Box>

                <Divider sx={{ my: 2 }} />

                {/* Search */}
                <TextField
                    size="small"
                    fullWidth
                    placeholder="Search role..."
                    value={roleSearch}
                    onChange={e => setRoleSearch(e.target.value)}
                    disabled={loading || saving || deleting}
                    sx={{ mb: 1.5 }}
                />

                {/* List */}
                <Box sx={{ maxHeight: 520, overflowY: "auto", pr: 0.5 }}>
                    {loading ? (
                        <Stack spacing={1}>
                            {Array.from({ length: 8 }).map((_, i) => (
                                <Skeleton key={i} variant="rounded" height={64} />
                            ))}
                        </Stack>
                    ) : filteredRoles.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">
                            No roles found
                        </Typography>
                    ) : (
                        <Stack spacing={1}>
                            {filteredRoles.map(r => {
                                const isSelected = selectedRole?._id === r._id;

                                return (
                                    <Paper
                                        key={r._id}
                                        variant="outlined"
                                        onClick={() => {
                                            if (isBusy) return;
                                            setSelectedRole(r);
                                            setEditing(false);
                                            setIsNewDraft(false);
                                        }}
                                        sx={{
                                            p: 1.5,
                                            cursor: isBusy ? "default" : "pointer",
                                            borderRadius: 2,
                                            bgcolor: isSelected ? "action.selected" : "background.paper",
                                            transition: "all 120ms ease",
                                            "&:hover": {
                                                bgcolor: "action.hover"
                                            }
                                        }}
                                    >
                                        <Typography fontWeight={700} sx={{ lineHeight: 1.2 }}>
                                            {r.name}
                                        </Typography>

                                        <Typography variant="caption" color="text.secondary">
                                            {r.permission_id?.length ?? 0} permission(s)
                                        </Typography>
                                    </Paper>
                                );
                            })}
                        </Stack>
                    )}
                </Box>
            </Paper>

            {/* ROLE DETAIL (แสดงเมื่อเลือก role แล้วเท่านั้น) */}
            {selectedRole && (
                <Paper sx={{ flex: 1, p: 2 }}>
                    {/* ✅ ใส่ปุ่ม Back เพื่อกลับไป full list */}
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                        <Typography fontWeight={700}>Role Detail</Typography>

                        {!editing && (
                            <Button
                                onClick={() => {
                                    setSelectedRole(null);
                                    setEditing(false);
                                    setIsNewDraft(false);
                                }}
                                disabled={isBusy}
                            >
                                Back to list
                            </Button>
                        )}
                    </Box>

                    {/* ... (ส่วน detail เดิมของคุณ 그대로) */}
                    <Stack spacing={2}>
                        <TextField label="Role Name" value={name} disabled={!editing || saving || deleting} onChange={e => setName(e.target.value)} />

                        {/* ✅ แสดง permissions */}
                        {permissionsLoading ? (
                            <Box>
                                <Skeleton variant="text" width="30%" height={28} />
                                <Skeleton variant="rounded" height={120} />
                                <Skeleton variant="rounded" height={120} sx={{ mt: 2 }} />
                            </Box>
                        ) : (
                            <>
                                {/* ถ้าจะเอา system กลับมา ก็ uncomment ได้ */}
                                {/* <PermissionSection
                                title="System Permissions"
                                permissions={permissions.filter(p => p.type === "SYSTEM")}
                                checkedIds={permissionIds}
                                editable={canEditPermissions}
                                onToggle={togglePermission}
                            /> */}

                                <PermissionSection
                                    title="Team Permissions"
                                    permissions={permissions.filter(p => p.type === "TEAM")}
                                    checkedIds={permissionIds}
                                    editable={canEditPermissions}
                                    onToggle={togglePermission}
                                />
                            </>
                        )}

                        {/* ✅ ACTION BAR เดิมของคุณ */}
                        <Stack direction="row" spacing={1}>
                            {!editing ? (
                                <Button onClick={() => setEditing(true)} disabled={saving || deleting}>
                                    Edit
                                </Button>
                            ) : (
                                <>
                                    <Button
                                        onClick={() => {
                                            if (isNewDraft) {
                                                const prev = roles.find(r => r._id === prevSelectedRoleId) ?? null;
                                                setSelectedRole(prev);
                                                setEditing(false);
                                                setIsNewDraft(false);
                                                setPrevSelectedRoleId(null);
                                            } else {
                                                if (!selectedRole) return;
                                                setName(selectedRole.name ?? "");
                                                setPermissionIds(selectedRole.permission_id ?? []);
                                                setEditing(false);
                                            }
                                        }}
                                        disabled={saving || deleting}
                                    >
                                        {isNewDraft ? "Back" : "Cancel"}
                                    </Button>

                                    <Button variant="contained" disabled={!name.trim() || saving || deleting || permissionsLoading} onClick={handleSave}>
                                        {saving ? (isNewDraft ? "Creating..." : "Saving...") : isNewDraft ? "Create" : "Save"}
                                    </Button>
                                </>
                            )}

                            {/* ✅ Delete แสดงเฉพาะตอน !editing */}
                            {!editing && !isNewDraft && (
                                <Button color="error" onClick={() => setConfirmDeleteOpen(true)} disabled={saving || deleting || !selectedRole?._id}>
                                    Delete
                                </Button>
                            )}
                        </Stack>
                    </Stack>
                </Paper>
            )}
            {/* CONFIRM DELETE */}
            <Dialog open={confirmDeleteOpen} onClose={() => setConfirmDeleteOpen(false)} maxWidth="xs" fullWidth>
                <DialogTitle>Delete Role</DialogTitle>
                <DialogContent>
                    <Typography>
                        Are you sure you want to delete role <strong>{selectedRole?.name}</strong>?
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
                        This will not affect existing user permissions.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setConfirmDeleteOpen(false)} disabled={deleting}>
                        Cancel
                    </Button>
                    <Button
                        color="error"
                        variant="contained"
                        disabled={deleting}
                        onClick={async () => {
                            await handleDelete();
                            setConfirmDeleteOpen(false);
                        }}
                    >
                        {deleting ? "Deleting..." : "Delete"}
                    </Button>
                </DialogActions>
            </Dialog>
        </Stack>
    );
}

/* =========================================================
   TAB 2: USER PERMISSION (mock until API provided)
========================================================= */

function UserPermissionPanel({
    team,
    permissions,
    permissionsLoading,
    enabled
}: {
    team: { _id: string } | null;
    permissions: Permission[];
    permissionsLoading: boolean;
    enabled: boolean;
}) {
    const { instance } = useMsal();

    const [users, setUsers] = useState<User[]>([]);
    const [roles, setRoles] = useState<Role[]>([]);

    const [loadingUsers, setLoadingUsers] = useState(false);
    const [loadingRoles, setLoadingRoles] = useState(false);

    const [searchUser, setSearchUser] = useState("");
    const [selectedUser, setSelectedUser] = useState<User | null>(null);

    // ✅ permission ของ user (โหลดจาก API)
    const [loadingUserPerm, setLoadingUserPerm] = useState(false);
    const [savedPermissions, setSavedPermissions] = useState<string[]>([]);
    const [editingPermissions, setEditingPermissions] = useState<string[]>([]);
    const [editing, setEditing] = useState(false);

    const [roleId, setRoleId] = useState("");
    const [saving, setSaving] = useState(false);

    const { showNotification } = useNotification();
    /* =========================
       LOAD USERS BY TEAM
       POST /get_team_users
    ========================= */
    useEffect(() => {
        const loadTeamUsers = async () => {
            // ✅ ป้องกัน: ยังไม่เข้า tab user permission ก็ไม่โหลด
            if (!enabled) return;

            // ✅ ป้องกัน: team ยังไม่พร้อม
            if (!team?._id) return;

            try {
                setLoadingUsers(true);
                const token = await getToken(instance);
                if (!token) return;

                const result = await get_team_users(team._id, token);
                const rawList = result?.user ?? result?.users ?? [];

                const list: User[] = (rawList ?? []).map((u: any) => {
                    // name = "Cha Ti" → split เป็น first/last ให้เข้าหน้าคุณ
                    const full = (u?.name ?? "").trim();
                    const parts = full.split(" ").filter(Boolean);

                    const first_name = parts[0] ?? "-";
                    const last_name = parts.slice(1).join(" ") ?? "";

                    return {
                        _id: u?._id ?? "",
                        active: true, // backend ไม่ได้ส่งมา → default
                        ad_email: u?.email ?? "",
                        email: u?.email ?? "",
                        employee_id: "", // backend ไม่ได้ส่งมา → default
                        first_name,
                        last_name,
                        is_sys_admin: false // backend ไม่ได้ส่งมา → default
                    } as User;
                });

                setUsers(list);

                // ✅ เลือก user ตัวแรกเสมอ
                setSelectedUser(null);
            } catch (err) {
                console.error("load team users failed:", err);
                setUsers([]);
                setSelectedUser(null);
            } finally {
                setLoadingUsers(false);
            }
        };

        loadTeamUsers();
    }, [enabled, team?._id, instance]);

    /* =========================
       LOAD ROLES PRESET
       POST /get_roles_by_team
    ========================= */
    useEffect(() => {
        const loadRoles = async () => {
            if (!enabled) return;
            if (!team?._id) return;

            try {
                setLoadingRoles(true);
                const token = await getToken(instance);
                if (!token) return;

                const list = await get_roles_by_team(team._id, token);
                setRoles(list ?? []);
            } catch (err) {
                console.error("load roles preset failed:", err);
                setRoles([]);
            } finally {
                setLoadingRoles(false);
            }
        };

        loadRoles();
    }, [enabled, team?._id, instance]);

    /* =========================
       LOAD USER PERMISSIONS
       POST /get_user_permissions
       whenever selected user change
    ========================= */
    useEffect(() => {
        const loadUserPermission = async () => {
            if (!enabled) return;
            if (!selectedUser?._id) return;

            try {
                setLoadingUserPerm(true);

                const token = await getToken(instance);
                if (!token) return;

                const userPerm = await get_user_permissions(selectedUser._id, team?._id ?? null, token);

                const permissionIds: string[] = Array.isArray(userPerm) && userPerm.length > 0 ? (userPerm[0].permission_id ?? []) : [];

                setSavedPermissions(permissionIds);
                setEditingPermissions(permissionIds);
                setEditing(false);
                setRoleId("");
            } catch (err) {
                console.error("load user permission failed:", err);
                setSavedPermissions([]);
                setEditingPermissions([]);
                setEditing(false);
                setRoleId("");
            } finally {
                setLoadingUserPerm(false);
            }
        };

        loadUserPermission();
    }, [enabled, selectedUser?._id, team?._id, instance]);

    /* =========================
       ROLE PRESET -> COPY PERMISSIONS
    ========================= */
    useEffect(() => {
        if (!roleId) return;

        const role = roles.find(r => r._id === roleId);
        if (!role) return;

        setEditingPermissions(role.permission_id ?? []);
        setEditing(true);
    }, [roleId, roles]);

    /* =========================
       ACTIONS
    ========================= */
    const togglePermission = (id: string) => {
        if (!editing) return;
        setEditingPermissions(prev => (prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]));
    };

    const startEdit = () => {
        setEditingPermissions(savedPermissions);
        setEditing(true);
    };

    const cancelEdit = () => {
        setEditingPermissions(savedPermissions);
        setEditing(false);
        setRoleId("");
    };

    const savePermission = async () => {
        if (!selectedUser?._id || !team?._id) return;

        try {
            setSaving(true);

            const token = await getToken(instance);
            if (!token) return;

            const isSysAdmin = !!selectedUser.is_sys_admin;

            // ✅ filter เฉพาะ TEAM permissions เท่านั้น
            const teamPermIdSet = new Set(
                permissions
                    .filter(p => p.type === "TEAM")
                    .map(p => p._id)
                    .filter(Boolean) as string[]
            );

            const payloadPermissionIds = editingPermissions.filter(id => teamPermIdSet.has(id));

            const updated = await create_edit_user_permissions(selectedUser._id, team._id, payloadPermissionIds, isSysAdmin, token);

            const updatedIds: string[] = updated?.permission_id ?? payloadPermissionIds;

            setSavedPermissions(updatedIds);
            setEditingPermissions(updatedIds);
            setEditing(false);
            setRoleId("");
            showNotification("User permissions saved successfully");
        } catch (err) {
            console.error("save user permission failed:", err);
            showNotification("Failed to save user permissions", "error");
        } finally {
            setSaving(false);
        }
    };

    /* =========================
       FILTER USER
    ========================= */
    const filteredUsers = useMemo(() => {
        const q = searchUser.trim().toLowerCase();
        if (!q) return users;

        return users.filter(u => {
            const fullName = `${u.first_name ?? ""} ${u.last_name ?? ""}`.toLowerCase();
            const email = (u.email ?? "").toLowerCase();
            const emp = (u.employee_id ?? "").toLowerCase();
            return fullName.includes(q) || email.includes(q) || emp.includes(q);
        });
    }, [users, searchUser]);

    const busy = loadingUsers || loadingRoles || permissionsLoading || loadingUserPerm || saving;
    const isUserSelected = !!selectedUser;

    return (
        <Stack direction="row" spacing={2}>
            {/* USER LIST */}
            <Paper
                variant="outlined"
                sx={{
                    width: isUserSelected ? 320 : "100%",
                    p: 2,
                    borderRadius: 2,
                    transition: "width 200ms ease"
                }}
            >
                {/* Header */}
                <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Box>
                        <Typography fontWeight={700}>Users</Typography>
                        <Typography variant="caption" color="text.secondary">
                            {users.length} user(s)
                        </Typography>
                    </Box>
                </Box>

                <Divider sx={{ my: 2 }} />

                <TextField
                    size="small"
                    placeholder="Search user..."
                    value={searchUser}
                    onChange={e => setSearchUser(e.target.value)}
                    disabled={busy}
                    fullWidth
                    sx={{ mb: 1.5 }}
                />

                <Box sx={{ maxHeight: 520, overflowY: "auto", pr: 0.5 }}>
                    {loadingUsers ? (
                        <Stack spacing={1}>
                            {Array.from({ length: 10 }).map((_, i) => (
                                <Skeleton key={i} variant="rounded" height={60} />
                            ))}
                        </Stack>
                    ) : filteredUsers.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">
                            No users found
                        </Typography>
                    ) : (
                        <Stack spacing={1}>
                            {filteredUsers.map(u => {
                                const isSelected = selectedUser?._id === u._id;
                                const fullName = `${u.first_name ?? ""} ${u.last_name ?? ""}`.trim();

                                return (
                                    <Paper
                                        key={u._id}
                                        variant="outlined"
                                        onClick={() => {
                                            if (busy) return;
                                            setSelectedUser(u);
                                        }}
                                        sx={{
                                            p: 1.2,
                                            borderRadius: 2,
                                            cursor: busy ? "default" : "pointer",
                                            bgcolor: isSelected ? "action.selected" : "background.paper",
                                            "&:hover": { bgcolor: "action.hover" }
                                        }}
                                    >
                                        <Typography fontWeight={700} sx={{ lineHeight: 1.2 }}>
                                            {fullName || "-"}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {u.email ?? "-"}
                                        </Typography>
                                    </Paper>
                                );
                            })}
                        </Stack>
                    )}
                </Box>
            </Paper>

            {/* PERMISSION DETAIL (แสดงเมื่อเลือก user แล้วเท่านั้น) */}
            {selectedUser && (
                <Paper variant="outlined" sx={{ flex: 1, p: 2, borderRadius: 2 }}>
                    {/* Header */}
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                        <Typography fontWeight={700}>User Permission</Typography>

                        {!editing && (
                            <Button
                                onClick={() => {
                                    setSelectedUser(null);
                                    setEditing(false);
                                    setRoleId("");
                                }}
                                disabled={busy}
                            >
                                Back
                            </Button>
                        )}
                    </Box>

                    <Stack spacing={2}>
                        {/* User info */}
                        <Box>
                            <Typography fontWeight={700}>User: {`${selectedUser.first_name ?? ""} ${selectedUser.last_name ?? ""}`.trim()}</Typography>
                            <Typography variant="caption" color="text.secondary">
                                {selectedUser.email ?? "-"}
                            </Typography>
                        </Box>

                        {/* ROLE PRESET */}
                        <Box>
                            <Typography variant="subtitle2">Role Preset</Typography>
                            <Select fullWidth disabled={!editing || busy} value={roleId} onChange={e => setRoleId(e.target.value)}>
                                <MenuItem value="">Custom</MenuItem>

                                {loadingRoles ? (
                                    <MenuItem value="__loading" disabled>
                                        Loading roles...
                                    </MenuItem>
                                ) : (
                                    roles.map(r => (
                                        <MenuItem key={r._id} value={r._id}>
                                            {r.name}
                                        </MenuItem>
                                    ))
                                )}
                            </Select>
                        </Box>

                        {/* PERMISSIONS */}
                        {permissionsLoading || loadingUserPerm ? (
                            <Box>
                                <Skeleton variant="rounded" height={160} />
                            </Box>
                        ) : (
                            <PermissionSection
                                title="Team Permissions"
                                permissions={permissions.filter(p => p.type === "TEAM")}
                                checkedIds={editingPermissions}
                                editable={editing && !busy}
                                onToggle={togglePermission}
                            />
                        )}

                        {/* ACTION */}
                        <Box display="flex" justifyContent="flex-end" gap={1}>
                            {!editing ? (
                                <Button onClick={startEdit} disabled={busy}>
                                    Edit Permission
                                </Button>
                            ) : (
                                <>
                                    <Button onClick={cancelEdit} disabled={busy}>
                                        Cancel
                                    </Button>
                                    <Button variant="contained" onClick={savePermission} disabled={busy}>
                                        {saving ? "Saving..." : "Save Permission"}
                                    </Button>
                                </>
                            )}
                        </Box>
                    </Stack>
                </Paper>
            )}
        </Stack>
    );
}

/* =========================================================
   SHARED
========================================================= */

function PermissionSection({
    title,
    permissions,
    checkedIds,
    editable,
    onToggle
}: {
    title: string;
    permissions: Permission[];
    checkedIds: string[];
    editable: boolean;
    onToggle: (id: string) => void;
}) {
    return (
        <Box mt={2}>
            <Typography variant="subtitle2">{title}</Typography>

            {permissions.map(p => (
                <Box key={p._id}>
                    <Checkbox checked={!!p._id && checkedIds.includes(p._id)} disabled={!editable || !p._id} onChange={() => p._id && onToggle(p._id)} />
                    {p.name}
                </Box>
            ))}
        </Box>
    );
}
