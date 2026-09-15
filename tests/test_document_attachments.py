import io
import zipfile

import pytest
from pypdf import PdfWriter

from core.document_attachments import (
    DisabledMalwareScanner,
    DocumentAttachmentError,
    validate_document_attachment,
)


def _pdf_bytes(page_count=1):
    output = io.BytesIO()
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=100, height=100)
    writer.write(output)
    return output.getvalue()


def _office_bytes(parts, *, compression=zipfile.ZIP_STORED):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        archive.writestr("[Content_Types].xml", b"<Types />")
        for name, content in parts.items():
            archive.writestr(name, content)
    return output.getvalue()


def test_validate_pdf_returns_canonical_metadata_and_page_count():
    content = _pdf_bytes(2)

    document = validate_document_attachment(
        filename="../requirements.PDF",
        declared_mime="application/pdf",
        content=content,
    )

    assert document.filename == "requirements.PDF"
    assert document.content_type == "application/pdf"
    assert document.page_count == 2
    assert document.content == content


@pytest.mark.parametrize(
    ("filename", "mime_type", "content", "page_count"),
    [
        (
            "spec.docx",
            "application/octet-stream",
            _office_bytes({"word/document.xml": b"<document />"}),
            None,
        ),
        (
            "slides.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            _office_bytes(
                {
                    "ppt/presentation.xml": b"<presentation />",
                    "ppt/slides/slide1.xml": b"<slide />",
                    "ppt/slides/slide2.xml": b"<slide />",
                }
            ),
            2,
        ),
        (
            "table.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            _office_bytes(
                {
                    "xl/workbook.xml": b"<workbook />",
                    "xl/worksheets/sheet1.xml": b"<worksheet />",
                }
            ),
            1,
        ),
        ("notes.txt", "text/plain; charset=utf-8", "ข้อมูล".encode(), None),
        ("data.csv", "application/vnd.ms-excel", b"name,value\na,1\n", None),
        ("readme.md", "text/x-markdown", b"# Heading\n", None),
    ],
)
def test_validate_supported_documents(filename, mime_type, content, page_count):
    document = validate_document_attachment(
        filename=filename,
        declared_mime=mime_type,
        content=content,
    )

    assert document.page_count == page_count


@pytest.mark.parametrize(
    ("filename", "mime_type", "content", "message"),
    [
        ("malware.exe", "application/octet-stream", b"MZ", "Unsupported document type"),
        ("fake.pdf", "application/pdf", b"not a pdf", "does not match"),
        ("fake.pdf", "image/png", _pdf_bytes(), "content type does not match"),
        ("binary.txt", "text/plain", b"hello\x00world", "binary data"),
        ("legacy.txt", "text/plain", b"\xff\xfe", "UTF-8"),
        ("empty.txt", "text/plain", b"", "1 to"),
    ],
)
def test_validate_document_rejects_invalid_content(filename, mime_type, content, message):
    with pytest.raises(DocumentAttachmentError, match=message):
        validate_document_attachment(
            filename=filename,
            declared_mime=mime_type,
            content=content,
        )


def test_validate_office_rejects_traversal_and_wrong_structure():
    traversal = _office_bytes(
        {
            "word/document.xml": b"<document />",
            "../outside.xml": b"unsafe",
        }
    )
    with pytest.raises(DocumentAttachmentError, match="unsafe archive path"):
        validate_document_attachment(
            filename="unsafe.docx",
            declared_mime="application/octet-stream",
            content=traversal,
        )

    wrong_structure = _office_bytes({"word/document.xml": b"<document />"})
    with pytest.raises(DocumentAttachmentError, match="structure does not match"):
        validate_document_attachment(
            filename="renamed.xlsx",
            declared_mime="application/octet-stream",
            content=wrong_structure,
        )


def test_validate_office_rejects_unsafe_compression_ratio():
    compressed = _office_bytes(
        {"word/document.xml": b"0" * (1024 * 1024)},
        compression=zipfile.ZIP_DEFLATED,
    )

    with pytest.raises(DocumentAttachmentError, match="compression ratio"):
        validate_document_attachment(
            filename="compressed.docx",
            declared_mime="application/octet-stream",
            content=compressed,
        )


@pytest.mark.asyncio
async def test_disabled_malware_scanner_is_an_explicit_noop():
    scanner = DisabledMalwareScanner()
    assert (
        await scanner.scan(filename="safe.txt", content_type="text/plain", content=b"safe")
        == "not_configured"
    )
