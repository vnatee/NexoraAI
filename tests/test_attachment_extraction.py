import io
import zipfile

import pytest
from pypdf import PdfWriter

from core import attachment_extraction as extraction


def _archive(parts):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return output.getvalue()


def _blank_pdf():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    return output.getvalue()


def test_extract_text_preserves_utf8_and_chunks_with_overlap(monkeypatch):
    monkeypatch.setattr(extraction, "MAX_CHUNK_CHARACTERS", 20)
    monkeypatch.setattr(extraction, "CHUNK_OVERLAP_CHARACTERS", 5)

    chunks = extraction.extract_attachment_chunks(
        filename="notes.txt",
        content_type="text/plain",
        content="ข้อกำหนดหนึ่ง ข้อกำหนดสอง ข้อกำหนดสาม".encode(),
    )

    assert len(chunks) > 1
    assert [chunk.position for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.page_number == 1 and chunk.page_label == "1" for chunk in chunks)


def test_extract_docx_and_powerpoint_provenance():
    docx = _archive(
        {
            "word/document.xml": b'<w:document xmlns:w="urn:w"><w:p><w:t>Requirement A</w:t></w:p></w:document>'
        }
    )
    docx_chunks = extraction.extract_attachment_chunks(
        filename="requirements.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content=docx,
    )
    assert docx_chunks[0].page_number is None
    assert docx_chunks[0].page_label == "document"
    assert docx_chunks[0].text == "Requirement A"

    pptx = _archive(
        {
            "ppt/slides/slide2.xml": b'<p:sld xmlns:p="urn:p"><p:t>Second</p:t></p:sld>',
            "ppt/slides/slide1.xml": b'<p:sld xmlns:p="urn:p"><p:t>First</p:t></p:sld>',
        }
    )
    slides = extraction.extract_attachment_chunks(
        filename="slides.pptx",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        content=pptx,
    )
    assert [(chunk.page_number, chunk.text) for chunk in slides] == [(1, "First"), (2, "Second")]


def test_extract_xlsx_resolves_shared_strings_and_cell_coordinates():
    xlsx = _archive(
        {
            "xl/sharedStrings.xml": b'<sst xmlns="urn:x"><si><t>Control Name</t></si></sst>',
            "xl/worksheets/sheet1.xml": (
                b'<worksheet xmlns="urn:x"><sheetData><row><c r="A1" t="s"><v>0</v></c>'
                b'<c r="B1"><v>42</v></c></row></sheetData></worksheet>'
            ),
        }
    )

    chunks = extraction.extract_attachment_chunks(
        filename="controls.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content=xlsx,
    )

    assert chunks[0].page_number == 1
    assert chunks[0].page_label == "sheet 1"
    assert chunks[0].text == "A1: Control Name\nB1: 42"


def test_extract_pdf_uses_one_based_page_provenance(monkeypatch):
    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class Reader:
        def __init__(self, *args, **kwargs):
            self.pages = [Page("Page one"), Page("Page two")]

    monkeypatch.setattr(extraction, "PdfReader", Reader)
    chunks = extraction.extract_attachment_chunks(
        filename="requirements.pdf",
        content_type="application/pdf",
        content=b"pdf",
    )

    assert [(chunk.page_number, chunk.page_label, chunk.text) for chunk in chunks] == [
        (1, "1", "Page one"),
        (2, "2", "Page two"),
    ]


def test_extract_blank_pdf_requires_ocr():
    with pytest.raises(extraction.AttachmentExtractionError, match="OCR is required"):
        extraction.extract_attachment_chunks(
            filename="scan.pdf",
            content_type="application/pdf",
            content=_blank_pdf(),
        )


def test_extract_rejects_character_and_chunk_limits(monkeypatch):
    monkeypatch.setattr(extraction, "MAX_EXTRACTED_CHARACTERS", 5)
    with pytest.raises(extraction.AttachmentExtractionError, match="exceeds"):
        extraction.extract_attachment_chunks(
            filename="large.txt",
            content_type="text/plain",
            content=b"too much text",
        )

    monkeypatch.setattr(extraction, "MAX_EXTRACTED_CHARACTERS", 1_000)
    monkeypatch.setattr(extraction, "MAX_CHUNK_CHARACTERS", 10)
    monkeypatch.setattr(extraction, "CHUNK_OVERLAP_CHARACTERS", 1)
    monkeypatch.setattr(extraction, "MAX_ATTACHMENT_CHUNKS", 1)
    with pytest.raises(extraction.AttachmentExtractionError, match="too many"):
        extraction.extract_attachment_chunks(
            filename="many.txt",
            content_type="text/plain",
            content=b"first words second words",
        )


def test_extract_rejects_oversized_office_xml_part(monkeypatch):
    monkeypatch.setattr(extraction, "MAX_XML_PART_BYTES", 10)
    docx = _archive({"word/document.xml": b"<document>too large</document>"})

    with pytest.raises(extraction.AttachmentExtractionError, match="XML part exceeds"):
        extraction.extract_attachment_chunks(
            filename="large.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content=docx,
        )
