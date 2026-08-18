import React, { useEffect, useState } from "react";
import {
    Dialog, DialogContent, DialogActions, Button, Stack,
    Drawer, Box, Typography, IconButton, Divider, Skeleton
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import DashboardIcon from "@mui/icons-material/Dashboard";

import SummaryCard from "./SummaryCard";
import FeedbackTable from "./FeedbackTable";
import FeedbackByUserChart from "./FeedbackByUserChart";
import FeedbackByDateChart from "./FeedbackByDateChart";
import FeedbackDetail from "./FeedbackDetail";

import { useMsal } from "@azure/msal-react";
import { getToken } from "../../authConfig";
import { listFeedback } from "../../api";

interface Props {
    open: boolean;
    onClose: () => void;
}

interface FeedbackItem {
    _id: string;
    feedback: string;
    images: { file_type: string; image: string }[];
    user: { name: string };
    created_at?: string;
    date?: string;
    status?: string;
}

const FeedbackDashboardDialog: React.FC<Props> = ({ open, onClose }) => {
    const [data, setData] = useState<FeedbackItem[]>([]);
    const [selected, setSelected] = useState<FeedbackItem | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const { instance: msalInstance } = useMsal();

    const fetchListFeedback = async () => {
        const token = await getToken(msalInstance);
        if (!token) return;
        try {
            return await listFeedback(token);
        } catch (err) {
            console.error("Error fetching feedback:", err);
            return null;
        }
    };

    useEffect(() => {
        if (!open) return;
        setLoading(true);
        setError(null);
        setData([]);
        setSelected(null);

        fetchListFeedback()
            .then(res => {
                if (!res) { setError("No response from server"); return; }
                if (Array.isArray(res.data)) setData(res.data);
                else setError("Invalid data format");
            })
            .catch(() => setError("Failed to load feedback"))
            .finally(() => setLoading(false));
    }, [open]);

    return (
        <>
            <Dialog
                open={open}
                onClose={onClose}
                fullWidth
                maxWidth="xl"
                PaperProps={{
                    sx: {
                        height: "92vh",
                        borderRadius: 3,
                        display: "flex",
                        flexDirection: "column",
                        overflow: "hidden"
                    }
                }}
            >
                {/* ── Custom header ── */}
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1.5,
                        px: 3,
                        py: 2.5,
                        background: "linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(139,92,246,0.06) 50%, transparent 100%)",
                        borderBottom: "1px solid",
                        borderColor: "divider",
                        flexShrink: 0
                    }}
                >
                    <Box
                        sx={{
                            width: 42, height: 42,
                            borderRadius: 2.5,
                            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            color: "white",
                            boxShadow: "0 4px 12px rgba(99,102,241,0.35)"
                        }}
                    >
                        <DashboardIcon fontSize="small" />
                    </Box>
                    <Box sx={{ flex: 1 }}>
                        <Typography variant="h6" fontWeight={800} lineHeight={1.2}
                            sx={{ background: "linear-gradient(90deg, #6366f1, #8b5cf6)", backgroundClip: "text", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}
                        >
                            Feedback Dashboard
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                            {loading ? "กำลังโหลด…" : `${data.length} รายการทั้งหมด`}
                        </Typography>
                    </Box>
                    <IconButton onClick={onClose} size="small" sx={{ bgcolor: "action.hover", "&:hover": { bgcolor: "action.selected" } }}>
                        <CloseIcon fontSize="small" />
                    </IconButton>
                </Box>

                {/* ── Body ── */}
                <DialogContent sx={{ p: 3, flex: 1, overflow: "auto" }}>
                    <Stack spacing={3}>

                        {/* Summary card */}
                        {loading
                            ? <Skeleton variant="rectangular" height={110} sx={{ borderRadius: 3 }} />
                            : <SummaryCard count={data.length} />
                        }

                        {/* Charts row */}
                        <Stack direction={{ xs: "column", md: "row" }} spacing={2.5} sx={{ width: "100%" }}>
                            <Box sx={{ flex: 1 }}>
                                {loading
                                    ? <Skeleton variant="rectangular" height={240} sx={{ borderRadius: 2 }} />
                                    : <FeedbackByUserChart data={data} />
                                }
                            </Box>
                            <Box sx={{ flex: 1 }}>
                                {loading
                                    ? <Skeleton variant="rectangular" height={240} sx={{ borderRadius: 2 }} />
                                    : <FeedbackByDateChart data={data} />
                                }
                            </Box>
                        </Stack>

                        <Divider />

                        {/* Table */}
                        <Box>
                            <Typography variant="subtitle1" fontWeight={700} mb={1.5}>
                                All Feedback
                            </Typography>

                            {error && (
                                <Box sx={{ p: 3, textAlign: "center", color: "error.main", borderRadius: 2, border: "1px dashed", borderColor: "error.light" }}>
                                    <Typography>{error}</Typography>
                                </Box>
                            )}

                            {loading ? (
                                <Stack spacing={1}>
                                    {[1, 2, 3, 4].map(i => <Skeleton key={i} height={56} sx={{ borderRadius: 1 }} />)}
                                </Stack>
                            ) : (
                                <FeedbackTable
                                    data={data}
                                    onSelect={item => setSelected(item)}
                                />
                            )}
                        </Box>
                    </Stack>
                </DialogContent>

                <DialogActions sx={{ px: 3, py: 1.5, borderTop: "1px solid", borderColor: "divider" }}>
                    <Button variant="outlined" onClick={onClose} sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600 }}>
                        Close
                    </Button>
                </DialogActions>
            </Dialog>

            {/* ── Detail drawer ── */}
            <Drawer
                anchor="right"
                open={Boolean(selected)}
                onClose={() => setSelected(null)}
                sx={{ zIndex: 1400 }}
                PaperProps={{
                    sx: {
                        width: { xs: "100vw", sm: 460 },
                        display: "flex",
                        flexDirection: "column"
                    }
                }}
            >
                {/* Drawer header */}
                <Box
                    sx={{
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        px: 2.5, py: 2,
                        borderBottom: "1px solid", borderColor: "divider",
                        flexShrink: 0
                    }}
                >
                    <Typography variant="subtitle1" fontWeight={700}>
                        Feedback Detail
                    </Typography>
                    <IconButton onClick={() => setSelected(null)} size="small">
                        <CloseIcon fontSize="small" />
                    </IconButton>
                </Box>

                {/* Drawer body */}
                <Box sx={{ flex: 1, overflow: "auto", p: 2.5 }}>
                    {selected && <FeedbackDetail item={selected} />}
                </Box>
            </Drawer>
        </>
    );
};

export default FeedbackDashboardDialog;
