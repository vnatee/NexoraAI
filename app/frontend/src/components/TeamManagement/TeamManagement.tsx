import React, { useEffect, useState, ChangeEvent, useMemo } from "react";
import {
    Box,
    TextField,
    CircularProgress,
    Snackbar,
    Alert,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button as ButtonMUI,
    Typography,
    Autocomplete,
    Chip,
    Divider,
    Stack
} from "@mui/material";
import { DataGrid, GridColDef, GridActionsCellItem } from "@mui/x-data-grid";
import AddIcon from "@mui/icons-material/Add";
import VisibilityIcon from "@mui/icons-material/Visibility";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import GroupIcon from "@mui/icons-material/Group";
import { TeamViewDialog } from "../TeamViewDialog/TeamViewDialog";
import { create_team, delete_team, edit_team_name, get_all_users, get_team_users, get_teams, insert_team_users, Team, TeamProfile, User, delete_team_user } from "../../api";
import { useMsal } from "@azure/msal-react";
import { getToken } from "../../authConfig";
import { useNotification } from "../../utill/NotificationProvider";

/* =========================
   TYPES (ของเดิมคุณ)
========================= */

export interface Agent {
    _id: string;
    agent_name: string;
    prompt: Record<string, any>;
    conf: Record<string, any>;
}

export interface DataGroup {
    _id: string;
    name: string;
    user_id?: string[];
}

export interface DataGroupWithUsers extends DataGroup {
    users: User[];
}

/* =========================
   MOCK MASTER DATA
========================= */

export const mockUsers: Record<string, User> = Object.fromEntries(
    Array.from({ length: 8 }).map((_, i) => {
        const id = `user-0${i + 1}`;
        return [
            id,
            {
                _id: id,
                email: `user${i + 1}@company.com`,
                ad_email: `user${i + 1}@ad.company.com`,
                first_name: `User`,
                last_name: `${i + 1}`,
                employee_id: `EMP00${i + 1}`,
                active: i % 2 === 0
            }
        ];
    })
);

export const mockAgents: Record<string, Agent> = Object.fromEntries(
    Array.from({ length: 8 }).map((_, i) => {
        const id = `agent-0${i + 1}`;
        return [
            id,
            {
                _id: id,
                agent_name: `Agent ${i + 1}`,
                prompt: { role: "assistant", version: i + 1 },
                conf: { temperature: 0.7 }
            }
        ];
    })
);

export const mockDataGroups: Record<string, DataGroup> = Object.fromEntries(
    Array.from({ length: 8 }).map((_, i) => {
        const id = `dg-0${i + 1}`;
        return [
            id,
            {
                _id: id,
                name: `Data Group ${i + 1}`,
                user_id: Object.keys(mockUsers).slice(i, i + 3) // group ละ ~3 คน
            }
        ];
    })
);

/* =========================
   COMPONENT
========================= */

interface TeamManagementProps {
    onTeamCreated?: (team: TeamProfile) => void;
}

