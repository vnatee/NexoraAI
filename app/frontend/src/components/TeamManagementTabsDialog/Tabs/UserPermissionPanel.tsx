import React, { useState, useEffect } from "react";
import { Stack, Typography, Divider, Box, Paper, Button, TextField, Checkbox, Select, MenuItem, FormControlLabel, CircularProgress, Chip } from "@mui/material";
import { useMsal } from "@azure/msal-react";
import { get_all_users, get_teams, get_all_permission, get_user_permissions, create_edit_user_permissions, User, Team, Permission } from "../../../api";
import { getToken } from "../../../authConfig";
import { useNotification } from "../../../utill/NotificationProvider";

/* =========================================================
   USER PERMISSION PANEL (FINAL)
========================================================= */

export function UserPermissionPanel() {
    const { instance: msalInstance } = useMsal();
    const { showNotification } = useNotification();

    const [users, setUsers] = useState<User[]>([]);
    const [teams, setTeams] = useState<Team[]>([]);
    const [permissions, setPermissions] = useState<Permission[]>([]);
    const [loading, setLoading] = useState(false);

    const [searchUser, setSearchUser] = useState("");
    const [selectedUser, setSelectedUser] = useState<User | null>(null);

    const [isSystemAdmin, setIsSystemAdmin] = useState(false);
    const [selectedTeamId, setSelectedTeamId] = useState("");

    const [systemPermissions, setSystemPermissions] = useState<string[]>([]);
    const [teamPermissions, setTeamPermissions] = useState<string[]>([]);

    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);

    const getFullName = (u: User) => `${u.first_name ?? ""} ${u.last_name ?? ""}`.trim();

    /* =========================
       LOAD MASTER DATA
    ========================= */

    useEffect(() => {
        const loadData = async () => {
            try {
                setLoading(true);
                const token = await getToken(msalInstance);
                if (!token) return;

                const [userResp, teamResp, permResp] = await Promise.all([get_all_users(token), get_teams(token), get_all_permission(token)]);

                setUsers(Array.isArray(userResp?.result) ? userResp.result : Array.isArray(userResp) ? userResp : []);

                setTeams(Array.isArray(teamResp?.result) ? teamResp.result : Array.isArray(teamResp) ? teamResp : []);

                setPermissions(Array.isArray(permResp) ? permResp : []);
            } finally {
                setLoading(false);
            }
        };

        loadData();
    }, []);

    /* =========================
       WHEN SELECT USER
    ========================= */

    useEffect(() => {
        if (!selectedUser) return;

        const loadSystemPermissions = async () => {
            const token = await getToken(msalInstance);
            if (!token) return;

            setIsSystemAdmin(!!selectedUser.is_sys_admin);
            setSelectedTeamId("");
            setTeamPermissions([]);
            setEditing(false);

            const resp = await get_user_permissions(selectedUser._id, null, token);

            setSystemPermissions(Array.isArray(resp) && resp.length > 0 ? (resp[0].permission_id ?? []) : []);
        };

        loadSystemPermissions();
    }, [selectedUser]);

    /* =========================
       WHEN SELECT TEAM
    ========================= */

    useEffect(() => {
        if (!selectedUser || !selectedTeamId) return;

        const loadTeamPermissions = async () => {
            const token = await getToken(msalInstance);
            if (!token) return;

            const resp = await get_user_permissions(selectedUser._id, selectedTeamId, token);

            setTeamPermissions(Array.isArray(resp) && resp.length > 0 ? (resp[0].permission_id ?? []) : []);
        };

        loadTeamPermissions();
    }, [selectedTeamId]);

    /* =========================
       HANDLERS
    ========================= */

    const togglePermission = (list: string[], setList: React.Dispatch<React.SetStateAction<string[]>>, id: string) => {
        setList(prev => (prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]));
    };

    const savePermissions = async (mode: "SYSTEM" | "TEAM" | "ADMIN") => {
        if (!selectedUser) return;

        try {
            setSaving(true);
            const token = await getToken(msalInstance);
            if (!token) return;

            if (mode === "ADMIN") {
                await create_edit_user_permissions(selectedUser._id, null, null, true, token);
            }

            if (mode === "SYSTEM") {
                await create_edit_user_permissions(selectedUser._id, null, systemPermissions, false, token);
            }

            if (mode === "TEAM") {
                await create_edit_user_permissions(selectedUser._id, selectedTeamId, teamPermissions, false, token);
            }
            showNotification("Permissions saved successfully", "success");
            setEditing(false);
        } catch (err) {
            showNotification("Failed to save permissions", "error");
        } finally {
            setSaving(false);
        }
    };

    /* =========================
       SEARCH
    ========================= */

    const filteredUsers = users.filter(u => getFullName(u).toLowerCase().includes(searchUser.toLowerCase()));

    /* =========================
       RENDER
    ========================= */

    return (
        <Stack spacing={2}>
            <Typography variant="h6">User Permission</Typography>

            <Stack direction="row" spacing={2}>
                {/* USER LIST */}
                <Paper
                    sx={{
                        p: 2,
                        width: selectedUser ? 280 : "100%",
                        transition: "width 0.2s ease"
                    }}
                >
                    {loading ? (
                        <Box sx={{ display: "flex", justifyContent: "center", mt: 4 }}>
                            <CircularProgress />
                        </Box>
                    ) : (
                        <>
                            <TextField size="small" placeholder="Search user" value={searchUser} onChange={e => setSearchUser(e.target.value)} />

                            <Box sx={{ mt: 1, display: "flex", flexDirection: "column", gap: 1 }}>
                                {filteredUsers.map(u => (
                                    <Paper
                                        key={u._id}
                                        onClick={() => setSelectedUser(u)}
                                        elevation={0}
                                        sx={{
                                            p: 2,
                                            border: "1px solid",
                                            borderColor: selectedUser?._id === u._id ? "primary.main" : "divider",
                                            cursor: "pointer",
                                            display: "flex",
                                            justifyContent: "space-between"
                                        }}
                                    >
                                        <Box>
                                            <Typography fontWeight={500}>{getFullName(u)}</Typography>
                                            <Typography variant="body2" color="text.secondary">
                                                {u.employee_id}
                                            </Typography>
                                        </Box>
                                        <Chip
                                            label={u.active ? "Active" : "Inactive"}
                                            size="small"
                                            variant="outlined"
                                            sx={{
                                                fontWeight: 500,
                                                borderColor: u.active ? "success.main" : "grey.400",
                                                color: u.active ? "success.main" : "text.secondary",
                                                height: 22
                                            }}
                                        />
                                    </Paper>
                                ))}
                            </Box>
                        </>
                    )}
                </Paper>

                {/* DETAIL */}
                {selectedUser && (
                    <Paper
                        sx={{
                            flex: 1,
                            p: 2,
                            opacity: saving ? 0.6 : 1,
                            pointerEvents: saving ? "none" : "auto",
                            transition: "opacity 0.2s ease"
                        }}
                    >
                        <Stack spacing={3}>
                            {/* HEADER */}
                            <Box
                                sx={{
                                    display: "grid",
                                    gridTemplateColumns: "auto 1fr auto",
                                    alignItems: "center"
                                }}
                            >
                                <Button onClick={() => setSelectedUser(null)} size="small">
                                    ← Back
                                </Button>

                                <Typography variant="h6" sx={{ textAlign: "center", fontWeight: 600 }}>
                                    {getFullName(selectedUser)}
                                </Typography>

                                <Box />
                            </Box>

                            <Divider />

                            {!editing && (
                                <Box display="flex" justifyContent="flex-end">
                                    <Button variant="outlined" disabled={saving} onClick={() => setEditing(true)}>
                                        Edit Permissions
                                    </Button>
                                </Box>
                            )}

                            {/* SYSTEM ADMIN */}
                            <FormControlLabel
                                control={<Checkbox checked={isSystemAdmin} disabled={!editing} onChange={e => setIsSystemAdmin(e.target.checked)} />}
                                label="System Admin"
                            />

                            {/* SYSTEM PERMISSIONS */}
                            <PermissionSection
                                title="System Permissions"
                                permissions={permissions.filter(p => p.type === "System Permissions")}
                                checkedIds={systemPermissions}
                                editable={editing && !isSystemAdmin}
                                onToggle={id => togglePermission(systemPermissions, setSystemPermissions, id)}
                            />

                            {/* TEAM */}
                            <Box>
                                <Typography variant="subtitle2">Team</Typography>
                                <Select fullWidth disabled={!editing || isSystemAdmin} value={selectedTeamId} onChange={e => setSelectedTeamId(e.target.value)}>
                                    <MenuItem value="">Select team</MenuItem>
                                    {teams.map(t => (
                                        <MenuItem key={t._id} value={t._id}>
                                            {t.name}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </Box>

                            <PermissionSection
                                title="Team Permissions"
                                permissions={permissions.filter(p => p.type === "Team Permissions")}
                                checkedIds={teamPermissions}
                                editable={editing && !isSystemAdmin && !!selectedTeamId}
                                onToggle={id => togglePermission(teamPermissions, setTeamPermissions, id)}
                            />

                            {/* SAVE */}
                            {editing && (
                                <Box display="flex" justifyContent="flex-end" gap={1}>
                                    {isSystemAdmin ? (
                                        <Button
                                            variant="contained"
                                            disabled={saving}
                                            onClick={() => savePermissions("ADMIN")}
                                            startIcon={saving ? <CircularProgress size={16} /> : null}
                                        >
                                            {saving ? "Saving..." : "Save"}
                                        </Button>
                                    ) : (
                                        <>
                                            <Button variant="contained" disabled={saving} onClick={() => savePermissions("SYSTEM")}>
                                                Save System Permission
                                            </Button>
                                            <Button variant="contained" disabled={saving || !selectedTeamId} onClick={() => savePermissions("TEAM")}>
                                                Save Team Permission
                                            </Button>
                                        </>
                                    )}
                                </Box>
                            )}
                        </Stack>
                    </Paper>
                )}
            </Stack>
        </Stack>
    );
}

/* =========================
   SHARED
========================= */

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
        <Box>
            <Typography variant="subtitle2">{title}</Typography>
            {permissions.map(p => (
                <Box key={p._id}>
                    <Checkbox checked={checkedIds.includes(p._id!)} disabled={!editable} onChange={() => onToggle(p._id!)} />
                    {p.name}
                </Box>
            ))}
        </Box>
    );
}
