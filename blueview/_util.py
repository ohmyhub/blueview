"""Shared internal utilities."""

from __future__ import annotations


def decode_pdf_label(raw: str, fallback: str = "") -> str:
    """Decode a PDF page label string.

    PyMuPDF returns UTF-16 labels as <FEFF...> hex strings. Decode those;
    pass plain strings through unchanged.
    """
    if not raw:
        return fallback
    if raw.startswith("<") and raw.endswith(">"):
        try:
            return bytes.fromhex(raw[1:-1]).decode("utf-16")
        except Exception:
            pass
    return raw
