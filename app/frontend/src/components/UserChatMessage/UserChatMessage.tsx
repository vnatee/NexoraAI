import styles from "./UserChatMessage.module.css";
import { Document24Regular } from "@fluentui/react-icons";
import { ChatAttachmentInput, ChatDocumentAttachment } from "../../api/models";

interface Props {
    message: string;
    attachments?: ChatAttachmentInput[];
    documents?: ChatDocumentAttachment[];
}

export const UserChatMessage = ({ message, attachments = [], documents = [] }: Props) => {
    return (
        <div className={styles.container}>
            <div className={styles.message}>
                {attachments.length > 0 && (
                    <div className={styles.attachments} aria-label="Sent image attachments">
                        {attachments.map(attachment => (
                            <figure className={styles.attachment} key={attachment.id} title={attachment.name}>
                                <img src={attachment.data_url} alt={attachment.name} />
                                <figcaption>{attachment.name}</figcaption>
                            </figure>
                        ))}
                    </div>
                )}
                {documents.length > 0 && (
                    <div className={styles.documents} aria-label="Sent document attachments">
                        {documents.map(document => (
                            <div className={styles.document} key={document.id} title={document.filename}>
                                <Document24Regular />
                                <span>{document.filename}</span>
                                <small>{document.page_count ? `${document.page_count} pages` : "Document"}</small>
                            </div>
                        ))}
                    </div>
                )}
                <div>{message}</div>
            </div>
        </div>
    );
};
