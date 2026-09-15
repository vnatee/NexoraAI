import { useState, useEffect, useContext, useRef } from "react";
import { Stack, TextField } from "@fluentui/react";
import { Button, Spinner, Tooltip } from "@fluentui/react-components";
import { Attach24Regular, Dismiss16Regular, Document24Regular, Send28Filled } from "@fluentui/react-icons";
import { useTranslation } from "react-i18next";

import styles from "./QuestionInput.module.css";
import { SpeechInput } from "./SpeechInput";
import { LoginContext } from "../../loginContext";
import { requireLogin } from "../../authConfig";
import { deleteChatDocumentApi, listChatDocumentsApi, uploadChatDocumentApi } from "../../api/api";
import { ChatAttachmentInput, ChatDocumentAttachment, EvidenceMatrixOptions } from "../../api/models";

const ACCEPTED_IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp", "image/gif"]);
const MAX_IMAGE_COUNT = 4;
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const MAX_TOTAL_BYTES = 20 * 1024 * 1024;
const ACCEPTED_DOCUMENT_EXTENSIONS = new Set(["pdf", "docx", "pptx", "xlsx", "txt", "csv", "md"]);
const MAX_DOCUMENT_COUNT = 10;
const MAX_DOCUMENT_BYTES = 25 * 1024 * 1024;
const DOCUMENT_POLL_INTERVAL_MS = 1_000;
const DOCUMENT_POLL_ATTEMPTS = 120;

type DocumentDraftStatus = "draft" | "uploading" | "processing" | "ready" | "failed";

type DocumentDraft = {
    uploadId: string;
    file: File;
    status: DocumentDraftStatus;
    attachment?: ChatDocumentAttachment;
    error?: string;
};

interface Props {
    onSend: (
        question: string,
        attachments?: ChatAttachmentInput[],
        documents?: ChatDocumentAttachment[],
        evidenceOptions?: EvidenceMatrixOptions
    ) => void | Promise<void>;
    disabled: boolean;
    initQuestion?: string;
    placeholder?: string;
    clearOnSend?: boolean;
    showSpeechInput?: boolean;
    imagesAvailable?: boolean;
    imageDisabledReason?: string;
    showAttachmentButton?: boolean;
    attachmentDisabledReason?: string;
    conversationId: string;
    agentId?: string;
    documentsAvailable?: boolean;
    getAccessToken?: () => Promise<string | undefined>;
}

