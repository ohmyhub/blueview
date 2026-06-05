"""
Extract the Bluebeam Markups List from a PDF.

Standard annotation fields (author, subject, contents, color, date, rect, page) are
read via PyMuPDF. Bluebeam-private fields (status, custom columns, checkmark, space)
are read via pikepdf from annotation's private dictionaries.

Bluebeam stores extra data in two places (per pymkup's reverse-engineering):
  - Per-annotation private dict under /BS, /BIL, and direct keys like /Subj, /T, etc.
  - A document-level /BB dictionary that holds the custom column definitions and
    the markup status history under /MarkupList → /Markup entries.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import fitz  # PyMuPDF
import pikepdf

from blueview._util import decode_pdf_label


# Bluebeam annotation type codes (Subject field maps to these when not overridden)
_BB_SUBTYPE_MAP: dict[str, str] = {
    "Text": "Note",
    "FreeText": "Text Box",
    "Line": "Line",
    "Square": "Rectangle",
    "Circle": "Ellipse",
    "Polygon": "Polygon",
    "PolyLine": "Polyline",
    "Stamp": "Stamp",
    "Ink": "Sketch",
    "Highlight": "Highlight",
    "Underline": "Underline",
    "StrikeOut": "Strikethrough",
    "Squiggly": "Squiggly",
    "Caret": "Caret",
    "FileAttachment": "Attachment",
    "Sound": "Sound",
    "Widget": "Form Field",
}


def extract(
    pdf_path: str,
    *,
    page_filter: int | None = None,
    status_filter: list[str] | None = None,
    author_filter: list[str] | None = None,
    subject_filter: list[str] | None = None,
    columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Return the full Markups List as a list of dicts.

    Standard columns are always included. Pass `columns` to restrict to a subset.
    Bluebeam-private fields (status, custom columns, space, etc.) are merged in where
    available; keys absent from a given annotation are omitted from its dict.
    """
    bb_data = _load_bb_annotation_data(pdf_path)
    rows: list[dict[str, Any]] = []

    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc):
            if page_filter is not None and page_index != page_filter:
                continue
            label = decode_pdf_label(page.get_label(), str(page_index + 1))

            for annot in page.annots():
                row = _standard_fields(annot, page_index, label)
                # Merge Bluebeam-private fields keyed by annotation UUID or object ref
                uuid = row.get("uuid") or ""
                bb_extra = bb_data.get(uuid, {})
                row.update(bb_extra)

                # AutoCAD SHX Text annotations are geometric text proxies, not real markups
                if row.get("author") == "AutoCAD SHX Text":
                    continue

                # Apply filters (case-insensitive substring)
                if status_filter and not _matches_any(row.get("status", ""), status_filter):
                    continue
                if author_filter and not _matches_any(row.get("author", ""), author_filter):
                    continue
                if subject_filter and not _matches_any(row.get("subject", ""), subject_filter):
                    continue

                if columns:
                    row = {k: v for k, v in row.items() if k in columns}

                rows.append(row)

    return rows


def _standard_fields(annot: fitz.Annot, page_index: int, page_label: str) -> dict[str, Any]:
    info = annot.info
    rect = annot.rect
    color = annot.colors

    subtype_raw = annot.type[1] if annot.type else ""
    subject = info.get("subject") or _BB_SUBTYPE_MAP.get(subtype_raw, subtype_raw)

    fill = color.get("fill") or []
    stroke = color.get("stroke") or []

    return {
        "page_index": page_index,
        "page_label": page_label,
        "uuid": info.get("id", ""),
        "subject": subject,
        "author": info.get("title", ""),
        "label": info.get("name", ""),
        "contents": info.get("content", ""),
        "creation_date": _parse_pdf_date(info.get("creationDate", "")),
        "modified_date": _parse_pdf_date(info.get("modDate", "")),
        "x": round(rect.x0, 2),
        "y": round(rect.y0, 2),
        "width": round(rect.width, 2),
        "height": round(rect.height, 2),
        "color_stroke": _rgb_tuple_to_hex(stroke),
        "color_fill": _rgb_tuple_to_hex(fill),
        "opacity": annot.opacity,
    }


