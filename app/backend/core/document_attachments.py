from __future__ import annotations

import io
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import PurePath
from typing import Protocol

from pypdf import PdfReader


MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_OFFICE_PARTS = 10_000
MAX_OFFICE_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_OFFICE_COMPRESSION_RATIO = 100
MAX_PRESENTATION_SLIDES = 500
MAX_WORKBOOK_SHEETS = 500

DOCUMENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".md": "text/markdown",
}

_MIME_ALIASES = {
    ".txt": {"text/plain"},
    ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"},
    ".md": {"text/markdown", "text/plain", "text/x-markdown"},
}
_GENERIC_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}


class DocumentAttachmentError(ValueError):
    pass


class MalwareDetectedError(DocumentAttachmentError):
    pass


class MalwareScanner(Protocol):
    async def scan(self, *, filename: str, content_type: str, content: bytes) -> str: ...


class DisabledMalwareScanner:
    """Explicit no-op integration point until a deployment configures a scanner."""

    async def scan(self, *, filename: str, content_type: str, content: bytes) -> str:
        return "not_configured"


@dataclass(frozen=True)
class ValidatedDocument:
    filename: str
    content_type: str
    content: bytes
    page_count: int | None


def _safe_filename(value: str) -> str:
    filename = PurePath(str(value or "").replace("\\", "/")).name.strip().strip(".")
    if not filename or len(filename) > 255 or any(ord(character) < 32 for character in filename):
        raise DocumentAttachmentError("Document filename is invalid")
    return filename


def _validate_declared_mime(extension: str, declared_mime: str) -> None:
    declared = str(declared_mime or "").split(";", 1)[0].strip().lower()
    accepted = _MIME_ALIASES.get(extension, {DOCUMENT_TYPES[extension]})
    if declared not in _GENERIC_MIME_TYPES and declared not in accepted:
        raise DocumentAttachmentError("Document content type does not match its filename")


def _validate_pdf(content: bytes) -> int:
    if not content.startswith(b"%PDF-"):
        raise DocumentAttachmentError("PDF content does not match its file type")
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise DocumentAttachmentError("Encrypted PDF documents are not supported")
        page_count = len(reader.pages)
    except DocumentAttachmentError:
        raise
    except Exception as error:
        raise DocumentAttachmentError("PDF document is invalid") from error
    if page_count < 1 or page_count > MAX_PDF_PAGES:
        raise DocumentAttachmentError(f"PDF documents must contain 1 to {MAX_PDF_PAGES} pages")
    return page_count


def _validate_office_archive(extension: str, content: bytes) -> int | None:
    if not content.startswith(b"PK\x03\x04"):
        raise DocumentAttachmentError("Office document content does not match its file type")
    required_part = {
        ".docx": "word/document.xml",
        ".pptx": "ppt/presentation.xml",
        ".xlsx": "xl/workbook.xml",
    }[extension]
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            parts = archive.infolist()
            if not parts or len(parts) > MAX_OFFICE_PARTS:
                raise DocumentAttachmentError("Office document contains too many archive parts")
            names: set[str] = set()
            total_uncompressed = 0
            for part in parts:
                name = part.filename.replace("\\", "/")
                path = PurePath(name)
                if path.is_absolute() or ".." in path.parts or "\x00" in name:
                    raise DocumentAttachmentError("Office document contains an unsafe archive path")
                mode = part.external_attr >> 16
                if mode and stat.S_ISLNK(mode):
                    raise DocumentAttachmentError("Office document contains an unsupported symbolic link")
                if part.flag_bits & 0x1:
                    raise DocumentAttachmentError("Encrypted Office documents are not supported")
                total_uncompressed += part.file_size
                if total_uncompressed > MAX_OFFICE_UNCOMPRESSED_BYTES:
                    raise DocumentAttachmentError("Office document expands beyond the allowed size")
                if part.file_size and part.file_size > max(1, part.compress_size) * MAX_OFFICE_COMPRESSION_RATIO:
                    raise DocumentAttachmentError("Office document has an unsafe compression ratio")
                names.add(name)
            if "[Content_Types].xml" not in names or required_part not in names:
                raise DocumentAttachmentError("Office document structure does not match its file type")
            # Reading a bounded required part verifies CRC and detects a truncated archive.
            required_info = archive.getinfo(required_part)
            if required_info.file_size > 10 * 1024 * 1024:
                raise DocumentAttachmentError("Office document primary XML part is too large")
            archive.read(required_info)
    except DocumentAttachmentError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise DocumentAttachmentError("Office document archive is invalid") from error

    if extension == ".pptx":
        page_count = len([name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)])
        if page_count < 1 or page_count > MAX_PRESENTATION_SLIDES:
            raise DocumentAttachmentError(
                f"PowerPoint documents must contain 1 to {MAX_PRESENTATION_SLIDES} slides"
            )
        return page_count
    if extension == ".xlsx":
        page_count = len([name for name in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)])
        if page_count < 1 or page_count > MAX_WORKBOOK_SHEETS:
            raise DocumentAttachmentError(
                f"Excel documents must contain 1 to {MAX_WORKBOOK_SHEETS} worksheets"
            )
        return page_count
    return None


def validate_document_attachment(
    *,
    filename: str,
    declared_mime: str,
    content: bytes,
    max_bytes: int = MAX_DOCUMENT_BYTES,
) -> ValidatedDocument:
    safe_filename = _safe_filename(filename)
    extension = PurePath(safe_filename).suffix.lower()
    if extension not in DOCUMENT_TYPES:
        raise DocumentAttachmentError("Unsupported document type")
    if not isinstance(content, bytes) or not content or len(content) > max_bytes:
        raise DocumentAttachmentError(f"Document must contain 1 to {max_bytes} bytes")
    _validate_declared_mime(extension, declared_mime)

    page_count: int | None = None
    if extension == ".pdf":
        page_count = _validate_pdf(content)
    elif extension in {".docx", ".pptx", ".xlsx"}:
        page_count = _validate_office_archive(extension, content)
    else:
        if b"\x00" in content:
            raise DocumentAttachmentError("Text document contains binary data")
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DocumentAttachmentError("Text documents must use UTF-8 encoding") from error

    return ValidatedDocument(
        filename=safe_filename,
        content_type=DOCUMENT_TYPES[extension],
        content=content,
        page_count=page_count,
    )
