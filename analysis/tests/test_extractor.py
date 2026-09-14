import io

import pytest
from pypdf import PdfWriter

from analysis.extractor import PDFExtractionError, ScannedPDFError, extract_text


def make_blank_pdf():
    """A valid PDF with one page and no text layer, like a scan without OCR."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_without_text_raises_scanned_error_instead_of_returning_empty():
    with pytest.raises(ScannedPDFError, match="OCR"):
        extract_text(make_blank_pdf())


def test_non_pdf_bytes_raise_extraction_error():
    with pytest.raises(PDFExtractionError, match="could not be read"):
        extract_text(b"definitely not a pdf")
