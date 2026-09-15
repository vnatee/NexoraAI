import React, { useState } from "react";
import { Box, Typography, Avatar, Chip, Divider, IconButton, Dialog, Tooltip } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import CalendarTodayIcon from "@mui/icons-material/CalendarToday";
import PersonIcon from "@mui/icons-material/Person";
import ChatBubbleOutlineIcon from "@mui/icons-material/ChatBubbleOutline";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import ArrowBackIosNewIcon from "@mui/icons-material/ArrowBackIosNew";
import ArrowForwardIosIcon from "@mui/icons-material/ArrowForwardIos";

interface Props {
    item: any;
}

const avatarColor = (name: string) => {
    const colors = ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#ef4444"];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
};

const getInitials = (name: string) =>
    name
        .split(" ")
        .map((n: string) => n[0])
        .slice(0, 2)
        .join("")
        .toUpperCase();

const statusColor = (status?: string): "success" | "warning" | "error" | "default" => {
    if (!status) return "warning";
    const s = status.toLowerCase();
    if (s === "resolved" || s === "done") return "success";
    if (s === "rejected" || s === "closed") return "error";
    return "warning";
};

const formatDate = (raw?: string): string => {
    if (!raw) return "—";
    try {
        return new Date(raw).toLocaleDateString("th-TH", {
            year: "numeric",
            month: "long",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        });
    } catch {
        return raw;
    }
};

