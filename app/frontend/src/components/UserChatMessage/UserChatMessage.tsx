import styles from "./UserChatMessage.module.css";
import { ChatAttachmentInput } from "../../api/models";

interface Props {
    message: string;
    attachments?: ChatAttachmentInput[];
}

export const UserChatMessage = ({ message, attachments = [] }: Props) => {
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
                <div>{message}</div>
            </div>
        </div>
    );
};
