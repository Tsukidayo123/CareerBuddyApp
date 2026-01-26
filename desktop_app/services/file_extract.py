# services/file_extract.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

# Optional PDF extraction via PyMuPDF (fitz)
try:
    import fitz  # PyMuPDF
    _HAS_PYMUPDF = True
except Exception:
    fitz = None  # type: ignore
    _HAS_PYMUPDF = False

# Optional DOCX extraction
try:
    import docx  # python-docx
    _HAS_DOCX = True
except Exception:
    docx = None  # type: ignore
    _HAS_DOCX = False


TEXT_EXTS = {".txt", ".md", ".csv", ".log", ".rtf"}


def extract_text_from_file(path: str, max_chars: int = 25_000) -> Tuple[str, str]:
    """
    Returns (label, extracted_text).
    label is a short type label e.g. "PDF", "DOCX", "TEXT", "UNKNOWN".
    extracted_text is truncated to max_chars.
    """
    p = Path(path)
    ext = p.suffix.lower()

    if not p.exists():
        return "MISSING", ""

    # TEXT
    if ext in TEXT_EXTS:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            return "TEXT", _clip(text, max_chars)
        except Exception:
            return "TEXT", ""

    # DOCX
    if ext == ".docx":
        if not _HAS_DOCX or docx is None:
            return "DOCX", ""
        try:
            d = docx.Document(str(p))
            parts = []
            for para in d.paragraphs:
                t = (para.text or "").strip()
                if t:
                    parts.append(t)
            text = "\n".join(parts)
            return "DOCX", _clip(text, max_chars)
        except Exception:
            return "DOCX", ""

    # PDF
    if ext == ".pdf":
        if not _HAS_PYMUPDF or fitz is None:
            return "PDF", ""
        try:
            doc = fitz.open(str(p))
            parts = []
            for i in range(min(doc.page_count, 6)):  # first 6 pages is usually enough for CVs
                page = doc.load_page(i)
                parts.append(page.get_text("text"))
            text = "\n".join(parts)
            return "PDF", _clip(text, max_chars)
        except Exception:
            return "PDF", ""

    # Other / unsupported (images etc.)
    return "UNKNOWN", ""


def _clip(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[:max_chars] + "\n\n[...truncated...]"
