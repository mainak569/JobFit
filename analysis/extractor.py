"""
PDF bytes -> plain text.

pdfplumber first, pypdf as a fallback, and a clear error when neither finds
usable text. This module never returns empty text.
"""

import io
import logging

import pdfplumber
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# WHY 50: a real resume has hundreds of characters at minimum. Anything under
# 50 is a page number, a stray header, or nothing at all, so it is treated as
# a failed extraction rather than a very short resume.
MIN_TEXT_LENGTH = 50

# WHY 1.5 instead of pdfplumber's default of 3: x_tolerance is the horizontal
# gap (in points) below which two characters are glued into one word.
# Justified text in LaTeX/Overleaf resumes has tight inter-word gaps, and at
# the default of 3 a line came out as
# "Developedamulti-agentworkflowwithInngest,tRPC,Prisma,andPostgreSQL",
# which hides every skill in it from the word-boundary matcher. 1.5 splits
# those words correctly without breaking normal words apart.
PDFPLUMBER_X_TOLERANCE = 1.5


class PDFExtractionError(Exception):
    """The file could not be turned into usable text."""


class ScannedPDFError(PDFExtractionError):
    """The file is a valid PDF but contains no selectable text."""


SCANNED_PDF_MESSAGE = (
    "We couldn't find any selectable text in this PDF. It is most likely a "
    "scanned image, which needs OCR before it can be analysed. Export your "
    "resume to PDF directly from your editor (Word, Google Docs, Overleaf), or "
    "run the scan through an OCR tool first."
)

UNREADABLE_PDF_MESSAGE = (
    "This file could not be read as a PDF. It may be corrupted, password "
    "protected, or not actually a PDF."
)


def _extract_with_pdfplumber(pdf_bytes):
    page_texts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=PDFPLUMBER_X_TOLERANCE)
            page_texts.append(page_text or "")
    return "\n".join(page_texts)


def _extract_with_pypdf(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_texts = []
    for page in reader.pages:
        page_texts.append(page.extract_text() or "")
    return "\n".join(page_texts)


def _clean(text):
    # WHY strip NUL: some PDFs embed \x00 in their text layer, and PostgreSQL
    # rejects NUL characters in text columns, so saving the Resume would fail
    # with an opaque database error far away from the real cause.
    return text.replace("\x00", "").strip()


def extract_text(pdf_bytes):
    """
    Return the text of a PDF given as bytes.

    Raises ScannedPDFError if the PDF has no usable text layer, or
    PDFExtractionError if neither library can parse the file at all.
    """
    # WHY bytes rather than a path: the upload endpoint receives bytes, and the
    # same bytes are then sent to storage. Taking bytes means the caller reads
    # the file once and both steps see identical content.
    failures = 0

    # WHY catch Exception broadly: pdfminer (under pdfplumber) and pypdf raise
    # a zoo of exception types for malformed files (PDFSyntaxError,
    # PdfReadError, struct.error, KeyError...). All of them mean the same
    # thing here: this library couldn't read it, try the other one.
    try:
        text = _clean(_extract_with_pdfplumber(pdf_bytes))
    except Exception as exc:
        logger.warning("pdfplumber could not parse the PDF: %s", exc)
        text = ""
        failures += 1

    if len(text) >= MIN_TEXT_LENGTH:
        return text

    # WHY a second library: pdfplumber and pypdf decode fonts and content
    # streams differently, and each succeeds on some files the other returns
    # nothing for (unusual font encodings, slightly malformed xref tables).
    logger.info(
        "pdfplumber returned %d characters (minimum %d); retrying with pypdf",
        len(text),
        MIN_TEXT_LENGTH,
    )
    try:
        fallback_text = _clean(_extract_with_pypdf(pdf_bytes))
    except Exception as exc:
        logger.warning("pypdf could not parse the PDF: %s", exc)
        fallback_text = ""
        failures += 1

    if len(fallback_text) >= MIN_TEXT_LENGTH:
        return fallback_text

    if failures == 2:
        raise PDFExtractionError(UNREADABLE_PDF_MESSAGE)

    # WHY raise instead of returning the short text: an empty resume would
    # flow through to a score of 5 and a list of "missing" skills, which looks
    # like a harsh verdict on the user rather than a problem with the file.
    raise ScannedPDFError(SCANNED_PDF_MESSAGE)
