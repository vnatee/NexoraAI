import React, { useState, useEffect, ChangeEvent } from "react";
import { Box, TextField, Typography, IconButton, CircularProgress, Snackbar, Alert, Chip, Button as Button2, Tooltip, Skeleton } from "@mui/material";
import { DataGrid, GridColDef, GridPaginationModel, GridValueFormatter } from "@mui/x-data-grid";
import DeleteIcon from "@mui/icons-material/Delete";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import { deleteTeamUploadedFileApi, listUploadedteamFilesApi, limit_size, uploadTeamFileApi, get_data_group_by_team } from "../../api/api";
import { getToken, getUsername } from "../../authConfig";
import { useMsal } from "@azure/msal-react";
import Autocomplete from "@mui/material/Autocomplete";
import { STORAGE_KEYS } from "../../utill/storageKeys";
import { Storage } from "../../utill/storage";
import { TeamProfile } from "../../api";
import { DocumentProcessingUploadSelector } from "../DocumentProcessingUploadSelector/DocumentProcessingUploadSelector";

interface DataGroup {
    _id: string;
    name: string;
    user_id?: string[];
}

interface FileRow {
    id: number | string;
    name?: string;
    folder?: string;
    baseName?: string;
    status?: string;
    isGroup?: boolean;
    folderName?: string;
    fullPath?: string;
    depth?: number;
    uploadedAt?: string;
    size?: number;
    dataGroups?: string[];
}

interface FileTreeNode {
    name: string;
    path: string;
    files: FileRow[];
    folders: Record<string, FileTreeNode>;
}

