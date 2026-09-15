// src/components/NotificationHandler/NotificationHandler.tsx
import React, { useState, useEffect } from "react";
import { Snackbar, Alert } from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";

// Type สำหรับ detail ที่ส่งมาจาก CustomEvent
interface NotificationDetail {
    message: string;
    severity: "success" | "error" | "warning" | "info";
}

interface SnackbarState extends NotificationDetail {
    open: boolean;
}

export const NotificationHandler: React.FC = () => {
    const [snackbar, setSnackbar] = useState<SnackbarState>({
        open: false,
        message: "",
        severity: "info"
    });

    useEffect(() => {
        // ฟังก์ชันสำหรับจัดการเมื่อได้รับ event
        const handleScrapingEvent = (event: CustomEvent<NotificationDetail>) => {
            const { message, severity } = event.detail;
            setSnackbar({
                open: true,
                message,
                severity
            });
        };

        // เริ่มดักฟัง custom event ชื่อ "scrapingNotification"
        window.addEventListener("scrapingNotification", handleScrapingEvent as EventListener);

        // Cleanup function: หยุดดักฟังเมื่อ component ถูก unmount (สำคัญมาก)
        return () => {
            window.removeEventListener("scrapingNotification", handleScrapingEvent as EventListener);
        };
    }, []); // dependency array เป็น [] เพื่อให้ useEffect ทำงานแค่ครั้งเดียวตอน mount

    const handleSnackbarClose = (event?: React.SyntheticEvent | Event, reason?: string) => {
        if (reason === "clickaway") {
            return;
        }
        setSnackbar(prev => ({ ...prev, open: false }));
    };

    const getSnackbarIcon = () => {
        switch (snackbar.severity) {
            case "success":
                return <CheckCircleIcon />;
            case "error":
                return <ErrorIcon />;
            default:
                return undefined;
        }
    };

    return (
        <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={handleSnackbarClose} anchorOrigin={{ vertical: "top", horizontal: "right" }}>
            <Alert
                onClose={handleSnackbarClose}
                severity={snackbar.severity}
                variant="filled"
                icon={getSnackbarIcon()}
                sx={{ width: "100%", borderRadius: "12px" }}
            >
                {snackbar.message}
            </Alert>
        </Snackbar>
    );
};
