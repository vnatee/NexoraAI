import { useMemo, useState } from "react";
import { Stack, IconButton } from "@fluentui/react";
import { useTranslation } from "react-i18next";
import DOMPurify from "dompurify";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeRaw from "rehype-raw";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

import styles from "./Answer.module.css";
import { ChatAppResponse, getCitationFilePath, SpeechConfig } from "../../api";
import { parseAnswerToHtml } from "./AnswerParser";
import { EChartsRenderer } from "./EChartsRenderer";
import { AnswerIcon } from "./AnswerIcon";
import { normalizeMathMarkdown } from "./mathMarkdown";
import { SpeechOutputBrowser } from "./SpeechOutputBrowser";
import { SpeechOutputAzure } from "./SpeechOutputAzure";
import {
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Chip,
    CircularProgress,
    Tooltip,
    IconButton as MUIIconButton,
    Button as MUIButton,
    Box,
    Typography
} from "@mui/material";
import ThumbUpOffAltIcon from "@mui/icons-material/ThumbUpOffAlt";
import ThumbUpAltIcon from "@mui/icons-material/ThumbUpAlt";
import ThumbDownOffAltIcon from "@mui/icons-material/ThumbDownOffAlt";
import ThumbDownAltIcon from "@mui/icons-material/ThumbDownAlt";
import DownloadIcon from "@mui/icons-material/Download";

interface Props {
    answer: ChatAppResponse;
    index: number;
    speechConfig: SpeechConfig;
    isSelected?: boolean;
    isStreaming: boolean;
    onCitationClicked: (filePath: string) => void;
    onThoughtProcessClicked: () => void;
    onSupportingContentClicked: () => void;
    onFollowupQuestionClicked?: (question: string) => void;
    showFollowupQuestions?: boolean;
    showSpeechOutputBrowser?: boolean;
    showSpeechOutputAzure?: boolean;
    agentName?: string;
    onAction?: (actionId: string, index: number) => void;
    feedback?: "like" | "dislike" | null;
    onSetFeedback?: (sentiment: "like" | "dislike", index: number) => void;
    feedbackSubmitting?: boolean;
}

const normalizeMarkdownTableSeparators = (markdown: string): string => {
    const lines = markdown.split("\n");
    let inCodeFence = false;
    for (let index = 0; index < lines.length - 1; index += 1) {
        if (lines[index].trimStart().startsWith("```")) {
            inCodeFence = !inCodeFence;
            continue;
        }
        if (inCodeFence) continue;

        const header = lines[index].trim();
        const next = lines[index + 1].trim();
        if (!header.includes("|") || !/^\|?[\s:|-]*-{3,}[\s:|-]*$/.test(next)) continue;

        const columnCount = header.replace(/^\|/, "").replace(/\|$/, "").split("|").length;
        if (columnCount < 2) continue;

        // A table immediately following `2. Section` is parsed as literal
        // content inside that ordered-list item. Separate the table block.
        if (index > 0 && lines[index - 1].trim() !== "") {
            lines.splice(index, 0, "");
            index += 1;
        }

        let continuationEnd = index + 1;
        while (
            continuationEnd + 1 < lines.length &&
            /^[\s:-]*-{3,}[\s:|-]*$/.test(lines[continuationEnd + 1].trim())
        ) {
            continuationEnd += 1;
        }
        lines.splice(index + 1, continuationEnd - index, `| ${Array(columnCount).fill("---").join(" | ")} |`);
    }
    return lines.join("\n");
};