export const GroupFileUpload: React.FC = () => {
    const client = useMsal().instance;
    const [files, setFiles] = useState<FileRow[]>([]);
    const [searchQuery, setSearchQuery] = useState("");
    const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({ __root__: true });
    const [fileTree, setFileTree] = useState<{ files: FileRow[]; folders: Record<string, FileTreeNode> }>({ files: [], folders: {} });

    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [uploading, setUploading] = useState(false);

    const [deletingFile, setDeletingFile] = useState<string | null>(null);
    const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);

    const [openSuccess, setOpenSuccess] = useState(false);
    const [openError, setOpenError] = useState(false);
    const [message, setMessage] = useState<string | null>(null);

    const [loadingFiles, setLoadingFiles] = useState(false);
    const [hasLoaded, setHasLoaded] = useState(false);

    const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({ pageSize: 10, page: 0 });
    const handleRemoveSelectedFile = (index: number) => setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    const [loadedTeamId, setLoadedTeamId] = useState<string | null>(null);
    const [processingProfileId, setProcessingProfileId] = useState("");

    const generateRowsForGrid = (node: { files: FileRow[]; folders: Record<string, FileTreeNode> }, depth = 0): FileRow[] => {
        let rows: FileRow[] = [];

        // --- Process Subfolders ---
        Object.keys(node.folders)
            .sort()
            .forEach(folderName => {
                const folder = node.folders[folderName];
                rows.push({
                    id: `group-${folder.path}`,
                    isGroup: true,
                    folderName: folder.name,
                    fullPath: folder.path,
                    depth: depth
                });

                if (expandedFolders[folder.path]) {
                    rows.push(...generateRowsForGrid(folder, depth + 1));
                }
            });

        // --- Process Files in the current node ---
        // If at root (depth 0) and files exist, create a collapsible "Root" group
        if (depth === 0 && node.files.length > 0) {
            rows.push({
                id: "group-__root__",
                isGroup: true,
                folderName: "Root", // Name for files without a folder
                fullPath: "__root__",
                depth: depth
            });

            // If the root group is expanded, add its files
            if (expandedFolders["__root__"]) {
                node.files
                    .slice()
                    .sort((a, b) => (a.baseName || "").localeCompare(b.baseName || ""))
                    .forEach(file => {
                        rows.push({ ...file, depth: depth });
                    });
            }
        } else if (depth > 0) {
            // For subfolders, add files directly as they are under an expanded parent
            node.files
                .slice()
                .sort((a, b) => (a.baseName || "").localeCompare(b.baseName || ""))
                .forEach(file => {
                    rows.push({ ...file, depth: depth });
                });
        }

        return rows;
    };
    const rowsWithGroups = generateRowsForGrid(fileTree);
    const [limitSizeConf, setLimitSizeConf] = useState(0);
    const storedSize = files.reduce((sum, f) => sum + (f.size ?? 0), 0);
    const newSize = selectedFiles.reduce((sum, f) => sum + f.size, 0);
    const totalUsed = storedSize + newSize;
    const [dataGroups, setDataGroups] = useState<DataGroup[]>([]);
    const [selectedDataGroupIds, setSelectedDataGroupIds] = useState<string[]>([]);
    const [selectTeamData, setSelectTeamData] = useState<TeamProfile | null>(null);
    const teamId = selectTeamData?._id || "";
    const refreshTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

    const formatFileSize = (bytes?: number) => {
        if (!bytes || bytes <= 0) return "0 B";

        const units = ["B", "KB", "MB", "GB", "TB"];
        let index = 0;
        let size = bytes;

        while (size >= 1024 && index < units.length - 1) {
            size /= 1024;
            index++;
        }

        return `${size.toFixed(2)} ${units[index]}`;
    };

    const fetchLimitSizeConf = async () => {
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            const result = await limit_size(token);
            setLimitSizeConf(result?.size_limit_group || 0);
        } catch (e) {
            console.error(e);
        }
    };

    // โหลดไฟล์จาก API
    const fetchFiles = async () => {
        if (!teamId) return;
        try {
            setLoadingFiles(true);

            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            const result = await listUploadedteamFilesApi(teamId, token);

            const rows: FileRow[] = result.map((fileData: [string, string, string, number, string[]] | string, index: number) => {
                let fileName: string;
                let status: string = "";
                let uploadedAt: string = "";
                let size: number = 0;
                let dataGroups: string[] = [];

                // ✅ รองรับทั้ง string[] และ [filename, status][]
                if (Array.isArray(fileData)) {
                    fileName = fileData[0];
                    status = fileData[1];
                    uploadedAt = fileData[2];
                    size = fileData[3];
                    dataGroups = fileData[4] ?? []; // ✅ data group
                } else {
                    fileName = fileData;
                }

                const parts = fileName.split("/");
                const folder = parts.length > 1 ? parts.slice(0, -1).join("/") : "";
                const baseName = parts[parts.length - 1];

                return {
                    id: index,
                    name: fileName,
                    folder,
                    baseName,
                    status,
                    uploadedAt,
                    size,
                    dataGroups
                };
            });

            setFiles(rows);
        } catch (err) {
            console.error(err);
            setMessage("Failed to load files");
            setOpenError(true);
        } finally {
            setLoadingFiles(false);
        }
    };

    useEffect(() => {
        if (!teamId) return;
        if (loadedTeamId === teamId) return;

        fetchFiles();
        fetchLimitSizeConf();
        setLoadedTeamId(teamId);
    }, [teamId, loadedTeamId]);

    useEffect(() => {
        const buildTree = (fileList: FileRow[]) => {
            const query = searchQuery.trim().toLowerCase();
            const filtered = !query ? fileList : fileList.filter(f => (f.name ?? "").toLowerCase().includes(query));
            const root: { files: FileRow[]; folders: Record<string, FileTreeNode> } = { files: [], folders: {} };

            filtered.forEach(file => {
                if (!file.folder) {
                    root.files.push(file);
                    return;
                }
                const parts = file.folder.split("/");
                let currentLevel = root;
                let currentPath = "";
                parts.forEach(part => {
                    currentPath = currentPath ? `${currentPath}/${part}` : part;
                    if (!currentLevel.folders[part]) {
                        currentLevel.folders[part] = { name: part, path: currentPath, files: [], folders: {} };
                    }
                    currentLevel = currentLevel.folders[part] as any;
                });
                (currentLevel as any).files.push(file);
            });
            return root;
        };
        setFileTree(buildTree(files));
    }, [searchQuery, files]);

    const toggleFolder = (folderPath: string) => {
        setExpandedFolders(prev => ({ ...prev, [folderPath]: !prev[folderPath] }));
    };

    const DataGridSkeleton = () => (
        <Box sx={{ width: "100%", mt: 1 }}>
            {/* Header */}
            <Skeleton variant="rectangular" height={40} sx={{ mb: 1 }} />

            {/* Rows */}
            {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} variant="rectangular" height={36} sx={{ mb: 0.5, borderRadius: 1 }} />
            ))}
        </Box>
    );

    const getStatusColor = (status: string) => {
        switch (status) {
            case "Pass":
                return "success";
            case "Failed":
                return "error";
            case "Duplicate":
                return "warning";
            case "InProgress":
                return "info";
            default:
                return "default";
        }
    };

    // ลบไฟล์
    const handleDelete = async (filename: string) => {
        if (!teamId) {
            setMessage("Cannot delete: no active team.");
            setOpenError(true);
            return;
        }
        setDeletingFile(filename);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            const team_id = selectTeamData?._id || "";
            await deleteTeamUploadedFileApi(filename, token, team_id);

            setFiles(prev => prev.filter(f => f.name !== filename));
            setMessage(`Deleted: ${filename}`);
            setOpenSuccess(true);
        } catch (err) {
            console.error(err);
            setMessage(`Failed to delete: ${filename}`);
            setOpenError(true);
        } finally {
            setDeletingFile(null);
            setConfirmingDelete(null);
        }
    };

    // upload
    const handleSubmitUpload = async () => {
        if (selectedDataGroupIds.length === 0) {
            setMessage("Please select at least one data group before uploading.");
            setOpenError(true);
            return;
        }

        if (!teamId) {
            setMessage("Cannot upload: no active group.");
            setOpenError(true);
            return;
        }
        if (selectedFiles.length === 0) return;
        if (totalUsed > limitSizeConf) {
            setMessage(`Upload blocked — storage limit exceeded. Limit: ${formatFileSize(limitSizeConf)}`);
            setOpenError(true);
            return;
        }

        setUploading(true);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            const formData = new FormData();
            const team_id = selectTeamData?._id || "";

            for (const file of selectedFiles) {
                formData.append("file", file);
                // await uploadGroupFileApi(formData, token, gid);
                // uploadTeamFileApi(formData, selectedDataGroupIds, team_id, token);
            }
            if (processingProfileId) formData.append("processing_profile_id", processingProfileId);

            uploadTeamFileApi(formData, selectedDataGroupIds, team_id, token).catch(err => {
                console.error("Background upload error", err);
            });

            setMessage("🚀 Upload job submitted. Processing in background.");
            setOpenSuccess(true);
            setSelectedFiles([]);

            // 🧠 Delayed refresh (debounce)
            if (refreshTimerRef.current) {
                clearTimeout(refreshTimerRef.current);
            }

            refreshTimerRef.current = setTimeout(() => {
                fetchFiles();
            }, 5000); // รอ 5 วิหลัง upload ล่าสุด
        } catch (err) {
            console.error(err);
            setMessage("Upload failed");
            setOpenError(true);
        } finally {
            setTimeout(() => setUploading(false), 500);
        }
    };

    const columnsWithGroups: GridColDef[] = [
        {
            field: "baseName",
            headerName: "File Name",
            flex: 1,
            renderCell: params => {
                const depth = params.row.depth || 0;
                const indent = depth * 24;

                if (params.row.isGroup) {
                    const isExpanded = !!expandedFolders[params.row.fullPath!];
                    return (
                        <Box
                            sx={{
                                cursor: "pointer",
                                fontWeight: "bold",
                                paddingLeft: `${indent}px`,
                                display: "flex",
                                alignItems: "center"
                            }}
                            onClick={() => toggleFolder(params.row.fullPath!)}
                        >
                            {isExpanded ? "▼ " : "▶ "}&nbsp;{params.row.folderName}
                        </Box>
                    );
                }

                return (
                    <Box
                        sx={{
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            width: "100%",
                            paddingLeft: `${indent + 18}px`,
                            display: "flex",
                            alignItems: "center",
                            gap: 1
                        }}
                        title={params.value}
                    >
                        <span style={{ flex: 1 }}>{params.value}</span>
                        {/* {params.row.status && (
                            <Chip
                                label={params.row.status}
                                size="small"
                                color={getStatusColor(params.row.status) as any}
                                variant="outlined"
                                sx={{ fontSize: "0.75rem", height: "20px", minWidth: "60px" }}
                            />
                        )} */}
                    </Box>
                );
            }
        },
        {
            field: "status",
            headerName: "Status",
            width: 120,
            renderCell: params => {
                if (params.row.isGroup || !params.value) return null;
                return (
                    <Chip
                        label={params.value}
                        size="small"
                        color={getStatusColor(params.value as string) as any}
                        variant="outlined"
                        sx={{ fontSize: "0.75rem", height: 20, minWidth: 60 }}
                    />
                );
            }
        },
        {
            field: "dataGroups",
            headerName: "Data Groups",
            flex: 1,
            sortable: false,
            renderCell: params => {
                if (params.row.isGroup || !params.value?.length) return null;

                const groups: string[] = params.value;
                const MAX_VISIBLE = 2;

                const visible = groups.slice(0, MAX_VISIBLE);
                const hiddenCount = groups.length - MAX_VISIBLE;

                return (
                    <Box
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            height: "100%",
                            gap: 0.5
                        }}
                    >
                        {visible.map(g => (
                            <Box
                                key={g}
                                sx={{
                                    px: 0.75,
                                    height: 20,
                                    display: "flex",
                                    alignItems: "center",
                                    borderRadius: 0.75,
                                    fontSize: "0.7rem",
                                    lineHeight: 1,
                                    bgcolor: "grey.100",
                                    color: "text.secondary",
                                    border: "1px solid",
                                    borderColor: "divider"
                                }}
                            >
                                {g}
                            </Box>
                        ))}

                        {hiddenCount > 0 && (
                            <Tooltip title={groups.join(", ")} arrow>
                                <Box
                                    sx={{
                                        px: 0.5,
                                        fontSize: "0.7rem",
                                        color: "text.disabled",
                                        cursor: "pointer"
                                    }}
                                >
                                    +{hiddenCount}
                                </Box>
                            </Tooltip>
                        )}
                    </Box>
                );
            }
        },
        {
            field: "uploadedAt",
            headerName: "Upload Time",
            width: 200,
            valueFormatter: ((value: any) => {
                if (!value) return "";
                const date = new Date(value);
                return date.toLocaleString("th-TH", {
                    timeZone: "Asia/Bangkok",
                    year: "numeric",
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit"
                });
            }) as GridValueFormatter
        },
        {
            field: "size",
            headerName: "Size",
            width: 140,
            renderCell: params => {
                if (params.row.isGroup || !params.value) return null;
                return formatFileSize(params.value as number);
            }
        },
        {
            field: "actions",
            headerName: "Actions",
            width: 100,
            sortable: false,
            renderCell: params => {
                if (params.row.isGroup) return null;
                const isDeleting = deletingFile === params.row.name;
                const isConfirming = confirmingDelete === params.row.name;

                if (!teamId) return null; // ❌ ไม่มี group → ไม่มี actions

                if (isDeleting) return <CircularProgress size={20} />;
                if (isConfirming) {
                    return (
                        <Box display="flex" gap={1}>
                            <Tooltip title="Confirm Delete">
                                <IconButton color="success" onClick={() => handleDelete(params.row.name!)} disabled={deletingFile !== null}>
                                    <CheckCircleIcon />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Cancel">
                                <IconButton color="inherit" onClick={() => setConfirmingDelete(null)} disabled={deletingFile !== null}>
                                    <CancelIcon />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    );
                }
                return (
                    <IconButton onClick={() => setConfirmingDelete(params.row.name!)} color="error" disabled={deletingFile !== null}>
                        <DeleteIcon />
                    </IconButton>
                );
            }
        }
    ];

    // Drag & Drop
    const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        const items = Array.from(e.dataTransfer.items);
        const promises = items
            .map(item => (item as any).webkitGetAsEntry?.())
            .filter(entry => !!entry)
            .map(entry => traverseFileTree(entry));
        const filesArrays = await Promise.all(promises);
        const allFiles = filesArrays.flat();
        setSelectedFiles(prev => [...prev, ...allFiles]);
    };

    const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => e.preventDefault();

    const traverseFileTree = (item: any, path = ""): Promise<File[]> => {
        return new Promise(resolve => {
            if (item.isFile) {
                item.file((file: File) => {
                    const fileWithPath = new File([file], path + file.name, { type: file.type });
                    resolve([fileWithPath]);
                });
            } else if (item.isDirectory) {
                const dirReader = item.createReader();
                const readEntriesRecursive = (reader: any): Promise<any[]> => {
                    return new Promise(resolveEntries => {
                        reader.readEntries((entries: any[]) => {
                            if (entries.length > 0) {
                                readEntriesRecursive(reader).then(nextEntries => resolveEntries(entries.concat(nextEntries)));
                            } else {
                                resolveEntries([]);
                            }
                        });
                    });
                };
                readEntriesRecursive(dirReader).then(async allEntries => {
                    const promises = allEntries.map(entry => traverseFileTree(entry, path + item.name + "/"));
                    const nestedFiles = await Promise.all(promises);
                    resolve(nestedFiles.flat());
                });
            } else {
                resolve([]);
            }
        });
    };

    const restoreActiveTeam = async () => {
        const activeTeams = Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, any> | null;
        if (!activeTeams) {
            return;
        }

        const name = (await getUsername(client)) ?? "";

        const selectTeam = activeTeams[name];
        setSelectTeamData(selectTeam);
    };

    useEffect(() => {
        restoreActiveTeam();
    }, []);

    useEffect(() => {
        const loadDataGroups = async () => {
            try {
                const token = await getToken(client);
                if (!token) return;

                // ✅ ดึง active team จาก storage
                const activeTeams = Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, any> | null;
                if (!activeTeams) return;

                const username = (await getUsername(client)) ?? "";
                if (!username) return;

                const team = activeTeams[username];
                const teamId = team?._id;
                if (!teamId) return;

                // ✅ call ของจริง
                const list = await get_data_group_by_team(teamId, token);

                setDataGroups(list ?? []);

                // ✅ reset selection เมื่อ group list เปลี่ยน (สำคัญ)
                setSelectedDataGroupIds([]);
            } catch (err) {
                console.error("load data groups failed:", err);
                setDataGroups([]);
            }
        };

        loadDataGroups();
    }, [client, teamId]);

    return (
        <Box>
            {!teamId && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                    You are not in any group. File upload, delete and listing are disabled.
                </Alert>
            )}

            {/* Search */}
            <Box mt={2} mb={2}>
                <TextField
                    label="Search Files"
                    variant="outlined"
                    size="small"
                    value={searchQuery}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
                    fullWidth
                    disabled={!teamId}
                />
            </Box>

            <Box sx={{ mb: 2 }}>
                <Typography variant="body2" fontWeight={600}>
                    Storage Usage: {formatFileSize(totalUsed)} / {formatFileSize(limitSizeConf)}
                </Typography>

                <Box
                    sx={{
                        mt: 1,
                        height: 12,
                        background: "#eee",
                        borderRadius: 6,
                        overflow: "hidden"
                    }}
                >
                    <Box
                        sx={{
                            width: `${(totalUsed / limitSizeConf) * 100}%`,
                            height: "100%",
                            background: totalUsed > limitSizeConf ? "red" : "#1976d2",
                            transition: "width 0.3s ease"
                        }}
                    />
                </Box>

                <Typography variant="caption" sx={{ display: "block", mt: 0.5 }}>
                    Used: {formatFileSize(storedSize)}
                    {" + "}
                    New: {formatFileSize(newSize)}
                    {" = "}
                    Total: {formatFileSize(totalUsed)}
                </Typography>
            </Box>

            {/* Drag & Drop */}
            <Box
                onDrop={e => {
                    if (teamId) handleDrop(e);
                }}
                onDragOver={handleDragOver}
                sx={{
                    border: "2px dashed #ccc",
                    padding: 2,
                    borderRadius: 2,
                    textAlign: "center",
                    mb: 2,
                    cursor: teamId ? "pointer" : "not-allowed",
                    opacity: teamId ? 1 : 0.5
                }}
            >
                <Typography variant="body1">Drag & drop group files or folders here</Typography>
            </Box>

            {/* Data Group Single Select */}
            <Box sx={{ mb: 2 }}>
                <DocumentProcessingUploadSelector value={processingProfileId} onChange={setProcessingProfileId} />
            </Box>
            <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                    Select Data Group
                </Typography>

                <Autocomplete
                    multiple
                    options={dataGroups}
                    getOptionLabel={option => option.name}
                    value={dataGroups.filter(g => selectedDataGroupIds.includes(g._id))}
                    onChange={(_, values) => {
                        setSelectedDataGroupIds(values.map(v => v._id));
                    }}
                    disabled={!teamId}
                    renderInput={params => <TextField {...params} size="small" placeholder="Search data group..." />}
                    isOptionEqualToValue={(option, value) => option._id === value._id}
                    noOptionsText="No data group found"
                />
            </Box>

            {/* Upload button */}
            <Box display="flex" gap={2} alignItems="center" mb={2}>
                {selectedFiles.length > 0 && (
                    <Button2 variant="contained" color="primary" onClick={handleSubmitUpload} disabled={uploading || !teamId} startIcon={<UploadFileIcon />}>
                        {uploading ? <CircularProgress size={24} color="inherit" /> : `Upload ${selectedFiles.length} item(s)`}
                    </Button2>
                )}
            </Box>

            {selectedFiles.length > 0 && (
                <Box sx={{ mb: 2, maxHeight: 150, overflowY: "auto", border: "1px solid #ddd", p: 1, borderRadius: 1 }}>
                    <Typography variant="subtitle1" gutterBottom>
                        Files to Upload:
                    </Typography>
                    {selectedFiles.map((file, index) => (
                        <Box key={index} sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1 }}>
                            <Typography variant="body2" sx={{ wordBreak: "break-all" }}>
                                {file.name}
                            </Typography>
                            <IconButton size="small" onClick={() => handleRemoveSelectedFile(index)}>
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                        </Box>
                    ))}
                </Box>
            )}

            {/* File Table */}
            <Box sx={{ minHeight: 400, width: "100%" }}>
                {loadingFiles ? (
                    <DataGridSkeleton />
                ) : (
                    <DataGrid
                        rows={rowsWithGroups}
                        columns={columnsWithGroups}
                        getRowId={row => row.id}
                        paginationModel={paginationModel}
                        onPaginationModelChange={setPaginationModel}
                        pageSizeOptions={[10]}
                        pagination
                        autoHeight
                        disableRowSelectionOnClick
                        disableColumnFilter
                        disableColumnSorting
                    />
                )}
            </Box>

            {/* Snackbar */}
            <Snackbar open={openSuccess} autoHideDuration={3000} anchorOrigin={{ vertical: "top", horizontal: "right" }} onClose={() => setOpenSuccess(false)}>
                <Alert severity="success" onClose={() => setOpenSuccess(false)} sx={{ width: "100%" }}>
                    {message}
                </Alert>
            </Snackbar>
            <Snackbar open={openError} autoHideDuration={3000} anchorOrigin={{ vertical: "top", horizontal: "right" }} onClose={() => setOpenError(false)}>
                <Alert severity="error" onClose={() => setOpenError(false)} sx={{ width: "100%" }}>
                    {message}
                </Alert>
            </Snackbar>
        </Box>
    );
};