const Section = ({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) => (
    <Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
            <Box sx={{ color: "text.disabled", display: "flex" }}>{icon}</Box>
            <Typography variant="caption" fontWeight={700} color="text.disabled" textTransform="uppercase" letterSpacing="0.06em">
                {label}
            </Typography>
        </Box>
        {children}
    </Box>
);

const FeedbackDetail = ({ item }: Props) => {
    const [lightboxOpen, setLightboxOpen] = useState(false);
    const [lightboxIndex, setLightboxIndex] = useState(0);

    const hasImages = item.images && item.images.length > 0;
    const dateVal = item.created_at || item.date;

    const openLightbox = (i: number) => {
        setLightboxIndex(i);
        setLightboxOpen(true);
    };
    const closeLightbox = () => setLightboxOpen(false);
    const next = () => setLightboxIndex(p => (p + 1) % item.images.length);
    const prev = () => setLightboxIndex(p => (p - 1 + item.images.length) % item.images.length);

    return (
        <>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
                {/* ── Header card ── */}
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 2,
                        p: 2.5,
                        borderRadius: 3,
                        background: `linear-gradient(135deg, ${avatarColor(item.user.name)}22 0%, transparent 100%)`,
                        border: "1px solid",
                        borderColor: "divider"
                    }}
                >
                    <Avatar
                        sx={{
                            width: 52,
                            height: 52,
                            bgcolor: avatarColor(item.user.name),
                            fontSize: "1.1rem",
                            fontWeight: 700
                        }}
                    >
                        {getInitials(item.user.name)}
                    </Avatar>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="subtitle1" fontWeight={700} lineHeight={1.2} noWrap sx={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                            {item.user.name}
                        </Typography>
                        {dateVal && (
                            <Typography variant="caption" color="text.secondary" noWrap sx={{ overflow: "hidden", textOverflow: "ellipsis", display: "block" }}>
                                {formatDate(dateVal)}
                            </Typography>
                        )}
                    </Box>
                    <Chip
                        label={item.status ?? "Open"}
                        size="small"
                        color={statusColor(item.status)}
                        variant="outlined"
                        sx={{ fontWeight: 600, fontSize: "0.7rem", borderRadius: 1, flexShrink: 0 }}
                    />
                </Box>

                <Divider />

                {/* ── Metadata row ── */}
                <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
                    <Section icon={<PersonIcon fontSize="small" />} label="Submitted by">
                        <Typography variant="body2" fontWeight={500}>
                            {item.user.name}
                        </Typography>
                    </Section>

                    <Section icon={<CalendarTodayIcon fontSize="small" />} label="Date">
                        <Typography variant="body2">{formatDate(dateVal)}</Typography>
                    </Section>
                </Box>

                <Divider />

                {/* ── Feedback text ── */}
                <Section icon={<ChatBubbleOutlineIcon fontSize="small" />} label="Feedback">
                    <Box
                        sx={{
                            p: 2.5,
                            borderRadius: 2,
                            bgcolor: "action.hover",
                            border: "1px solid",
                            borderColor: "divider"
                        }}
                    >
                        <Typography variant="body2" lineHeight={1.8} color="text.primary">
                            {item.feedback || <span style={{ color: "#9e9e9e" }}>No comment provided.</span>}
                        </Typography>
                    </Box>
                </Section>

                {/* ── Images ── */}
                {hasImages && (
                    <>
                        <Divider />
                        <Section icon={<ImageOutlinedIcon fontSize="small" />} label={`Attachments (${item.images.length})`}>
                            <Box
                                sx={{
                                    display: "grid",
                                    gridTemplateColumns: "repeat(auto-fill, minmax(100px, 1fr))",
                                    gap: 1.5
                                }}
                            >
                                {item.images.map((img: any, i: number) => (
                                    <Tooltip key={i} title="Click to enlarge">
                                        <Box
                                            onClick={() => openLightbox(i)}
                                            sx={{
                                                height: 90,
                                                borderRadius: 2,
                                                overflow: "hidden",
                                                border: "1px solid",
                                                borderColor: "divider",
                                                cursor: "zoom-in",
                                                transition: "transform 0.2s, box-shadow 0.2s",
                                                "&:hover": { transform: "scale(1.04)", boxShadow: 4 }
                                            }}
                                        >
                                            <img
                                                src={`data:${img.file_type};base64,${img.image}`}
                                                alt={`attachment-${i + 1}`}
                                                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                                            />
                                        </Box>
                                    </Tooltip>
                                ))}
                            </Box>
                        </Section>
                    </>
                )}
            </Box>

            {/* ── Lightbox ── */}
            <Dialog
                open={lightboxOpen}
                onClose={closeLightbox}
                maxWidth="md"
                fullWidth
                sx={{ zIndex: 1500 }}
                PaperProps={{ sx: { bgcolor: "#0a0a0a", borderRadius: 3, overflow: "hidden" } }}
            >
                <Box sx={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center", p: 2 }}>
                    <IconButton
                        onClick={closeLightbox}
                        sx={{
                            position: "absolute",
                            right: 12,
                            top: 12,
                            zIndex: 10,
                            bgcolor: "rgba(255,255,255,0.1)",
                            color: "white",
                            "&:hover": { bgcolor: "rgba(255,255,255,0.2)" }
                        }}
                    >
                        <CloseIcon />
                    </IconButton>

                    <Box sx={{ display: "flex", alignItems: "center", gap: 1, width: "100%", justifyContent: "center" }}>
                        {item.images.length > 1 && (
                            <IconButton
                                onClick={prev}
                                sx={{ color: "white", bgcolor: "rgba(255,255,255,0.1)", "&:hover": { bgcolor: "rgba(255,255,255,0.2)" } }}
                            >
                                <ArrowBackIosNewIcon />
                            </IconButton>
                        )}
                        <img
                            src={`data:${item.images[lightboxIndex]?.file_type};base64,${item.images[lightboxIndex]?.image}`}
                            alt="full"
                            style={{ maxHeight: "70vh", maxWidth: "100%", objectFit: "contain", borderRadius: 8 }}
                        />
                        {item.images.length > 1 && (
                            <IconButton
                                onClick={next}
                                sx={{ color: "white", bgcolor: "rgba(255,255,255,0.1)", "&:hover": { bgcolor: "rgba(255,255,255,0.2)" } }}
                            >
                                <ArrowForwardIosIcon />
                            </IconButton>
                        )}
                    </Box>

                    {item.images.length > 1 && (
                        <Box sx={{ display: "flex", gap: 0.75, mt: 1.5 }}>
                            {item.images.map((_: any, i: number) => (
                                <Box
                                    key={i}
                                    onClick={() => setLightboxIndex(i)}
                                    sx={{
                                        width: i === lightboxIndex ? 20 : 8,
                                        height: 8,
                                        borderRadius: 4,
                                        bgcolor: i === lightboxIndex ? "primary.main" : "rgba(255,255,255,0.3)",
                                        cursor: "pointer",
                                        transition: "all 0.25s"
                                    }}
                                />
                            ))}
                        </Box>
                    )}

                    <Typography variant="caption" color="rgba(255,255,255,0.4)" mt={1}>
                        {lightboxIndex + 1} / {item.images.length}
                    </Typography>
                </Box>
            </Dialog>
        </>
    );
};

export default FeedbackDetail;
