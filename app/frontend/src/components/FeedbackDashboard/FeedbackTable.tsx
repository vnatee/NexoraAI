import {
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Chip,
    IconButton,
    Tooltip,
    Box,
    Dialog,
    Button,
    Collapse,
    Avatar,
    Typography,
    Paper
} from "@mui/material";
import { useState } from "react";
import CloseIcon from "@mui/icons-material/Close";
import ImageIcon from "@mui/icons-material/Image";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import ArrowBackIosNewIcon from "@mui/icons-material/ArrowBackIosNew";
import ArrowForwardIosIcon from "@mui/icons-material/ArrowForwardIos";

interface FeedbackItem {
    _id: string;
    feedback: string;
    images: { file_type: string; image: string }[];
    user: { name: string };
    created_at?: string;
    date?: string;
    status?: string;
}

interface Props {
    data: FeedbackItem[];
    onSelect?: (item: FeedbackItem) => void;
}

const statusColor = (status?: string): "success" | "warning" | "error" | "default" => {
    if (!status) return "default";
    const s = status.toLowerCase();
    if (s === "resolved" || s === "done") return "success";
    if (s === "pending" || s === "open") return "warning";
    if (s === "rejected" || s === "closed") return "error";
    return "default";
};

const formatDate = (raw?: string): string => {
    if (!raw) return "—";
    try {
        return new Date(raw).toLocaleDateString("th-TH", {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        });
    } catch {
        return raw;
    }
};

const getInitials = (name: string) =>
    name
        .split(" ")
        .map(n => n[0])
        .slice(0, 2)
        .join("")
        .toUpperCase();

const avatarColor = (name: string) => {
    const colors = ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#ef4444"];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
};

const FeedbackTable = ({ data, onSelect }: Props) => {
    const [expandedRow, setExpandedRow] = useState<string | null>(null);
    const [viewerOpen, setViewerOpen] = useState(false);
    const [viewerImages, setViewerImages] = useState<any[]>([]);
    const [viewerIndex, setViewerIndex] = useState(0);

    const toggleExpand = (id: string) => setExpandedRow(prev => (prev === id ? null : id));

    const openViewer = (images: any[], index: number) => {
        setViewerImages(images);
        setViewerIndex(index);
        setViewerOpen(true);
    };

    const closeViewer = () => setViewerOpen(false);
    const showNext = () => setViewerIndex(prev => (prev + 1) % viewerImages.length);
    const showPrev = () => setViewerIndex(prev => (prev - 1 + viewerImages.length) % viewerImages.length);

    const headCellSx = {
        fontWeight: 700,
        fontSize: "0.75rem",
        textTransform: "uppercase" as const,
        letterSpacing: "0.06em",
        color: "text.secondary",
        py: 1.5,
        px: 2,
        bgcolor: "transparent",
        borderBottom: "2px solid",
        borderColor: "divider"
    };

    return (
        <>
            <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
                <Table size="small" stickyHeader>
                    <TableHead>
                        <TableRow sx={{ bgcolor: "background.paper" }}>
                            <TableCell sx={headCellSx}>Name</TableCell>
                            <TableCell sx={headCellSx}>Comment</TableCell>
                            <TableCell sx={{ ...headCellSx, width: 160 }}>Date</TableCell>
                            {/* <TableCell sx={{ ...headCellSx, width: 120 }} align="center">
                                Status
                            </TableCell> */}
                            <TableCell sx={{ ...headCellSx, width: 100 }} align="center">
                                Images
                            </TableCell>
                        </TableRow>
                    </TableHead>

                    <TableBody>
                        {data.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={6} align="center" sx={{ py: 6, color: "text.disabled" }}>
                                    No feedback found
                                </TableCell>
                            </TableRow>
                        )}

                        {data.map((item: any) => {
                            const hasImages = item.images && item.images.length > 0;
                            const isExpanded = expandedRow === item._id;
                            const dateVal = item.created_at || item.date || item.create_at;

                            return (
                                <>
                                    <TableRow
                                        key={item._id}
                                        hover
                                        onClick={() => onSelect?.(item)}
                                        sx={{
                                            cursor: onSelect ? "pointer" : "default",
                                            transition: "background 0.15s",
                                            "&:hover": { bgcolor: "action.hover" },
                                            "& td": { border: "none" },
                                            borderBottom: isExpanded ? "none" : undefined
                                        }}
                                    >
                                        {/* name */}
                                        <TableCell sx={{ px: 2, py: 1.5 }}>
                                            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                                                <Avatar
                                                    sx={{
                                                        width: 34,
                                                        height: 34,
                                                        fontSize: "0.75rem",
                                                        fontWeight: 700,
                                                        bgcolor: avatarColor(item.user.name)
                                                    }}
                                                >
                                                    {getInitials(item.user.name)}
                                                </Avatar>
                                                <Typography variant="body2" fontWeight={600} noWrap>
                                                    {item.user.name}
                                                </Typography>
                                            </Box>
                                        </TableCell>

                                        {/* comment */}
                                        <TableCell sx={{ px: 2, py: 1.5, maxWidth: 360 }}>
                                            <Typography
                                                variant="body2"
                                                color="text.secondary"
                                                sx={{
                                                    overflow: "hidden",
                                                    textOverflow: "ellipsis",
                                                    display: "-webkit-box",
                                                    WebkitLineClamp: 2,
                                                    WebkitBoxOrient: "vertical"
                                                }}
                                            >
                                                {item.feedback}
                                            </Typography>
                                        </TableCell>

                                        {/* date */}
                                        <TableCell sx={{ px: 2, py: 1.5 }}>
                                            <Typography variant="caption" color="text.secondary">
                                                {formatDate(dateVal)}
                                            </Typography>
                                        </TableCell>

                                        {/* status */}
                                        {/* <TableCell align="center" sx={{ px: 2, py: 1.5 }}>
                                            <Chip
                                                label={item.status ?? "Open"}
                                                size="small"
                                                color={statusColor(item.status ?? "open")}
                                                variant="outlined"
                                                sx={{ fontWeight: 600, fontSize: "0.7rem", borderRadius: 1 }}
                                            />
                                        </TableCell> */}

                                        {/* images count */}
                                        <TableCell align="center" sx={{ px: 2, py: 1.5 }}>
                                            {hasImages && (
                                                <Tooltip title={`${item.images.length} image(s)`}>
                                                    <Box
                                                        sx={{
                                                            display: "flex",
                                                            alignItems: "center",
                                                            justifyContent: "center",
                                                            gap: 0.5,
                                                            color: "text.secondary"
                                                        }}
                                                    >
                                                        <ImageIcon fontSize="small" />
                                                        <Typography variant="caption">{item.images.length}</Typography>
                                                    </Box>
                                                </Tooltip>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                </>
                            );
                        })}
                    </TableBody>
                </Table>
            </TableContainer>
        </>
    );
};

export default FeedbackTable;
