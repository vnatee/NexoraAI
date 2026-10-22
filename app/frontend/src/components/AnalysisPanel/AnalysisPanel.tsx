import { Stack, Pivot, PivotItem } from "@fluentui/react";
import { useTranslation } from "react-i18next";
import styles from "./AnalysisPanel.module.css";
import { Alert, Stack as StackMUI } from "@mui/material"; // 👈 ใช้ตัวนี้แทน Fluent UI Stack

import { SupportingContent } from "../SupportingContent";
import { ChatAppResponse } from "../../api";
import { AnalysisPanelTabs } from "./AnalysisPanelTabs";
import { ThoughtProcess } from "./ThoughtProcess";
import { MarkdownViewer } from "../MarkdownViewer";
import { useMsal } from "@azure/msal-react";
import { getHeaders } from "../../api";
import { useLogin, getToken } from "../../authConfig";
import { useState, useEffect } from "react";
import { Skeleton } from "@mui/material";

interface Props {
    className: string;
    activeTab: AnalysisPanelTabs;
    onActiveTabChanged: (tab: AnalysisPanelTabs) => void;
    activeCitation: string | undefined;
    activeWebUrl?: string;
    citationHeight: string;
    answer: ChatAppResponse;
}

const pivotItemDisabledStyle = { disabled: true, style: { color: "grey" } };

