import React, { useState, ChangeEvent } from "react";
import { Callout, Label, Text } from "@fluentui/react";
import { Button } from "@fluentui/react-components";
import { Add24Regular, Delete24Regular } from "@fluentui/react-icons";
import { useMsal } from "@azure/msal-react";
import { useTranslation } from "react-i18next";
import DeleteIcon from "@mui/icons-material/Delete";
import { SimpleAPIResponse, uploadFileApi, deleteUploadedFileApi, listUploadedFilesApi, limit_size } from "../../api";
import { useLogin, getToken } from "../../authConfig";
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button as Button2,
    Typography,
    Box,
    Stack,
    CircularProgress,
    Alert,
    Paper,
    Snackbar,
    IconButton
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import Tooltip from "@mui/material/Tooltip";
import { DocumentProcessingUploadSelector } from "../DocumentProcessingUploadSelector/DocumentProcessingUploadSelector";

import styles from "./UploadFile.module.css";

interface Props {
    className?: string;
    disabled?: boolean;
    dialogRef?: React.RefObject<HTMLDivElement>;
}

export const UploadFile: React.FC<Props> = ({ className, disabled, dialogRef }: Props) => {
    // State variables to manage the component behavior
    const [isCalloutVisible, setIsCalloutVisible] = useState<boolean>(false);
    const [isUploading, setIsUploading] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [deletionStatus, setDeletionStatus] = useState<{ [filename: string]: "pending" | "error" | "success" }>({});
    const [uploadedFile, setUploadedFile] = useState<SimpleAPIResponse>();
    const [uploadedFileError, setUploadedFileError] = useState<string>();
    const [uploadedFiles, setUploadedFiles] = useState<[string, number][]>([]);

    const { t } = useTranslation();
    const [isOpen, setIsOpen] = useState(false);
    const [openSuccess, setOpenSuccess] = useState(false);
    const [openError, setOpenError] = useState(false);
    const [openDeleteSuccess, setOpenDeleteSuccess] = useState(false);
    const [openDeleteError, setOpenDeleteError] = useState(false);
    const [snackOpen, setSnackOpen] = useState(false);
    const [message, setMessage] = useState<string | null>(null);
    const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
    const [deletingFile, setDeletingFile] = useState<string | null>(null);
    const [limitSizeConf, setLimitSizeConf] = useState<number>(0);
    const [storedSize, setStoredSize] = useState<number>(0);
    const [newSize, setNewSize] = useState<number>(0);
    const [totalUsed, setTotalUsed] = useState<number>(0);
    const [processingProfileId, setProcessingProfileId] = useState("");

    const formatFileSize = (size: number): string => {
        if (size === 0) return "0 KB";
        const units = ["B", "KB", "MB", "GB", "TB"];
        const index = Math.floor(Math.log(size) / Math.log(1024));
        return `${(size / Math.pow(1024, index)).toFixed(2)} ${units[index]}`;
    };

    const fetchLimitSizeConf = async () => {
        try {
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            const result = await limit_size(token); // ⬅ เปลี่ยนตาม API ของคุณ
            setLimitSizeConf(result?.size_limit_group || 0);
        } catch (e) {
            console.error(e);
        }
    };

    if (!useLogin) {
        throw new Error("The UploadFile component requires useLogin to be true");
    }

    const client = useMsal().instance;

    // Handler for the "Manage file uploads" button
    const handleButtonClick = async () => {
        setIsOpen(true);
        setIsCalloutVisible(!isCalloutVisible); // Toggle the Callout visibility

        // Update uploaded files by calling the API
        try {
            const idToken = await getToken(client);
            if (!idToken) {
                throw new Error("No authentication token available");
            }
            await listUploadedFiles(idToken);
            fetchLimitSizeConf();
        } catch (error) {
            console.error(error);
            setIsLoading(false);
        }
    };

    const listUploadedFiles = async (idToken: string) => {
        try {
            const raw = await listUploadedFilesApi(idToken);
            setIsLoading(false);
            setDeletionStatus({});

            if (!raw || typeof raw !== "object") {
                setUploadedFiles([]);
                setStoredSize(0);
                setTotalUsed(newSize);
                return;
            }

            const entries = Object.values(raw);

            const safeEntries: [string, number][] = entries
                .filter(v => Array.isArray(v) && typeof v[0] === "string" && (typeof v[1] === "string" || typeof v[1] === "number"))
                .map(v => [v[0], Number(v[1])]); // ⬅ แปลงตรงนี้

            setUploadedFiles(safeEntries);

            const sum = safeEntries.reduce((acc, item) => acc + item[1], 0);

            setStoredSize(sum);
            setTotalUsed(sum + newSize);
        } catch (error) {
            console.error(error);
            setIsLoading(false);
            throw error;
        }
    };

    const handleRemoveFile = async (filename: string) => {
        setDeletionStatus(current => ({ ...current, [filename]: "pending" }));
        setDeletingFile(filename);
        try {
            const idToken = await getToken(client);
            if (!idToken) {
                throw new Error("No authentication token available");
            }

            await deleteUploadedFileApi(filename, idToken);
            setDeletionStatus(current => ({ ...current, [filename]: "success" }));
            setMessage(`Deleted: ${filename}`);
            setOpenDeleteSuccess(true);
            await listUploadedFiles(idToken);
        } catch (error) {
            setDeletionStatus(current => ({ ...current, [filename]: "error" }));
            setMessage(`Failed to delete: ${filename}`);
            setOpenDeleteError(true);
        } finally {
            setDeletingFile(null);
            setConfirmingDelete(null);
        }
    };

    // Handler for the form submission (file upload)
    const handleUploadFile = async (e: ChangeEvent<HTMLInputElement>) => {
        e.preventDefault();
        if (!e.target.files || e.target.files.length === 0) {
            return;
        }

        if (totalUsed > limitSizeConf) {
            setMessage(`Upload blocked — storage limit exceeded. Limit: ${formatFileSize(limitSizeConf)}`);
            setOpenError(true);
            return;
        }

        setIsUploading(true); // Start the loading state
        const file: File = e.target.files[0];
        const formData = new FormData();
        formData.append("file", file);
        if (processingProfileId) formData.append("processing_profile_id", processingProfileId);

        try {
            const idToken = await getToken(client);
            if (!idToken) {
                throw new Error("No authentication token available");
            }
            const response: SimpleAPIResponse = await uploadFileApi(formData, idToken);
            setUploadedFile(response);
            setIsUploading(false);
            setUploadedFileError(undefined);
            setOpenSuccess(true);
            await listUploadedFiles(idToken);
        } catch (error) {
            console.error(error);
            setIsUploading(false);
            setUploadedFileError(t("upload.uploadedFileError"));
            setOpenError(true);
        }
    };

    const truncateFileName = (name: string, maxLength: number = 45): string => {
        if (name.length <= maxLength) return name;

        const ellipsis = "...";
        const keep = maxLength - ellipsis.length;

        const startLength = Math.ceil(keep * 0.6); // 60% ด้านหน้า
        const endLength = keep - startLength; // ที่เหลือด้านหลัง

        return `${name.slice(0, startLength)}${ellipsis}${name.slice(-endLength)}`;
    };

    return (
        <div className={`${styles.container} ${className ?? ""}`} ref={dialogRef}>
            <div>
                <Button id="calloutButton" icon={<Add24Regular />} style={{ columnGap: "0.5rem" }} disabled={disabled} onClick={handleButtonClick}>
                    {t("upload.manageFileUploads")}
                </Button>

                <Dialog open={isOpen} onClose={() => setIsOpen(false)} fullWidth maxWidth="sm">
                    <DialogTitle>{t("upload.manageFileUploads")}</DialogTitle>

                    <DialogContent dividers>
                        <Stack spacing={2}>
                            <DocumentProcessingUploadSelector value={processingProfileId} onChange={setProcessingProfileId} />
                            <Box>
                                <Typography variant="subtitle1" gutterBottom>
                                    {t("upload.fileLabel")}
                                </Typography>
                                <Button2 component="label" variant="contained" color="primary" disabled={disabled || isUploading}>
                                    {t("Select File")}
                                    <input
                                        hidden
                                        accept=".txt,.md,.json,.png,.jpg,.jpeg,.bmp,.heic,.tiff,.pdf,.docx,.xlsx,.pptx,.html"
                                        type="file"
                                        onChange={handleUploadFile}
                                    />
                                </Button2>
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
                                            width: limitSizeConf > 0 ? `${(totalUsed / limitSizeConf) * 100}%` : "0%",
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

                            {isUploading && (
                                <Box display="flex" alignItems="center" gap={1}>
                                    <CircularProgress size={20} />
                                    <Typography variant="body2">{t("upload.uploadingFiles")}</Typography>
                                </Box>
                            )}

                            <Snackbar
                                open={openError}
                                autoHideDuration={3000}
                                onClose={() => setOpenError(false)}
                                anchorOrigin={{ vertical: "top", horizontal: "right" }} // หรือเปลี่ยนตำแหน่งได้
                            >
                                <Alert severity="error" onClose={() => setOpenError(false)} sx={{ width: "100%" }}>
                                    {uploadedFileError}
                                </Alert>
                            </Snackbar>

                            <Snackbar
                                open={openSuccess}
                                autoHideDuration={3000}
                                onClose={() => setOpenSuccess(false)}
                                anchorOrigin={{ vertical: "top", horizontal: "right" }} // หรือเปลี่ยนตำแหน่งได้
                            >
                                <Alert severity="success" onClose={() => setOpenSuccess(false)} sx={{ width: "100%" }}>
                                    {uploadedFile?.message}
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

                            <Typography variant="h6" sx={{ mt: 2 }}>
                                {t("upload.uploadedFilesLabel")}
                            </Typography>

                            {isLoading ? (
                                <Box display="flex" alignItems="center" gap={1}>
                                    <CircularProgress size={20} />
                                    <Typography>{t("upload.loading")}</Typography>
                                </Box>
                            ) : uploadedFiles.length === 0 ? (
                                <Typography>{t("upload.noFilesUploaded")}</Typography>
                            ) : (
                                <Stack spacing={1}>
                                    {uploadedFiles.map(([file, size]) => (
                                        <Paper
                                            key={file}
                                            elevation={1}
                                            sx={{
                                                p: 1.5,
                                                display: "flex",
                                                justifyContent: "space-between",
                                                alignItems: "center"
                                            }}
                                        >
                                            <Typography variant="body2" noWrap title={file}>
                                                {truncateFileName(file, 45)}
                                            </Typography>

                                            <Typography variant="caption" sx={{ opacity: 0.6 }}>
                                                {formatFileSize(size)}
                                            </Typography>

                                            <Box display="flex" alignItems="center" gap={1}>
                                                {deletingFile === file ? (
                                                    <CircularProgress size={20} />
                                                ) : confirmingDelete === file ? (
                                                    <>
                                                        <Tooltip title={t("Confirm Delete")}>
                                                            <IconButton
                                                                color="success"
                                                                onClick={() => handleRemoveFile(file)}
                                                                disabled={deletingFile !== null}
                                                                size="small"
                                                            >
                                                                <CheckCircleIcon fontSize="small" />
                                                            </IconButton>
                                                        </Tooltip>
                                                        <Tooltip title={t("Cancel")}>
                                                            <IconButton
                                                                color="inherit"
                                                                onClick={() => setConfirmingDelete(null)}
                                                                disabled={deletingFile !== null}
                                                                size="small"
                                                            >
                                                                <CancelIcon fontSize="small" />
                                                            </IconButton>
                                                        </Tooltip>
                                                    </>
                                                ) : (
                                                    <Tooltip title={t("upload.deleteFile")}>
                                                        <IconButton
                                                            onClick={() => setConfirmingDelete(file)}
                                                            color="error"
                                                            disabled={deletingFile !== null}
                                                            size="small"
                                                        >
                                                            <DeleteIcon fontSize="small" />
                                                        </IconButton>
                                                    </Tooltip>
                                                )}
                                            </Box>
                                        </Paper>
                                    ))}
                                </Stack>
                            )}
                        </Stack>
                    </DialogContent>

                    <DialogActions>
                        <Button2
                            onClick={() => {
                                setIsOpen(false);
                                setConfirmingDelete(null);
                            }}
                            color="secondary"
                            variant="outlined"
                        >
                            {t("close")}
                        </Button2>
                    </DialogActions>
                </Dialog>
            </div>
        </div>
    );
};
