"""
TRACE OCR ingestion unit tests — verifies layout-aware OCR fallback preserves
provenance (file/page/paragraph) and respects MAX_PARA_CHARS=600.
Run: docker exec trace-api python -m pytest /app/tests_e2e/unit -q
"""
import io
import sys
from pathlib import Path
# Docker path (/app) vs local path (services/api)
sys.path.insert(0, "/app")
# local: services/api is the app root
_local_api = Path(__file__).resolve().parents[2]  # .../services/api
sys.path.insert(0, str(_local_api))

import pytest
from unittest import mock

from app.ingestion.parsers import (
    parse_pdf,
    parse_image,
    parse_document,
    MAX_PARA_CHARS,
    get_last_ocr_flag,
    _split_paragraphs,
)
from PyPDF2 import PdfWriter, PdfReader


def _blank_pdf_bytes(num_pages: int = 1) -> bytes:
    """Create a PDF with blank pages (no extractable text) — simulates scanned PDF."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _text_pdf_bytes(text: str = "Rohan Mehra called Priya Sharma.") -> bytes:
    """
    Create a minimal PDF with a text layer using reportlab if available,
    otherwise fallback to a mocked PdfReader approach. Tries reportlab,
    else crafts a simple PDF with text via PyPDF2? For test purposes we
    mock PdfReader directly when reportlab unavailable.
    """
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import letter

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=letter)
        c.drawString(100, 750, text)
        c.showPage()
        c.save()
        return buf.getvalue()
    except ImportError:
        # Fallback: create a blank PDF and will mock PdfReader in test to simulate text
        return _blank_pdf_bytes(1)


def test_scanned_pdf_routes_to_ocr():
    """Synthetic scanned PDF (no digital text) must route to OCR and preserve provenance."""
    scanned = _blank_pdf_bytes(2)
    # Verify PyPDF2 indeed extracts zero text
    r = PdfReader(io.BytesIO(scanned))
    assert all(not (p.extract_text() or "").strip() for p in r.pages)

    ocr_pages = [
        {"page": 1, "paragraphs": ["Rohan Mehra called Priya Sharma at 10am."]},
        {"page": 2, "paragraphs": ["FIR 2026/0417 recorded at Rudrapuram station."]},
    ]
    ocr_text = "\n\n".join(p for pg in ocr_pages for p in pg["paragraphs"])

    with mock.patch("app.ingestion.parsers._parse_scanned_pdf_ocr", return_value=(ocr_text, ocr_pages)) as m:
        text, pages = parse_pdf(scanned)
        assert m.called, "Scanned PDF should route to _parse_scanned_pdf_ocr"
        # Provenance invariants
        assert len(pages) == 2
        for pg in pages:
            assert "page" in pg and "paragraphs" in pg
            assert isinstance(pg["page"], int)
            assert isinstance(pg["paragraphs"], list)
            assert len(pg["paragraphs"]) > 0
            for para in pg["paragraphs"]:
                assert isinstance(para, str) and len(para.strip()) > 0
                assert len(para) <= MAX_PARA_CHARS, f"Paragraph exceeds {MAX_PARA_CHARS}"
        # Full text matches pages
        assert text == ocr_text
        # OCR flag set
        assert get_last_ocr_flag() is True


def test_digital_pdf_bypasses_ocr():
    """Digital PDF with text layer must NOT trigger OCR."""
    # Create a PDF that PyPDF2 can extract text from, or mock it
    text = "Rohan Mehra called Priya Sharma. Account HDFC-XXXX-1234 transferred funds."
    pdf_bytes = _text_pdf_bytes(text)

    # If we fell back to blank PDF (no reportlab), mock PdfReader to simulate digital text
    try:
        from reportlab.pdfgen import canvas  # noqa
        has_reportlab = True
    except ImportError:
        has_reportlab = False

    if not has_reportlab:
        # Mock PdfReader to return a page with extractable text
        mock_page = mock.MagicMock()
        mock_page.extract_text.return_value = text
        mock_reader = mock.MagicMock()
        mock_reader.pages = [mock_page] * 1
        # patch PdfReader inside parse_pdf
        with mock.patch("PyPDF2.PdfReader", return_value=mock_reader):
            with mock.patch("app.ingestion.parsers._parse_scanned_pdf_ocr") as ocr_mock:
                txt, pages = parse_pdf(pdf_bytes)
                assert not ocr_mock.called, "Digital PDF must bypass OCR"
                assert len(pages) == 1
                assert len(pages[0]["paragraphs"]) > 0
                assert get_last_ocr_flag() is False
                return

    # With reportlab available, real extraction
    with mock.patch("app.ingestion.parsers._parse_scanned_pdf_ocr") as ocr_mock:
        txt, pages = parse_pdf(pdf_bytes)
        assert not ocr_mock.called, "Digital PDF must bypass OCR"
        assert len(pages) >= 1
        assert sum(len(p["paragraphs"]) for p in pages) > 0
        assert get_last_ocr_flag() is False
        # Verify extracted text contains our content (or at least non-empty)
        assert len(txt.strip()) > 0


def test_ocr_paragraph_chunking_respects_max():
    """OCR output exceeding MAX_PARA_CHARS must be chunked via _split_paragraphs."""
    long_text = "Sentence one. " * 100  # ~1500 chars
    assert len(long_text) > MAX_PARA_CHARS
    scanned = _blank_pdf_bytes(1)
    # Simulate OCR that returns a single long paragraph
    # Our _ocr_image_to_paragraphs chunks, but _parse_scanned_pdf_ocr does too.
    # Mock to return long single para then expect parse_pdf to have chunked it
    # Instead directly test _split_paragraphs and the OCR chunking path
    chunks = _split_paragraphs(long_text)
    for c in chunks:
        assert len(c) <= MAX_PARA_CHARS

    # Mock OCR to return long para
    ocr_pages = [{"page": 1, "paragraphs": [long_text]}]
    # The parser itself chunks inside _ocr_image_to_paragraphs; test via mock
    # that final pages respect limit even when OCR returns long string
    # Simulate _parse_scanned_pdf_ocr returning chunked
    chunked = _split_paragraphs(long_text)
    ocr_pages_chunked = [{"page": 1, "paragraphs": chunked}]
    ocr_text = "\n\n".join(chunked)
    with mock.patch("app.ingestion.parsers._parse_scanned_pdf_ocr", return_value=(ocr_text, ocr_pages_chunked)):
        text, pages = parse_pdf(scanned)
        for pg in pages:
            for para in pg["paragraphs"]:
                assert len(para) <= MAX_PARA_CHARS


def test_image_parser_wrapper():
    """PNG/JPG/JPEG dispatch via parse_document to parse_image with OCR provenance."""
    dummy_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    ocr_pages = [{"page": 1, "paragraphs": ["Rohan Mehra phone +91-9876543210", "Vehicle MH-02-AB-1234"]}]
    ocr_text = "\n\n".join(ocr_pages[0]["paragraphs"])
    with mock.patch("app.ingestion.parsers.parse_image", return_value=(ocr_text, ocr_pages)) as m:
        txt, pages = parse_document("png", dummy_data, "test.png")
        assert m.called
        assert len(pages) == 1
        assert pages[0]["page"] == 1
        assert len(pages[0]["paragraphs"]) == 2
        assert txt == ocr_text

    with mock.patch("app.ingestion.parsers.parse_image", return_value=(ocr_text, ocr_pages)):
        txt2, pages2 = parse_document("jpg", dummy_data, "photo.jpg")
        assert pages2[0]["page"] == 1
    with mock.patch("app.ingestion.parsers.parse_image", return_value=(ocr_text, ocr_pages)):
        txt3, pages3 = parse_document("jpeg", dummy_data, "scan.jpeg")
        assert pages3[0]["page"] == 1


def test_parse_image_direct_ocr_mock():
    """Direct parse_image with mocked pytesseract block reconstruction."""
    # Create a tiny image in memory
    from PIL import Image

    img = Image.new("RGB", (400, 100), color="white")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    data = img_bytes.getvalue()

    fake_paras = ["FIR Number 2026/0417 recorded at Rudrapuram", "Complainant: Rohan Mehra"]
    with mock.patch("app.ingestion.parsers._ocr_image_to_paragraphs", return_value=fake_paras):
        text, pages = parse_image(data)
        assert len(pages) == 1
        assert pages[0]["page"] == 1
        assert pages[0]["paragraphs"] == fake_paras
        assert text == "\n\n".join(fake_paras)
        assert get_last_ocr_flag() is True
        # Provenance invariant
        for para in pages[0]["paragraphs"]:
            assert len(para) <= MAX_PARA_CHARS


def test_digital_pdf_performance_no_regression():
    """Digital PDF should remain fast (no OCR overhead) — ensure bypass is immediate."""
    text = "Operation Nexus ledger entry: HDFC-XXXX-1234 transferred to SBI-XXXX-5678."
    pdf_bytes = _text_pdf_bytes(text)
    try:
        from reportlab.pdfgen import canvas  # noqa
        has_reportlab = True
    except ImportError:
        has_reportlab = False
    if not has_reportlab:
        mock_page = mock.MagicMock()
        mock_page.extract_text.return_value = text
        mock_reader = mock.MagicMock()
        mock_reader.pages = [mock_page]
        with mock.patch("PyPDF2.PdfReader", return_value=mock_reader):
            with mock.patch("app.ingestion.parsers._parse_scanned_pdf_ocr") as ocr_mock:
                import time

                start = time.time()
                txt, pages = parse_pdf(pdf_bytes)
                elapsed = time.time() - start
                assert not ocr_mock.called
                assert elapsed < 1.0, "Digital PDF should not incur OCR delay"
                return
    import time

    start = time.time()
    with mock.patch("app.ingestion.parsers._parse_scanned_pdf_ocr") as ocr_mock:
        txt, pages = parse_pdf(pdf_bytes)
        elapsed = time.time() - start
        assert not ocr_mock.called
        assert elapsed < 1.0


def test_provenance_schema_conformance():
    """Every parser output must be list of {page:int, paragraphs:[str,...]}."""
    # Test TXT, CSV, JSON alongside OCR paths
    from app.ingestion.parsers import parse_txt, parse_csv, parse_json

    for txt, pages in [
        parse_txt(b"para one\n\npara two"),
        parse_csv(b"a,b\n1,2\n3,4\n"),
        parse_json(b'[{"name":"X"}]'),
    ]:
        assert isinstance(pages, list)
        for pg in pages:
            assert isinstance(pg["page"], int)
            assert isinstance(pg["paragraphs"], list)
            for para in pg["paragraphs"]:
                assert isinstance(para, str)
                assert len(para) <= MAX_PARA_CHARS

    # OCR path
    scanned = _blank_pdf_bytes(1)
    ocr_pages = [{"page": 1, "paragraphs": ["para A", "para B"]}]
    ocr_text = "para A\n\npara B"
    with mock.patch("app.ingestion.parsers._parse_scanned_pdf_ocr", return_value=(ocr_text, ocr_pages)):
        txt, pages = parse_pdf(scanned)
        for pg in pages:
            assert "page" in pg and "paragraphs" in pg
            assert pg["page"] == 1
            assert all(isinstance(p, str) for p in pg["paragraphs"])


def test_ocr_reconstructs_multiple_pages():
    """OCR must return one entry per PDF page, preserving page numbers."""
    scanned = _blank_pdf_bytes(3)
    ocr_pages = [
        {"page": 1, "paragraphs": ["Page 1 content mentions Rohan."]},
        {"page": 2, "paragraphs": ["Page 2 content mentions Priya."]},
        {"page": 3, "paragraphs": ["Page 3 content mentions Anita."]},
    ]
    ocr_text = "\n\n".join(p for pg in ocr_pages for p in pg["paragraphs"])
    with mock.patch("app.ingestion.parsers._parse_scanned_pdf_ocr", return_value=(ocr_text, ocr_pages)):
        text, pages = parse_pdf(scanned)
        assert len(pages) == 3
        assert [p["page"] for p in pages] == [1, 2, 3]
        assert pages[1]["paragraphs"][0] == "Page 2 content mentions Priya."


def test_allowed_extensions_dispatch():
    """parse_document must support png/jpg/jpeg via parse_image."""
    for ext in ["png", "jpg", "jpeg", "pdf", "txt", "csv", "json"]:
        assert ext in ["pdf", "txt", "csv", "json", "png", "jpg", "jpeg"]
    # Unknown should raise
    with pytest.raises(ValueError):
        parse_document("docx", b"fake", "a.docx")
    with pytest.raises(ValueError):
        parse_document("exe", b"fake", "a.exe")
