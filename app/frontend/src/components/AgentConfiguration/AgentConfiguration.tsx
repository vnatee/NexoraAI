// src/components/AgentConfiguration.tsx
import React, { useEffect, useState } from "react";
import {
    Box,
    TextField,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Snackbar,
    Alert,
    CircularProgress,
    IconButton,
    FormControl,
    FormHelperText,
    InputLabel,
    Select,
    MenuItem
} from "@mui/material";
import { Button as ButtonMUI } from "@mui/material";
import { Button } from "@fluentui/react-components";
import { DataGrid, GridColDef, GridPaginationModel } from "@mui/x-data-grid";

import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";

import { useMsal } from "@azure/msal-react";
import { getToken } from "../../authConfig";

// API & Models
import { listAgentsApi, createAgentApi, updateAgentApi, deleteAgentApi, listGroupsApi, AgentConfig } from "../../api";
import { GroupDetail } from "../../api/models"; // ปรับ path ให้ตรงโปรเจกต์จริงถ้าไม่ใช่อันนี้

import styles from "./AgentConfiguration.module.css";

export const AgentConfiguration: React.FC = () => {
    const client = useMsal().instance;

    const [agents, setAgents] = useState<AgentConfig[]>([]);
    const [groups, setGroups] = useState<GroupDetail[]>([]); // 🆕 groups ทั้งระบบ

    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState("");

    const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
        page: 0,
        pageSize: 5
    });

    const [openSuccess, setOpenSuccess] = useState(false);
    const [openWarn, setOpenWarn] = useState(false);
    const [openError, setOpenError] = useState(false);
    const [message, setMessage] = useState<string | null>(null);

    const [addOpen, setAddOpen] = useState(false);
    const [creating, setCreating] = useState(false);

    const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [agentToDelete, setAgentToDelete] = useState<string | null>(null);

    // Edit dialog
    const [editOpen, setEditOpen] = useState(false);
    const [editingAgent, setEditingAgent] = useState<AgentConfig | null>(null);
    const [updating, setUpdating] = useState(false);

    // ฟิลด์สำหรับ Add
    const [newName, setNewName] = useState("");
    const [newDescription, setNewDescription] = useState("");
    const [newIsActive, setNewIsActive] = useState(true);
    const [newTemperature, setNewTemperature] = useState<number>(0.3);
    const [newSeed, setNewSeed] = useState<number | null>(null);
    const [newMinSearchScore, setNewMinSearchScore] = useState<number>(0);
    const [newMaxSearchResults, setNewMaxSearchResults] = useState<number>(3);
    const [newMaxTokens, setNewMaxTokens] = useState<number | null>(null);
    const [newGroups, setNewGroups] = useState<GroupDetail[]>([]); // 🆕 groups ที่เลือกตอน Add

    // ฟิลด์สำหรับ Edit
    const [editName, setEditName] = useState("");
    const [editDescription, setEditDescription] = useState("");
    const [editIsActive, setEditIsActive] = useState(true);
    const [editTemperature, setEditTemperature] = useState<number>(0.3);
    const [editSeed, setEditSeed] = useState<number | null>(null);
    const [editMinSearchScore, setEditMinSearchScore] = useState<number>(0);
    const [editMaxSearchResults, setEditMaxSearchResults] = useState<number>(3);
    const [editMaxTokens, setEditMaxTokens] = useState<number | null>(null);
    const [editGroups, setEditGroups] = useState<GroupDetail[]>([]); // 🆕 groups ที่เลือกตอน Edit

    // โหลด Agents + Groups
    const fetchAgents = async () => {
        try {
            setLoading(true);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            const rawAgents = await listAgentsApi(token);
            const agentList: AgentConfig[] = Array.isArray(rawAgents) ? rawAgents : Object.values(rawAgents);

            const groupList: GroupDetail[] = await listGroupsApi(token);

            setAgents(agentList);
            setGroups(groupList);
        } catch (e) {
            console.error(e);
            setMessage("Failed to load agents");
            setOpenError(true);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAgents();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // filter search
    const filteredAgents = !search
        ? agents
        : agents.filter(a => {
              const lower = search.toLowerCase();
              const name = a.name ?? "";
              const desc = a.description ?? "";
              return name.toLowerCase().includes(lower) || desc.toLowerCase().includes(lower);
          });

    // ลบ
    const handleDeleteRequest = (id: string) => {
        setAgentToDelete(id);
        setConfirmDeleteOpen(true);
    };

    const handleDeleteConfirm = async () => {
        if (!agentToDelete) return;
        setDeleting(true);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            await deleteAgentApi(agentToDelete, token);

            removeAgentFromActiveConfigs(agentToDelete);

            setMessage("Agent deleted successfully");
            setOpenSuccess(true);
            fetchAgents();
        } catch (e) {
            console.error(e);
            setMessage("Failed to delete agent");
            setOpenError(true);
        } finally {
            setDeleting(false);
            setConfirmDeleteOpen(false);
            setAgentToDelete(null);
        }
    };

    // Add
    const handleCreateAgent = async () => {
        setCreating(true);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            const createdAgent: AgentConfig = await createAgentApi(
                {
                    name: newName,
                    description: newDescription,
                    is_active: newIsActive,
                    temperature: newTemperature,
                    seed: newSeed,
                    min_search_score: newMinSearchScore,
                    max_search_results: newMaxSearchResults,
                    max_tokens: newMaxTokens,
                    groups: newGroups
                },
                token
            );

            if (createdAgent) {
                updateActiveAgentConfigsCache(createdAgent);
            }

            setMessage("Agent created successfully");
            setOpenSuccess(true);

            setAddOpen(false);
            setNewName("");
            setNewDescription("");
            setNewIsActive(true);
            setNewTemperature(0.3);
            setNewSeed(null);
            setNewMinSearchScore(0);
            setNewMaxSearchResults(3);
            setNewMaxTokens(null);
            setNewGroups([]);

            fetchAgents();
        } catch (e: any) {
            if (e.error === "some groups are already used by another agent") {
                // 🆕 แสดงข้อความละเอียดขึ้น พร้อมชื่อ agent ที่ชน
                setMessage(e.error);
            } else if (typeof e.error === "string") {
                setMessage(e.error);
            } else {
                setMessage("Failed to update agent");
            }

            setOpenError(true);
        } finally {
            setCreating(false);
        }
    };

    // เปิด dialog Edit
    const handleOpenEdit = (agent: AgentConfig) => {
        setEditingAgent(agent);

        setEditName(agent.name ?? "");
        setEditDescription(agent.description ?? "");
        setEditIsActive(agent.is_active ?? true);
        setEditTemperature(agent.temperature ?? 0.3);
        setEditSeed(agent.seed ?? null);
        setEditMinSearchScore(agent.min_search_score ?? 0);
        setEditMaxSearchResults(agent.max_search_results ?? 3);
        setEditMaxTokens(agent.max_tokens ?? null);
        setEditGroups(agent.groups ?? []); // 🆕 โหลด groups เดิมของ agent นั้น

        setEditOpen(true);
    };

    const handleCloseEdit = () => {
        if (updating) return;
        setEditOpen(false);
        setEditingAgent(null);
        setEditGroups([]);
    };

    // Save Edit
    const handleSaveEdit = async () => {
        if (!editingAgent || !editingAgent._id) {
            setMessage("Invalid agent data");
            setOpenError(true);
            return;
        }

        setUpdating(true);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            await updateAgentApi(
                {
                    _id: editingAgent._id,
                    name: editName,
                    description: editDescription,
                    is_active: editIsActive,
                    temperature: editTemperature,
                    seed: editSeed,
                    min_search_score: editMinSearchScore,
                    max_search_results: editMaxSearchResults,
                    max_tokens: editMaxTokens,
                    groups: editGroups // 🆕 ส่ง groups ที่เลือกแก้ใหม่
                },
                token
            );

            // 🆕 สร้าง object config ใหม่ของ agent นี้
            const updatedAgent: AgentConfig = {
                ...editingAgent,
                name: editName,
                description: editDescription,
                is_active: editIsActive,
                temperature: editTemperature,
                seed: editSeed,
                min_search_score: editMinSearchScore,
                max_search_results: editMaxSearchResults,
                max_tokens: editMaxTokens,
                groups: editGroups
            };

            // 🆕 อัปเดต cache current agent config ใน localStorage ถ้า agent นี้แมทช์กับ activeGroup ของใคร
            updateActiveAgentConfigsCache(updatedAgent);

            setMessage("Agent updated successfully");
            setOpenSuccess(true);
            setEditOpen(false);
            setEditingAgent(null);
            setEditGroups([]);

            fetchAgents();
        } catch (e: any) {
            if (e.error === "some groups are already used by another agent") {
                // 🆕 แสดงข้อความละเอียดขึ้น พร้อมชื่อ agent ที่ชน
                setMessage(e.error);
            } else if (typeof e.error === "string") {
                setMessage(e.error);
            } else {
                setMessage("Failed to update agent");
            }
            setOpenError(true);
        } finally {
            setUpdating(false);
        }
    };

    // helper: แสดงชื่อ group ที่ agent มี
    const getGroupNames = (agent: AgentConfig) => {
        const arr = agent.groups ?? [];
        if (!arr.length) return "";
        return arr.map(g => g.name).join(", ");
    };

    // Columns
    const columns: GridColDef<AgentConfig>[] = [
        { field: "name", headerName: "Agent Name", flex: 1, editable: false },
        { field: "description", headerName: "Description", flex: 0.5, editable: false },
        // {
        //     field: "temperature",
        //     headerName: "Temperature",
        //     width: 130,
        //     // type: "number",
        //     editable: false,
        //     valueFormatter: (params: any) => {
        //         const v = params;

        //         if (v == null || v === "") return "0.00";
        //         const num = Number(v);
        //         return Number.isFinite(num) ? num.toFixed(2) : String(v);
        //     }
        // },
        // {
        //     field: "seed",
        //     headerName: "Seed",
        //     width: 120,
        //     // type: "number",
        //     editable: false,
        //     valueFormatter: (params: any) => {
        //         const v = params;
        //         if (v == null || v === "") return "0";
        //         const num = Number(v);
        //         return Number.isFinite(num) ? num.toString() : String(v);
        //     }
        // },
        // {
        //     field: "min_search_score",
        //     headerName: "Min search score",
        //     width: 160,
        //     editable: false
        // },
        // {
        //     field: "max_search_results",
        //     headerName: "Search results",
        //     width: 160,
        //     editable: false
        // },
        {
            field: "groups",
            headerName: "Groups",
            flex: 1.5,
            sortable: false,
            filterable: false,
            renderCell: params => {
                const label = getGroupNames(params.row); // ใช้ helper ด้านบน
                return (
                    <span
                        style={{
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            width: "100%"
                        }}
                    >
                        {label || "-"}
                    </span>
                );
            }
        },
        // {
        //     field: "is_active",
        //     headerName: "Active",
        //     width: 120,
        //     editable: false,
        //     type: "boolean",
        //     renderCell: params => {
        //         const active = params.row.is_active;

        //         return (
        //             <Box
        //                 sx={{
        //                     width: 14,
        //                     height: 14,
        //                     borderRadius: "50%",
        //                     bgcolor: active ? "#4caf50" : "#9e9e9e",
        //                     margin: "0 auto"
        //                 }}
        //             />
        //         );
        //     }
        // },
        {
            field: "actions",
            headerName: "Actions",
            width: 140,
            sortable: false,
            filterable: false,
            renderCell: params => {
                const id = params.row._id;
                return (
                    <Box sx={{ display: "flex", gap: 1 }}>
                        <IconButton onClick={() => handleOpenEdit(params.row)} disabled={!id}>
                            <EditIcon />
                        </IconButton>
                        <IconButton color="error" onClick={() => id && handleDeleteRequest(id)} disabled={!id}>
                            <DeleteIcon />
                        </IconButton>
                    </Box>
                );
            }
        }
    ];

    // Helpers สำหรับ multi select (Add / Edit)
    const mapSelectedIdsToGroups = (ids: string[]) => groups.filter(g => ids.includes(g._id));

    const getIdsFromGroups = (gs: GroupDetail[]) => gs.map(g => g._id);

    const updateActiveAgentConfigsCache = (updatedAgent: AgentConfig) => {
        try {
            const rawGroups = localStorage.getItem("activeGroups");
            if (!rawGroups) return;

            // activeGroups: { [username]: GroupDetail }
            const activeGroups: Record<string, GroupDetail> = JSON.parse(rawGroups);

            const rawConfigs = localStorage.getItem("activeAgentConfigs") || "{}";
            const activeConfigs: Record<string, any> = JSON.parse(rawConfigs);

            const agentGroupIds = (updatedAgent.groups ?? []).map(g => g._id);

            Object.entries(activeGroups).forEach(([username, group]) => {
                if (!group) return;

                const userGroupId = group._id;
                const currentConfig = activeConfigs[username];

                if (agentGroupIds.includes(userGroupId)) {
                    // ✅ เคสที่ 1:
                    // activeGroup ของ user ตอนนี้อยู่ใน groups ของ updatedAgent
                    // → ไม่ว่าจะเคยมี config หรือไม่ ให้เซ็ตเป็น updatedAgent ไปเลย
                    activeConfigs[username] = updatedAgent;
                } else {
                    // ✅ เคสที่ 2:
                    // activeGroup ของ user ไม่ได้อยู่ใน groups ของ updatedAgent
                    // → ลบเฉพาะกรณีที่เคย cache agent ตัวนี้อยู่ (กันลบของ agent อื่น)
                    if (currentConfig && currentConfig._id === updatedAgent._id) {
                        delete activeConfigs[username];
                    }
                }
            });

            localStorage.setItem("activeAgentConfigs", JSON.stringify(activeConfigs));
        } catch (err) {
            console.error("Failed to update activeAgentConfigs cache:", err);
        }
    };

    // 🆕 ลบ cache current agent config ของทุก user ที่ใช้ agentId นี้อยู่
    const removeAgentFromActiveConfigs = (agentId: string) => {
        try {
            const rawConfigs = localStorage.getItem("activeAgentConfigs") || "{}";
            const activeConfigs: Record<string, any> = JSON.parse(rawConfigs);

            let changed = false;

            Object.entries(activeConfigs).forEach(([username, config]) => {
                if (config && config._id === agentId) {
                    delete activeConfigs[username];
                    changed = true;
                }
            });

            if (changed) {
                localStorage.setItem("activeAgentConfigs", JSON.stringify(activeConfigs));
            }
        } catch (err) {
            console.error("Failed to remove agent from activeAgentConfigs:", err);
        }
    };

    return (
        <Box className={styles.root}>
            {/* Search bar */}
            <Box className={styles.searchRow} sx={{ mb: 2, display: "flex", alignItems: "center" }}>
                <TextField
                    placeholder="Search Agent"
                    variant="outlined"
                    size="small"
                    fullWidth
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    sx={{ mr: 2 }}
                />
            </Box>

            {/* Add button */}
            <Box className={styles.toolbarRow} sx={{ mb: 2 }}>
                <Button icon={<AddIcon />} onClick={() => setAddOpen(true)}>
                    Add Agent
                </Button>
            </Box>

            {/* DataGrid */}
            {loading ? (
                <Box sx={{ display: "flex", justifyContent: "center", minHeight: 200 }}>
                    <CircularProgress />
                </Box>
            ) : (
                <DataGrid
                    rows={filteredAgents}
                    columns={columns}
                    getRowId={row => row._id ?? crypto.randomUUID()}
                    paginationModel={paginationModel}
                    onPaginationModelChange={setPaginationModel}
                    pageSizeOptions={[5]}
                    disableRowSelectionOnClick
                    autoHeight
                />
            )}

            {/* Dialog: Add Agent */}
            <Dialog open={addOpen} onClose={() => !creating && setAddOpen(false)} fullWidth maxWidth="sm">
                <DialogTitle>Add Agent</DialogTitle>
                <DialogContent>
                    {creating ? (
                        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
                            <TextField disabled label="Agent Name" value={newName} onChange={e => setNewName(e.target.value)} fullWidth />

                            <TextField
                                disabled
                                label="Description"
                                value={newDescription}
                                onChange={e => setNewDescription(e.target.value)}
                                fullWidth
                                multiline
                                minRows={2}
                            />

                            <TextField
                                disabled
                                label="Temperature"
                                type="number"
                                inputProps={{ step: "0.1" }}
                                value={newTemperature}
                                onChange={e => setNewTemperature(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                disabled
                                label="Seed"
                                type="number"
                                value={newSeed ?? ""}
                                onChange={e => setNewSeed(e.target.value === "" ? null : Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                disabled
                                label="Minimum search score"
                                type="number"
                                inputProps={{ step: "0.1" }}
                                value={newMinSearchScore}
                                onChange={e => setNewMinSearchScore(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                disabled
                                label="Retrieve this many search results"
                                type="number"
                                value={newMaxSearchResults}
                                onChange={e => setNewMaxSearchResults(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                disabled
                                label="Max tokens"
                                type="number"
                                value={newMaxTokens}
                                onChange={e => setNewMaxTokens(Number(e.target.value))}
                                fullWidth
                            />

                            {/* 🆕 Multi select groups (Add) */}
                            <FormControl fullWidth disabled>
                                <InputLabel id="groups-add-label">Groups</InputLabel>
                                <Select
                                    labelId="groups-add-label"
                                    multiple
                                    label="Groups"
                                    value={getIdsFromGroups(newGroups)}
                                    onChange={e => {
                                        const selectedIds = e.target.value as string[];
                                        const selectedGroups = mapSelectedIdsToGroups(selectedIds);
                                        setNewGroups(selectedGroups);
                                    }}
                                    renderValue={selected => {
                                        const ids = selected as string[];
                                        return mapSelectedIdsToGroups(ids)
                                            .map(g => g.name)
                                            .join(", ");
                                    }}
                                >
                                    {groups.map(g => (
                                        <MenuItem key={g._id} value={g._id}>
                                            {g.name} ({g.agent_name})
                                        </MenuItem>
                                    ))}
                                </Select>
                                <FormHelperText>Select one or more groups</FormHelperText>
                            </FormControl>

                            {/* <FormControl fullWidth disabled>
                                <InputLabel id="active-label">Status</InputLabel>
                                <Select
                                    labelId="active-label"
                                    label="Status"
                                    value={newIsActive ? "active" : "inactive"}
                                    onChange={e => setNewIsActive(e.target.value === "active")}
                                >
                                    <MenuItem value="active">Active</MenuItem>
                                    <MenuItem value="inactive">Inactive</MenuItem>
                                </Select>
                                <FormHelperText>Set initial status of this agent</FormHelperText>
                            </FormControl> */}
                        </Box>
                    ) : (
                        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
                            <TextField label="Agent Name" value={newName} onChange={e => setNewName(e.target.value)} fullWidth />

                            <TextField
                                label="Description"
                                value={newDescription}
                                onChange={e => setNewDescription(e.target.value)}
                                fullWidth
                                multiline
                                minRows={2}
                            />

                            <TextField
                                label="Temperature"
                                type="number"
                                inputProps={{ step: "0.1" }}
                                value={newTemperature}
                                onChange={e => setNewTemperature(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                label="Seed"
                                type="number"
                                value={newSeed ?? ""}
                                onChange={e => setNewSeed(e.target.value === "" ? null : Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                label="Minimum search score"
                                type="number"
                                inputProps={{ step: "0.1" }}
                                value={newMinSearchScore}
                                onChange={e => setNewMinSearchScore(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                label="Retrieve this many search results"
                                type="number"
                                value={newMaxSearchResults}
                                onChange={e => setNewMaxSearchResults(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                label="Max tokens"
                                type="number"
                                value={newMaxTokens}
                                onChange={e => setNewMaxTokens(Number(e.target.value))}
                                fullWidth
                            />

                            {/* 🆕 Multi select groups (Add) */}
                            <FormControl fullWidth>
                                <InputLabel id="groups-add-label">Groups</InputLabel>
                                <Select
                                    labelId="groups-add-label"
                                    multiple
                                    label="Groups"
                                    value={getIdsFromGroups(newGroups)}
                                    onChange={e => {
                                        const selectedIds = e.target.value as string[];
                                        const selectedGroups = mapSelectedIdsToGroups(selectedIds);
                                        setNewGroups(selectedGroups);
                                    }}
                                    renderValue={selected => {
                                        const ids = selected as string[];
                                        return mapSelectedIdsToGroups(ids)
                                            .map(g => g.name)
                                            .join(", ");
                                    }}
                                >
                                    {groups.map(g => (
                                        <MenuItem key={g._id} value={g._id}>
                                            {g.name} ({g.agent_name})
                                        </MenuItem>
                                    ))}
                                </Select>
                                <FormHelperText>Select one or more groups</FormHelperText>
                            </FormControl>

                            {/* <FormControl fullWidth>
                                <InputLabel id="active-label">Status</InputLabel>
                                <Select
                                    labelId="active-label"
                                    label="Status"
                                    value={newIsActive ? "active" : "inactive"}
                                    onChange={e => setNewIsActive(e.target.value === "active")}
                                >
                                    <MenuItem value="active">Active</MenuItem>
                                    <MenuItem value="inactive">Inactive</MenuItem>
                                </Select>
                                <FormHelperText>Set initial status of this agent</FormHelperText>
                            </FormControl> */}
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <ButtonMUI onClick={() => setAddOpen(false)} disabled={creating}>
                        Cancel
                    </ButtonMUI>
                    <ButtonMUI onClick={handleCreateAgent} variant="contained" disabled={creating} startIcon={creating ? <CircularProgress size={20} /> : null}>
                        {creating ? "Creating..." : "Create"}
                    </ButtonMUI>
                </DialogActions>

                <Snackbar
                    open={openError}
                    autoHideDuration={5000}
                    anchorOrigin={{ vertical: "top", horizontal: "right" }}
                    onClose={() => setOpenError(false)}
                    sx={{ zIndex: 99999 }}
                >
                    <Alert severity="error" onClose={() => setOpenError(false)} sx={{ width: "100%" }}>
                        {message}
                    </Alert>
                </Snackbar>
            </Dialog>

            {/* Dialog: Edit Agent */}
            <Dialog open={editOpen} onClose={handleCloseEdit} fullWidth maxWidth="sm">
                <DialogTitle>Edit Agent{editingAgent?.name ? `: ${editingAgent.name}` : ""}</DialogTitle>
                <DialogContent>
                    {updating ? (
                        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
                            <TextField disabled label="Agent Name" value={editName} onChange={e => setEditName(e.target.value)} fullWidth />

                            <TextField
                                disabled
                                label="Description"
                                value={editDescription}
                                onChange={e => setEditDescription(e.target.value)}
                                fullWidth
                                multiline
                                minRows={2}
                            />

                            <TextField
                                disabled
                                label="Temperature"
                                type="number"
                                inputProps={{ step: "0.1" }}
                                value={editTemperature}
                                onChange={e => setEditTemperature(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                disabled
                                label="Seed"
                                type="number"
                                value={editSeed ?? ""}
                                onChange={e => setEditSeed(e.target.value === "" ? null : Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                disabled
                                label="Minimum search score"
                                type="number"
                                inputProps={{ step: "0.1" }}
                                value={editMinSearchScore}
                                onChange={e => setEditMinSearchScore(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                disabled
                                label="Retrieve this many search results"
                                type="number"
                                value={editMaxSearchResults}
                                onChange={e => setEditMaxSearchResults(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                disabled
                                label="Max tokens"
                                type="number"
                                value={editMaxTokens}
                                onChange={e => setEditMaxTokens(Number(e.target.value))}
                                fullWidth
                            />

                            {/* 🆕 Multi select groups (Edit) */}
                            <FormControl fullWidth disabled>
                                <InputLabel id="groups-edit-label">Groups</InputLabel>
                                <Select
                                    labelId="groups-edit-label"
                                    multiple
                                    label="Groups"
                                    value={getIdsFromGroups(editGroups)}
                                    onChange={e => {
                                        const selectedIds = e.target.value as string[];
                                        const selectedGroups = mapSelectedIdsToGroups(selectedIds);
                                        setEditGroups(selectedGroups);
                                    }}
                                    renderValue={selected => {
                                        const ids = selected as string[];
                                        return mapSelectedIdsToGroups(ids)
                                            .map(g => g.name)
                                            .join(", ");
                                    }}
                                >
                                    {groups.map(g => (
                                        <MenuItem key={g._id} value={g._id}>
                                            {g.name} ({g.agent_name})
                                        </MenuItem>
                                    ))}
                                </Select>
                                <FormHelperText>Select one or more groups</FormHelperText>
                            </FormControl>

                            {/* <FormControl fullWidth disabled>
                                <InputLabel id="edit-active-label">Status</InputLabel>
                                <Select
                                    labelId="edit-active-label"
                                    label="Status"
                                    value={editIsActive ? "active" : "inactive"}
                                    onChange={e => setEditIsActive(e.target.value === "active")}
                                >
                                    <MenuItem value="active">Active</MenuItem>
                                    <MenuItem value="inactive">Inactive</MenuItem>
                                </Select>
                                <FormHelperText>Set status of this agent</FormHelperText>
                            </FormControl> */}
                        </Box>
                    ) : (
                        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
                            <TextField label="Agent Name" value={editName} onChange={e => setEditName(e.target.value)} fullWidth />

                            <TextField
                                label="Description"
                                value={editDescription}
                                onChange={e => setEditDescription(e.target.value)}
                                fullWidth
                                multiline
                                minRows={2}
                            />

                            <TextField
                                label="Temperature"
                                type="number"
                                inputProps={{ step: "0.1" }}
                                value={editTemperature}
                                onChange={e => setEditTemperature(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                label="Seed"
                                type="number"
                                value={editSeed ?? ""}
                                onChange={e => setEditSeed(e.target.value === "" ? null : Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                label="Minimum search score"
                                type="number"
                                inputProps={{ step: "0.1" }}
                                value={editMinSearchScore}
                                onChange={e => setEditMinSearchScore(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                label="Retrieve this many search results"
                                type="number"
                                value={editMaxSearchResults}
                                onChange={e => setEditMaxSearchResults(Number(e.target.value))}
                                fullWidth
                            />

                            <TextField
                                label="Max tokens"
                                type="number"
                                value={editMaxTokens}
                                onChange={e => setEditMaxTokens(Number(e.target.value))}
                                fullWidth
                            />

                            {/* 🆕 Multi select groups (Edit) */}
                            <FormControl fullWidth>
                                <InputLabel id="groups-edit-label">Groups</InputLabel>
                                <Select
                                    labelId="groups-edit-label"
                                    multiple
                                    label="Groups"
                                    value={getIdsFromGroups(editGroups)}
                                    onChange={e => {
                                        const selectedIds = e.target.value as string[];
                                        const selectedGroups = mapSelectedIdsToGroups(selectedIds);
                                        setEditGroups(selectedGroups);
                                    }}
                                    renderValue={selected => {
                                        const ids = selected as string[];
                                        return mapSelectedIdsToGroups(ids)
                                            .map(g => g.name)
                                            .join(", ");
                                    }}
                                >
                                    {groups.map(g => (
                                        <MenuItem key={g._id} value={g._id}>
                                            {g.name} ({g.agent_name})
                                        </MenuItem>
                                    ))}
                                </Select>
                                <FormHelperText>Select one or more groups</FormHelperText>
                            </FormControl>

                            {/* <FormControl fullWidth>
                                <InputLabel id="edit-active-label">Status</InputLabel>
                                <Select
                                    labelId="edit-active-label"
                                    label="Status"
                                    value={editIsActive ? "active" : "inactive"}
                                    onChange={e => setEditIsActive(e.target.value === "active")}
                                >
                                    <MenuItem value="active">Active</MenuItem>
                                    <MenuItem value="inactive">Inactive</MenuItem>
                                </Select>
                                <FormHelperText>Set status of this agent</FormHelperText>
                            </FormControl> */}
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <ButtonMUI onClick={handleCloseEdit} disabled={updating}>
                        Cancel
                    </ButtonMUI>
                    <ButtonMUI onClick={handleSaveEdit} variant="contained" disabled={updating} startIcon={updating ? <CircularProgress size={20} /> : null}>
                        {updating ? "Saving..." : "Save"}
                    </ButtonMUI>
                </DialogActions>
                {/* Snackbar */}

                <Snackbar
                    open={openError}
                    autoHideDuration={5000}
                    anchorOrigin={{ vertical: "top", horizontal: "right" }}
                    onClose={() => setOpenError(false)}
                    sx={{ zIndex: 99999 }}
                >
                    <Alert severity="error" onClose={() => setOpenError(false)} sx={{ width: "100%" }}>
                        {message}
                    </Alert>
                </Snackbar>
            </Dialog>

            {/* Dialog: Confirm delete */}
            <Dialog open={confirmDeleteOpen} onClose={() => !deleting && setConfirmDeleteOpen(false)}>
                <DialogTitle>Confirm Delete</DialogTitle>
                <DialogContent>Are you sure you want to delete this agent?</DialogContent>
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

                <Snackbar
                    open={openError}
                    autoHideDuration={5000}
                    anchorOrigin={{ vertical: "top", horizontal: "right" }}
                    onClose={() => setOpenError(false)}
                    sx={{ zIndex: 99999 }}
                >
                    <Alert severity="error" onClose={() => setOpenError(false)} sx={{ width: "100%" }}>
                        {message}
                    </Alert>
                </Snackbar>
            </Dialog>

            <Snackbar
                open={openSuccess}
                autoHideDuration={3000}
                anchorOrigin={{ vertical: "top", horizontal: "right" }}
                onClose={() => setOpenSuccess(false)}
                sx={{ zIndex: 99999 }}
            >
                <Alert severity="success" onClose={() => setOpenSuccess(false)} sx={{ width: "100%" }}>
                    {message}
                </Alert>
            </Snackbar>
        </Box>
    );
};
