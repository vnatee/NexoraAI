import uuid
from typing import Union


class ConversationIdError(ValueError):
    pass


def ensure_conversation_id(value: object) -> str:
    """Return a canonical private conversation UUID, generating one for old clients."""
    if value in (None, ""):
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError) as error:
        raise ConversationIdError("conversation_id must be a valid UUID") from error


def create_session_id(
    config_chat_history_cosmos_enabled: bool, config_chat_history_browser_enabled: bool
) -> Union[str, None]:
    if config_chat_history_cosmos_enabled:
        return str(uuid.uuid4())
    if config_chat_history_browser_enabled:
        return str(uuid.uuid4())
    return None
