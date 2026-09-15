import { useEffect, useMemo, useState } from "react";
import {
    Avatar,
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
    Paper,
    Chip,
    Stack,
    TextField,
    Typography
} from "@mui/material";
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
                ) : filteredTeams.length === 0 ? (
                    <Typography color="text.secondary">No teams found</Typography>
                ) : (
                    <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 240px), 1fr))", gap: 2 }}>
                        {filteredTeams.map(team => (
                            <Paper
                                key={team._id}
                                variant="outlined"
                                role="button"
                                tabIndex={0}
                                onClick={() => manageTeam(team)}
                                onKeyDown={event => {
                                    if (event.key === "Enter" || event.key === " ") {
                                        event.preventDefault();
                                        manageTeam(team);
                                    }
                                }}
                                sx={{
                                    p: 2,
                                    minHeight: 270,
                                    display: "flex",
                                    flexDirection: "column",
                                    alignItems: "center",
                                    textAlign: "center",
                                    position: "relative",
                                    cursor: "pointer",
                                    transition: "transform 150ms ease, box-shadow 150ms ease, border-color 150ms ease",
                                    "&:hover": { transform: "translateY(-2px)", boxShadow: 3, borderColor: "primary.light" },
                                    "&:focus-visible": { outline: "3px solid", outlineColor: "primary.light", outlineOffset: 2 }
                                }}
                            >
                                <Chip size="small" color={team.waiting_approve.length ? "warning" : "success"} label={team.waiting_approve.length ? `${team.waiting_approve.length} pending` : "Ready"} sx={{ position: "absolute", top: 12, left: 12 }} />
                                <IconButton size="small" aria-label={`Actions for ${team.name}`} onClick={event => { event.stopPropagation(); setActionAnchor(event.currentTarget); setActionTeam(team); }} sx={{ position: "absolute", top: 8, right: 8 }}>
                                    <MoreVertIcon fontSize="small" />
                                </IconButton>
                                <Avatar variant="rounded" sx={{ width: 72, height: 72, mt: 3, mb: 2, bgcolor: "primary.main", fontSize: 26, boxShadow: 1 }}>
                                    {team.name.trim().slice(0, 2).toUpperCase() || "TM"}
                                </Avatar>
                                <Typography variant="h6" fontSize="1rem" fontWeight={700} sx={{ minHeight: 42, overflowWrap: "anywhere" }}>{team.name}</Typography>
                                <Typography variant="body2" color="text.secondary">Team workspace</Typography>
                                <Box sx={{ flex: 1 }} />
                                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap justifyContent="center" sx={{ mt: 2 }}>
                                    <Chip size="small" variant="outlined" label={`${team.user_id.length} members`} />
                                    <Chip size="small" variant="outlined" label={`${team.agent_id.length} agents`} />
                                    <Chip size="small" variant="outlined" label={`${team.data_group_id.length} data groups`} />
                                </Stack>
                            </Paper>
                        ))}
                    </Box>
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
                <MenuItem onClick={() => { if (actionTeam) manageTeam(actionTeam); setActionAnchor(null); setActionTeam(null); }}>
                    <ListItemIcon><SettingsOutlinedIcon fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Manage team" />
                </MenuItem>
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