export const QuestionInput = ({
    onSend,
    disabled,
    placeholder,
    clearOnSend,
    initQuestion,
    showSpeechInput,
    imagesAvailable = false,
    imageDisabledReason,
    showAttachmentButton = false,
    attachmentDisabledReason,
    conversationId,
    agentId,
    documentsAvailable = false,
    getAccessToken
}: Props) => {
    const [question, setQuestion] = useState<string>("");
    const { loggedIn } = useContext(LoginContext);
    const { t } = useTranslation();
    const [isComposing, setIsComposing] = useState(false);
    const [attachments, setAttachments] = useState<ChatAttachmentInput[]>([]);
    const [documents, setDocuments] = useState<DocumentDraft[]>([]);
    const [attachmentError, setAttachmentError] = useState("");
    const [isPreparingDocuments, setIsPreparingDocuments] = useState(false);
    const [evidenceMatrix, setEvidenceMatrix] = useState(false);
    const [attachmentEvidenceScope, setAttachmentEvidenceScope] = useState<EvidenceMatrixOptions["attachmentEvidenceScope"]>("knowledge_only");
    const fileInputRef = useRef<HTMLInputElement>(null);
    const conversationIdRef = useRef(conversationId);

    useEffect(() => {
        initQuestion && setQuestion(initQuestion);
    }, [initQuestion]);

    useEffect(() => {
        conversationIdRef.current = conversationId;
        setDocuments([]);
        setEvidenceMatrix(false);
        setAttachmentError("");
    }, [conversationId]);

    const updateDocument = (uploadId: string, update: Partial<DocumentDraft>) => {
        setDocuments(items => items.map(item => (item.uploadId === uploadId ? { ...item, ...update } : item)));
    };

    const prepareDocuments = async (): Promise<ChatDocumentAttachment[]> => {
        if (!documents.length) return [];
        if (!documentsAvailable) throw new Error("Private document attachments are not enabled for this deployment.");
        const activeConversationId = conversationId;
        const token = await getAccessToken?.();
        const prepared: ChatDocumentAttachment[] = [];
        const attachmentUploadIds = new Map<string, string>();
        for (const draft of documents) {
            if (draft.attachment?.status === "ready") {
                prepared.push(draft.attachment);
                attachmentUploadIds.set(draft.attachment.id, draft.uploadId);
                continue;
            }
            if (draft.attachment?.status === "failed") {
                throw new Error(`${draft.file.name} could not be processed. Remove it and attach the file again.`);
            }
            updateDocument(draft.uploadId, { status: "uploading", error: undefined });
            try {
                const attachment = await uploadChatDocumentApi(
                    draft.file,
                    activeConversationId,
                    draft.uploadId,
                    agentId,
                    token
                );
                updateDocument(draft.uploadId, {
                    attachment,
                    status: attachment.status === "ready" ? "ready" : attachment.status === "failed" ? "failed" : "processing"
                });
                prepared.push(attachment);
                attachmentUploadIds.set(attachment.id, draft.uploadId);
            } catch (error) {
                const message = error instanceof Error ? error.message : "Document upload failed";
                updateDocument(draft.uploadId, { status: "failed", error: message });
                throw error;
            }
        }

        for (let attempt = 0; attempt < DOCUMENT_POLL_ATTEMPTS; attempt += 1) {
            if (conversationIdRef.current !== activeConversationId) throw new Error("The active conversation changed during document processing.");
            const latest = await listChatDocumentsApi(activeConversationId, token);
            const byId = new Map(latest.map(item => [item.id, item]));
            let allReady = true;
            const ready: ChatDocumentAttachment[] = [];
            for (const item of prepared) {
                const current = byId.get(item.id) || item;
                const uploadId = attachmentUploadIds.get(item.id);
                if (uploadId) {
                    updateDocument(uploadId, {
                        attachment: current,
                        status: current.status === "ready" ? "ready" : current.status === "failed" ? "failed" : "processing",
                        error: current.status === "failed" ? current.error_code || "Document processing failed" : undefined
                    });
                }
                if (current.status === "failed") {
                    throw new Error(`${current.filename} could not be processed (${current.error_code || "processing_failed"}).`);
                }
                if (current.status !== "ready") allReady = false;
                else ready.push(current);
            }
            if (allReady) return ready;
            await new Promise(resolve => window.setTimeout(resolve, DOCUMENT_POLL_INTERVAL_MS));
        }
        throw new Error("Document processing is taking longer than expected. You can leave the files attached and try Send again.");
    };

    const sendQuestion = async () => {
        if (disabled || isPreparingDocuments || (!question.trim() && attachments.length === 0 && documents.length === 0)) {
            return;
        }
        setAttachmentError("");
        setIsPreparingDocuments(true);
        try {
            const readyDocuments = await prepareDocuments();
            const fallback = readyDocuments.length ? "Please analyze the attached document(s)." : "Please analyze the attached image(s).";
            const sendResult = onSend(question.trim() || fallback, attachments, readyDocuments, {
                evidenceMatrix,
                attachmentEvidenceScope
            });
            setAttachments([]);
            setDocuments([]);
            setEvidenceMatrix(false);
            if (clearOnSend) setQuestion("");
            await sendResult;
        } catch (error) {
            if (conversationIdRef.current === conversationId) {
                setAttachmentError(error instanceof Error ? error.message : "Unable to prepare document attachments.");
            }
        } finally {
            setIsPreparingDocuments(false);
        }
    };

    const fileToAttachment = (file: File): Promise<ChatAttachmentInput> =>
        new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onerror = () => reject(new Error(`Unable to read ${file.name}`));
            reader.onload = () =>
                resolve({
                    id: crypto.randomUUID(),
                    kind: "image",
                    name: file.name || "clipboard-image",
                    mime_type: file.type,
                    size: file.size,
                    data_url: String(reader.result || "")
                });
            reader.readAsDataURL(file);
        });

    const addFiles = async (files: File[]) => {
        setAttachmentError("");
        const images = files.filter(file => ACCEPTED_IMAGE_TYPES.has(file.type));
        const documentFiles = files.filter(file => {
            const extension = file.name.split(".").pop()?.toLowerCase() || "";
            return ACCEPTED_DOCUMENT_EXTENSIONS.has(extension);
        });
        if (images.length + documentFiles.length !== files.length) {
            setAttachmentError("Supported files: PNG, JPEG, WebP, GIF, PDF, DOCX, PPTX, XLSX, TXT, CSV, and Markdown.");
            return;
        }
        if (documentFiles.length && !documentsAvailable) {
            setAttachmentError("Private document attachments are not enabled for this deployment.");
            return;
        }
        if (images.length && !imagesAvailable) {
            setAttachmentError(imageDisabledReason || "Image input is not available for this agent.");
            return;
        }
        if (attachments.length + images.length > MAX_IMAGE_COUNT) {
            setAttachmentError(`Attach up to ${MAX_IMAGE_COUNT} images per message.`);
            return;
        }
        if (images.some(file => file.size > MAX_IMAGE_BYTES)) {
            setAttachmentError("Each image must be 10 MB or smaller.");
            return;
        }
        const totalBytes = attachments.reduce((sum, item) => sum + item.size, 0) + images.reduce((sum, file) => sum + file.size, 0);
        if (totalBytes > MAX_TOTAL_BYTES) {
            setAttachmentError("Combined image size must be 20 MB or smaller.");
            return;
        }
        if (documents.length + documentFiles.length > MAX_DOCUMENT_COUNT) {
            setAttachmentError(`Attach up to ${MAX_DOCUMENT_COUNT} documents per message.`);
            return;
        }
        if (documentFiles.some(file => file.size > MAX_DOCUMENT_BYTES)) {
            setAttachmentError("Each document must be 25 MB or smaller.");
            return;
        }
        try {
            const newAttachments = await Promise.all(images.map(fileToAttachment));
            setAttachments(current => [...current, ...newAttachments]);
            setDocuments(current => [
                ...current,
                ...documentFiles.map(file => ({ uploadId: crypto.randomUUID(), file, status: "draft" as const }))
            ]);
        } catch (error) {
            setAttachmentError(error instanceof Error ? error.message : "Unable to read attachment.");
        }
    };

    const handlePaste = (event: React.ClipboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        const imageFiles = Array.from(event.clipboardData.items)
            .filter(item => item.kind === "file" && item.type.startsWith("image/"))
            .map(item => item.getAsFile())
            .filter((file): file is File => Boolean(file));
        if (imageFiles.length) {
            event.preventDefault();
            void addFiles(imageFiles);
        }
    };

    const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        if (!disabled && !isPreparingDocuments && !disableRequiredAccessControl) void addFiles(Array.from(event.dataTransfer.files));
    };

    const onEnterPress = (ev: React.KeyboardEvent<Element>) => {
        if (isComposing) return;

        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            void sendQuestion();
        }
    };

    const handleCompositionStart = () => {
        setIsComposing(true);
    };
    const handleCompositionEnd = () => {
        setIsComposing(false);
    };

    const onQuestionChange = (_ev: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, newValue?: string) => {
        if (!newValue) {
            setQuestion("");
        } else if (newValue.length <= 1000) {
            setQuestion(newValue);
        }
    };

    const disableRequiredAccessControl = requireLogin && !loggedIn;
    const sendQuestionDisabled = disabled || isPreparingDocuments || (!question.trim() && attachments.length === 0 && documents.length === 0) || disableRequiredAccessControl;
    const attachmentControlDisabled =
        disabled || isPreparingDocuments || disableRequiredAccessControl || (!documentsAvailable && !imagesAvailable);
    const attachmentTooltip = attachmentControlDisabled
        ? attachmentDisabledReason || imageDisabledReason || "Attachments are not available for this agent."
        : documentsAvailable && imagesAvailable
          ? "Attach images or documents"
          : documentsAvailable
            ? "Attach documents"
            : "Attach images";

    if (disableRequiredAccessControl) {
        placeholder = "Please login to continue...";
    }

    return (
        <div
            className={styles.composer}
            onDragOver={event => event.preventDefault()}
            onDrop={handleDrop}
        >
            {attachments.length > 0 && (
                <div className={styles.attachmentList} aria-label="Image attachments">
                    {attachments.map(attachment => (
                        <div className={styles.attachmentPreview} key={attachment.id}>
                            <img src={attachment.data_url} alt={attachment.name} />
                            <span title={attachment.name}>{attachment.name}</span>
                            <Button
                                appearance="subtle"
                                size="small"
                                aria-label={`Remove ${attachment.name}`}
                                icon={<Dismiss16Regular />}
                                onClick={() => setAttachments(items => items.filter(item => item.id !== attachment.id))}
                            />
                        </div>
                    ))}
                </div>
            )}
            {documents.length > 0 && (
                <>
                    <div className={styles.documentList} aria-label="Document attachments">
                        {documents.map(document => (
                        <div className={styles.documentPreview} key={document.uploadId}>
                            <Document24Regular />
                            <div className={styles.documentDetails}>
                                <span title={document.file.name}>{document.file.name}</span>
                                <small>
                                    {document.status === "draft" && `${(document.file.size / 1024 / 1024).toFixed(1)} MB · Ready to upload`}
                                    {document.status === "uploading" && "Uploading…"}
                                    {document.status === "processing" && "Processing text…"}
                                    {document.status === "ready" && "Ready"}
                                    {document.status === "failed" && (document.error || "Failed")}
                                </small>
                            </div>
                            {(document.status === "uploading" || document.status === "processing") && <Spinner size="tiny" />}
                            <Button
                                appearance="subtle"
                                size="small"
                                aria-label={`Remove ${document.file.name}`}
                                disabled={document.status === "uploading" || document.status === "processing"}
                                icon={<Dismiss16Regular />}
                                onClick={() => {
                                    setDocuments(items => items.filter(item => item.uploadId !== document.uploadId));
                                    if (document.attachment?.id) {
                                        void getAccessToken?.().then(token =>
                                            deleteChatDocumentApi(document.attachment!.id, conversationId, token).catch(error =>
                                                setAttachmentError(error instanceof Error ? error.message : "Unable to remove document attachment.")
                                            )
                                        );
                                    }
                                }}
                            />
                        </div>
                        ))}
                    </div>
                    <div className={styles.evidenceControls}>
                        <Button
                            appearance={evidenceMatrix ? "primary" : "outline"}
                            disabled={disabled || isPreparingDocuments}
                            onClick={() => setEvidenceMatrix(value => !value)}
                        >
                            Evidence matrix
                        </Button>
                        {evidenceMatrix && (
                            <label className={styles.evidenceScopeLabel}>
                                Evidence from
                                <select
                                    aria-label="Evidence source scope"
                                    value={attachmentEvidenceScope}
                                    disabled={disabled || isPreparingDocuments}
                                    onChange={event =>
                                        setAttachmentEvidenceScope(event.target.value as EvidenceMatrixOptions["attachmentEvidenceScope"])
                                    }
                                >
                                    <option value="knowledge_only">Knowledge only (recommended)</option>
                                    <option value="uploaded_only">Attached files only</option>
                                    <option value="both">Attached files + Knowledge</option>
                                </select>
                            </label>
                        )}
                    </div>
                </>
            )}
            {attachmentError && <div className={styles.attachmentError} role="alert">{attachmentError}</div>}
            <Stack horizontal className={styles.questionInputContainer} style={{ background: disableRequiredAccessControl ? "#f2f2f2" : "white" }}>
                <input
                    ref={fileInputRef}
                    className={styles.hiddenFileInput}
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif,.pdf,.docx,.pptx,.xlsx,.txt,.csv,.md"
                    multiple
                    onChange={event => {
                        void addFiles(Array.from(event.target.files || []));
                        event.target.value = "";
                    }}
                />
                <div className={styles.questionInputOptionsContainer}>
                    {showAttachmentButton && (
                        <Tooltip content={attachmentTooltip} relationship="description">
                            <Button
                                size="large"
                                icon={<Attach24Regular />}
                                disabled={attachmentControlDisabled}
                                onClick={() => fileInputRef.current?.click()}
                            />
                        </Tooltip>
                    )}
                </div>
                <TextField
                    className={styles.questionInputTextArea}
                    disabled={disableRequiredAccessControl}
                    placeholder={placeholder}
                    multiline
                    resizable={false}
                    borderless
                    value={question}
                    onChange={onQuestionChange}
                    onKeyDown={onEnterPress}
                    onPaste={handlePaste}
                    onCompositionStart={handleCompositionStart}
                    onCompositionEnd={handleCompositionEnd}
                />
                <div className={styles.questionInputButtonsContainer}>
                    <Tooltip content={isPreparingDocuments ? "Preparing documents" : t("tooltips.submitQuestion")} relationship="label">
                        <Button
                            size="large"
                            icon={isPreparingDocuments ? <Spinner size="tiny" /> : <Send28Filled primaryFill="rgba(225, 83, 13, 1)" />}
                            disabled={sendQuestionDisabled}
                            onClick={() => void sendQuestion()}
                        />
                    </Tooltip>
                </div>
                {showSpeechInput && <SpeechInput updateQuestion={setQuestion} />}
            </Stack>
        </div>
    );
};
