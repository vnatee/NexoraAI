import React, { useEffect, useState, DragEvent, useContext } from "react";
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Button,
    IconButton,
    Stack,
    Typography,
    Avatar,
    Box,
    Snackbar,
    Paper,
    Alert
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import DeleteIcon from "@mui/icons-material/Delete";
import { useMsal } from "@azure/msal-react";
import { getToken, getUsername } from "../../authConfig";
import { LoginContext } from "../../loginContext";
import { AuthProfile, feedBackPageApi, listFeedback, User } from "../../api";
import { json } from "react-router-dom";
import CircularProgress from "@mui/material/CircularProgress";
import { STORAGE_KEYS } from "../../utill/storageKeys";
import { Storage } from "../../utill/storage";

type FeedbackDialogProps = {
    open: boolean;
    onClose: () => void;
    // onSubmit: (data: FormData) => void | Promise<void>;
    maxFiles?: number;
    maxFileSizeBytes?: number;
};

export default function FeedbackDialog({ open, onClose, maxFiles = 5, maxFileSizeBytes = 2 * 1024 * 1024 }: FeedbackDialogProps) {
    const [comment, setComment] = useState("");
    const [files, setFiles] = useState<File[]>([]);
    const [previews, setPreviews] = useState<string[]>([]);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const [dragOver, setDragOver] = useState(false);
    const { instance } = useMsal();
    const [username, setUsername] = useState("");
    const { userDetails } = useContext(LoginContext);
    const { instance: msalInstance } = useMsal();
    const [openSuccess, setOpenSuccess] = useState(false);
    const [openError, setOpenError] = useState(false);
    const [message, setMessage] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const totalFileSize = files.reduce((acc, f) => acc + f.size, 0);

    useEffect(() => {
        const urls = files.map(f => URL.createObjectURL(f));
        setPreviews(urls);
        return () => urls.forEach(u => URL.revokeObjectURL(u));
    }, [files]);

    useEffect(() => {
        if (!open) {
            setComment("");
            setFiles([]);
            setErrorMsg(null);
        }
    }, [open]);

    const formatBytes = (bytes: number) => {
        return (bytes / (1024 * 1024)).toFixed(2); // 2 decimals
    };

    const validateAndAddFiles = (selected: FileList | File[] | null) => {
        if (!selected) return;

        const next = Array.from(selected);
        const allowed = ["image/png", "image/jpeg"];

        // เช็คจำนวนไฟล์
        if (files.length + next.length > maxFiles) {
            setErrorMsg(`Maximum ${maxFiles} images allowed.`);
            return;
        }

        // เช็คประเภทไฟล์
        for (const f of next) {
            if (!allowed.includes(f.type)) {
                setErrorMsg("Only .png and .jpg images are allowed.");
                return;
            }
        }
        // ผ่านทั้งหมด → เพิ่มไฟล์
        setFiles(prev => [...prev, ...next]);
    };

    const clear = () => {
        setComment("");
        setFiles([]);
        setErrorMsg(null);
    };

    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        validateAndAddFiles(e.target.files);
        e.target.value = "";
    };

    const onDragOver = (e: DragEvent) => {
        e.preventDefault();
        setDragOver(true);
    };

    const onDragLeave = () => setDragOver(false);

    const onDrop = (e: DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        validateAndAddFiles(e.dataTransfer.files);
    };

    const removeFileAt = (i: number) => {
        setFiles(s => s.filter((_, idx) => idx !== i));
    };

    const handleSubmit = async () => {
        if (totalFileSize > maxFileSizeBytes) {
            setMessage(`Total file size must be under ${formatBytes(maxFileSizeBytes)} MB.`);
            setOpenError(true);
            return;
        }

        setIsSubmitting(true);

        const fd = new FormData();
        const accounts = instance.getAllAccounts();

        fd.append("comment", comment);
        files.forEach(f => fd.append("file", f, f.name));

        // const token = await getToken(msalInstance);
        const token = await getToken(msalInstance);
        if (!token) {
            console.warn("No token while persisting currentAgentConfig");
            setIsSubmitting(false);
            return;
        }

        try {
            // await onSubmit(fd);
            const authProfile = Storage.get(STORAGE_KEYS.AUTH_PROFILE) as AuthProfile;
            fd.append(
                "user",
                JSON.stringify({
                    _id: authProfile.user._id,
                    name: authProfile.user.ad_email
                })
            );
            await feedBackPageApi(fd, token);
            setMessage("Feedback submitted successfully!");
            setOpenSuccess(true);
            clear();
            // onClose();
        } catch (err) {
            setMessage("An error occurred while submitting. Please try again.");
            setOpenError(true);
        }
        setIsSubmitting(false);
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle sx={{ display: "flex", justifyContent: "space-between" }}>
                Feedback
                <IconButton onClick={onClose} size="small">
                    <CloseIcon />
                </IconButton>
            </DialogTitle>

            <DialogContent dividers>
                <Stack spacing={2}>
                    <TextField
                        label="Comment"
                        multiline
                        minRows={3}
                        value={comment}
                        disabled={isSubmitting}
                        onChange={e => setComment(e.target.value)}
                        placeholder="Write your feedback here..."
                        fullWidth
                    />

                    <Box>
                        <Typography variant="body2" sx={{ mb: 1 }}>
                            Upload Images (.png, .jpg) — Total:{" "}
                            <Box
                                component="span"
                                sx={{
                                    color: totalFileSize > maxFileSizeBytes ? "red" : "inherit",
                                    fontWeight: totalFileSize > maxFileSizeBytes ? "bold" : "inherit"
                                }}
                            >
                                {formatBytes(totalFileSize)}
                            </Box>{" "}
                            MB / {formatBytes(maxFileSizeBytes)} MB
                        </Typography>

                        <Paper
                            variant="outlined"
                            sx={{
                                p: 3,
                                textAlign: "center",
                                borderStyle: "dashed",
                                bgcolor: dragOver ? "grey.200" : "inherit",
                                cursor: "pointer"
                            }}
                            onDragOver={isSubmitting ? undefined : onDragOver}
                            onDragLeave={isSubmitting ? undefined : onDragLeave}
                            onDrop={isSubmitting ? undefined : onDrop}
                        >
                            <input
                                id="fileInput"
                                type="file"
                                disabled={isSubmitting}
                                accept="image/png, image/jpeg"
                                multiple
                                style={{ display: "none" }}
                                onChange={handleFileInput}
                            />
                            <label htmlFor="fileInput">
                                <Button disabled={isSubmitting} variant="outlined" component="span">
                                    Choose Files
                                </Button>
                            </label>
                            <Typography sx={{ mt: 1 }}>or drag and drop files here</Typography>
                        </Paper>

                        {previews.length > 0 && (
                            <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: "wrap" }}>
                                {previews.map((src, i) => (
                                    <Box key={i} sx={{ position: "relative" }}>
                                        <Avatar src={src} variant="rounded" sx={{ width: 80, height: 80 }} />
                                        <IconButton
                                            size="small"
                                            disabled={isSubmitting}
                                            onClick={() => removeFileAt(i)}
                                            sx={{ position: "absolute", top: -8, right: -8, bgcolor: "white" }}
                                        >
                                            <DeleteIcon fontSize="small" />
                                        </IconButton>
                                    </Box>
                                ))}
                            </Stack>
                        )}
                    </Box>
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button disabled={isSubmitting} onClick={onClose}>
                    Cancel
                </Button>
                <Button
                    variant="contained"
                    onClick={handleSubmit}
                    disabled={isSubmitting}
                    startIcon={isSubmitting ? <CircularProgress color="inherit" size={20} /> : null}
                >
                    {isSubmitting ? "Submitting..." : "Submit"}
                </Button>
            </DialogActions>

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
        </Dialog>
    );
}
