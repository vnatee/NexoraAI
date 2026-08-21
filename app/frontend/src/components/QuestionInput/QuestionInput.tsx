import { useState, useEffect, useContext, useRef } from "react";
import { Stack, TextField } from "@fluentui/react";
import { Button, Tooltip } from "@fluentui/react-components";
import { Attach24Regular, Dismiss16Regular, Eye24Regular, EyeOff24Regular, Send28Filled } from "@fluentui/react-icons";
import { useTranslation } from "react-i18next";

import styles from "./QuestionInput.module.css";
import { SpeechInput } from "./SpeechInput";
import { LoginContext } from "../../loginContext";
import { requireLogin } from "../../authConfig";
import { ChatAttachmentInput } from "../../api/models";

const ACCEPTED_IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp", "image/gif"]);
const MAX_IMAGE_COUNT = 4;
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const MAX_TOTAL_BYTES = 20 * 1024 * 1024;

interface Props {
    onSend: (question: string, attachments?: ChatAttachmentInput[]) => void;
    disabled: boolean;
    initQuestion?: string;
    placeholder?: string;
    clearOnSend?: boolean;
    showSpeechInput?: boolean;
    visionAvailable?: boolean;
    visionEnabled?: boolean;
    visionDisabledReason?: string;
    onVisionChange?: (enabled: boolean) => void;
}

export const QuestionInput = ({
    onSend,
    disabled,
    placeholder,
    clearOnSend,
    initQuestion,
    showSpeechInput,
    visionAvailable = false,
    visionEnabled = false,
    visionDisabledReason,
    onVisionChange
}: Props) => {
    const [question, setQuestion] = useState<string>("");
    const { loggedIn } = useContext(LoginContext);
    const { t } = useTranslation();
    const [isComposing, setIsComposing] = useState(false);
    const [attachments, setAttachments] = useState<ChatAttachmentInput[]>([]);
    const [attachmentError, setAttachmentError] = useState("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        initQuestion && setQuestion(initQuestion);
    }, [initQuestion]);

    const sendQuestion = () => {
        if (disabled || (!question.trim() && attachments.length === 0)) {
            return;
        }

        onSend(question.trim() || "Please analyze the attached image(s).", attachments);
        setAttachments([]);
        setAttachmentError("");

        if (clearOnSend) {
            setQuestion("");
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
        if (!visionAvailable) {
            setAttachmentError(visionDisabledReason || "Vision is not available for this agent.");
            return;
        }
        if (!visionEnabled) {
            setAttachmentError("Turn on Vision before attaching an image.");
            return;
        }
        const images = files.filter(file => ACCEPTED_IMAGE_TYPES.has(file.type));
        if (images.length !== files.length) {
            setAttachmentError("This phase accepts PNG, JPEG, WebP, and GIF images. Document attachments are next.");
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
        try {
            const newAttachments = await Promise.all(images.map(fileToAttachment));
            setAttachments(current => [...current, ...newAttachments]);
        } catch (error) {
            setAttachmentError(error instanceof Error ? error.message : "Unable to read image attachment.");
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
        if (!disabled && !disableRequiredAccessControl) void addFiles(Array.from(event.dataTransfer.files));
    };

    const onEnterPress = (ev: React.KeyboardEvent<Element>) => {
        if (isComposing) return;

        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            sendQuestion();
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
    const sendQuestionDisabled = disabled || (!question.trim() && attachments.length === 0) || disableRequiredAccessControl;
    const visionControlDisabled = disabled || disableRequiredAccessControl || !visionAvailable;
    const attachmentControlDisabled = disabled || disableRequiredAccessControl || !visionAvailable || !visionEnabled;
    const visionTooltip = visionAvailable
        ? visionEnabled
            ? "Vision is on. Click to turn it off."
            : "Vision is off. Click to analyze attached images."
        : visionDisabledReason || "Vision is not configured for this deployment.";

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
            {attachmentError && <div className={styles.attachmentError} role="alert">{attachmentError}</div>}
            <Stack horizontal className={styles.questionInputContainer} style={{ background: disableRequiredAccessControl ? "#f2f2f2" : "white" }}>
                <input
                    ref={fileInputRef}
                    className={styles.hiddenFileInput}
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    multiple
                    onChange={event => {
                        void addFiles(Array.from(event.target.files || []));
                        event.target.value = "";
                    }}
                />
                <div className={styles.questionInputOptionsContainer}>
                    <Tooltip content={visionTooltip} relationship="description">
                        <span>
                            <Button
                                appearance={visionEnabled ? "primary" : "subtle"}
                                icon={visionEnabled ? <Eye24Regular /> : <EyeOff24Regular />}
                                disabled={visionControlDisabled}
                                aria-pressed={visionEnabled}
                                onClick={() => {
                                    const nextValue = !visionEnabled;
                                    if (!nextValue) {
                                        setAttachments([]);
                                        setAttachmentError("");
                                    }
                                    onVisionChange?.(nextValue);
                                }}
                            >
                                Vision {visionEnabled ? "On" : "Off"}
                            </Button>
                        </span>
                    </Tooltip>
                    <Tooltip content="Attach images" relationship="label">
                        <Button
                            size="large"
                            icon={<Attach24Regular />}
                            disabled={attachmentControlDisabled}
                            onClick={() => fileInputRef.current?.click()}
                        />
                    </Tooltip>
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
                    <Tooltip content={t("tooltips.submitQuestion")} relationship="label">
                        <Button size="large" icon={<Send28Filled primaryFill="rgba(225, 83, 13, 1)" />} disabled={sendQuestionDisabled} onClick={sendQuestion} />
                    </Tooltip>
                </div>
                {showSpeechInput && <SpeechInput updateQuestion={setQuestion} />}
            </Stack>
        </div>
    );
};
