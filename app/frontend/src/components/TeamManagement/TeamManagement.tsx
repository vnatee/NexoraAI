import { useEffect, useMemo, useState } from "react";
import {
    Box,
    Button,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    ListItemIcon,
    ListItemText,
    Menu,
    MenuItem,
    Stack,
    TextField,
    Typography
} from "@mui/material";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import { useMsal } from "@azure/msal-react";

import { create_team, delete_team, get_teams, Team, TeamProfile } from "../../api";
import { getToken } from "../../authConfig";
import { AuthStorage } from "../../utill/authStorage";
import { useNotification } from "../../utill/NotificationProvider";

interface TeamManagementProps {
    onTeamCreated?: (team: TeamProfile) => void;
    onTeamManage?: (team: TeamProfile) => void;
}

export function TeamManagement({ onTeamCreated, onTeamManage }: TeamManagementProps) {
    const { instance } = useMsal();
    const { showNotification } = useNotification();
    const [teams, setTeams] = useState<Team[]>([]);
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState("");
    const [newTeamOpen, setNewTeamOpen] = useState(false);
    const [teamName, setTeamName] = useState("");
    const [creating, setCreating] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [deleteTeam, setDeleteTeam] = useState<Team | null>(null);
    const [actionAnchor, setActionAnchor] = useState<HTMLElement | null>(null);
    const [actionTeam, setActionTeam] = useState<Team | null>(null);

    const teamProfile = (team: Team): TeamProfile => {
        const authorizedProfile = AuthStorage.get()?.teams.find(item => item._id === team._id);
        return authorizedProfile ? { ...authorizedProfile, name: team.name } : { _id: team._id, name: team.name, permissions: [] };
    };

    const loadTeams = async () => {
        try {
            setLoading(true);
            const token = await getToken(instance);
            if (!token) return;
            const response = await get_teams(token);
            setTeams(response.result ?? []);
        } catch (error) {
            console.error("Failed to load teams", error);
            showNotification("Failed to load teams", "error");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void loadTeams();
    }, [instance]);

    const filteredTeams = useMemo(() => {
        const keyword = search.trim().toLowerCase();
        return keyword ? teams.filter(team => team.name.toLowerCase().includes(keyword)) : teams;
    }, [search, teams]);

    const manageTeam = (team: Team) => onTeamManage?.(teamProfile(team));

    const columns: GridColDef<Team>[] = [
        { field: "name", headerName: "Team name", flex: 1, minWidth: 220 },
        {
            field: "data_group_id",
            headerName: "Data groups",
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
            headerName: "Members",
            width: 105,
            valueGetter: (_, row) => row.user_id.length
        },
        {
            field: "waiting_approve",
            headerName: "Pending",
            width: 105,
            valueGetter: (_, row) => row.waiting_approve.length
        },
        {
            field: "actions",
            headerName: "",
            sortable: false,
            filterable: false,
            width: 170,
            renderCell: params => (
                <Stack direction="row" spacing={0.5} alignItems="center" sx={{ height: "100%" }}>
                    <Button size="small" startIcon={<SettingsOutlinedIcon />} onClick={() => manageTeam(params.row)}>
                        Manage
                    </Button>
                    <IconButton
                        size="small"
                        aria-label={`More actions for ${params.row.name}`}
                        onClick={event => {
                            event.stopPropagation();
                            setActionAnchor(event.currentTarget);
                            setActionTeam(params.row);
                        }}
                    >
                        <MoreVertIcon fontSize="small" />
                    </IconButton>
                </Stack>
            )
        }
    ];

    const createTeam = async () => {
        const normalizedName = teamName.trim();
        if (!normalizedName) return;
        try {
            setCreating(true);
            const token = await getToken(instance);
            if (!token) return;
            const response = await create_team(normalizedName, token);
            await loadTeams();
            setNewTeamOpen(false);
            setTeamName("");
            showNotification("Team created successfully", "success");
            if (response?.team?._id) {
                onTeamCreated?.({
                    _id: response.team._id,
                    name: response.team.name ?? normalizedName,
                    permissions: response.team.permissions ?? []
                });
            }
        } catch (error) {
            console.error("Failed to create team", error);
            showNotification("Failed to create team", "error");
        } finally {
            setCreating(false);
        }
    };

    const confirmDeleteTeam = async () => {
        if (!deleteTeam) return;
        try {
            setDeleting(true);
            const token = await getToken(instance);
            if (!token) return;
            await delete_team(deleteTeam._id, token);
            await loadTeams();
            setDeleteTeam(null);
            showNotification("Team deleted successfully", "success");
        } catch (error) {
            console.error("Failed to delete team", error);
            showNotification("Failed to delete team", "error");
        } finally {
            setDeleting(false);
        }
    };

    return (
        <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
            <Box sx={{ mb: 2 }}>
                <Typography variant="h6">Teams</Typography>
                <Typography variant="body2" color="text.secondary">
                    Create teams and open Team Settings to manage members, access, agents, integrations, and governance.
                </Typography>
            </Box>

            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, mb: 2 }}>
                <TextField
                    size="small"
                    placeholder="Search teams"
                    value={search}
                    onChange={event => setSearch(event.target.value)}
                    sx={{ width: 280 }}
                />
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={() => {
                        setTeamName("");
                        setNewTeamOpen(true);
                    }}
                >
                    New team
                </Button>
            </Box>

            <Box sx={{ flex: 1, minHeight: 320 }}>
                {loading ? (
                    <Box sx={{ display: "flex", justifyContent: "center", mt: 4 }}>
                        <CircularProgress />
                    </Box>
                ) : (
                    <DataGrid
                        rows={filteredTeams}
                        columns={columns}
                        getRowId={row => row._id}
                        pageSizeOptions={[5, 10]}
                        disableRowSelectionOnClick
                        onRowDoubleClick={params => manageTeam(params.row)}
                    />
                )}
            </Box>

            <Menu
                anchorEl={actionAnchor}
                open={Boolean(actionAnchor)}
                onClose={() => {
                    setActionAnchor(null);
                    setActionTeam(null);
                }}
            >
                <MenuItem
                    onClick={() => {
                        setDeleteTeam(actionTeam);
                        setActionAnchor(null);
                        setActionTeam(null);
                    }}
                >
                    <ListItemIcon>
                        <DeleteIcon fontSize="small" color="error" />
                    </ListItemIcon>
                    <ListItemText primary="Delete team" primaryTypographyProps={{ color: "error" }} />
                </MenuItem>
            </Menu>

            <Dialog open={newTeamOpen} onClose={() => !creating && setNewTeamOpen(false)} maxWidth="xs" fullWidth>
                <DialogTitle>New team</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        fullWidth
                        label="Team name"
                        value={teamName}
                        onChange={event => setTeamName(event.target.value)}
                        sx={{ mt: 1 }}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setNewTeamOpen(false)} disabled={creating}>Cancel</Button>
                    <Button variant="contained" disabled={!teamName.trim() || creating} onClick={() => void createTeam()}>
                        {creating ? "Creating..." : "Create"}
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog open={Boolean(deleteTeam)} onClose={() => !deleting && setDeleteTeam(null)} maxWidth="xs" fullWidth>
                <DialogTitle>Delete team</DialogTitle>
                <DialogContent>
                    <Typography>
                        Are you sure you want to delete <strong>{deleteTeam?.name}</strong>?
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteTeam(null)} disabled={deleting}>Cancel</Button>
                    <Button color="error" variant="contained" disabled={deleting} onClick={() => void confirmDeleteTeam()}>
                        {deleting ? "Deleting..." : "Delete"}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
