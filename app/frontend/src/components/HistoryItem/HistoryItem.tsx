import { useState, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import styles from "./HistoryItem.module.css";
import { DefaultButton } from "@fluentui/react";
import { Delete24Regular } from "@fluentui/react-icons";
import Tooltip from "@mui/material/Tooltip";
import { Dialog, DialogTitle, DialogContent, DialogActions, Button as MUIButton, Typography } from "@mui/material";
export interface HistoryData {
    id: string;
    title: string;
    timestamp: number;
}

interface HistoryItemProps {
    item: HistoryData;
    onSelect: (id: string) => void;
    onDelete: (id: string) => void;
}

export function HistoryItem({ item, onSelect, onDelete }: HistoryItemProps) {
    const [isModalOpen, setIsModalOpen] = useState(false);

    const handleDelete = useCallback(() => {
        setIsModalOpen(false);
        onDelete(item.id);
    }, [item.id, onDelete]);

    const truncateText = (text: any, maxLength: any) => {
        if (text.length <= maxLength) {
            return text;
        }
        return text.substring(0, maxLength) + "...";
    };

    const formatMultilineText = (text: string) => {
        // แปลงข้อความยาวให้ตัดบรรทัดทุก ๆ 40 ตัวอักษร
        const chunkSize = 40;
        const regex = new RegExp(`(.{1,${chunkSize}})`, "g");
        return text.match(regex)?.join("\n") ?? text;
    };

    return (
        <>
            <div className={styles.historyItem}>
                <Tooltip
                    placement="bottom-start"
                    title={
                        <div
                            style={{
                                whiteSpace: "pre-wrap",
                                wordBreak: "break-word",
                                overflowWrap: "break-word",
                                maxWidth: "unset" // ยกเลิกการจำกัดความกว้าง
                            }}
                        >
                            {item.title}
                        </div>
                    }
                    PopperProps={{
                        modifiers: [
                            {
                                name: "preventOverflow",
                                enabled: false // ปิดการบีบ tooltip เมื่ออยู่ขอบจอ
                            },
                            {
                                name: "flip",
                                enabled: false // ปิดการสลับด้านอัตโนมัติ
                            }
                        ]
                    }}
                    slotProps={{
                        tooltip: {
                            sx: {
                                whiteSpace: "pre-wrap",
                                wordBreak: "break-word",
                                overflowWrap: "break-word",
                                backgroundColor: "#333",
                                color: "#fff",
                                fontSize: "0.9rem",
                                lineHeight: 1.4,
                                padding: "8px 12px",
                                borderRadius: "8px",
                                boxShadow: 3,
                                maxWidth: "none !important" // ปิด maxWidth ของ tooltip เอง
                            }
                        }
                    }}
                >
                    <button onClick={() => onSelect(item.id)} className={styles.historyItemButton}>
                        <div className={styles.historyItemTitle}>{truncateText(item.title, 25)}</div>
                    </button>
                </Tooltip>

                <button onClick={() => setIsModalOpen(true)} className={styles.deleteButton} aria-label="delete this chat history">
                    <Delete24Regular className={styles.deleteIcon} />
                </button>
            </div>
            <DeleteHistoryModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onConfirm={handleDelete} />
        </>
    );
}

function DeleteHistoryModal({ isOpen, onClose, onConfirm }: { isOpen: boolean; onClose: () => void; onConfirm: () => void }) {
    const { t } = useTranslation();

    return (
        <Dialog open={isOpen} onClose={onClose} fullWidth maxWidth="xs">
            <DialogTitle sx={{ color: "#000" }}>{t("history.deleteModalTitle")}</DialogTitle>

            <DialogContent dividers>
                <Typography sx={{ color: "#000" }}>{t("history.deleteModalDescription")}</Typography>
            </DialogContent>

            <DialogActions>
                <MUIButton onClick={onClose} variant="outlined" sx={{ color: "#000", borderColor: "#d1d5db" }}>
                    {t("history.cancelLabel")}
                </MUIButton>
                <MUIButton onClick={onConfirm} variant="contained" color="error">
                    {t("history.deleteLabel")}
                </MUIButton>
            </DialogActions>
        </Dialog>
    );
}
