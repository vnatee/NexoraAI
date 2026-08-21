import base64
import binascii
from pathlib import PurePath
from typing import Any


MAX_IMAGE_COUNT = 4
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_BASE64_CHARS = 4 * ((MAX_IMAGE_BYTES + 2) // 3)

SUPPORTED_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


class ChatAttachmentError(ValueError):
    pass


def _has_expected_signature(mime_type: str, content: bytes) -> bool:
    if mime_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if mime_type == "image/gif":
        return content.startswith((b"GIF87a", b"GIF89a"))
    if mime_type == "image/webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return False


def validate_chat_attachments(value: Any) -> list[dict[str, Any]]:
    """Validate inline phase-one image attachments and return a canonical payload."""
    if value in (None, []):
        return []
    if not isinstance(value, list):
        raise ChatAttachmentError("attachments must be an array")
    if len(value) > MAX_IMAGE_COUNT:
        raise ChatAttachmentError(f"A message can contain at most {MAX_IMAGE_COUNT} images")

    validated: list[dict[str, Any]] = []
    total_bytes = 0
    for position, item in enumerate(value, start=1):
        if not isinstance(item, dict) or item.get("kind") != "image":
            raise ChatAttachmentError(f"Attachment {position} must be an image")

        mime_type = str(item.get("mime_type") or "").lower()
        if mime_type not in SUPPORTED_IMAGE_TYPES:
            raise ChatAttachmentError(f"Attachment {position} has an unsupported image type")

        data_url = item.get("data_url")
        expected_prefix = f"data:{mime_type};base64,"
        if not isinstance(data_url, str) or not data_url.startswith(expected_prefix):
            raise ChatAttachmentError(f"Attachment {position} must use a matching base64 data URL")
        encoded_content = data_url[len(expected_prefix):]
        if len(encoded_content) > MAX_IMAGE_BASE64_CHARS:
            raise ChatAttachmentError(f"Attachment {position} exceeds the image size limit")
        try:
            content = base64.b64decode(encoded_content, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ChatAttachmentError(f"Attachment {position} contains invalid base64 data") from error

        if not content or len(content) > MAX_IMAGE_BYTES:
            raise ChatAttachmentError(f"Each image must be between 1 byte and {MAX_IMAGE_BYTES} bytes")
        if not _has_expected_signature(mime_type, content):
            raise ChatAttachmentError(f"Attachment {position} content does not match its image type")

        declared_size = item.get("size")
        if isinstance(declared_size, bool) or not isinstance(declared_size, int) or declared_size != len(content):
            raise ChatAttachmentError(f"Attachment {position} size does not match its content")

        total_bytes += len(content)
        if total_bytes > MAX_TOTAL_IMAGE_BYTES:
            raise ChatAttachmentError(f"Combined image size must not exceed {MAX_TOTAL_IMAGE_BYTES} bytes")

        raw_name = str(item.get("name") or f"image-{position}")
        name = PurePath(raw_name.replace("\\", "/")).name[:255] or f"image-{position}"
        attachment_id = str(item.get("id") or f"image-{position}")[:128]
        validated.append(
            {
                "id": attachment_id,
                "kind": "image",
                "name": name,
                "mime_type": mime_type,
                "size": len(content),
                "data_url": data_url,
            }
        )
    return validated


def redact_inline_images(value: Any, image_urls: list[str] | None = None) -> Any:
    """Copy nested prompt data while replacing selected inline images for UI diagnostics."""
    redacted_urls = set(image_urls or [])

    def _redact(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: _redact(nested) for key, nested in item.items()}
        if isinstance(item, list):
            return [_redact(nested) for nested in item]
        if isinstance(item, tuple):
            return tuple(_redact(nested) for nested in item)
        if isinstance(item, str) and item in redacted_urls:
            return "[inline image omitted]"
        return item

    return _redact(value)
