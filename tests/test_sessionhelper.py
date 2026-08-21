import uuid

import pytest

from core.sessionhelper import ConversationIdError, ensure_conversation_id


def test_ensure_conversation_id_preserves_valid_uuid():
    value = "9AEE2161-D67F-45A1-B4A5-7D2042DD1C26"
    assert ensure_conversation_id(value) == "9aee2161-d67f-45a1-b4a5-7d2042dd1c26"


def test_ensure_conversation_id_generates_for_legacy_client():
    assert uuid.UUID(ensure_conversation_id(None))


def test_ensure_conversation_id_rejects_invalid_value():
    with pytest.raises(ConversationIdError):
        ensure_conversation_id("../../conversation")
