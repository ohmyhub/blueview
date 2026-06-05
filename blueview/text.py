"""Text extraction and search."""

from __future__ import annotations

import re
from typing import Any

import fitz  # PyMuPDF

from blueview._util import decode_pdf_label


def extract(pdf_path: str, page_filter: int | None = None) -> list[dict[str, Any]]:
    """Return page text as a list of {page_index, page_label, text} dicts."""
    pages = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            if page_filter is not None and i != page_filter:
                continue
            label = decode_pdf_label(page.get_label(), str(i + 1))
            pages.append({
                "page_index": i,
                "page_label": label,
                "text": page.get_text("text"),
            })
    return pages


def search(pdf_path: str, pattern: str, page_filter: int | None = None) -> list[dict[str, Any]]:
    """
    Search for `pattern` (plain string or regex) across the document.

    Returns matches with page index, label, matched text, and bounding box.
    """
    results = []
    try:
        rx = re.compile(pattern, re.IGNORECASE)
        use_regex = True
    except re.error:
        use_regex = False

    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            if page_filter is not None and i != page_filter:
                continue
            label = decode_pdf_label(page.get_label(), str(i + 1))

            if use_regex:
                # PyMuPDF's search_for does literal matching; use text blocks + re for regex
                blocks = page.get_text("blocks")
                for block in blocks:
                    block_text = block[4]
                    for m in rx.finditer(block_text):
                        results.append({
                            "page_index": i,
                            "page_label": label,
                            "match": m.group(),
                            "block_bbox": [round(block[j], 2) for j in range(4)],
                        })
            else:
                hits = page.search_for(pattern, quads=False)
                for rect in hits:
                    results.append({
                        "page_index": i,
                        "page_label": label,
                        "match": pattern,
                        "bbox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
                    })

    return results