def _load_bb_annotation_data(pdf_path: str) -> dict[str, dict[str, Any]]:
    """
    Read Bluebeam-private annotation data from the PDF via pikepdf.

    Returns a dict keyed by annotation UUID → dict of extra fields.

    Bluebeam embeds extended data in each annotation object, including:
      - /T  → author (redundant with PyMuPDF's title, but sometimes differs)
      - /NM → annotation name / UUID (same as PyMuPDF's id)
      - /BS or /BIL → private Bluebeam keys (checkmark, custom columns, status)
      - A /Subtype-specific private dict (e.g. /Measure for measurement markups)

    The document-level /BB /MarkupList carries status history and custom-column
    values for each annotation, referenced by /NM (UUID).
    """
    result: dict[str, dict[str, Any]] = {}

    try:
        with pikepdf.open(pdf_path) as pdf:
            # Document-level Bluebeam block
            bb_doc = pdf.Root.get("/BB")
            custom_col_defs = _parse_custom_column_defs(bb_doc)
            bb_markup_index = _parse_bb_markup_list(bb_doc, custom_col_defs)

            # Per-page annotation objects
            for page in pdf.pages:
                annots_arr = page.get("/Annots")
                if annots_arr is None:
                    continue
                for annot_ref in annots_arr:
                    annot_obj = annot_ref if isinstance(annot_ref, pikepdf.Dictionary) else annot_ref.obj
                    uuid = _str(annot_obj.get("/NM")) or _str(annot_obj.get("/T", ""))
                    if not uuid:
                        continue

                    extra: dict[str, Any] = {}

                    # Measurement data
                    measure = annot_obj.get("/Measure")
                    if measure is not None:
                        extra.update(_parse_measurement(measure))

                    # Checkmark / locked state (Bluebeam stores these as /F bits and /Lock)
                    lock = annot_obj.get("/Lock")
                    if lock is not None:
                        extra["locked"] = bool(lock)

                    # Merge document-level BB data for this UUID
                    if uuid in bb_markup_index:
                        extra.update(bb_markup_index[uuid])

                    if extra:
                        result[uuid] = extra
    except Exception:
        # pikepdf failures are non-fatal; callers get standard fields only
        pass

    return result


def _parse_custom_column_defs(bb_doc: Any) -> dict[str, str]:
    """Return {column_id: column_name} from /BB/CustomColumns."""
    defs: dict[str, str] = {}
    if bb_doc is None:
        return defs
    try:
        cols = bb_doc.get("/CustomColumns")
        if cols is None:
            return defs
        for col in cols:
            col_id = _str(col.get("/ID", ""))
            col_name = _str(col.get("/Name", col_id))
            if col_id:
                defs[col_id] = col_name
    except Exception:
        pass
    return defs


def _parse_bb_markup_list(bb_doc: Any, col_defs: dict[str, str]) -> dict[str, dict[str, Any]]:
    """
    Parse /BB/MarkupList to get per-annotation status and custom column values.
    Returns {uuid: {field: value, ...}}.
    """
    index: dict[str, dict[str, Any]] = {}
    if bb_doc is None:
        return index
    try:
        ml = bb_doc.get("/MarkupList")
        if ml is None:
            return index
        entries = ml.get("/Markup") or ml  # may be the array directly
        if isinstance(entries, pikepdf.Dictionary):
            entries = [entries]
        for entry in entries:
            uuid = _str(entry.get("/NM", ""))
            if not uuid:
                continue
            extra: dict[str, Any] = {}

            status = entry.get("/Status")
            if status is not None:
                extra["status"] = _str(status)

            checked = entry.get("/Checked")
            if checked is not None:
                extra["checked"] = bool(checked)

            space = entry.get("/Space")
            if space is not None:
                extra["space"] = _str(space)

            # Custom column values stored as /CC array of {/ID, /V} dicts
            cc = entry.get("/CC")
            if cc is not None:
                for col_val in cc:
                    col_id = _str(col_val.get("/ID", ""))
                    col_v = col_val.get("/V")
                    if col_id and col_v is not None:
                        col_name = col_defs.get(col_id, col_id)
                        extra[f"col:{col_name}"] = _str(col_v)

            if extra:
                index[uuid] = extra
    except Exception:
        pass
    return index


def _parse_measurement(measure: Any) -> dict[str, Any]:
    """Extract value and unit from a /Measure annotation dict."""
    result: dict[str, Any] = {}
    try:
        value = measure.get("/V") or measure.get("/AV")
        if value is not None:
            result["measurement_value"] = float(value)
        subtype = measure.get("/Subtype")
        if subtype is not None:
            result["measurement_type"] = _str(subtype)
        x_arr = measure.get("/X")
        if x_arr is not None and len(x_arr) >= 2:
            nf = x_arr[1]
            if isinstance(nf, pikepdf.Dictionary):
                result["measurement_unit"] = _str(nf.get("/U", ""))
    except Exception:
        pass
    return result


# ── Helpers ──────────────────────────────────────────────────────────────────

def _str(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, (pikepdf.String, pikepdf.Name)):
        return str(obj)
    return str(obj)


def _rgb_tuple_to_hex(rgb: list | tuple) -> str:
    if not rgb or len(rgb) < 3:
        return ""
    r, g, b = (int(round(c * 255)) for c in rgb[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


_PDF_DATE_RE = re.compile(
    r"D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})"
)


def _parse_pdf_date(raw: str) -> str:
    if not raw:
        return ""
    m = _PDF_DATE_RE.search(raw)
    if not m:
        return raw
    y, mo, d, h, mi, s = m.groups()
    try:
        dt = datetime(int(y), int(mo), int(d), int(h), int(mi), int(s), tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return raw


def _matches_any(value: str, filters: list[str]) -> bool:
    v = value.lower()
    return any(f.lower() in v for f in filters)
