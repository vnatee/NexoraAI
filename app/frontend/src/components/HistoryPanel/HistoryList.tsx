import { useMsal } from "@azure/msal-react";
import { getToken, useLogin } from "../../authConfig";
import { useEffect, useMemo, useRef, useState } from "react";
import { HistoryData, HistoryItem } from "../HistoryItem";
import { Answers, HistoryProviderOptions } from "../HistoryProviders/IProvider";
import { useHistoryManager, HistoryMetaData } from "../HistoryProviders";
import { useTranslation } from "react-i18next";
import { Button, Skeleton } from "@mui/material";
import styles from "./HistoryPanel.module.css";
import HistoryIcon from "@mui/icons-material/History";

const HISTORY_COUNT_PER_LOAD = 20;

export const HistoryList = ({
    provider,
    notify,
    onChatSelected
}: {
    provider: HistoryProviderOptions;
    notify: boolean;
    onChatSelected: (answers: Answers) => void;
}) => {
    const historyManager = useHistoryManager(provider);
    const [history, setHistory] = useState<HistoryMetaData[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [hasMoreHistory, setHasMoreHistory] = useState(true);

    const client = useLogin ? useMsal().instance : undefined;
    const loaderRef = useRef<HTMLDivElement | null>(null);

    // โหลดข้อมูลครั้งแรก (เหมือน HistoryPanel)
    useEffect(() => {
        setHistory([]);
        historyManager.resetContinuationToken();
        setHasMoreHistory(true);
        loadMoreHistory();
    }, [notify]);

    const loadMoreHistory = async () => {
        setIsLoading(true);
        const token = client ? await getToken(client) : undefined;
        const items = await historyManager.getNextItems(HISTORY_COUNT_PER_LOAD, token);
        if (items.length === 0) {
            setHasMoreHistory(false);
        }
        setHistory(prevHistory => [...prevHistory, ...items]);
        setIsLoading(false);
    };

    // เลื่อนถึงท้าย list → auto load
    useEffect(() => {
        if (!loaderRef.current) return;
        const observer = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && hasMoreHistory && !isLoading) {
                loadMoreHistory();
            }
        });
        observer.observe(loaderRef.current);
        return () => observer.disconnect();
    }, [hasMoreHistory, isLoading]);

    const handleSelect = async (id: string) => {
        const token = client ? await getToken(client) : undefined;
        const item = await historyManager.getItem(id, token);
        if (item) {
            onChatSelected(item);
        }
    };

    const handleDelete = async (id: string) => {
        const token = client ? await getToken(client) : undefined;
        await historyManager.deleteItem(id, token);
        setHistory(prevHistory => prevHistory.filter(item => item.id !== id));
    };

    const groupedHistory = useMemo(() => groupHistory(history), [history]);
    const { t } = useTranslation();

    return (
        <div className={styles.historyList}>
            {/* Header + เนื้อหา */}
            <div className={styles.historySection}>
                <div className={styles.historyHeader}>
                    <Button variant="text" startIcon={<HistoryIcon />} className={styles.newChatTextButton}>
                        History
                    </Button>
                </div>

                <div className={styles.historyContent}>
                    {Object.entries(groupedHistory).map(([group, items]) => (
                        <div key={group} className={styles.group}>
                            <p className={styles.groupLabel}>{t(group)}</p>
                            {items.map((item: HistoryMetaData) => (
                                <HistoryItem key={item.id} item={item} onSelect={handleSelect} onDelete={handleDelete} />
                            ))}
                        </div>
                    ))}

                    {/* Loading skeleton */}
                    {isLoading && (
                        <div style={{ padding: "0.5rem 1rem" }}>
                            <Skeleton variant="text" height={24} sx={{ mb: 1 }} />
                            <Skeleton variant="text" height={24} sx={{ mb: 1 }} />
                            <Skeleton variant="text" height={24} />
                        </div>
                    )}

                    {/* 👉 ไม่มี history */}
                    {!isLoading && history.length === 0 && <div className={styles.noHistory}>No history available</div>}

                    {/* trigger auto-load */}
                    {hasMoreHistory && <div ref={loaderRef} style={{ height: "1px" }} />}
                </div>
            </div>
        </div>
    );
};

function groupHistory(history: HistoryData[]) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const lastWeek = new Date(today);
    lastWeek.setDate(lastWeek.getDate() - 7);
    const lastMonth = new Date(today);
    lastMonth.setDate(lastMonth.getDate() - 30);

    return history.reduce(
        (groups, item) => {
            const itemDate = new Date(item.timestamp);
            let group;

            if (itemDate >= today) {
                group = "history.today";
            } else if (itemDate >= yesterday) {
                group = "history.yesterday";
            } else if (itemDate >= lastWeek) {
                group = "history.last7days";
            } else if (itemDate >= lastMonth) {
                group = "history.last30days";
            } else {
                group = itemDate.toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "long"
                });
            }

            if (!groups[group]) {
                groups[group] = [];
            }
            groups[group].push(item);
            return groups;
        },
        {} as Record<string, HistoryData[]>
    );
}
