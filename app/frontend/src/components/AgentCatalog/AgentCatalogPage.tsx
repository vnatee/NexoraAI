import { useCallback, useEffect, useMemo, useState } from "react";
import {
    Alert,
    Avatar,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    InputLabel,
    InputAdornment,
    IconButton,
    Menu,
    MenuItem,
    Paper,
    Select,
    Stack,
    TextField,
    Typography
} from "@mui/material";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import SearchIcon from "@mui/icons-material/Search";
import { useMsal } from "@azure/msal-react";

import { Agent, AgentCatalogItem, Team, TeamProfile } from "../../api/models";
import { create_system_agent_catalog, get_teams, install_agent_catalog, list_agent_catalog, update_agent_catalog } from "../../api/api";
import { getToken } from "../../authConfig";
import { useNotification } from "../../utill/NotificationProvider";
import { AgentDialog } from "../TeamManagementTabsDialog/Tabs/AgentManagementPage";


type Props = {
    team: TeamProfile | null;
    governance?: boolean;
    canInstall?: boolean;
    onAgentsChanged?: () => void;
};

export function AgentCatalogPage({ team, governance = false, canInstall = false, onAgentsChanged }: Props) {
    const { instance } = useMsal();
    const { showNotification } = useNotification();
    const [items, setItems] = useState<AgentCatalogItem[]>([]);
    const [teams, setTeams] = useState<Team[]>([]);
    const [loading, setLoading] = useState(true);
    const [busyId, setBusyId] = useState<string | null>(null);
    const [search, setSearch] = useState("");
    const [category, setCategory] = useState("All");
    const [error, setError] = useState("");
    const [agentEditorOpen, setAgentEditorOpen] = useState(false);
    const [catalogDraft, setCatalogDraft] = useState<Agent | null>(null);
    const [metadataOpen, setMetadataOpen] = useState(false);
    const [summary, setSummary] = useState("");
    const [instructions, setInstructions] = useState("");
    const [tags, setTags] = useState("");
    const [newCategory, setNewCategory] = useState("General");
    const [visibility, setVisibility] = useState<"selected_teams" | "all_teams">("all_teams");
    const [allowedTeamIds, setAllowedTeamIds] = useState<string[]>([]);
    const [creating, setCreating] = useState(false);
    const [selectedItem, setSelectedItem] = useState<AgentCatalogItem | null>(null);
    const [menuItem, setMenuItem] = useState<AgentCatalogItem | null>(null);
    const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);

    const load = useCallback(async () => {
        try {
            setLoading(true);
            setError("");
            const token = await getToken(instance);
            if (!token) return;
            const [catalog, allTeams] = await Promise.all([
                list_agent_catalog(token, governance ? undefined : team?._id),
                governance ? get_teams(token) : Promise.resolve([])
            ]);
            setItems(catalog);
            setTeams((allTeams as { result?: Team[] })?.result ?? []);
        } catch (caught) {
            console.error("Unable to load Agent Catalog", caught);
            setError("Unable to load Agent Catalog.");
        } finally {
            setLoading(false);
        }
    }, [governance, instance, team?._id]);

    useEffect(() => void load(), [load]);

    const categories = useMemo(
        () => ["All", ...Array.from(new Set(items.map(item => item.category || "General"))).sort()],
        [items]
    );
    const filtered = useMemo(() => {
        const query = search.trim().toLowerCase();
        return items.filter(item =>
            (category === "All" || item.category === category) &&
            (!query || `${item.name} ${item.summary} ${item.publisher_team.name}`.toLowerCase().includes(query))
        );
    }, [category, items, search]);

    const install = async (item: AgentCatalogItem) => {
        if (!team?._id) return;
        try {
            setBusyId(item._id);
            const token = await getToken(instance);
            if (!token) return;
            await install_agent_catalog(item._id, team._id, token);
            showNotification(`${item.name} installed for ${team.name}`, "success");
            onAgentsChanged?.();
            await load();
        } catch (caught) {
            console.error("Unable to install catalog agent", caught);
            showNotification("Unable to install this Agent. Verify its model requirements.", "error");
        } finally {
            setBusyId(null);
        }
    };

    const update = async (item: AgentCatalogItem, changes: Parameters<typeof update_agent_catalog>[1]) => {
        try {
            setBusyId(item._id);
            const token = await getToken(instance);
            if (!token) return;
            await update_agent_catalog(item._id, changes, token);
            setSelectedItem(current => current?._id === item._id ? { ...current, ...changes } : current);
            showNotification("Catalog entry updated", "success");
            await load();
        } catch (caught) {
            console.error("Unable to update Agent Catalog", caught);
            showNotification("Unable to update catalog entry", "error");
        } finally {
            setBusyId(null);
        }
    };

    const initials = (name: string) => name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map(value => value[0]?.toUpperCase())
        .join("") || "AI";
    const avatarColor = (name: string) => {
        const colors = ["#6C7FD8", "#B86FB0", "#7666A6", "#EF8F2F", "#668F83", "#477CC2"];
        const index = Array.from(name).reduce((sum, character) => sum + character.charCodeAt(0), 0) % colors.length;
        return colors[index];
    };

    const createSystemTemplate = async () => {
        if (!catalogDraft || !summary.trim() || !instructions.trim()) return;
        try {
            setCreating(true);
            const token = await getToken(instance);
            if (!token) return;
            await create_system_agent_catalog({
                agent_name: catalogDraft.agent_name,
                config: catalogDraft.config,
                prompt: catalogDraft.prompt,
                summary: summary.trim(),
                usage_instructions: instructions.trim(),
                tags: tags.split(",").map(value => value.trim()).filter(Boolean),
                category: newCategory.trim() || "General",
                visibility,
                allowed_team_ids: visibility === "selected_teams" ? allowedTeamIds : []
            }, token);
            showNotification("System Catalog Agent created", "success");
            setMetadataOpen(false);
            setCatalogDraft(null);
            setSummary("");
            setInstructions("");
            setTags("");
            setNewCategory("General");
            setVisibility("all_teams");
            setAllowedTeamIds([]);
            await load();
        } catch (caught) {
            console.error("Unable to create system catalog agent", caught);
            showNotification("Unable to create System Catalog Agent", "error");
        } finally {
            setCreating(false);
        }
    };

    return (
        <Stack spacing={2} sx={{ p: governance ? 3 : 0 }}>
            <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} spacing={1}>
                <Box>
                    <Typography variant="h6">{governance ? "Agent Catalog Governance" : "Agent Catalog"}</Typography>
                    <Typography variant="body2" color="text.secondary">
                        {governance
                            ? "Create organization templates and control catalog visibility across teams."
                            : `Browse reusable Agents available to ${team?.name ?? "this team"}. Installation creates a team-local copy.`}
                    </Typography>
                </Box>
                {governance && (
                    <Button variant="contained" startIcon={<AddCircleOutlineIcon />} onClick={() => setAgentEditorOpen(true)}>
                        New Catalog Agent
                    </Button>
                )}
            </Stack>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                <TextField
                    fullWidth
                    size="small"
                    placeholder="Search agents..."
                    value={search}
                    onChange={event => setSearch(event.target.value)}
                    InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon color="action" /></InputAdornment> }}
                />
                <TextField select size="small" label="Category" value={category} onChange={event => setCategory(event.target.value)} sx={{ minWidth: 190 }}>
                    {categories.map(value => <MenuItem key={value} value={value}>{value}</MenuItem>)}
                </TextField>
            </Stack>
            {error && <Alert severity="error">{error}</Alert>}
            {loading ? <Box textAlign="center" py={4}><CircularProgress /></Box> : filtered.length === 0 ? (
                <Alert severity="info">No catalog Agents are available for this scope.</Alert>
            ) : (
                <Box sx={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 240px), 1fr))",
                    gap: 2
                }}>
                    {filtered.map(item => (
                        <Paper
                            key={item._id}
                            variant="outlined"
                            role="button"
                            tabIndex={0}
                            onClick={() => setSelectedItem(item)}
                            onKeyDown={event => {
                                if (event.key === "Enter" || event.key === " ") setSelectedItem(item);
                            }}
                            sx={{
                                p: 2,
                                minHeight: 310,
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
                            <Chip
                                size="small"
                                color={item.status !== "published" || item.update_available ? "warning" : "success"}
                                label={item.status !== "published" ? "Unpublished" : item.update_available ? "Update" : item.installed ? "Installed" : "Available"}
                                sx={{ position: "absolute", top: 12, left: 12 }}
                            />
                            <IconButton
                                size="small"
                                aria-label={`Actions for ${item.name}`}
                                onClick={event => {
                                    event.stopPropagation();
                                    setMenuItem(item);
                                    setMenuAnchor(event.currentTarget);
                                }}
                                sx={{ position: "absolute", top: 8, right: 8 }}
                            >
                                <MoreHorizIcon />
                            </IconButton>
                            <Avatar
                                variant="rounded"
                                sx={{ width: 72, height: 72, mt: 3, mb: 2, bgcolor: avatarColor(item.name), fontSize: 28, boxShadow: 1 }}
                            >
                                {initials(item.name)}
                            </Avatar>
                            <Typography variant="h6" fontSize="1rem" fontWeight={700} sx={{ lineHeight: 1.3, minHeight: 42 }}>
                                {item.name}
                            </Typography>
                            <Typography
                                variant="body2"
                                color="text.secondary"
                                sx={{
                                    mt: 1,
                                    display: "-webkit-box",
                                    WebkitLineClamp: 3,
                                    WebkitBoxOrient: "vertical",
                                    overflow: "hidden",
                                    overflowWrap: "anywhere"
                                }}
                            >
                                {item.summary}
                            </Typography>
                            <Box sx={{ flex: 1 }} />
                            <Typography variant="caption" color="text.secondary" sx={{ mt: 2 }}>
                                By {item.created_by.name}
                            </Typography>
                            <Stack direction="row" spacing={0.5} sx={{ mt: 1 }}>
                                <Chip size="small" label={item.category} />
                                <Chip size="small" variant="outlined" label={`v${item.latest_version}`} />
                            </Stack>
                        </Paper>
                    ))}
                </Box>
            )}
            <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={() => setMenuAnchor(null)}>
                <MenuItem onClick={() => { setSelectedItem(menuItem); setMenuAnchor(null); }}>View details</MenuItem>
                {!governance && canInstall && menuItem && !menuItem.installed && (
                    <MenuItem onClick={() => { void install(menuItem); setMenuAnchor(null); }}>Install for {team?.name}</MenuItem>
                )}
                {governance && menuItem && (
                    <MenuItem onClick={() => { void update(menuItem, { status: menuItem.status === "published" ? "unpublished" : "published" }); setMenuAnchor(null); }}>
                        {menuItem.status === "published" ? "Unpublish" : "Publish"}
                    </MenuItem>
                )}
            </Menu>
            <Dialog open={Boolean(selectedItem)} onClose={() => setSelectedItem(null)} maxWidth="sm" fullWidth>
                <DialogTitle>{selectedItem?.name}</DialogTitle>
                <DialogContent dividers>
                    {selectedItem && <Stack spacing={2}>
                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                            <Chip size="small" label={selectedItem.category} />
                            <Chip size="small" variant="outlined" label={`Version ${selectedItem.latest_version}`} />
                            <Chip size="small" color={selectedItem.status === "published" ? "success" : "default"} label={selectedItem.status} />
                            {selectedItem.installed && <Chip size="small" color="success" label={`Installed v${selectedItem.installed_version}`} />}
                        </Stack>
                        <Box>
                            <Typography variant="subtitle2">What this Agent does</Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: "pre-wrap" }}>{selectedItem.summary}</Typography>
                        </Box>
                        <Box>
                            <Typography variant="subtitle2">How to use</Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: "pre-wrap" }}>{selectedItem.usage_instructions || "No usage instructions provided."}</Typography>
                        </Box>
                        {(selectedItem.tags?.length ?? 0) > 0 && <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                            {selectedItem.tags.map(tag => <Chip key={tag} size="small" variant="outlined" label={tag} />)}
                        </Stack>}
                        <Typography variant="body2" color="text.secondary">
                            Created by {selectedItem.created_by.name}<br />
                            Published by {selectedItem.publisher_team.name}<br />
                            Runtime: {selectedItem.requirements.runtime || "legacy"}<br />
                            Model profile: {selectedItem.requirements.llm_profile_id || "system"}
                            {(selectedItem.requirements.declared_tools?.length ?? 0) > 0 ? <><br />Requires Team configuration: {selectedItem.requirements.declared_tools!.join(", ")}</> : null}
                        </Typography>
                        {governance && <>
                            <FormControl size="small">
                                <InputLabel>Visibility</InputLabel>
                                <Select
                                    label="Visibility"
                                    value={selectedItem.visibility}
                                    disabled={busyId === selectedItem._id}
                                    onChange={event => void update(selectedItem, {
                                        visibility: event.target.value as AgentCatalogItem["visibility"],
                                        allowed_team_ids: event.target.value === "selected_teams" ? (selectedItem.allowed_team_ids?.length ? selectedItem.allowed_team_ids : teams.slice(0, 1).map(value => value._id)) : []
                                    })}
                                >
                                    <MenuItem value="team" disabled={selectedItem.publisher_type === "system"}>Publisher team</MenuItem>
                                    <MenuItem value="selected_teams" disabled={teams.length === 0}>Selected teams</MenuItem>
                                    <MenuItem value="all_teams">All teams</MenuItem>
                                </Select>
                            </FormControl>
                            {selectedItem.visibility === "selected_teams" && <FormControl size="small">
                                <InputLabel>Allowed teams</InputLabel>
                                <Select multiple label="Allowed teams" value={selectedItem.allowed_team_ids ?? []} onChange={event => void update(selectedItem, { visibility: "selected_teams", allowed_team_ids: event.target.value as string[] })}>
                                    {teams.map(value => <MenuItem key={value._id} value={value._id}>{value.name}</MenuItem>)}
                                </Select>
                            </FormControl>}
                        </>}
                    </Stack>}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setSelectedItem(null)}>Close</Button>
                    {!governance && canInstall && selectedItem && (
                        <Button variant="contained" disabled={selectedItem.installed || busyId === selectedItem._id} onClick={() => void install(selectedItem)}>
                            {selectedItem.installed ? "Installed" : "Install"}
                        </Button>
                    )}
                    {governance && selectedItem && (
                        <Button color={selectedItem.status === "published" ? "warning" : "success"} variant="contained" disabled={busyId === selectedItem._id} onClick={() => void update(selectedItem, { status: selectedItem.status === "published" ? "unpublished" : "published" })}>
                            {selectedItem.status === "published" ? "Unpublish" : "Publish"}
                        </Button>
                    )}
                </DialogActions>
            </Dialog>
            {governance && (
                <AgentDialog
                    open={agentEditorOpen}
                    mode="new"
                    agent={null}
                    loading={false}
                    onClose={() => setAgentEditorOpen(false)}
                    onSave={agent => {
                        setCatalogDraft(agent);
                        setAgentEditorOpen(false);
                        setMetadataOpen(true);
                    }}
                    availableAgents={[]}
                    templateOnly
                />
            )}
            <Dialog open={metadataOpen} onClose={() => !creating && setMetadataOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Catalog details</DialogTitle>
                <DialogContent dividers>
                    <Alert severity="info" sx={{ mb: 2 }}>
                        System Catalog Agents are templates only. Team credentials, integrations and Data Groups are configured after installation.
                    </Alert>
                    <Stack spacing={2}>
                        <TextField label="Agent" value={catalogDraft?.agent_name ?? ""} disabled />
                        <TextField required label="What this Agent does" value={summary} onChange={event => setSummary(event.target.value)} multiline minRows={3} inputProps={{ maxLength: 500 }} />
                        <TextField required label="How to use" value={instructions} onChange={event => setInstructions(event.target.value)} multiline minRows={4} inputProps={{ maxLength: 4000 }} helperText="Include suitable inputs, expected output, limitations and setup required after installation." />
                        <TextField required label="Category" value={newCategory} onChange={event => setNewCategory(event.target.value)} inputProps={{ maxLength: 80 }} />
                        <TextField label="Tags" value={tags} onChange={event => setTags(event.target.value)} helperText="Comma-separated; maximum 12 tags" />
                        <TextField select label="Visibility" value={visibility} onChange={event => setVisibility(event.target.value as typeof visibility)}>
                            <MenuItem value="all_teams">All teams</MenuItem>
                            <MenuItem value="selected_teams">Selected teams</MenuItem>
                        </TextField>
                        {visibility === "selected_teams" && (
                            <FormControl>
                                <InputLabel>Allowed teams</InputLabel>
                                <Select multiple label="Allowed teams" value={allowedTeamIds} onChange={event => setAllowedTeamIds(event.target.value as string[])}>
                                    {teams.map(value => <MenuItem key={value._id} value={value._id}>{value.name}</MenuItem>)}
                                </Select>
                            </FormControl>
                        )}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button disabled={creating} onClick={() => setMetadataOpen(false)}>Back</Button>
                    <Button variant="contained" disabled={creating || !summary.trim() || !instructions.trim() || (visibility === "selected_teams" && allowedTeamIds.length === 0)} onClick={() => void createSystemTemplate()}>
                        {creating ? "Creating…" : "Create and publish"}
                    </Button>
                </DialogActions>
            </Dialog>
        </Stack>
    );
}
