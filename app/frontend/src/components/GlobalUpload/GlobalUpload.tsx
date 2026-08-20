import React, { useEffect, useState, ChangeEvent, useContext } from "react";
import { Button } from "@fluentui/react-components";

import {
    Box,
    Button as Button2,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Typography,
    IconButton,
    TextField,
    Snackbar,
    Alert,
    CircularProgress,
    Chip,
    Tabs,
    Tab,
    Skeleton
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { DataGrid, GridColDef, GridPaginationModel, GridValueFormatter } from "@mui/x-data-grid";
import { useMsal } from "@azure/msal-react";
import { useTranslation } from "react-i18next";
import { LoginContext } from "../../loginContext";

import { uploadGlobalFileApi, listUploadedGlobalFilesApi, deleteGlobalUploadedFileApi, limit_size, User, TeamProfile } from "../../api";
import { getToken, getUsername, useLogin } from "../../authConfig";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import { Tooltip } from "@mui/material";
import { GroupFileUpload } from "../GroupUpload/GroupFileUpload";
import Autocomplete from "@mui/material/Autocomplete";

import styles from "./GlobalUpload.module.css";
import { Storage } from "../../utill/storage";
import { STORAGE_KEYS } from "../../utill/storageKeys";
import { AuthStorage } from "../../utill/authStorage";
import { hasPermission } from "../../utill/hasPermission";
import { DocumentProcessingUploadSelector } from "../DocumentProcessingUploadSelector/DocumentProcessingUploadSelector";

interface Props {
    disabled?: boolean;
    className?: string;
    dialogRef?: React.RefObject<HTMLDivElement>;
}

interface FileRow {
    id: number | string;
    name?: string;
    folder?: string;
    baseName?: string;
    status?: string;
    isGroup?: boolean;
    folderName?: string;
    depth?: number;
    fullPath?: string;
    uploadedAt?: string;
    size?: number;
}

interface FileTreeNode {
    name: string;
    path: string;
    files: FileRow[];
    folders: Record<string, FileTreeNode>;
}

interface DataGroup {
    _id: string;
    name: string;
    user_id?: string[];
}

export const GlobalUpload: React.FC<Props> = ({ disabled, dialogRef, className }) => {
    const [files, setFiles] = useState<FileRow[]>([]);
    const [searchQuery, setSearchQuery] = useState("");
    const [uploading, setUploading] = useState(false);
    const [open, setOpen] = useState(false);
    const [message, setMessage] = useState<string | null>(null);
    const [snackOpen, setSnackOpen] = useState(false);
    const [openSuccess, setOpenSuccess] = useState(false);
    const [openError, setOpenError] = useState(false);
    const [openDeleteSuccess, setOpenDeleteSuccess] = useState(false);
    const [openDeleteError, setOpenDeleteError] = useState(false);
    const [deletingFile, setDeletingFile] = useState<string | null>(null);
    const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [fileTree, setFileTree] = useState<{ files: FileRow[]; folders: Record<string, FileTreeNode> }>({ files: [], folders: {} });
    const [tab, setTab] = useState(0);
    const { userDetails } = useContext(LoginContext);
    const [limitSizeConf, setLimitSizeConf] = useState(0);
    const storedSize = files.reduce((sum, f) => sum + (f.size ?? 0), 0);
    const selectedSize = selectedFiles.reduce((sum, f) => sum + f.size, 0);
    const [loadingFiles, setLoadingFiles] = useState(false);
    const [hasLoaded, setHasLoaded] = useState(false);
    const [sysPers, setSysPers] = useState<string[] | null>(null);
    const [processingProfileId, setProcessingProfileId] = useState("");
    const totalUsed = storedSize + selectedSize;

    const [userData, setUserData] = useState<User | null>(null);
    const [selectTeamData, setSelectTeamData] = useState<TeamProfile | null>(null);

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setTab(newValue);
    };

    // State to track expanded folders, with the root expanded by default
    const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({
        __root__: true
    });
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

    const { t } = useTranslation();
    const client = useMsal().instance;

    if (!useLogin) throw new Error("This component requires login");

    const toggleFolder = (folderPath: string) => {
        setExpandedFolders(prev => ({
            ...prev,
            [folderPath]: !prev[folderPath]
        }));
    };

    // Helper function to get status color
    const getStatusColor = (status: string) => {
        switch (status) {
            case "Pass":
                return "success";
            case "Failed":
                return "error";
            case "Duplicate":
                return "warning";
            default:
                return "default";
        }
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
        if (!open) return;

        const load = async () => {
            const user = AuthStorage.get()?.user ?? null;
            const sys_permissions = AuthStorage.get()?.sys_permissions ?? null;
            setUserData(user);
            setSysPers(sys_permissions);
            await restoreActiveTeam();
        };

        load();
    }, [open]);

    const fetchFiles = async () => {
        try {
            setLoadingFiles(true);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            const result = await listUploadedGlobalFilesApi(token);

            // Updated to handle new data format with status
            const rows: FileRow[] = result.map((fileData: [string, string, string, number, string[]] | string, index: number) => {
                let fileName = "";
                let status = "";
                let uploadedAt = "";
                let size = 0;

                if (Array.isArray(fileData)) {
                    fileName = fileData[0];
                    status = fileData[1];
                    uploadedAt = fileData[2];
                    size = fileData[3];
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
                    size
                };
            });

            setFiles(rows);
        } catch (e) {
            console.error(e);
        } finally {
            // setHasLoaded(true);
            setLoadingFiles(false);
        }
    };

    const fetchLimitSizeConf = async () => {
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            const result = await limit_size(token);
            setLimitSizeConf(result?.size_limit_global || 0);
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        if (!open) return;
        if (hasLoaded) return;

        fetchLimitSizeConf();
        fetchFiles();
    }, [open]);

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

    const handleUploadFile = (e: ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || e.target.files.length === 0) return;
        const filesArray = Array.from(e.target.files);
        setSelectedFiles(prev => [...prev, ...filesArray]);
        if (e.target) e.target.value = "";
    };

    const handleDelete = async (filename: string) => {
        setDeletingFile(filename);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            await deleteGlobalUploadedFileApi(filename, token);
            await fetchFiles();
            setMessage(`Deleted: ${filename}`);
            setOpenDeleteSuccess(true);
        } catch (err) {
            console.error(err);
            setMessage(`Failed to delete: ${filename}`);
            setOpenDeleteError(true);
        } finally {
            setDeletingFile(null);
            setConfirmingDelete(null);
        }
    };

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
    const handleRemoveSelectedFile = (index: number) => setSelectedFiles(prev => prev.filter((_, i) => i !== index));

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

    const handleSubmitUpload = async () => {
        if (selectedFiles.length === 0) return;
        if (totalUsed > limitSizeConf) {
            setMessage(`Upload blocked — storage limit exceeded. Limit: ${formatFileSize(limitSizeConf)}`);
            setOpenError(true);
            return;
        }

        setUploading(true);
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No token");
            const formData = new FormData();
            for (const file of selectedFiles) {
                formData.append("file", file, file.name);
            }
            if (processingProfileId) formData.append("processing_profile_id", processingProfileId);
            await uploadGlobalFileApi(formData, token);
            setHasLoaded(false);
            await fetchFiles();
            setMessage("Upload success");
            setOpenSuccess(true);
            setSelectedFiles([]);
        } catch (err) {
            console.error(err);
            setMessage("Upload failed");
            setOpenError(true);
        } finally {
            setUploading(false);
        }
    };

    const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({ pageSize: 10, page: 0 });

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
                            sx={{ cursor: "pointer", fontWeight: "bold", paddingLeft: `${indent}px`, display: "flex", alignItems: "center" }}
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
                                sx={{
                                    fontSize: "0.75rem",
                                    height: "20px",
                                    minWidth: "60px"
                                }}
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

    const hasRole = (roles: string | string[] | undefined, check: string[]) => {
        if (!roles) return false;
        if (Array.isArray(roles)) {
            return roles.some(r => check.includes(r));
        }
        return check.includes(roles);
    };

    // useEffect(() => {
    //     const mockDataGroups: DataGroup[] = Array.from({ length: 40 }).map((_, i) => ({
    //         _id: `dg-${i + 1}`,
    //         name: `Data Group ${i + 1}`,
    //         user_id: []
    //     }));

    //     setDataGroups(mockDataGroups);

    //     // ✅ เลือกตัวแรกเป็น default (ถ้าต้องการ)
    //     setSelectedDataGroupIds([]);
    // }, []);

    const canGlobal = hasPermission({
        is_sys_admin: userData ? userData?.is_sys_admin : false,
        permissions: selectTeamData ? selectTeamData?.permissions : [],
        sys_permissions: sysPers ? sysPers : [],
        requiredPermissions: ["Manage global uploads"]
    });

    const canGroup = hasPermission({
        is_sys_admin: userData ? userData?.is_sys_admin : false,
        permissions: selectTeamData ? selectTeamData?.permissions : [],
        sys_permissions: [],
        requiredPermissions: ["Manage team uploads"]
    });

    const tabs = [
        ...(canGlobal ? [{ key: "global", label: "Public Files Management" }] : []),
        ...(canGroup ? [{ key: "group", label: "Team Files Management" }] : [])
    ];

    return (
        <Box>
            <div className={`${styles.container} ${className ?? ""}`} ref={dialogRef}>
                <Button
                    id="calloutButton"
                    icon={<UploadFileIcon />}
                    className="buttonText"
                    style={{ columnGap: "0.5rem" }}
                    onClick={() => setOpen(true)}
                    disabled={disabled}
                >
                    Files Management
                </Button>
            </div>
            <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="lg">
                <DialogTitle>
                    <Tabs value={tab} onChange={handleTabChange}>
                        {tabs.map(t => (
                            <Tab key={t.key} label={t.label} />
                        ))}
                    </Tabs>
                </DialogTitle>
                <DialogContent>
                    {!userData || !selectTeamData ? (
                        <Box sx={{ p: 3, display: "flex", justifyContent: "center" }}>
                            <CircularProgress />
                        </Box>
                    ) : (
                        <>
                            {tabs[tab]?.key === "global" && (
                                <>
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
                                        open={openDeleteSuccess}
                                        autoHideDuration={3000}
                                        anchorOrigin={{ vertical: "top", horizontal: "right" }}
                                        onClose={() => setOpenDeleteSuccess(false)}
                                    >
                                        <Alert severity="success" onClose={() => setOpenDeleteSuccess(false)} sx={{ width: "100%" }}>
                                            {message}
                                        </Alert>
                                    </Snackbar>
                                    <Snackbar
                                        open={openDeleteError}
                                        autoHideDuration={3000}
                                        anchorOrigin={{ vertical: "top", horizontal: "right" }}
                                        onClose={() => setOpenDeleteError(false)}
                                    >
                                        <Alert severity="error" onClose={() => setOpenDeleteError(false)} sx={{ width: "100%" }}>
                                            {message}
                                        </Alert>
                                    </Snackbar>

                                    <Box mt={2} mb={2}>
                                        <TextField
                                            label="Search Files"
                                            variant="outlined"
                                            size="small"
                                            value={searchQuery}
                                            onChange={e => setSearchQuery(e.target.value)}
                                            fullWidth
                                        />
                                    </Box>

                                    <Box sx={{ mb: 2 }}>
                                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                            Storage Usage: {formatFileSize(totalUsed)}
                                            {" / "}
                                            {formatFileSize(limitSizeConf)}
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
                                            New: {formatFileSize(selectedSize)}
                                            {" = "}
                                            Total: {formatFileSize(totalUsed)}
                                        </Typography>
                                    </Box>

                                    <Box
                                        onDrop={handleDrop}
                                        onDragOver={handleDragOver}
                                        sx={{ border: "2px dashed #ccc", padding: 2, borderRadius: 2, textAlign: "center", mb: 2, cursor: "pointer" }}
                                    >
                                        <Typography variant="body1">Drag & drop files or folders here</Typography>
                                    </Box>
                                    <Box sx={{ mb: 2 }}>
                                        <DocumentProcessingUploadSelector value={processingProfileId} onChange={setProcessingProfileId} />
                                    </Box>
                                    {/* Data Group Multi Select */}
                                    {/* <Box sx={{ mb: 2 }}>
                                        <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                                            Select Data Group
                                        </Typography>

                                        <Autocomplete
                                            multiple // ⭐ เพิ่ม
                                            options={dataGroups}
                                            getOptionLabel={option => option.name}
                                            value={dataGroups.filter(g => selectedDataGroupIds.includes(g._id))}
                                            onChange={(_, values) => {
                                                setSelectedDataGroupIds(values.map(v => v._id));
                                            }}
                                            renderInput={params => <TextField {...params} size="small" placeholder="Search data group..." />}
                                            isOptionEqualToValue={(option, value) => option._id === value._id}
                                            noOptionsText="No data group found"
                                        />
                                    </Box> */}
                                    <Box display="flex" gap={2} alignItems="center" mb={2}>
                                        {selectedFiles.length > 0 && (
                                            <Button2 variant="contained" color="primary" onClick={handleSubmitUpload} disabled={uploading}>
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
                                </>
                            )}

                            {tabs[tab]?.key === "group" && <GroupFileUpload />}
                        </>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button2
                        onClick={() => {
                            setOpen(false);
                            setConfirmingDelete(null);
                        }}
                    >
                        Close
                    </Button2>
                </DialogActions>
            </Dialog>
        </Box>
    );
};
