import React, { useEffect, useState, ChangeEvent } from "react";
import { Button } from "@fluentui/react-components";
import { Button as ButtonMUI, FormControl, FormHelperText, InputLabel } from "@mui/material";
import Skeleton from "@mui/material/Skeleton";

import {
    Box,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Snackbar,
    Alert,
    CircularProgress,
    Select,
    MenuItem,
    IconButton
} from "@mui/material";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import SaveIcon from "@mui/icons-material/Save";
import CancelIcon from "@mui/icons-material/Cancel";
import AddIcon from "@mui/icons-material/Add";
import { DataGrid, GridColDef, GridPaginationModel, GridRenderEditCellParams, GridRowModesModel, GridRowModes, GridRowEditStopReasons } from "@mui/x-data-grid";
import { useMsal } from "@azure/msal-react";
import { listUsersApi, listRolesApi, updateUserApi, deleteUserApi, createUserApi, listGroupsApi } from "../../api";
import { getToken } from "../../authConfig";
import { GroupDetail, RoleDetail, UserProfile } from "../../api/models";
import styles from "./UserManagement.module.css";
import ManageAccountsIcon from "@mui/icons-material/ManageAccounts";
import { Tooltip } from "@mui/material";
import { SelectChangeEvent } from "@mui/material/Select";
import { GroupManagement } from "../GroupManagement";
import { Tabs, Tab } from "@mui/material";
import { AgentConfiguration } from "../AgentConfiguration";

interface Props {
    disabled?: boolean;
    className?: string;
    dialogRef?: React.RefObject<HTMLDivElement>;
}

