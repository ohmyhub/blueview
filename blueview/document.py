"""Document-level metadata: pages, sizes, labels, rotation, measurement scale."""

from __future__ import annotations

import fitz  # PyMuPDF
import pikepdf

from typing import Any
from blueview._util import decode_pdf_label


def info(pdf_path: str) -> dict[str, Any]:
    """Return high-level document metadata."""
    with fitz.open(pdf_path) as doc:
        pages = []
        for i, page in enumerate(doc):
            rect = page.rect
            pages.append({
                "index": i,
                "label": decode_pdf_label(page.get_label(), str(i + 1)),
                "width_pt": round(rect.width, 2),
                "height_pt": round(rect.height, 2),
                "rotation": page.rotation,
                "markup_count": sum(1 for _ in page.annots()),
            })

        meta = doc.metadata or {}
        total_markups = sum(p["markup_count"] for p in pages)

    scales = _extract_scales(pdf_path)

    return {
        "path": pdf_path,
        "page_count": len(pages),
        "total_markups": total_markups,
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "creator": meta.get("creator", ""),
        "pages": pages,
        "measurement_scales": scales,
    }


def _extract_scales(pdf_path: str) -> list[dict[str, Any]]:
    """
    Pull per-page measurement scales from Bluebeam's private ViewportDict.

    Bluebeam stores calibrated scales in the page's /VP (Viewport) dictionary,
    under /Measure → /X (horizontal) and /Y (vertical) scale arrays.
    This mirrors what pymkup found when reverse-engineering the format.
    """
    scales = []
    try:
        with pikepdf.open(pdf_path) as pdf:
            for page_index, page in enumerate(pdf.pages):
                vp_list = page.get("/VP")
                if vp_list is None:
                    continue
                if isinstance(vp_list, pikepdf.Dictionary):
                    vp_list = [vp_list]
                for vp in vp_list:
                    measure = vp.get("/Measure")
                    if measure is None:
                        continue
                    scale_entry: dict[str, Any] = {"page_index": page_index}
                    x_arr = measure.get("/X")
                    y_arr = measure.get("/Y")
                    if x_arr is not None and len(x_arr) >= 2:
                        scale_entry["x_scale"] = _parse_scale_array(x_arr)
                    if y_arr is not None and len(y_arr) >= 2:
                        scale_entry["y_scale"] = _parse_scale_array(y_arr)
                    area = measure.get("/A")
                    if area is not None and len(area) >= 2:
                        scale_entry["area_scale"] = _parse_scale_array(area)
                    unit_type = measure.get("/Subtype")
                    if unit_type is not None:
                        scale_entry["subtype"] = str(unit_type)
                    if len(scale_entry) > 1:
                        scales.append(scale_entry)
    except Exception:
        # Silently skip — scale is a nice-to-have; failures here shouldn't abort info()
        pass
    return scales


def _parse_scale_array(arr: Any) -> dict[str, Any]:
    """Convert a PDF measurement NumberFormat array to a readable dict."""
    try:
        # Standard PDF scale array: [ratio, NumberFormat dict, ...]
        if len(arr) >= 2:
            num_format = arr[1]
            return {
                "factor": float(arr[0]) if not isinstance(arr[0], pikepdf.Dictionary) else None,
                "units": str(num_format.get("/U", "")) if isinstance(num_format, pikepdf.Dictionary) else "",
                "denominator": float(num_format.get("/D", 1)) if isinstance(num_format, pikepdf.Dictionary) else 1,
            }
    except Exception:
        pass
    return {}