export const Answer = ({
    answer,
    index,
    speechConfig,
    isSelected,
    isStreaming,
    onCitationClicked,
    onThoughtProcessClicked,
    onSupportingContentClicked,
    onFollowupQuestionClicked,
    showFollowupQuestions,
    showSpeechOutputAzure,
    showSpeechOutputBrowser,
    agentName,
    onAction,
    feedback,
    onSetFeedback,
    feedbackSubmitting
}: Props) => {
    const followupQuestions = answer.context?.followup_questions;
    const parsedAnswer = useMemo(() => parseAnswerToHtml(answer, isStreaming, onCitationClicked), [answer]);
    const { t } = useTranslation();
    // ⭐ CHART CAPABILITY: strip chart spec ออกจากข้อความก่อน sanitize
    //    ซ่อน raw JSON spec เสมอ — ระหว่าง streaming ถ้าตรวจพบ JSON กำลังถูกพิมพ์
    //    ให้ซ่อนทั้งหมดตั้งแต่ { แรก และแสดง placeholder แทน
    const stripChartSpec = (html: string, streaming: boolean): { result: string; isGenerating: boolean } => {
        // strip code fence blocks (```chart-spec / ```json)
        let result = html.replace(/```(?:chart-spec|json)?[\s\S]*?```/g, "");
        let isGenerating = false;

        if (streaming) {
            // ระหว่าง streaming: ถ้าเจอ { ที่มี "option" ตามมา (แม้ยังไม่ปิด) → ซ่อนทั้งหมดแทน
            const jsonStartIdx = result.search(/\{\s*\n?\s*"option"\s*:/);
            if (jsonStartIdx !== -1) {
                result = result.substring(0, jsonStartIdx).trimEnd();
                isGenerating = true;
            }
        } else {
            // หลัง streaming จบ: strip bare JSON block ที่มี "option" และ "height"
            if (result.includes('"option"') && result.includes('"height"')) {
                result = result.replace(/\{\s*\n?\s*"option"\s*:[\s\S]*?"height"\s*:\s*\d+\s*\n?\s*\}/g, "");
            }
            // กรณี JSON ยังค้างอยู่โดยไม่มี height (parse ล้มเหลว) → ซ่อน
            if (result.includes('"option"')) {
                result = result.replace(/\{[\s\S]*?"option"\s*:[\s\S]*$/g, "");
            }
        }
        return { result: result.trim(), isGenerating };
    };
    const { result: answerWithoutChartSpec, isGenerating: isGeneratingChart } = stripChartSpec(parsedAnswer.answerHtml, isStreaming);
    const sanitizedAnswerHtml = DOMPurify.sanitize(normalizeMarkdownTableSeparators(answerWithoutChartSpec));
    // Do not append Markdown hard-break spaces to every line. A hard break on
    // table header/separator rows prevents remark-gfm from recognizing tables.
    const markdownReady = normalizeMathMarkdown(sanitizedAnswerHtml);

    const [copied, setCopied] = useState(false);

    const handleDiagramDownload = () => {
        const diagram = answer.context?.diagram;
        if (!diagram) return;
        const url = URL.createObjectURL(new Blob([diagram.content], { type: diagram.mime_type }));
        const link = document.createElement("a");
        link.href = url;
        link.download = diagram.filename;
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 0);
    };

    const handleCopy = () => {
        // Single replace to remove all HTML tags to remove the citations
        // ⭐ CHART CAPABILITY: ลบ chart-spec block ออกจากข้อความที่ copy ด้วย
        const textToCopy = sanitizedAnswerHtml
            .replace(/<a [^>]*><sup>\d+<\/sup><\/a>|<[^>]+>/g, "")
            .replace(/```chart-spec\s*[\s\S]*?```/g, "")
            .trim();

        navigator.clipboard
            .writeText(textToCopy)
            .then(() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            })
            .catch(err => console.error("Failed to copy text: ", err));
    };

    const getCitationLabel = (citation: string) => {
        const trimmedCitation = citation.trim();
        if (/^https?:\/\//i.test(trimmedCitation)) {
            try {
                const url = new URL(trimmedCitation);
                const readablePath = decodeURIComponent(url.pathname).replace(/\/$/, "");
                return readablePath ? `${url.hostname}${readablePath}` : url.hostname;
            } catch {
                return trimmedCitation;
            }
        }

        // citation ตัวอย่าง:
        // 9e2fa6ed-.../n8n week 1 - intro to n8n.pdf#page=13

        // ✅ ตัด query/fragment ไว้ก่อน (ถ้ามี)
        const [pathPart, hashPart] = citation.split("#"); // hashPart = "page=13" หรือ undefined

        // ✅ เอาแค่ชื่อไฟล์ตัวท้ายสุด
        const fileName = decodeURIComponent(pathPart.split("/").pop() ?? pathPart);

        // ✅ ถ้ามี #page=... ให้แสดงต่อท้าย
        if (hashPart?.startsWith("page=")) {
            return `${fileName}#${hashPart}`;
        }

        return fileName;
    };

    return (
        <Stack className={`${styles.answerContainer} ${isSelected && styles.selected}`} verticalAlign="space-between">
            <Stack.Item>
                <Stack horizontal horizontalAlign="space-between">
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <AnswerIcon />
                        {agentName && (
                            <Chip
                                label={agentName}
                                color="secondary"
                                sx={{
                                    fontWeight: "bold",
                                    fontSize: "0.9rem",
                                    height: "26px",
                                    borderRadius: "8px",
                                    background: "linear-gradient(90deg, #5c6bc0, #3f51b5)",
                                    color: "white",
                                    "& .MuiChip-label": { padding: "0 10px" }
                                }}
                            />
                        )}
                    </div>
                    <div>
                        <IconButton
                            style={{ color: "black" }}
                            iconProps={{ iconName: copied ? "CheckMark" : "Copy" }}
                            title={copied ? t("tooltips.copied") : t("tooltips.copy")}
                            ariaLabel={copied ? t("tooltips.copied") : t("tooltips.copy")}
                            onClick={handleCopy}
                        />
                        {/* <IconButton
                            style={{ color: "black" }}
                            iconProps={{ iconName: "Lightbulb" }}
                            title={t("tooltips.showThoughtProcess")}
                            ariaLabel={t("tooltips.showThoughtProcess")}
                            onClick={() => onThoughtProcessClicked()}
                            disabled={!answer.context.thoughts?.length || isStreaming}
                        />
                        <IconButton
                            style={{ color: "black" }}
                            iconProps={{ iconName: "ClipboardList" }}
                            title={t("tooltips.showSupportingContent")}
                            ariaLabel={t("tooltips.showSupportingContent")}
                            onClick={() => onSupportingContentClicked()}
                            disabled={!answer.context.data_points || isStreaming}
                        /> */}
                        {/* {showSpeechOutputAzure && (
                            <SpeechOutputAzure answer={sanitizedAnswerHtml} index={index} speechConfig={speechConfig} isStreaming={isStreaming} />
                        )} */}
                        {showSpeechOutputBrowser && <SpeechOutputBrowser answer={sanitizedAnswerHtml} />}
                    </div>
                </Stack>
            </Stack.Item>

            <Stack.Item grow>
                <div className={styles.answerText}>
                    {/* <ReactMarkdown children={sanitizedAnswerHtml} rehypePlugins={[rehypeRaw]} remarkPlugins={[remarkGfm]} /> */}
                    <ReactMarkdown
                        children={markdownReady}
                        rehypePlugins={[rehypeRaw, [rehypeKatex, { strict: false, throwOnError: false }]]}
                        remarkPlugins={[remarkGfm, remarkMath]}
                        components={{
                            table: ({ node, ...props }: any) => (
                                <TableContainer
                                    component={Paper}
                                    elevation={0} // ปรับ shadow ด้วย sx แทน
                                    sx={{
                                        borderRadius: 3,
                                        margin: "1em 0",
                                        overflowX: "auto",
                                        overflowY: "hidden",
                                        border: "1px solid #1f2937",
                                        backgroundClip: "padding-box",
                                        boxShadow: "0 4px 8px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.06)"
                                    }}
                                >
                                    <Table
                                        {...props}
                                        sx={{
                                            width: "100%",
                                            minWidth: { xs: 650, md: 0 },
                                            tableLayout: { xs: "auto", md: "fixed" }
                                        }}
                                    />
                                </TableContainer>
                            ),
                            thead: ({ node, ...props }: any) => <TableHead {...props} sx={{ backgroundColor: "#f5f7fb" }} />,
                            tbody: ({ node, ...props }: any) => <TableBody {...props} />,
                            tr: ({ node, ...props }: any) => (
                                <TableRow
                                    sx={{
                                        "&:nth-of-type(even)": { backgroundColor: "#fafbff" },
                                        // "&:hover": {
                                        //     backgroundColor: "#eef2ff",
                                        //     transform: "scale(1.005)", // subtle scale effect
                                        //     boxShadow: "0 2px 4px rgba(0,0,0,0.08)"
                                        // },
                                        transition: "all 0.2s ease-in-out"
                                    }}
                                    {...props}
                                />
                            ),
                            th: ({ node, ...props }: any) => (
                                <TableCell
                                    sx={{
                                        fontWeight: 700,
                                        padding: "0.75em 1em",
                                        textAlign: "left",
                                        background: "linear-gradient(90deg, #e0e7ff, #f5f7fb)" // gradient header
                                    }}
                                    {...props}
                                />
                            ),
                            td: ({ node, ...props }: any) => (
                                <TableCell
                                    sx={{
                                        padding: "0.85em 1.2em",
                                        borderBottom: "1px solid #e0e0e0",
                                        borderRadius: "0.25em", // subtle corner
                                        overflowWrap: "anywhere",
                                        wordBreak: "break-word"
                                    }}
                                    {...props}
                                />
                            )
                        }}
                    />
                </div>
            </Stack.Item>

            {/* ✅ ADD: Action Buttons */}
            {!!answer?.context?.actions?.length && (
                <Stack.Item>
                    <Stack horizontal tokens={{ childrenGap: 8 }}>
                        {answer.context.actions.map((a, i) => (
                            <MUIButton
                                key={a.id || i}
                                variant={a.variant || "contained"}
                                disabled={!!a.disabled}
                                onClick={() => onAction && onAction(a.id, index)}
                                sx={{ borderRadius: "10px", textTransform: "none", fontWeight: 600 }}
                            >
                                {a.label}
                            </MUIButton>
                        ))}
                    </Stack>
                </Stack.Item>
            )}

            {answer.context?.diagram && (
                <Stack.Item>
                    <Paper variant="outlined" sx={{ mt: 1.5, p: 1.5, borderRadius: 2 }}>
                        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 1 }}>
                            <Typography variant="subtitle2">Diagram ready</Typography>
                            <MUIButton
                                variant="contained"
                                startIcon={<DownloadIcon />}
                                onClick={handleDiagramDownload}
                                disabled={isStreaming}
                                aria-label={`Download ${answer.context.diagram.filename}`}
                                sx={{ borderRadius: "10px", textTransform: "none", fontWeight: 600, maxWidth: "100%" }}
                            >
                                Download {answer.context.diagram.filename}
                            </MUIButton>
                        </Box>
                    </Paper>
                </Stack.Item>
            )}

            {/* ⭐ CHART CAPABILITY: loading placeholder ระหว่าง streaming */}
            {isGeneratingChart && (
                <Stack.Item>
                    <Paper
                        variant="outlined"
                        sx={{
                            mt: 1.5,
                            borderRadius: 3,
                            border: "1px solid #e0e0e0",
                            boxShadow: "0 4px 10px rgba(0,0,0,0.06)",
                            backgroundColor: "#fff",
                            width: "100%",
                            overflow: "hidden",
                            height: 200,
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 1.5
                        }}
                    >
                        <Box sx={{ display: "flex", gap: 0.8, alignItems: "flex-end", height: 40 }}>
                            {[0.6, 1, 0.75, 1.2, 0.85].map((h, i) => (
                                <Box
                                    key={i}
                                    sx={{
                                        width: 10,
                                        borderRadius: "3px 3px 0 0",
                                        background: "linear-gradient(180deg, #5470c6, #91cc75)",
                                        animation: "chartBarPulse 1.2s ease-in-out infinite",
                                        animationDelay: `${i * 0.15}s`,
                                        height: `${h * 100}%`,
                                        "@keyframes chartBarPulse": {
                                            "0%, 100%": { opacity: 0.4, transform: "scaleY(0.6)" },
                                            "50%": { opacity: 1, transform: "scaleY(1)" }
                                        }
                                    }}
                                />
                            ))}
                        </Box>
                        <Typography variant="caption" color="text.secondary" sx={{ letterSpacing: 0.5 }}>
                            กำลังสร้างกราฟ...
                        </Typography>
                    </Paper>
                </Stack.Item>
            )}

            {/* ⭐ CHART CAPABILITY: render กราฟด้วย EChartsRenderer เท่านั้น */}
            {answer.context?.chart && (
                <Stack.Item>
                    <EChartsRenderer spec={answer.context.chart} />
                </Stack.Item>
            )}

            {/* ✅ ADD: Feedback Buttons (Like / Dislike) */}
            <Stack.Item>
                <div className={styles.feedbackRow}>
                    <div className={styles.feedbackRight}>
                        <div className={styles.feedbackButtons}>
                            <div className={styles.feedbackLoader} aria-hidden={!feedbackSubmitting}>
                                {feedbackSubmitting ? <CircularProgress size={16} /> : null}
                            </div>

                            <Tooltip title="Like" placement="top">
                                <MUIIconButton
                                    size="small"
                                    disableRipple
                                    className={`${styles.feedbackBtn} ${feedback === "like" ? styles.activeLike : ""}`}
                                    onClick={() => onSetFeedback && onSetFeedback("like", index)}
                                    disabled={isStreaming || feedbackSubmitting}
                                    aria-label="like"
                                >
                                    {feedback === "like" ? <ThumbUpAltIcon fontSize="small" /> : <ThumbUpOffAltIcon fontSize="small" />}
                                </MUIIconButton>
                            </Tooltip>

                            <Tooltip title="Dislike" placement="top">
                                <MUIIconButton
                                    size="small"
                                    disableRipple
                                    className={`${styles.feedbackBtn} ${feedback === "dislike" ? styles.activeDislike : ""}`}
                                    onClick={() => onSetFeedback && onSetFeedback("dislike", index)}
                                    disabled={isStreaming || feedbackSubmitting}
                                    aria-label="dislike"
                                >
                                    {feedback === "dislike" ? <ThumbDownAltIcon fontSize="small" /> : <ThumbDownOffAltIcon fontSize="small" />}
                                </MUIIconButton>
                            </Tooltip>
                        </div>
                    </div>
                </div>
            </Stack.Item>

            {/* ✅ Chart Image (legacy — รูปภาพ URL) */}
            {answer.context?.chartUrl && (
                <Stack.Item>
                    <div style={{ marginTop: "12px", textAlign: "center" }}>
                        <img
                            src={answer.context.chartUrl}
                            alt="Generated Chart"
                            style={{
                                maxWidth: "100%",
                                borderRadius: "12px",
                                border: "1px solid #e0e0e0",
                                boxShadow: "0 4px 10px rgba(0,0,0,0.08)"
                            }}
                        />
                    </div>
                </Stack.Item>
            )}

            {!!parsedAnswer.citations.length && (
                <Stack.Item>
                    <Stack horizontal wrap tokens={{ childrenGap: 5 }}>
                        <span className={styles.citationLearnMore}>{t("citationWithColon")}</span>
                        {parsedAnswer.citations.map((x, i) => {
                            const path = getCitationFilePath(x);
                            return (
                                <a
                                    key={i}
                                    className={styles.citation}
                                    title={x} // tooltip ยังคงเป็น full citation
                                    onClick={() => onCitationClicked(path)} // ✅ ส่ง full path เหมือนเดิม
                                >
                                    {`${i + 1}. ${getCitationLabel(x)}`} {/* ✅ แสดงสั้น */}
                                </a>
                            );
                        })}
                    </Stack>
                </Stack.Item>
            )}

            {!!followupQuestions?.length && showFollowupQuestions && onFollowupQuestionClicked && (
                <Stack.Item>
                    <Stack horizontal wrap className={`${!!parsedAnswer.citations.length ? styles.followupQuestionsList : ""}`} tokens={{ childrenGap: 6 }}>
                        <span className={styles.followupQuestionLearnMore}>{t("followupQuestions")}</span>
                        {followupQuestions.map((x, i) => {
                            return (
                                <a key={i} className={styles.followupQuestion} title={x} onClick={() => onFollowupQuestionClicked(x)}>
                                    {`${x}`}
                                </a>
                            );
                        })}
                    </Stack>
                </Stack.Item>
            )}
        </Stack>
    );
};
