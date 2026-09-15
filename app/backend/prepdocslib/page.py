import math
from typing import Any


def safe_processing_metadata(metadata: dict[str, Any] | None) -> dict[str, str | float]:
    """Return the small provider-neutral metadata subset allowed in search chunks."""

    if not metadata:
        return {}
    result: dict[str, str | float] = {}
    for key in ("provider", "profile"):
        value = str(metadata.get(key) or "").strip()
        if value:
            result[key] = value[:256]
    confidence = metadata.get("confidence")
    if confidence is not None and not isinstance(confidence, bool):
        try:
            numeric_confidence = float(confidence)
        except (TypeError, ValueError):
            pass
        else:
            if math.isfinite(numeric_confidence):
                result["confidence"] = numeric_confidence
    return result


class Page:
    """
    A single page from a document

    Attributes:
        page_num (int): Page number (0-indexed)
        offset (int): If the text of the entire Document was concatenated into a single string, the index of the first character on the page. For example, if page 1 had the text "hello" and page 2 had the text "world", the offset of page 2 is 5 ("hellow")
        text (str): The text of the page
    """

    def __init__(self, page_num: int, offset: int, text: str, metadata: dict | None = None):
        self.page_num = page_num
        self.offset = offset
        self.text = text
        self.metadata = metadata or {}


class SplitPage:
    """
    A section of a page that has been split into a smaller chunk.

    Attributes:
        page_num (int): Page number (0-indexed)
        text (str): The text of the section
    """

    def __init__(self, page_num: int, text: str, metadata: dict[str, Any] | None = None):
        self.page_num = page_num
        self.text = text
        self.metadata = safe_processing_metadata(metadata)
