import React, { useEffect, useState, ChangeEvent } from "react";
import {
    Box,
    TextField,
    IconButton,
    CircularProgress,
    Snackbar,
    Alert,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button as ButtonMUI,
    Tooltip
} from "@mui/material";
import { DataGrid, GridColDef, GridRowModesModel, GridRowModes, GridPaginationModel } from "@mui/x-data-grid";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import SaveIcon from "@mui/icons-material/Save";
import CancelIcon from "@mui/icons-material/Cancel";
import { getToken } from "../../authConfig";
import { useMsal } from "@azure/msal-react";
import { listGroupsApi, createGroupApi, updateGroupApi, deleteGroupApi } from "../../api";
import { GroupDetail } from "../../api/models";
import { Button } from "@fluentui/react-components";
import { useContext } from "react";
import { LoginContext } from "../../loginContext";
import { getFixedPromptsApi } from "../../api/api";

export const GroupManagement: React.FC = () => {
    const client = useMsal().instance;
    const [groups, setGroups] = useState<GroupDetail[]>([]);
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState("");
    const [rowModesModel, setRowModesModel] = useState<GridRowModesModel>({});
    const [savingRowId, setSavingRowId] = useState<string | null>(null);
    const [allGroups, setAllGroups] = useState<GroupDetail[]>([]);
    const [openSuccess, setOpenSuccess] = useState(false);
    const [openError, setOpenError] = useState(false);
    const [message, setMessage] = useState<string | null>(null);
    const [finalPrompt, setFinalPrompt] = useState<string>("");
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [deleteId, setDeleteId] = useState<string | null>(null);
    const [deleting, setDeleting] = useState(false);
    const { userDetails } = useContext(LoginContext);
    const [addOpen, setAddOpen] = useState(false);
    const defaultGroupPromt = {
        role: "{บทบาท / Persona}",
        task: "หน้าที่ของคุณคือ {สิ่งที่อยากให้ทำ}",
        detail_context: "- {รายละเอียดสำคัญ}\n- {ข้อมูลเพิ่มเติม / เงื่อนไข}\n- {โทนภาษา / กลุ่มเป้าหมาย}",
        output_format: "กรุณาตอบกลับในรูปแบบ: {เช่น bullet points, ตาราง,\n โค้ด, ย่อหน้า, บทความสั้น}",
        constraints: "- {จำนวนคำ / ภาษาที่ใช้ / สิ่งที่ห้ามทำ}"
    };

    const [newGroup, setNewGroup] = useState<GroupDetail>({
        _id: "",
        name: "",
        agent_name: "",
        group_promt: defaultGroupPromt,
        create_at: "",
        update_at: "",
        delete_at: null
    });

    const [creating, setCreating] = useState(false);
    // state สำหรับแก้ไข
    const [editOpen, setEditOpen] = useState(false);
    const [editGroup, setEditGroup] = useState<GroupDetail | null>(null);
    const [saving, setSaving] = useState(false);

    // state
    const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
        page: 0,
        pageSize: 5
    });

    const previewColors = {
        heading: "#00ff00", // เขียวอ่อน สำหรับหัวข้อ
        value: "#00ff00" // เขียวสด สำหรับค่าด้านใน
    };

    // โหลด groups
    const fetchGroups = async () => {
        try {
            setLoading(true);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            const groupList: GroupDetail[] = await listGroupsApi(token);
            setAllGroups(groupList);
            setGroups(groupList);
        } catch (e) {
            console.error(e);
            setMessage("Failed to load groups");
            setOpenError(true);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchGroups();
    }, []);

    useEffect(() => {
        if (search) {
            setGroups(allGroups.filter(g => g.name.toLowerCase().includes(search.toLowerCase())));
        } else {
            setGroups(allGroups);
        }
    }, [search, allGroups]);

    // Update row
    const processRowUpdate = async (newRow: GroupDetail, oldRow: GroupDetail) => {
        setSavingRowId(newRow._id);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            await updateGroupApi(newRow._id, newRow.name, token);
            setMessage("Group updated successfully");
            setOpenSuccess(true);
            return newRow;
        } catch (e) {
            console.error(e);
            setMessage("Failed to update group");
            setOpenError(true);
            return oldRow;
        } finally {
            setSavingRowId(null);
            fetchGroups();
        }
    };

    // Delete group
    const handleDelete = async (id: string) => {
        setDeleting(true);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            await deleteGroupApi(id, token);
            setMessage("Group deleted successfully");
            setOpenSuccess(true);
            fetchGroups();
            setConfirmOpen(false); // ✅ ปิด dialog หลังลบเสร็จ
        } catch (e) {
            console.error(e);
            setMessage("Failed to delete group");
            setOpenError(true);
        } finally {
            setDeleting(false);
            setDeleteId(null);
        }
    };

    const handleCreateGroup = async () => {
        setCreating(true);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            await createGroupApi(newGroup.name, token, newGroup.agent_name, {
                role: normalizePrompt(newGroup.group_promt.role),
                task: normalizePrompt(newGroup.group_promt.task),
                detail_context: normalizePrompt(newGroup.group_promt.detail_context, true), // 👈 บังคับ multiLine
                output_format: normalizePrompt(newGroup.group_promt.output_format),
                constraints: normalizePrompt(newGroup.group_promt.constraints, true) // 👈 บังคับ multiLine
            });

            setMessage("Group created successfully");
            setOpenSuccess(true);
            setAddOpen(false);

            // reset state
            setNewGroup({
                _id: "",
                name: "",
                group_promt: defaultGroupPromt,
                create_at: "",
                update_at: "",
                delete_at: null
            });

            fetchGroups();
        } catch (e) {
            console.error(e);
            setMessage("Failed to create group");
            setOpenError(true);
        } finally {
            setCreating(false);
        }
    };

    const normalizePrompt = (text: string, multiLine: boolean = false): string => {
        if (!text) return "";

        let result = text.trim();

        if (multiLine && !result.includes("\n")) {
            // split ได้ทั้ง -, , ; . และ space
            const parts = result
                .split(/[;|]/) // 👈 รวมทุก delimiter
                .map(p => p.trim())
                .filter(p => p.length > 0);

            if (parts.length > 1) {
                result = parts.map(p => `- ${p}`).join("\n");
            } else {
                result = `- ${result}`;
            }
        }

        return result;
    };

    const buildPrompt = (promt: any, withSuffix: boolean = true): string => {
        let result = "";

        // 👇 รองรับหลาย role โดย split ด้วย ; หรือ |
        if (promt.role) {
            const roles = promt.role
                .split(/[;|]/)
                .map((r: string) => r.trim())
                .filter((r: string) => r.length > 0);

            if (roles.length === 1) {
                result += `You are ${roles[0]}.\n\n`;
            } else if (roles.length > 1) {
                result += `You are ${roles.slice(0, -1).join(", ")} and ${roles[roles.length - 1]}.\n\n`;
            }
        }

        if (promt.task) {
            result += `Your task is ${promt.task}.\n\n`;
        }
        if (promt.detail_context) {
            result += `Consider the following details:\n${promt.detail_context}\n\n`;
        }
        if (promt.output_format) {
            result += `Please answer in this format: ${promt.output_format}.\n\n`;
        }
        if (promt.constraints) {
            result += `Constraints:\n${promt.constraints}\n\n`;
        }

        return result.trim();
    };

    // 🆕 persist activeGroups & activePrompts สำหรับ user ปัจจุบัน (ต่อท้าย suffix ที่ดึงจาก API)
    const updateActiveGroupInLocalStorage = async (group: GroupDetail) => {
        try {
            // ต้องมี token เพื่อเรียก suffix
            const token = await getToken(client);
            if (!token) return;

            // เอา username จาก context (เหมือน key ที่ใช้ใน LoginButton)
            const name = userDetails?.name || "";
            if (!name) return;

            const savedGroups = JSON.parse(localStorage.getItem("activeGroups") || "{}");
            const savedPrompts = JSON.parse(localStorage.getItem("activePrompts") || "{}");

            // ทำเฉพาะกรณี group ที่แก้ = activeGroup ปัจจุบัน
            const active = savedGroups[name];
            if (!active || active._id !== group._id) return;

            // ดึง suffix ปัจจุบันจาก API
            let suffix = "";
            try {
                const res = await getFixedPromptsApi(token);
                suffix = res?.fixed_prompt || "";
            } catch (e) {
                console.warn("getFixedPromptsApi failed in GroupManagement; fallback to empty suffix.", e);
            }

            // ใช้ base prompt เดิมที่มี (ไม่ต่อ suffix ในนี้)
            const base = buildPrompt(group.group_promt, false);
            const finalPrompt = `${base}${base && suffix ? "\n\n" : ""}${suffix}`.trim();

            // เขียนกลับ localStorage
            savedGroups[name] = group;
            savedPrompts[name] = finalPrompt;
            localStorage.setItem("activeGroups", JSON.stringify(savedGroups));
            localStorage.setItem("activePrompts", JSON.stringify(savedPrompts));

            console.log("🔄 Updated activeGroups & activePrompts for current user (with suffix).");
        } catch (e) {
            console.error("updateActiveGroupInLocalStorage failed:", e);
        }
    };

    const columns: GridColDef<GroupDetail>[] = [
        { field: "name", headerName: "Name", flex: 1, editable: true },
        { field: "agent_name", headerName: "Agent Name", flex: 1 },
        {
            field: "group_promt",
            headerName: "Data Group Prompt", // 👈 เปลี่ยนชื่อ column
            flex: 2,
            renderCell: params => {
                const prompt = params.value || {};
                const fullText = [
                    `role: ${prompt.role || "-"}`,
                    `task: ${prompt.task || "-"}`,
                    `detail_context: ${prompt.detail_context || "-"}`,
                    `output_format: ${prompt.output_format || "-"}`,
                    `constraints: ${prompt.constraints || "-"}`
                ].join("\n");

                // 👇 ใช้แสดงใน cell (ถ้ายาวเกิน 80 ตัวอักษรให้ตัดแล้วใส่ ...)
                const preview = fullText.length > 80 ? fullText.substring(0, 80) + "..." : fullText;

                return (
                    <Tooltip
                        title={
                            <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 12 }}>
                                role
                                {"\n"}
                                {`"${prompt.role || "-"}"`}
                                {"\n"}task
                                {"\n"}
                                {`"${prompt.task || "-"}"`}
                                {"\n"}detail_context
                                {"\n"}
                                {`"${prompt.detail_context || "-"}"`}
                                {"\n"}output_format
                                {"\n"}
                                {`"${prompt.output_format || "-"}"`}
                                {"\n"}constraints
                                {"\n"}
                                {`"${prompt.constraints || "-"}"`}
                            </pre>
                        }
                    >
                        <span
                            style={{
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                maxWidth: "100%",
                                display: "inline-block"
                            }}
                        >
                            {preview}
                        </span>
                    </Tooltip>
                );
            }
        },
        {
            field: "actions",
            headerName: "Actions",
            width: 120,
            renderCell: params => {
                const isInEditMode = rowModesModel[params.row._id]?.mode === GridRowModes.Edit;
                const isSaving = savingRowId === params.row._id;

                return (
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        {isInEditMode ? (
                            <>
                                <IconButton
                                    color="primary"
                                    onClick={() => setRowModesModel({ ...rowModesModel, [params.row._id]: { mode: GridRowModes.View } })}
                                >
                                    <SaveIcon />
                                </IconButton>
                                <IconButton
                                    color="inherit"
                                    onClick={() =>
                                        setRowModesModel({ ...rowModesModel, [params.row._id]: { mode: GridRowModes.View, ignoreModifications: true } })
                                    }
                                >
                                    <CancelIcon />
                                </IconButton>
                            </>
                        ) : (
                            <>
                                <IconButton
                                    color="primary"
                                    onClick={() => {
                                        setEditGroup({
                                            ...params.row,
                                            group_promt: params.row.group_promt || {
                                                role: "",
                                                task: "",
                                                detail_context: "",
                                                output_format: "",
                                                constraints: ""
                                            }
                                        });
                                        console.log(params.row);
                                        console.log("aaaaa", params.row.group_promt);

                                        setEditOpen(true);
                                    }}
                                >
                                    <EditIcon />
                                </IconButton>

                                <IconButton
                                    color="error"
                                    onClick={() => {
                                        setDeleteId(params.row._id);
                                        setConfirmOpen(true);
                                    }}
                                >
                                    <DeleteIcon />
                                </IconButton>
                            </>
                        )}
                    </Box>
                );
            }
        }
    ];

    const handleUpdateGroup = async () => {
        if (!editGroup) return;
        setSaving(true);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            await updateGroupApi(
                editGroup._id,
                editGroup.name,
                token,
                {
                    role: normalizePrompt(editGroup.group_promt.role),
                    task: normalizePrompt(editGroup.group_promt.task),
                    detail_context: normalizePrompt(editGroup.group_promt.detail_context, true),
                    output_format: normalizePrompt(editGroup.group_promt.output_format),
                    constraints: normalizePrompt(editGroup.group_promt.constraints, true)
                },
                editGroup.agent_name
            );

            await updateActiveGroupInLocalStorage(editGroup);

            setMessage("Source updated successfully");
            setOpenSuccess(true);
            fetchGroups();
            setEditOpen(false);
        } catch (e) {
            console.error(e);
            setMessage("Failed to update source");
            setOpenError(true);
        } finally {
            setSaving(false);
        }
    };

    useEffect(() => {
        if (newGroup) {
            setFinalPrompt(buildPrompt(newGroup.group_promt, false));
        }
    }, [newGroup]);

    useEffect(() => {
        if (editGroup) {
            setFinalPrompt(buildPrompt(editGroup.group_promt, false));
        }
    }, [editGroup]);

    return (
        <Box>
            <Box sx={{ mb: 2, display: "flex", alignItems: "center" }}>
                <TextField
                    placeholder="Search Data Group"
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
                    Add Data Group
                </Button>
            </Box>

            {loading ? (
                <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "200px" }}>
                    <CircularProgress />
                </Box>
            ) : (
                <DataGrid
                    rows={groups}
                    columns={columns}
                    getRowId={row => row._id}
                    autoHeight
                    disableRowSelectionOnClick
                    processRowUpdate={processRowUpdate}
                    rowModesModel={rowModesModel}
                    onRowModesModelChange={setRowModesModel}
                    paginationModel={paginationModel}
                    onPaginationModelChange={setPaginationModel}
                    pageSizeOptions={[5]} // 👈 ให้เลือกได้ 5 (จะเพิ่ม 10, 20 ก็ได้)
                    pagination
                />
            )}

            {/* Snackbar */}
            <Snackbar open={openSuccess} autoHideDuration={3000} onClose={() => setOpenSuccess(false)}>
                <Alert severity="success">{message}</Alert>
            </Snackbar>
            <Snackbar open={openError} autoHideDuration={3000} onClose={() => setOpenError(false)}>
                <Alert severity="error">{message}</Alert>
            </Snackbar>

            {/* Add Group Dialog */}
            <Dialog open={addOpen} onClose={() => setAddOpen(false)} fullWidth maxWidth="md">
                <DialogTitle>Add Data Group</DialogTitle>
                <DialogContent>
                    <Box sx={{ display: "flex", gap: 3, mt: 1 }}>
                        {/* Left Form */}
                        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
                            <TextField
                                label="Data Group Name"
                                value={newGroup.name}
                                onChange={e => setNewGroup({ ...newGroup, name: e.target.value })}
                                fullWidth
                            />
                            <TextField
                                label="Agent Name"
                                value={newGroup.agent_name}
                                onChange={e => setNewGroup({ ...newGroup, agent_name: e.target.value })}
                                fullWidth
                            />
                            <TextField
                                label="Role"
                                value={newGroup.group_promt.role}
                                onChange={e =>
                                    setNewGroup({
                                        ...newGroup,
                                        group_promt: { ...newGroup.group_promt, role: e.target.value }
                                    })
                                }
                                placeholder="e.g.: Python Expert; ML Teaching Assistant"
                                helperText="Use ';' or '|' to separate multiple roles"
                                fullWidth
                            />
                            <TextField
                                label="Task"
                                value={newGroup.group_promt.task}
                                onChange={e =>
                                    setNewGroup({
                                        ...newGroup,
                                        group_promt: { ...newGroup.group_promt, task: e.target.value }
                                    })
                                }
                                fullWidth
                            />
                            <TextField
                                label="Detail Context"
                                multiline
                                rows={3}
                                value={newGroup.group_promt.detail_context}
                                onChange={e =>
                                    setNewGroup({
                                        ...newGroup,
                                        group_promt: { ...newGroup.group_promt, detail_context: e.target.value }
                                    })
                                }
                                fullWidth
                                placeholder="e.g. 'Important detail; Additional info; Tone' or 'Item1 | Item2 | Item3'"
                                helperText="Use Enter ';' or '|' to create new lines"
                            />
                            <TextField
                                label="Output Format"
                                value={newGroup.group_promt.output_format}
                                onChange={e =>
                                    setNewGroup({
                                        ...newGroup,
                                        group_promt: { ...newGroup.group_promt, output_format: e.target.value }
                                    })
                                }
                                fullWidth
                            />
                            <TextField
                                label="Constraints"
                                multiline
                                rows={2}
                                value={newGroup.group_promt.constraints}
                                onChange={e =>
                                    setNewGroup({
                                        ...newGroup,
                                        group_promt: { ...newGroup.group_promt, constraints: e.target.value }
                                    })
                                }
                                fullWidth
                                placeholder="e.g. 'Important detail; Additional info; Tone' or 'Item1 | Item2 | Item3'"
                                helperText="Use Enter ';' or '|' to create new lines"
                            />
                        </Box>

                        {/* Right Preview */}
                        <Box
                            sx={{
                                flex: 1,
                                bgcolor: "#1e1e1e",
                                color: "#00ff00",
                                borderRadius: 2,
                                p: 2,
                                fontSize: 13,
                                fontFamily: "monospace",
                                maxHeight: 625,
                                overflowY: "auto",
                                overflowX: "auto"
                            }}
                        >
                            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{finalPrompt}</pre>
                        </Box>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <ButtonMUI onClick={() => setAddOpen(false)}>Cancel</ButtonMUI>
                    <ButtonMUI onClick={handleCreateGroup} color="primary" variant="contained" disabled={creating}>
                        {creating ? "Creating..." : "Create"}
                    </ButtonMUI>
                </DialogActions>
            </Dialog>

            {/* Edit Group Dialog */}
            <Dialog open={editOpen} onClose={() => setEditOpen(false)} fullWidth maxWidth="md">
                <DialogTitle>Edit Data Group</DialogTitle>
                <DialogContent>
                    <Box sx={{ display: "flex", gap: 3, mt: 1 }}>
                        {/* Left: Form */}
                        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
                            <TextField
                                label="Data Group Name"
                                value={editGroup?.name || ""}
                                onChange={e => setEditGroup(editGroup ? { ...editGroup, name: e.target.value } : null)}
                                fullWidth
                            />
                            <TextField
                                label="Agent Name"
                                value={editGroup?.agent_name || ""}
                                onChange={e => setEditGroup(editGroup ? { ...editGroup, agent_name: e.target.value } : null)}
                                fullWidth
                            />
                            <TextField
                                label="Role"
                                value={editGroup?.group_promt?.role || ""}
                                onChange={e =>
                                    setEditGroup(
                                        editGroup
                                            ? {
                                                  ...editGroup,
                                                  group_promt: { ...editGroup.group_promt, role: e.target.value }
                                              }
                                            : null
                                    )
                                }
                                placeholder="e.g.: Python Expert; ML Teaching Assistant"
                                helperText="Use ';' or '|' to separate multiple roles"
                                fullWidth
                            />
                            <TextField
                                label="Task"
                                value={editGroup?.group_promt?.task || ""}
                                onChange={e =>
                                    setEditGroup(
                                        editGroup
                                            ? {
                                                  ...editGroup,
                                                  group_promt: { ...editGroup.group_promt, task: e.target.value }
                                              }
                                            : null
                                    )
                                }
                                fullWidth
                            />
                            <TextField
                                label="Detail Context"
                                value={editGroup?.group_promt?.detail_context || ""}
                                onChange={e =>
                                    setEditGroup(
                                        editGroup
                                            ? {
                                                  ...editGroup,
                                                  group_promt: { ...editGroup.group_promt, detail_context: e.target.value }
                                              }
                                            : null
                                    )
                                }
                                multiline
                                rows={3}
                                fullWidth
                                placeholder="e.g. 'Important detail; Additional info; Tone' or 'Item1 | Item2 | Item3'"
                                helperText="Use Enter ';' or '|' to create new lines"
                            />
                            <TextField
                                label="Output Format"
                                value={editGroup?.group_promt?.output_format || ""}
                                onChange={e =>
                                    setEditGroup(
                                        editGroup
                                            ? {
                                                  ...editGroup,
                                                  group_promt: { ...editGroup.group_promt, output_format: e.target.value }
                                              }
                                            : null
                                    )
                                }
                                fullWidth
                            />
                            <TextField
                                label="Constraints"
                                value={editGroup?.group_promt?.constraints || ""}
                                onChange={e =>
                                    setEditGroup(
                                        editGroup
                                            ? {
                                                  ...editGroup,
                                                  group_promt: { ...editGroup.group_promt, constraints: e.target.value }
                                              }
                                            : null
                                    )
                                }
                                multiline
                                rows={2}
                                fullWidth
                                placeholder="e.g. 'Important detail; Additional info; Tone' or 'Item1 | Item2 | Item3'"
                                helperText="Use Enter ';' or '|' to create new lines"
                            />
                        </Box>

                        {/* Right Preview */}
                        <Box
                            sx={{
                                flex: 1,
                                bgcolor: "#1e1e1e",
                                color: "#00ff00",
                                borderRadius: 2,
                                p: 2,
                                fontSize: 13,
                                fontFamily: "monospace",
                                maxHeight: 625,
                                overflowY: "auto",
                                overflowX: "auto"
                            }}
                        >
                            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{finalPrompt}</pre>
                        </Box>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <ButtonMUI onClick={() => setEditOpen(false)}>Cancel</ButtonMUI>
                    <ButtonMUI
                        onClick={handleUpdateGroup}
                        color="primary"
                        variant="contained"
                        disabled={saving}
                        startIcon={saving ? <CircularProgress size={20} /> : null}
                    >
                        {saving ? "Saving..." : "Save"}
                    </ButtonMUI>
                </DialogActions>
            </Dialog>

            {/* Confirm Delete Dialog */}
            <Dialog open={confirmOpen} onClose={() => !deleting && setConfirmOpen(false)}>
                <DialogTitle>Confirm Delete</DialogTitle>
                <DialogContent>Are you sure you want to delete this group?</DialogContent>
                <DialogActions>
                    <ButtonMUI onClick={() => setConfirmOpen(false)} disabled={deleting}>
                        Cancel
                    </ButtonMUI>
                    <ButtonMUI
                        onClick={() => deleteId && handleDelete(deleteId)}
                        color="error"
                        variant="contained"
                        disabled={deleting}
                        startIcon={deleting ? <CircularProgress size={20} /> : null}
                    >
                        {deleting ? "Deleting..." : "Delete"}
                    </ButtonMUI>
                </DialogActions>
            </Dialog>
        </Box>
    );
};
