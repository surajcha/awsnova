"""OCR and text extraction service for PDFs and images."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)

# Try to import tesseract; fall back gracefully
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    logger.warning("pytesseract not available — image OCR will be limited")


def extract_text_from_pdf(file_path: str) -> list[dict]:
    """Extract text from each page of a PDF.

    Returns list of {"page": int, "text": str}.
    """
    pages: list[dict] = []
    reader = PdfReader(file_path)

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append({"page": i + 1, "text": text.strip()})

    logger.info("Extracted %d pages from PDF %s", len(pages), file_path)
    return pages


def extract_text_from_image(file_path: str) -> str:
    """Run OCR on a single image and return extracted text."""
    if not HAS_TESSERACT:
        logger.warning("Tesseract not available, returning empty text for %s", file_path)
        return ""

    img = Image.open(file_path)
    text = pytesseract.image_to_string(img)
    logger.info("OCR extracted %d chars from %s", len(text), file_path)
    return text.strip()


def extract_text_from_txt(file_path: str) -> str:
    """Read plain text file."""
    return Path(file_path).read_text(encoding="utf-8", errors="ignore").strip()


def extract_content(file_path: str) -> list[dict]:
    """Unified extraction: returns list of {"page": int|None, "text": str}.

    Dispatches based on file extension.
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        text = extract_text_from_image(file_path)
        return [{"page": None, "text": text}]
    elif ext == ".txt":
        text = extract_text_from_txt(file_path)
        return [{"page": None, "text": text}]
    else:
        logger.warning("Unsupported file type: %s", ext)
        return []
