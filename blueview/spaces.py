"""
Extract Bluebeam Spaces from a PDF.

Bluebeam Spaces are stored in the document-level /BB dictionary under
/Spaces → array of Space dictionaries, each with /Name, /Color, /Pages, etc.
This matches what pymkup uncovered in its reverse-engineering.
"""

from __future__ import annotations

from typing import Any

import pikepdf


def extract(pdf_path: str) -> list[dict[str, Any]]:
    """Return the Bluebeam Spaces list, or an empty list if none are defined."""
    spaces: list[dict[str, Any]] = []
    try:
        with pikepdf.open(pdf_path) as pdf:
            bb = pdf.Root.get("/BB")
            if bb is None:
                return spaces
            spaces_arr = bb.get("/Spaces")
            if spaces_arr is None:
                return spaces
            for sp in spaces_arr:
                spaces.append(_parse_space(sp))
    except Exception:
        pass
    return spaces


def _parse_space(sp: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {}

    name = sp.get("/Name")
    if name is not None:
        entry["name"] = str(name)

    label = sp.get("/Label")
    if label is not None:
        entry["label"] = str(label)

    color = sp.get("/Color")
    if color is not None:
        entry["color"] = _color_to_hex(color)

    shape = sp.get("/Shape")
    if shape is not None:
        entry["shape"] = _vertices_to_list(shape)

    pages = sp.get("/Pages")
    if pages is not None:
        try:
            entry["pages"] = [int(p) for p in pages]
        except Exception:
            entry["pages"] = str(pages)

    markup_count = sp.get("/Count")
    if markup_count is not None:
        try:
            entry["markup_count"] = int(markup_count)
        except Exception:
            pass

    return entry


def _color_to_hex(color: Any) -> str:
    try:
        if isinstance(color, (list, pikepdf.Array)) and len(color) >= 3:
            r, g, b = (int(round(float(color[i]) * 255)) for i in range(3))
            return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        pass
    return str(color)


def _vertices_to_list(shape: Any) -> list[list[float]]:
    """Convert a flat coordinate array to [[x,y], ...] pairs."""
    try:
        flat = [float(v) for v in shape]
        return [[flat[i], flat[i + 1]] for i in range(0, len(flat) - 1, 2)]
    except Exception:
        return []