export const UserManagement: React.FC<Props> = ({ disabled, dialogRef, className }) => {
    const client = useMsal().instance;
    const [open, setOpen] = useState(false);
    const [users, setUsers] = useState<UserProfile[]>([]);
    const [roles, setRoles] = useState<RoleDetail[]>([]);
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState("");
    const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
        page: 0,
        pageSize: 5
    });
    const [rowModesModel, setRowModesModel] = useState<GridRowModesModel>({});
    const [openSuccess, setOpenSuccess] = useState(false);
    const [openWarn, setOpenWarn] = useState(false);
    const [openError, setOpenError] = useState(false);
    const [message, setMessage] = useState<string | null>(null);
    const [addOpen, setAddOpen] = useState(false);
    const [newUsername, setNewUsername] = useState("");
    const [groups, setGroups] = useState<GroupDetail[]>([]);
    const [newGroups, setNewGroups] = useState<GroupDetail[]>([]);
    const [allUsers, setAllUsers] = useState<UserProfile[]>([]);
    const [newRole, setNewRole] = useState<string | null>(null);
    const [creating, setCreating] = useState(false);
    const [teamsInput, setTeamsInput] = useState("");
    const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [userToDelete, setUserToDelete] = useState<string | null>(null);
    const [savingRowId, setSavingRowId] = useState<string | null>(null);
    const [tab, setTab] = useState(0);

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setTab(newValue);
    };

    // โหลด users
    const fetchUsers = async () => {
        try {
            setLoading(true);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            const userList: UserProfile[] = await listUsersApi(token);
            setAllUsers(userList);
            setUsers(userList);
        } catch (e) {
            console.error(e);
            setMessage("Failed to load users");
            setOpenError(true);
        } finally {
            setLoading(false);
        }
    };

    // โหลด roles
    const fetchRoles = async () => {
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            const roleList: RoleDetail[] = await listRolesApi(token);
            setRoles(roleList);
        } catch (e) {
            console.error(e);
            setMessage("Failed to load roles");
            setOpenError(true);
        }
    };

    const fetchGroups = async () => {
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            const groupList: GroupDetail[] = await listGroupsApi(token);
            setGroups(groupList);
        } catch (e) {
            console.error(e);
            setMessage("Failed to load groups");
            setOpenError(true);
        }
    };

    useEffect(() => {
        if (open) {
            fetchUsers();
            fetchRoles();
            fetchGroups();
        }
    }, [open]);

    useEffect(() => {
        if (!search) {
            setUsers(allUsers);
        } else {
            const lower = search.toLowerCase();
            setUsers(
                allUsers.filter(
                    u =>
                        u.name.toLowerCase().includes(lower) ||
                        u.groups?.some(g => g.name.toLowerCase().includes(lower)) ||
                        roles
                            .find(r => r._id === u.role_id)
                            ?.name.toLowerCase()
                            .includes(lower)
                )
            );
        }
    }, [search, allUsers, roles]);

    // อัปเดต user (inline save)
    const processRowUpdate = async (newRow: UserProfile, oldRow: UserProfile) => {
        setSavingRowId(newRow._id);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            const updated = await updateUserApi(newRow._id, newRow.name, token, newRow.groups, newRow.role_id);

            setMessage("User updated successfully");
            setOpenSuccess(true);
            setRowModesModel({
                ...rowModesModel,
                [newRow._id]: { mode: GridRowModes.View, ignoreModifications: true }
            });

            return { ...newRow };
        } catch (e) {
            console.error(e);
            setMessage("Failed to update user");
            setOpenError(true);

            return oldRow;
        } finally {
            setSavingRowId(null);
            fetchUsers();
            fetchRoles();
            fetchGroups();
        }
    };

    // ลบ user
    const handleDelete = async (userId: string) => {
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            await deleteUserApi(userId, token);
            setMessage("User deleted successfully");
            setOpenSuccess(true);
            fetchUsers();
        } catch (e) {
            console.error(e);
            setMessage("Failed to delete user");
            setOpenError(true);
        }
    };

    // cell editor ของ Role
    const RoleEditCell = (params: GridRenderEditCellParams) => (
        <Select
            disabled={savingRowId === params.id}
            value={params.value || ""}
            onChange={e => {
                params.api.setEditCellValue({
                    id: params.id,
                    field: params.field,
                    value: e.target.value
                });
            }}
            fullWidth
        >
            {roles.map(role => (
                <MenuItem key={role._id} value={role._id}>
                    {role.name}
                </MenuItem>
            ))}
        </Select>
    );

    const handleEditClick = (id: string) => {
        setRowModesModel({
            ...rowModesModel,
            [id]: { mode: GridRowModes.Edit }
        });
    };

    const handleSaveClick = (id: string) => {
        setRowModesModel(prev => ({
            ...prev,
            [id]: { mode: GridRowModes.View, ignoreModifications: false }
        }));
    };

    const handleCancelClick = (id: string) => {
        setRowModesModel({
            ...rowModesModel,
            [id]: { mode: GridRowModes.View, ignoreModifications: true }
        });
    };

    const GroupEditCell = (params: GridRenderEditCellParams) => {
        const handleChange = (e: SelectChangeEvent<string[]>) => {
            const selectedIds = e.target.value as string[];
            const selectedGroups = groups.filter(g => selectedIds.includes(g._id));

            params.api.setEditCellValue({
                id: params.id,
                field: params.field,
                value: selectedGroups
            });
        };

        return (
            <Select<string[]>
                disabled={savingRowId === params.id}
                multiple
                value={(params.value as GroupDetail[] | undefined)?.map(g => g._id) || []}
                onChange={handleChange}
                fullWidth
                renderValue={selected => {
                    const selectedIds = selected as string[];
                    return groups
                        .filter(g => selectedIds.includes(g._id))
                        .map(g => g.name)
                        .join(", ");
                }}
            >
                {groups.map(group => (
                    <MenuItem key={group._id} value={group._id}>
                        {group.name}
                    </MenuItem>
                ))}
            </Select>
        );
    };

    const columns: GridColDef<UserProfile>[] = [
        { field: "name", headerName: "Email", flex: 1, editable: true },
        {
            field: "groups",
            headerName: "Data Groups",
            flex: 1,
            editable: true,
            renderCell: params => {
                const text = params.row.groups?.map(g => g.name).join(", ") || "-";
                return (
                    <Tooltip title={text}>
                        <span
                            style={{
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                maxWidth: "100%"
                            }}
                        >
                            {text}
                        </span>
                    </Tooltip>
                );
            },
            renderEditCell: GroupEditCell
        },
        {
            field: "role_id",
            headerName: "Role",
            flex: 1,
            editable: true,
            renderEditCell: RoleEditCell,
            renderCell: params => roles.find(r => r._id === params.row.role_id)?.name || "-"
        },
        {
            field: "actions",
            headerName: "Actions",
            width: 120,
            sortable: false,
            filterable: false,
            renderCell: params => {
                const isInEditMode = rowModesModel[params.row._id]?.mode === GridRowModes.Edit;
                const isSaving = savingRowId === params.row._id;

                return (
                    <Box sx={{ position: "relative", width: "100%", display: "flex", justifyContent: "center", alignItems: "center" }}>
                        {/* ปุ่มปกติ */}
                        {isInEditMode ? (
                            <>
                                <IconButton color="primary" onClick={() => handleSaveClick(params.row._id)} disabled={isSaving}>
                                    <SaveIcon />
                                </IconButton>
                                <IconButton color="inherit" onClick={() => handleCancelClick(params.row._id)} disabled={isSaving}>
                                    <CancelIcon />
                                </IconButton>
                            </>
                        ) : (
                            <>
                                <IconButton color="primary" onClick={() => handleEditClick(params.row._id)} disabled={isSaving}>
                                    <EditIcon />
                                </IconButton>
                                <IconButton color="error" onClick={() => handleDeleteRequest(params.row._id)} disabled={isSaving}>
                                    <DeleteIcon />
                                </IconButton>
                            </>
                        )}

                        {/* Overlay Loading */}
                        {isSaving && (
                            <Box
                                sx={{
                                    position: "absolute",
                                    inset: 0,
                                    bgcolor: "rgba(255,255,255,0.6)",
                                    display: "flex",
                                    justifyContent: "center",
                                    alignItems: "center",
                                    borderRadius: 1,
                                    zIndex: 2
                                }}
                            >
                                <CircularProgress size={20} />
                            </Box>
                        )}
                    </Box>
                );
            }
        }
    ];

    const handleClose = () => {
        const resetRowModes: GridRowModesModel = {};
        users.forEach(user => {
            resetRowModes[user._id] = { mode: GridRowModes.View, ignoreModifications: true };
        });

        setRowModesModel(resetRowModes);

        setOpen(false);
        setSearch("");
        setUsers([]);
        setMessage(null);
        setOpenSuccess(false);
        setOpenError(false);
    };

    const handleCreateUser = async () => {
        setCreating(true);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            const response = await createUserApi(newUsername, token, newGroups, newRole);

            setMessage(response);

            if (response === "user already exists") {
                setOpenWarn(true);
            } else {
                setOpenSuccess(true);
            }

            setAddOpen(false);

            // reset form
            setNewUsername("");
            setNewGroups([]);
            setNewRole(null);

            fetchUsers();
        } catch (e: any) {
            // ✅ ถ้า backend มีข้อความ error ก็ใช้เลย
            if (e.response?.data) {
                setMessage(e.response.data);
            } else {
                setMessage("Failed to create user");
            }
            setOpenError(true);
        } finally {
            setCreating(false);
        }
    };

    const handleDeleteRequest = (userId: string) => {
        setUserToDelete(userId);
        setConfirmDeleteOpen(true);
    };

    const handleDeleteConfirm = async () => {
        if (!userToDelete) return;
        setDeleting(true);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            await deleteUserApi(userToDelete, token);
            setMessage("User deleted successfully");
            setOpenSuccess(true);
            fetchUsers();
        } catch (e) {
            console.error(e);
            setMessage("Failed to delete user");
            setOpenError(true);
        } finally {
            setDeleting(false);
            setConfirmDeleteOpen(false);
            setUserToDelete(null);
        }
    };

    return (
        <Box>
            <div className={`${styles.container} ${className ?? ""}`} ref={dialogRef}>
                <Button id="calloutButton" icon={<ManageAccountsIcon />} style={{ columnGap: "0.5rem" }} className="buttonText" onClick={() => setOpen(true)}>
                    User Management
                </Button>
            </div>
            <Dialog
                open={open}
                onClose={(event, reason) => {
                    if (reason === "backdropClick" || reason === "escapeKeyDown") {
                        return;
                    }
                    setOpen(false);
                }}
                fullWidth
                maxWidth="lg"
            >
                <DialogTitle>
                    <Tabs value={tab} onChange={handleTabChange}>
                        <Tab label="User Management" />
                        <Tab label="Data Group Management" />
                        <Tab label="Agent Configuration" />
                    </Tabs>
                </DialogTitle>

                <DialogContent>
                    {tab === 0 && (
                        <>
                            <Box sx={{ mb: 2, display: "flex", alignItems: "center" }}>
                                <TextField
                                    placeholder="Search User"
                                    variant="outlined"
                                    size="small"
                                    fullWidth
                                    value={search}
                                    onChange={(e: ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
                                    sx={{ mr: 2 }}
                                />
                            </Box>
                            <Box sx={{ mb: 2, display: "flex", alignItems: "center" }}>
                                <Button icon={<AddIcon />} onClick={() => setAddOpen(true)}>
                                    Add User
                                </Button>
                            </Box>

                            {loading ? (
                                <Box
                                    sx={{
                                        display: "flex",
                                        justifyContent: "center",
                                        alignItems: "center",
                                        minHeight: "200px"
                                    }}
                                >
                                    <CircularProgress />
                                </Box>
                            ) : (
                                <DataGrid
                                    rows={users}
                                    columns={columns}
                                    getRowId={row => row._id}
                                    paginationModel={paginationModel}
                                    onPaginationModelChange={setPaginationModel}
                                    pageSizeOptions={[5]}
                                    disableRowSelectionOnClick
                                    autoHeight
                                    processRowUpdate={processRowUpdate}
                                    rowModesModel={rowModesModel}
                                    onRowModesModelChange={setRowModesModel}
                                    onProcessRowUpdateError={error => {
                                        console.error("Update failed:", error);
                                        setMessage("Failed to update user");
                                        setOpenError(true);
                                    }}
                                />
                            )}
                        </>
                    )}

                    {tab === 1 && <GroupManagement />}
                    {tab === 2 && <AgentConfiguration />}

                    {/* Snackbar */}
                    <Snackbar
                        open={openSuccess}
                        autoHideDuration={3000}
                        anchorOrigin={{ vertical: "top", horizontal: "right" }}
                        onClose={() => setOpenSuccess(false)}
                    >
                        <Alert severity="success" onClose={() => setOpenSuccess(false)} sx={{ width: "100%" }}>
                            {message}
                        </Alert>
                    </Snackbar>
                    <Snackbar
                        open={openError}
                        autoHideDuration={3000}
                        anchorOrigin={{ vertical: "top", horizontal: "right" }}
                        onClose={() => setOpenError(false)}
                    >
                        <Alert severity="error" onClose={() => setOpenError(false)} sx={{ width: "100%" }}>
                            {message}
                        </Alert>
                    </Snackbar>
                    <Snackbar
                        open={openWarn}
                        autoHideDuration={3000}
                        anchorOrigin={{ vertical: "top", horizontal: "right" }}
                        onClose={() => setOpenWarn(false)}
                    >
                        <Alert severity="warning" onClose={() => setOpenWarn(false)} sx={{ width: "100%" }}>
                            {message}
                        </Alert>
                    </Snackbar>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => handleClose()}>Close</Button>
                </DialogActions>
            </Dialog>
            <Dialog open={addOpen} onClose={() => setAddOpen(false)} fullWidth maxWidth="sm">
                <DialogTitle>Add User</DialogTitle>
                <DialogContent>
                    {creating && (
                        <Box
                            sx={{
                                position: "absolute",
                                inset: 0,
                                bgcolor: "rgba(255,255,255,0.6)",
                                display: "flex",
                                justifyContent: "center",
                                alignItems: "center",
                                zIndex: 10
                            }}
                        >
                            <CircularProgress />
                        </Box>
                    )}
                    <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
                        <TextField label="Email" value={newUsername} onChange={e => setNewUsername(e.target.value)} fullWidth />

                        {/* Groups */}
                        <FormControl fullWidth>
                            <InputLabel id="groups-label">Source</InputLabel>
                            <Select<string[]>
                                labelId="groups-label"
                                label="Source"
                                multiple
                                value={newGroups.map(g => g._id)}
                                onChange={(e: SelectChangeEvent<string[]>) => {
                                    const selectedIds = e.target.value as string[];
                                    const selectedGroups = groups.filter(g => selectedIds.includes(g._id));
                                    setNewGroups(selectedGroups);
                                }}
                                renderValue={selected => {
                                    const selectedIds = selected as string[];
                                    return groups
                                        .filter(g => selectedIds.includes(g._id))
                                        .map(g => g.name)
                                        .join(", ");
                                }}
                            >
                                {groups.map(group => (
                                    <MenuItem key={group._id} value={group._id}>
                                        {group.name}
                                    </MenuItem>
                                ))}
                            </Select>
                            <FormHelperText>Select one or more source</FormHelperText>
                        </FormControl>

                        {/* Role */}
                        <FormControl fullWidth>
                            <InputLabel id="role-label">Role</InputLabel>

                            <Select labelId="role-label" label="Role" value={newRole || ""} onChange={e => setNewRole(e.target.value)}>
                                {roles.map(role => (
                                    <MenuItem key={role._id} value={role._id}>
                                        {role.name}
                                    </MenuItem>
                                ))}
                            </Select>
                            <FormHelperText>Select a role for this user</FormHelperText>
                        </FormControl>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <ButtonMUI onClick={() => setAddOpen(false)}>Cancel</ButtonMUI>
                    <ButtonMUI
                        onClick={handleCreateUser}
                        color="primary"
                        variant="contained"
                        disabled={creating}
                        startIcon={creating ? <CircularProgress size={20} /> : null}
                    >
                        {creating ? "Creating..." : "Create"}
                    </ButtonMUI>
                </DialogActions>
            </Dialog>
            <Dialog open={confirmDeleteOpen} onClose={() => !deleting && setConfirmDeleteOpen(false)}>
                <DialogTitle>Confirm Delete</DialogTitle>
                <DialogContent>Are you sure you want to delete this user?</DialogContent>
                <DialogActions>
                    <ButtonMUI onClick={() => setConfirmDeleteOpen(false)} disabled={deleting}>
                        Cancel
                    </ButtonMUI>
                    <ButtonMUI
                        onClick={handleDeleteConfirm}
                        color="error"
                        variant="contained"
                        disabled={deleting}
                        startIcon={deleting ? <CircularProgress size={20} /> : <DeleteIcon />}
                    >
                        {deleting ? "Deleting..." : "Delete"}
                    </ButtonMUI>
                </DialogActions>
            </Dialog>
        </Box>
    );
};
