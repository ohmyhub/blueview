"""Render PDF pages to PNG images."""

from __future__ import annotations

import fitz  # PyMuPDF


def render_page(
    pdf_path: str,
    page_index: int,
    output_path: str,
    *,
    dpi: int = 150,
    include_annots: bool = True,
) -> str:
    """
    Render a single page to a PNG file.

    Returns the output path on success.
    PyMuPDF renders annotations by default; pass include_annots=False to suppress them.
    """
    with fitz.open(pdf_path) as doc:
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of range (document has {len(doc)} pages)")
        page = doc[page_index]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        # annot=True is the default; annot=False hides annotation rendering
        pix = page.get_pixmap(matrix=mat, annots=include_annots)
        pix.save(output_path)
    return output_path