export const AnalysisPanel = ({ answer, activeTab, activeCitation, citationHeight, activeWebUrl, className, onActiveTabChanged }: Props) => {
    const isDisabledThoughtProcessTab: boolean = !answer.context.thoughts;
    const isDisabledSupportingContentTab: boolean = !answer.context.data_points;
    const isDisabledCitationTab: boolean = !activeCitation;
    const isDisabledWebTab = !activeWebUrl;
    const [citation, setCitation] = useState("");
    const [citationError, setCitationError] = useState("");

    const client = useLogin ? useMsal().instance : undefined;
    const { t } = useTranslation();
    const [citationLoading, setCitationLoading] = useState(false);
    const [webLoading, setWebLoading] = useState(false);

    // const fetchCitation = async () => {
    //     const token = client ? await getToken(client) : undefined;
    //     if (activeCitation) {
    //         // Get hash from the URL as it may contain #page=N
    //         // which helps browser PDF renderer jump to correct page N
    //         const originalHash = activeCitation.indexOf("#") ? activeCitation.split("#")[1] : "";
    //         const response = await fetch(activeCitation, {
    //             method: "GET",
    //             headers: await getHeaders(token)
    //         });
    //         const citationContent = await response.blob();
    //         let citationObjectUrl = URL.createObjectURL(citationContent);
    //         // Add hash back to the new blob URL
    //         if (originalHash) {
    //             citationObjectUrl += "#" + originalHash;
    //         }
    //         setCitation(citationObjectUrl);
    //     }
    // };

    const fetchCitation = async () => {
        if (!activeCitation) return;
        setCitationLoading(true);
        setCitationError("");
        try {
            const token = client ? await getToken(client) : undefined;
            const hashIndex = activeCitation.indexOf("#");
            const originalHash = hashIndex >= 0 ? activeCitation.slice(hashIndex + 1) : "";
            let requestUrl = hashIndex >= 0 ? activeCitation.slice(0, hashIndex) : activeCitation;
            const contentMarker = "/content/";
            const contentIndex = requestUrl.indexOf(contentMarker);
            if (contentIndex >= 0 && !requestUrl.includes("/chat/attachments/")) {
                const prefix = requestUrl.slice(0, contentIndex + contentMarker.length);
                const filePath = requestUrl.slice(contentIndex + contentMarker.length).replace(/\//g, "|");
                requestUrl = prefix + filePath;
            }

            const response = await fetch(requestUrl, {
                method: "GET",
                headers: await getHeaders(token)
            });
            if (!response.ok) {
                throw new Error(`Unable to open citation (${response.status})`);
            }
            const citationContent = await response.blob();
            let citationObjectUrl = URL.createObjectURL(citationContent);
            if (originalHash) {
                citationObjectUrl += "#" + originalHash;
            }
            setCitation(previous => {
                if (previous.startsWith("blob:")) URL.revokeObjectURL(previous.split("#")[0]);
                return citationObjectUrl;
            });
        } catch (error) {
            setCitation("");
            setCitationError(error instanceof Error ? error.message : "Unable to open citation");
        } finally {
            setCitationLoading(false);
        }
    };

    useEffect(() => {
        fetchCitation();
    }, [activeCitation]);

    // const renderFileViewer = () => {
    //     if (!activeCitation) {
    //         return null;
    //     }

    //     const fileExtension = activeCitation.split(".").pop()?.toLowerCase();
    //     switch (fileExtension) {
    //         case "png":
    //             return <img src={citation} className={styles.citationImg} alt="Citation Image" />;
    //         case "md":
    //             return <MarkdownViewer src={activeCitation} />;
    //         default:
    //             return <iframe title="Citation" src={citation} width="100%" height={citationHeight} />;
    //     }
    // };

    const renderFileViewer = () => {
        if (!activeCitation) return null;

        if (citationLoading) {
            return (
                <StackMUI spacing={1}>
                    <Skeleton variant="text" width="40%" animation="wave" />
                    <Skeleton variant="text" width="80%" animation="wave" />
                    <Skeleton variant="text" width="60%" animation="wave" />
                    <Skeleton variant="rectangular" width="100%" height={citationHeight} animation="wave" />
                </StackMUI>
            );
        }

        if (citationError) {
            return <Alert severity="error">{citationError}</Alert>;
        }

        const fileExtension = activeCitation.split(".").pop()?.toLowerCase();
        switch (fileExtension) {
            case "png":
                return <img src={citation} className={styles.citationImg} alt="Citation Image" />;
            case "md":
                return <MarkdownViewer src={activeCitation} />;
            default:
                return <iframe title="Citation" src={citation} width="100%" height={citationHeight} />;
        }
    };

    useEffect(() => {
        if (activeWebUrl && activeWebUrl.startsWith("https://")) {
            setWebLoading(true);
        }
    }, [activeWebUrl]);

    useEffect(() => {
        if (webLoading) {
            const timer = setTimeout(() => {
                setWebLoading(false); // ถ้า iframe ไม่ trigger onLoad ภายใน 5 วินาที
            }, 5000);
            return () => clearTimeout(timer);
        }
    }, [webLoading]);

    return (
        <Pivot
            className={className}
            selectedKey={activeTab}
            onLinkClick={pivotItem => pivotItem && onActiveTabChanged(pivotItem.props.itemKey! as AnalysisPanelTabs)}
        >
            {/* <PivotItem
                itemKey={AnalysisPanelTabs.ThoughtProcessTab}
                headerText={t("headerTexts.thoughtProcess")}
                headerButtonProps={isDisabledThoughtProcessTab ? pivotItemDisabledStyle : undefined}
            >
                <ThoughtProcess thoughts={answer.context.thoughts || []} />
            </PivotItem> */}
            {/* <PivotItem
                itemKey={AnalysisPanelTabs.SupportingContentTab}
                headerText={t("headerTexts.supportingContent")}
                headerButtonProps={isDisabledSupportingContentTab ? pivotItemDisabledStyle : undefined}
            >
                <SupportingContent supportingContent={answer.context.data_points} />
            </PivotItem> */}
            <PivotItem
                itemKey={AnalysisPanelTabs.CitationTab}
                headerText={t("headerTexts.citation")}
                headerButtonProps={isDisabledCitationTab ? pivotItemDisabledStyle : undefined}
            >
                {renderFileViewer()}
            </PivotItem>
            {/* ใหม่: แท็บ Web */}
            <PivotItem
                itemKey={AnalysisPanelTabs.WebTab}
                headerText="Web"
                headerButtonProps={isDisabledWebTab ? { disabled: true, style: { color: "grey" } } : undefined}
            >
                {activeWebUrl ? (
                    <StackMUI spacing={2} sx={{ p: 2 }}>
                        <Alert severity="info">
                            This website does not allow embedded display. Open it in a new browser tab.
                        </Alert>
                        <div style={{ color: "#555", overflowWrap: "anywhere" }}>{activeWebUrl}</div>
                        <a
                            href={activeWebUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                                alignSelf: "flex-start",
                                padding: "8px 14px",
                                backgroundColor: "#1976d2",
                                color: "white",
                                borderRadius: 4,
                                textDecoration: "none"
                            }}
                        >
                            Open in new tab
                        </a>
                    </StackMUI>
                ) : null}
                {activeWebUrl && false ? (
                    <>
                        {activeWebUrl!.startsWith("http://") ? (
                            <StackMUI spacing={2} alignItems="center" sx={{ mt: 2 }}>
                                <div style={{ color: "#555" }}>Web site not supported (HTTPS required)</div>
                                <button
                                    onClick={() => window.open(activeWebUrl, "_blank", "noopener,noreferrer")}
                                    style={{ padding: "6px 12px", backgroundColor: "#1976d2", color: "white", border: "none", borderRadius: 4 }}
                                >
                                    Open in new tab
                                </button>
                            </StackMUI>
                        ) : webLoading ? (
                            <StackMUI spacing={2} alignItems="center">
                                <Skeleton variant="text" width="40%" height={30} animation="wave" />
                                <Skeleton variant="rectangular" width="100%" height={citationHeight} animation="wave" />
                                <div style={{ marginTop: 8, color: "#777", fontStyle: "italic" }}>Loading web page...</div>
                            </StackMUI>
                        ) : (
                            <iframe
                                key={activeWebUrl}
                                title="Web"
                                src={activeWebUrl}
                                width="100%"
                                height={citationHeight}
                                style={{ border: 0 }}
                                referrerPolicy="no-referrer"
                                sandbox="allow-scripts allow-same-origin allow-popups"
                                onLoad={() => setWebLoading(false)}
                                onError={() => {
                                    setWebLoading(false);
                                    window.open(activeWebUrl, "_blank", "noopener,noreferrer");
                                }}
                            />
                        )}
                    </>
                ) : null}
            </PivotItem>
        </Pivot>
    );
};
