# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the CLI

The package is installed in editable mode into the system Python. Invoke it via:

```powershell
python -m blueview.cli <subcommand> [options]
```

Subcommands: `info`, `markups`, `spaces`, `text`, `search`, `render`

## Install / reinstall

```powershell
python -m pip install -e .
```

No venv is used — the package is installed directly into the system Python (`Python313`).

## Architecture

One package (`blueview/`), no frameworks. Each module is a thin layer over the two PDF libraries:

- **PyMuPDF (`fitz`)** — standard annotation fields, text extraction, page rendering. Used in `markups.py`, `text.py`, `render.py`, `document.py`.
- **pikepdf** — low-level PDF object access for Bluebeam's undocumented private data. Used in `markups.py` (`_load_bb_annotation_data`) and `document.py` (`_extract_scales`).

### Bluebeam data layout (reverse-engineered)

Bluebeam stores private data in two places within the PDF:

1. **Per-annotation objects** — extra keys on each annotation dict (measurement values, lock state).
2. **`/Root/BB` document dictionary** — holds `/CustomColumns` definitions and `/MarkupList` (an array of per-markup dicts keyed by `/NM` UUID) carrying status, custom column values, and space assignment.

`markups.extract()` reads standard fields via PyMuPDF, then calls `_load_bb_annotation_data()` (pikepdf) to merge in the Bluebeam-private fields, keyed by annotation UUID (`/NM`).

### Filtering

`markups.extract()` hard-excludes `author == "AutoCAD SHX Text"` unconditionally — these are geometry-proxy annotations from CAD exports, not real markups. All other filtering (`--status`, `--author`, `--subject`, `--page`) is opt-in via CLI flags.

### Page labels

PyMuPDF's `page.get_label()` returns UTF-16 labels as raw PDF hex strings (`<FEFF...>`). `_util.decode_pdf_label()` decodes these transparently and is used in every module that emits a `page_label` field.

### Export

`export.py` has four writers (`to_json`, `to_csv`, `to_xlsx`, `to_table`). XLSX output includes styled headers and frozen first row. All writers accept `rows: list[dict]` with heterogeneous keys — `_unified_fieldnames()` collects the union of all keys in insertion order.
