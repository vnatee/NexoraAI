from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePath
from xml.etree import ElementTree

from pypdf import PdfReader


MAX_EXTRACTED_CHARACTERS = 2_000_000
MAX_ATTACHMENT_CHUNKS = 2_000
MAX_CHUNK_CHARACTERS = 2_000
CHUNK_OVERLAP_CHARACTERS = 200
MAX_XML_PART_BYTES = 10 * 1024 * 1024


class AttachmentExtractionError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedChunk:
    position: int
    page_number: int | None
    page_label: str
    text: str


def _normalized_text(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in str(value or "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _xml_text(content: bytes) -> str:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise AttachmentExtractionError("Office document XML is invalid") from error
    return _normalized_text(" ".join(root.itertext()))


def _read_xml_part(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        part = archive.getinfo(name)
    except KeyError as error:
        raise AttachmentExtractionError("Office document XML part is missing") from error
    if part.file_size > MAX_XML_PART_BYTES:
        raise AttachmentExtractionError("Office document XML part exceeds the extraction limit")
    return archive.read(part)


def _pdf_pages(content: bytes) -> list[tuple[int | None, str, str]]:
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        return [
            (page_number, str(page_number), _normalized_text(page.extract_text() or ""))
            for page_number, page in enumerate(reader.pages, start=1)
        ]
    except Exception as error:
        raise AttachmentExtractionError("Unable to extract PDF text") from error


def _ordered_parts(names: set[str], pattern: str) -> list[str]:
    matched: list[tuple[int, str]] = []
    expression = re.compile(pattern)
    for name in names:
        result = expression.fullmatch(name)
        if result:
            matched.append((int(result.group(1)), name))
    return [name for _, name in sorted(matched)]


def _xlsx_page_text(archive: zipfile.ZipFile, name: str, shared_strings: list[str]) -> str:
    try:
        root = ElementTree.fromstring(_read_xml_part(archive, name))
    except (KeyError, ElementTree.ParseError) as error:
        raise AttachmentExtractionError("Excel worksheet XML is invalid") from error
    values: list[str] = []
    for cell in root.findall(".//{*}c"):
        cell_type = cell.attrib.get("t")
        inline = cell.find("{*}is")
        value = cell.find("{*}v")
        if inline is not None:
            text = " ".join(inline.itertext())
        elif value is not None and value.text is not None:
            text = value.text
            if cell_type == "s":
                try:
                    text = shared_strings[int(text)]
                except (ValueError, IndexError):
                    raise AttachmentExtractionError("Excel shared string reference is invalid")
        else:
            continue
        coordinate = str(cell.attrib.get("r") or "").strip()
        values.append(f"{coordinate}: {text}" if coordinate else text)
    return _normalized_text("\n".join(values))


def _office_pages(extension: str, content: bytes) -> list[tuple[int | None, str, str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            if extension == ".docx":
                return [(None, "document", _xml_text(_read_xml_part(archive, "word/document.xml")))]
            if extension == ".pptx":
                parts = _ordered_parts(names, r"ppt/slides/slide(\d+)\.xml")
                return [
                    (position, str(position), _xml_text(_read_xml_part(archive, name)))
                    for position, name in enumerate(parts, start=1)
                ]
            if extension == ".xlsx":
                shared_strings: list[str] = []
                if "xl/sharedStrings.xml" in names:
                    try:
                        root = ElementTree.fromstring(_read_xml_part(archive, "xl/sharedStrings.xml"))
                    except ElementTree.ParseError as error:
                        raise AttachmentExtractionError("Excel shared strings XML is invalid") from error
                    shared_strings = [_normalized_text(" ".join(item.itertext())) for item in root.findall("{*}si")]
                parts = _ordered_parts(names, r"xl/worksheets/sheet(\d+)\.xml")
                return [
                    (position, f"sheet {position}", _xlsx_page_text(archive, name, shared_strings))
                    for position, name in enumerate(parts, start=1)
                ]
    except AttachmentExtractionError:
        raise
    except (KeyError, OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise AttachmentExtractionError("Unable to extract Office document text") from error
    raise AttachmentExtractionError("Unsupported Office document type")


def _split_text(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARACTERS:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + MAX_CHUNK_CHARACTERS)
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(" ", start, end))
            if boundary > start + MAX_CHUNK_CHARACTERS // 2:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP_CHARACTERS)
    return chunks


def chunk_attachment_pages(
    pages: Iterable[tuple[int | None, str, str]],
) -> list[ExtractedChunk]:
    pages = [
        (page_number, str(page_label or ""), _normalized_text(text))
        for page_number, page_label, text in pages
    ]
    total_characters = sum(len(text) for _, _, text in pages)
    if total_characters > MAX_EXTRACTED_CHARACTERS:
        raise AttachmentExtractionError("Extracted document text exceeds the allowed size")
    chunks: list[ExtractedChunk] = []
    for page_number, page_label, text in pages:
        for chunk_text in _split_text(text) if text else []:
            chunks.append(
                ExtractedChunk(
                    position=len(chunks),
                    page_number=page_number,
                    page_label=page_label,
                    text=chunk_text,
                )
            )
            if len(chunks) > MAX_ATTACHMENT_CHUNKS:
                raise AttachmentExtractionError("Document produces too many text chunks")
    if not chunks:
        raise AttachmentExtractionError("Document has no machine-readable text; OCR is required")
    return chunks


def extract_attachment_chunks(*, filename: str, content_type: str, content: bytes) -> list[ExtractedChunk]:
    extension = PurePath(str(filename or "")).suffix.lower()
    if extension == ".pdf" and content_type == "application/pdf":
        pages = _pdf_pages(content)
    elif extension in {".docx", ".pptx", ".xlsx"}:
        pages = _office_pages(extension, content)
    elif extension in {".txt", ".csv", ".md"}:
        try:
            pages = [(1, "1", _normalized_text(content.decode("utf-8-sig")))]
        except UnicodeDecodeError as error:
            raise AttachmentExtractionError("Unable to decode document text") from error
    else:
        raise AttachmentExtractionError("Unsupported document extraction type")
    return chunk_attachment_pages(pages)