export const TeamManagement: React.FC<TeamManagementProps> = ({ onTeamCreated }) => {
    const { instance: msalInstance } = useMsal();
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [openSuccess, setOpenSuccess] = useState(false);
    const [openError, setOpenError] = useState(false);
    const [message, setMessage] = useState("");
    const [openView, setOpenView] = useState(false);
    const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
    const [openNew, setOpenNew] = useState(false);
    const [openEdit, setOpenEdit] = useState(false);
    const [openDelete, setOpenDelete] = useState(false);
    const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
    const [selectedTeamUser, setSelectedTeamUser] = useState<Team | null>(null);
    const { showNotification } = useNotification();
    const [teamName, setTeamName] = useState("");
    const [openMembers, setOpenMembers] = useState(false);
    const [selectedUsers, setSelectedUsers] = useState<User[]>([]);
    const [teams, setTeams] = useState<Team[]>([]);
    const [memberSearch, setMemberSearch] = useState("");
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [confirmTitle, setConfirmTitle] = useState("");
    const [confirmMessage, setConfirmMessage] = useState("");
    const [onConfirm, setOnConfirm] = useState<(() => void) | null>(null);
    const [users, setUsers] = useState<User[]>([]);
    const [adding, setAdding] = useState(false);
    const [teamUsers, setTeamUsers] = useState<User[]>([]);
    const [loadingMembers, setLoadingMembers] = useState(false);
    const [confirmRemoveOpen, setConfirmRemoveOpen] = useState(false);
    const [removeUserId, setRemoveUserId] = useState<string | null>(null);
    const [removeUserName, setRemoveUserName] = useState("");
    const [removingUserId, setRemovingUserId] = useState<string | null>(null);
    const [creating, setCreating] = useState(false);
    const [editing, setEditing] = useState(false);
    const [deleting, setDeleting] = useState(false);

    const availableUsers = useMemo(() => {
        const memberSet = new Set(teamUsers.map(u => u._id));
        return users.filter(u => !memberSet.has(u._id));
    }, [users, teamUsers]);

    /* =========================
       DEBOUNCE SEARCH
    ========================= */

    useEffect(() => {
        const t = setTimeout(() => setDebouncedSearch(search), 300);
        return () => clearTimeout(t);
    }, [search]);

    useEffect(() => {
        if (!openMembers) {
            setMemberSearch("");
            setSelectedUsers([]);
        }
    }, [openMembers]);
    /* =========================
       FILTER TEAMS (ใช้ mock เดิม)
    ========================= */

    const filteredTeams = teams.filter(team => team.name.toLowerCase().includes(debouncedSearch.toLowerCase()));
    /* =========================
       FILTER Members (ใช้ mock เดิม)
    ========================= */
    const userMap = useMemo(() => {
        return Object.fromEntries(users.map(u => [u._id, u]));
    }, [users]);

    const teamUserMap = useMemo(() => {
        return Object.fromEntries(teamUsers.map(u => [u._id, u]));
    }, [teamUsers]);

    const filteredMemberIds = useMemo(() => {
        const keyword = memberSearch.toLowerCase();

        return teamUsers
            .filter(u => u.first_name.toLowerCase().includes(keyword) || u.last_name.toLowerCase().includes(keyword) || u.email.toLowerCase().includes(keyword))
            .map(u => u._id);
    }, [teamUsers, memberSearch]);

    /* =========================
       GRID COLUMNS
    ========================= */

    const teamColumns: GridColDef<Team>[] = [
        { field: "name", headerName: "Team Name", flex: 1, minWidth: 200 },
        {
            field: "data_group_id",
            headerName: "Data Groups",
            width: 130,
            valueGetter: (_, row) => row.data_group_id.length
        },
        {
            field: "agent_id",
            headerName: "Agents",
            width: 100,
            valueGetter: (_, row) => row.agent_id.length
        },
        {
            field: "user_id",
            headerName: "Users",
            width: 100,
            valueGetter: (_, row) => row.user_id.length
        },
        {
            field: "waiting_approve",
            headerName: "Waiting",
            width: 120,
            valueGetter: (_, row) => row.waiting_approve.length
        },
        {
            field: "actions",
            type: "actions",
            width: 160,
            getActions: params => [
                <GridActionsCellItem
                    icon={<VisibilityIcon />}
                    label="View"
                    onClick={() => {
                        setSelectedTeamId(params.row._id);
                        setOpenView(true);
                        setTeamName(params.row.name);
                    }}
                />,
                <GridActionsCellItem
                    icon={<EditIcon />}
                    label="Edit"
                    onClick={() => {
                        setSelectedTeamId(params.row._id);
                        setSelectedTeam(params.row);
                        setTeamName(params.row.name);
                        setOpenEdit(true);
                    }}
                />,
                <GridActionsCellItem
                    icon={<GroupIcon />}
                    label="Manage Members"
                    onClick={() => {
                        setSelectedTeamUser(params.row);
                        setOpenMembers(true);
                    }}
                />,

                <GridActionsCellItem
                    icon={<DeleteIcon />}
                    label="Delete"
                    onClick={() => {
                        setSelectedTeamId(params.row._id);
                        setOpenDelete(true);
                    }}
                />
            ]
        }
    ];

    const fetchTeamUsers = async (teamId: string) => {
        try {
            setLoadingMembers(true);

            const token = await getToken(msalInstance);
            if (!token) return;

            const res = await get_team_users(teamId, token);

            const mappedUsers: User[] = (res.user ?? []).map((u: any) => {
                const [first_name, ...rest] = (u.name ?? "").split(" ");

                return {
                    _id: u._id,
                    email: u.email,
                    first_name: first_name ?? "",
                    last_name: rest.join(" "),
                    employee_id: "",
                    ad_email: "",
                    active: true
                };
            });

            setTeamUsers(mappedUsers);
        } catch (err) {
            console.error("Failed to fetch team users:", err);
        } finally {
            setLoadingMembers(false);
        }
    };

    const handleAddMembers = async () => {
        if (!selectedTeamUser || selectedUsers.length === 0) return;

        try {
            setAdding(true);

            const token = await getToken(msalInstance);
            if (!token) {
                console.warn("No token while adding team members");
                return;
            }

            const userIds = selectedUsers.map(u => u._id);

            // 🔥 CALL API
            await insert_team_users(selectedTeamUser._id, userIds, token);

            // ✅ UPDATE UI (optimistic แต่ปลอดภัย)
            setSelectedTeamUser(prev => {
                if (!prev) return prev;

                const updated = {
                    ...prev,
                    user_id: [...new Set([...prev.user_id, ...userIds])]
                };

                setTeams(ts => ts.map(t => (t._id === updated._id ? updated : t)));
                return updated;
            });

            await fetchAllTeam();

            // เคลียร์ selection
            setSelectedUsers([]);
            setOpenMembers(false);
            showNotification("Members added successfully", "success");
        } catch (err) {
            console.error("Failed to add members:", err);
            setOpenError(true);
            showNotification("Failed to add members", "error");
        } finally {
            setAdding(false);
        }
    };

    const handleNewTeam = async () => {
        try {
            setCreating(true);
            const token = await getToken(msalInstance);
            if (!token) {
                console.warn("Token expired → force logout");
                localStorage.clear();
                return;
            }
            const response = await create_team(teamName, token);
            await fetchAllTeam();
            if (response?.team?._id) {
                onTeamCreated?.(response.team as TeamProfile);
            }
            setOpenNew(false);
            setOpenSuccess(true);
            showNotification("Team created successfully", "success");
        } catch (error) {
            console.error("Failed to create team:", error);
            setOpenError(true);
            showNotification("Failed to create team", "error");
        } finally {
            setCreating(false); // 🔥 จบ create
        }
    };

    const handleEditTeamName = async () => {
        try {
            if (!selectedTeamId) return;

            setEditing(true); // 🔥 เริ่ม edit

            const token = await getToken(msalInstance);
            if (!token) {
                localStorage.clear();
                return;
            }

            await edit_team_name(selectedTeamId, teamName, token);
            await fetchAllTeam();

            setOpenEdit(false);
            showNotification("Team edited successfully", "success");
        } catch (error) {
            console.error("Failed to edit team:", error);
            showNotification("Failed to edit team", "error");
        } finally {
            setEditing(false); // 🔥 จบ edit
        }
    };

    const handleDeleteTeam = async () => {
        try {
            const token = await getToken(msalInstance);
            if (!token) {
                console.warn("Token expired → force logout");
                localStorage.clear();
                return;
            }
            await delete_team(selectedTeamId!, token).then(() => {
                setOpenSuccess(true);
                showNotification("Team deleted successfully", "success");
            });
            await fetchAllTeam();
            setOpenNew(false);
        } catch (error) {
            console.error("Failed to deleted team:", error);
            setOpenError(true);
            showNotification("Failed to deleted team", "error");
        } finally {
            setOpenDelete(false);
            setDeleting(false);
        }
    };
    const handleDeleteTeamUser = async () => {
        try {
            if (!selectedTeamUser || !removeUserId) return;

            setRemovingUserId(removeUserId); // 🔥 บอกว่า user นี้กำลังลบ

            const token = await getToken(msalInstance);
            if (!token) {
                localStorage.clear();
                return;
            }

            await delete_team_user(selectedTeamUser._id, removeUserId, token);

            // ✅ update UI
            setTeamUsers(prev => prev.filter(u => u._id !== removeUserId));

            setSelectedTeam(prev =>
                prev
                    ? {
                          ...prev,
                          user_id: prev.user_id.filter(id => id !== removeUserId)
                      }
                    : prev
            );

            await fetchAllTeam();

            showNotification("Member removed successfully", "success");
        } catch (err) {
            console.error("Failed to remove team user:", err);
            showNotification("Failed to remove member", "error");
        } finally {
            setRemovingUserId(null); // 🔥 จบการลบ
            setConfirmRemoveOpen(false);
            setRemoveUserId(null);
        }
    };

    const fetchAllTeam = async () => {
        try {
            setLoading(true);

            const token = await getToken(msalInstance);
            if (!token) {
                console.warn("No token while persisting currentAgentConfig");
                return;
            }

            const teams = await get_teams(token);
            setTeams(teams.result);
        } catch (error) {
            console.error("Failed to fetch teams:", error);
            setOpenError(true);
            showNotification("Failed to load teams", "error");
        } finally {
            setLoading(false);
        }
    };

    const fetchAllUser = async () => {
        try {
            setLoading(true);

            const token = await getToken(msalInstance);
            if (!token) {
                console.warn("No token while persisting currentAgentConfig");
                return;
            }

            const users = await get_all_users(token);
            setUsers(users.result);
        } catch (error) {
            console.error("Failed to fetch users:", error);
            setOpenError(true);
            showNotification("Failed to load users", "error");
        } finally {
            setLoading(false);
        }
    };

    const openConfirmRemoveUser = (user: User) => {
        setRemoveUserId(user._id);
        setRemoveUserName(`${user.first_name} ${user.last_name}`);
        setConfirmRemoveOpen(true);
    };

    useEffect(() => {
        fetchAllTeam();
    }, []);

    useEffect(() => {
        if (openMembers) {
            fetchTeamUsers(selectedTeamUser?._id!);
            fetchAllUser(); // สำหรับ Add Members
        }
    }, [openMembers]);

    /* =========================
       RENDER
    ========================= */

    return (
        <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
                Team Management
            </Typography>

            <Box
                sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    mb: 2
                }}
            >
                <TextField size="small" placeholder="Search Team" value={search} onChange={e => setSearch(e.target.value)} sx={{ width: 260 }} />

                <ButtonMUI
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={() => {
                        setTeamName("");
                        setOpenNew(true);
                    }}
                >
                    New Team
                </ButtonMUI>
            </Box>

            <Box sx={{ flex: 1 }}>
                {loading ? (
                    <Box sx={{ display: "flex", justifyContent: "center", mt: 4 }}>
                        <CircularProgress />
                    </Box>
                ) : (
                    <DataGrid rows={filteredTeams} columns={teamColumns} getRowId={row => row._id} pageSizeOptions={[5, 10]} disableRowSelectionOnClick />
                )}
            </Box>

            {/* ===== VIEW TEAM ===== */}
            <TeamViewDialog open={openView} teamId={selectedTeamId} teamName={teamName} onClose={() => setOpenView(false)} />

            {/* ===== NEW TEAM ===== */}
            <Dialog open={openNew} onClose={() => setOpenNew(false)} maxWidth="xs" fullWidth>
                <DialogTitle>New Team</DialogTitle>
                <DialogContent>
                    <TextField autoFocus fullWidth placeholder="Team Name" value={teamName} onChange={e => setTeamName(e.target.value)} />
                </DialogContent>
                <DialogActions>
                    <ButtonMUI onClick={() => setOpenNew(false)} disabled={creating}>
                        Cancel
                    </ButtonMUI>
                    <ButtonMUI
                        variant="contained"
                        disabled={!teamName.trim() || creating}
                        onClick={handleNewTeam}
                        startIcon={creating ? <CircularProgress size={16} /> : null}
                    >
                        {creating ? "Creating..." : "Create"}
                    </ButtonMUI>
                </DialogActions>
            </Dialog>

            {/* ===== EDIT TEAM ===== */}
            <Dialog open={openEdit} onClose={() => setOpenEdit(false)} maxWidth="xs" fullWidth>
                <DialogTitle>Edit Team</DialogTitle>
                <DialogContent>
                    <TextField autoFocus fullWidth value={teamName} onChange={e => setTeamName(e.target.value)} />
                </DialogContent>
                <DialogActions>
                    <ButtonMUI onClick={() => setOpenEdit(false)}>Cancel</ButtonMUI>
                    <ButtonMUI
                        variant="contained"
                        disabled={!teamName.trim() || editing}
                        onClick={handleEditTeamName}
                        startIcon={editing ? <CircularProgress size={16} /> : null}
                    >
                        {editing ? "Saving..." : "Save"}
                    </ButtonMUI>
                </DialogActions>
            </Dialog>

            {/* ===== DELETE TEAM ===== */}
            <Dialog open={openDelete} onClose={() => setOpenDelete(false)} maxWidth="xs" fullWidth>
                <DialogTitle>Delete Team</DialogTitle>
                <DialogContent>
                    <Typography>
                        Are you sure you want to delete <b>{selectedTeam?.name}</b> ?
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <ButtonMUI onClick={() => setOpenDelete(false)} disabled={deleting}>
                        Cancel
                    </ButtonMUI>
                    <ButtonMUI
                        color="error"
                        variant="contained"
                        disabled={deleting}
                        onClick={() => {
                            setDeleting(true);
                            handleDeleteTeam();
                            // setOpenDelete(false);
                            setOpenSuccess(true);
                            setMessage("Team deleted");
                        }}
                    >
                        {deleting ? <CircularProgress size={16} /> : "Delete"}
                    </ButtonMUI>
                </DialogActions>
            </Dialog>

            <Dialog open={openMembers} onClose={() => setOpenMembers(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Manage Team Members</DialogTitle>

                <DialogContent dividers>
                    {/* ===== CURRENT MEMBERS ===== */}
                    <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        Current Members ({filteredMemberIds.length})
                    </Typography>

                    <TextField size="small" placeholder="Search member" value={memberSearch} onChange={e => setMemberSearch(e.target.value)} sx={{ mb: 1 }} />

                    <Box
                        sx={{
                            maxHeight: 240,
                            overflowY: "auto",
                            border: "1px solid",
                            borderColor: "divider",
                            borderRadius: 1
                        }}
                    >
                        {loadingMembers ? (
                            <Typography sx={{ p: 2 }}>Loading members...</Typography>
                        ) : filteredMemberIds.length === 0 ? (
                            <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                                No members found
                            </Typography>
                        ) : (
                            <Stack spacing={0}>
                                {filteredMemberIds.map(uid => {
                                    const user = teamUserMap[uid];
                                    if (!user) return null;

                                    return (
                                        <Box
                                            key={uid}
                                            sx={{
                                                display: "flex",
                                                alignItems: "center",
                                                justifyContent: "space-between",
                                                px: 1.5,
                                                py: 1,
                                                borderBottom: "1px solid",
                                                borderColor: "divider",
                                                "&:last-child": { borderBottom: "none" },

                                                // 🔥 เพิ่มตรงนี้
                                                opacity: removingUserId === uid ? 0.5 : 1,
                                                pointerEvents: removingUserId === uid ? "none" : "auto",
                                                transition: "opacity 0.2s ease"
                                            }}
                                        >
                                            <Box>
                                                <Typography variant="body2">
                                                    {user.first_name} {user.last_name}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    {user.email}
                                                </Typography>
                                            </Box>

                                            <ButtonMUI
                                                size="small"
                                                color="error"
                                                disabled={removingUserId === user._id}
                                                onClick={() => openConfirmRemoveUser(user)}
                                                startIcon={removingUserId === user._id ? <CircularProgress size={14} /> : null}
                                            >
                                                {removingUserId === user._id ? "Removing..." : "Remove"}
                                            </ButtonMUI>
                                        </Box>
                                    );
                                })}
                            </Stack>
                        )}
                    </Box>

                    <Divider sx={{ my: 2 }} />

                    {/* ===== ADD MEMBERS ===== */}
                    <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        Add Members
                    </Typography>

                    <Autocomplete
                        multiple
                        options={availableUsers}
                        value={selectedUsers}
                        onChange={(_, value) => setSelectedUsers(value)}
                        isOptionEqualToValue={(option, value) => option._id === value._id}
                        getOptionLabel={u => `${u.first_name} ${u.last_name}`}
                        loading={loading}
                        renderInput={params => (
                            <TextField
                                {...params}
                                placeholder="Select users"
                                InputProps={{
                                    ...params.InputProps,
                                    endAdornment: (
                                        <>
                                            {loading ? <CircularProgress size={18} /> : null}
                                            {params.InputProps.endAdornment}
                                        </>
                                    )
                                }}
                            />
                        )}
                    />
                </DialogContent>

                <DialogActions>
                    <ButtonMUI onClick={() => setOpenMembers(false)}>Done</ButtonMUI>

                    <ButtonMUI variant="contained" disabled={selectedUsers.length === 0 || adding} onClick={handleAddMembers}>
                        {adding ? "Adding..." : "Add Members"}
                    </ButtonMUI>
                </DialogActions>
            </Dialog>

            <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)} maxWidth="xs" fullWidth>
                <DialogTitle>{confirmTitle}</DialogTitle>

                <DialogContent>
                    <Typography>{confirmMessage}</Typography>
                </DialogContent>

                <DialogActions>
                    <ButtonMUI onClick={() => setConfirmOpen(false)}>Cancel</ButtonMUI>

                    <ButtonMUI
                        variant="contained"
                        color="error"
                        onClick={() => {
                            onConfirm?.();
                        }}
                    >
                        Confirm
                    </ButtonMUI>
                </DialogActions>
            </Dialog>

            <Dialog open={confirmRemoveOpen} onClose={() => setConfirmRemoveOpen(false)} maxWidth="xs" fullWidth>
                <DialogTitle>Remove Member</DialogTitle>

                <DialogContent>
                    <Typography>
                        Are you sure you want to remove <b>{removeUserName}</b> from this team?
                    </Typography>
                </DialogContent>

                <DialogActions>
                    <ButtonMUI onClick={() => setConfirmRemoveOpen(false)}>Cancel</ButtonMUI>

                    <ButtonMUI variant="contained" color="error" onClick={handleDeleteTeamUser}>
                        Remove
                    </ButtonMUI>
                </DialogActions>
            </Dialog>

            {/* ===== SNACKBAR ===== */}
            <Snackbar open={openSuccess} autoHideDuration={3000} onClose={() => setOpenSuccess(false)}>
                <Alert severity="success">{message}</Alert>
            </Snackbar>
            <Snackbar open={openError} autoHideDuration={3000} onClose={() => setOpenError(false)}>
                <Alert severity="error">{message}</Alert>
            </Snackbar>
        </Box>
    );
};
