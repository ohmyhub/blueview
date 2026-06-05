"""blueview CLI — read Bluebeam Revu markup data from local PDF files."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="blueview",
        description="Read Bluebeam Revu markup data from local PDF files.",
    )
    subs = parser.add_subparsers(dest="command", metavar="COMMAND")
    subs.required = True

    # ── info ──────────────────────────────────────────────────────────────────
    p_info = subs.add_parser("info", help="Document metadata: pages, sizes, markup count, scales.")
    p_info.add_argument("file", metavar="FILE.pdf")
    p_info.add_argument("--format", choices=["json", "table"], default="table")

    # ── markups ───────────────────────────────────────────────────────────────
    p_markups = subs.add_parser("markups", help="Extract the full Markups List.")
    p_markups.add_argument("file", metavar="FILE.pdf")
    p_markups.add_argument("--page", type=int, default=None, help="0-based page index to filter to.")
    p_markups.add_argument("--status", nargs="+", metavar="STATUS", help="Filter by status (substring match).")
    p_markups.add_argument("--author", nargs="+", metavar="AUTHOR", help="Filter by author (substring match).")
    p_markups.add_argument("--subject", nargs="+", metavar="SUBJECT", help="Filter by subject/type (substring match).")
    p_markups.add_argument("--columns", nargs="+", metavar="COL", help="Restrict output to these column names.")
    p_markups.add_argument("--format", choices=["json", "csv", "xlsx", "table"], default="table")
    p_markups.add_argument("--output", "-o", default=None, help="Write output to this file (required for xlsx).")

    # ── spaces ────────────────────────────────────────────────────────────────
    p_spaces = subs.add_parser("spaces", help="List Bluebeam Spaces defined in the document.")
    p_spaces.add_argument("file", metavar="FILE.pdf")
    p_spaces.add_argument("--format", choices=["json", "table"], default="table")

    # ── text ──────────────────────────────────────────────────────────────────
    p_text = subs.add_parser("text", help="Extract page text.")
    p_text.add_argument("file", metavar="FILE.pdf")
    p_text.add_argument("--page", type=int, default=None, help="0-based page index.")

    # ── search ────────────────────────────────────────────────────────────────
    p_search = subs.add_parser("search", help="Search for text or a regex pattern.")
    p_search.add_argument("file", metavar="FILE.pdf")
    p_search.add_argument("pattern", metavar="PATTERN")
    p_search.add_argument("--page", type=int, default=None, help="Restrict to a single page (0-based).")
    p_search.add_argument("--format", choices=["json", "table"], default="table")

    # ── render ────────────────────────────────────────────────────────────────
    p_render = subs.add_parser("render", help="Render a page to a PNG image.")
    p_render.add_argument("file", metavar="FILE.pdf")
    p_render.add_argument("--page", type=int, default=0, help="0-based page index (default: 0).")
    p_render.add_argument("--output", "-o", required=True, help="Output PNG file path.")
    p_render.add_argument("--dpi", type=int, default=150, help="Render resolution in DPI (default: 150).")
    p_render.add_argument("--no-annots", dest="annots", action="store_false", default=True,
                          help="Render without markup annotations.")

    args = parser.parse_args(argv)

    try:
        if args.command == "info":
            _cmd_info(args)
        elif args.command == "markups":
            _cmd_markups(args)
        elif args.command == "spaces":
            _cmd_spaces(args)
        elif args.command == "text":
            _cmd_text(args)
        elif args.command == "search":
            _cmd_search(args)
        elif args.command == "render":
            _cmd_render(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def _cmd_info(args: argparse.Namespace) -> None:
    from blueview import document, export

    data = document.info(args.file)

    if args.format == "json":
        print(json.dumps(data, indent=2, default=str))
        return

    # Table output
    print(f"File:          {data['path']}")
    print(f"Pages:         {data['page_count']}")
    print(f"Total markups: {data['total_markups']}")
    if data["title"]:
        print(f"Title:         {data['title']}")
    if data["author"]:
        print(f"Author:        {data['author']}")
    print()
    print(f"{'Page':<8} {'Label':<12} {'Width (pt)':<12} {'Height (pt)':<12} {'Rot':<5} {'Markups'}")
    print("-" * 60)
    for p in data["pages"]:
        print(f"{p['index']:<8} {p['label']:<12} {p['width_pt']:<12} {p['height_pt']:<12} {p['rotation']:<5} {p['markup_count']}")

    if data["measurement_scales"]:
        print()
        print("Measurement scales:")
        for s in data["measurement_scales"]:
            print(f"  Page {s['page_index']}: {s}")


def _cmd_markups(args: argparse.Namespace) -> None:
    from blueview import markups, export

    if args.format == "xlsx" and not args.output:
        print("Error: --output is required for xlsx format.", file=sys.stderr)
        sys.exit(1)

    rows = markups.extract(
        args.file,
        page_filter=args.page,
        status_filter=args.status,
        author_filter=args.author,
        subject_filter=args.subject,
        columns=args.columns,
    )

    if args.format == "json":
        export.to_json(rows, args.output)
    elif args.format == "csv":
        export.to_csv(rows, args.output)
    elif args.format == "xlsx":
        export.to_xlsx(rows, args.output)
        print(f"Wrote {len(rows)} markups to {args.output}")
    else:
        export.to_table(rows)


def _cmd_spaces(args: argparse.Namespace) -> None:
    from blueview import spaces, export

    data = spaces.extract(args.file)

    if args.format == "json":
        print(json.dumps(data, indent=2, default=str))
        return

    if not data:
        print("(no Bluebeam Spaces found)")
        return

    export.to_table(data)


def _cmd_text(args: argparse.Namespace) -> None:
    from blueview import text

    pages = text.extract(args.file, page_filter=args.page)
    for page in pages:
        print(f"── Page {page['page_index']} ({page['page_label']}) ──")
        print(page["text"])


def _cmd_search(args: argparse.Namespace) -> None:
    from blueview import text, export

    results = text.search(args.file, args.pattern, page_filter=args.page)

    if args.format == "json":
        print(json.dumps(results, indent=2))
        return

    if not results:
        print("(no matches)")
        return

    export.to_table(results)


def _cmd_render(args: argparse.Namespace) -> None:
    from blueview import render

    out = render.render_page(
        args.file,
        args.page,
        args.output,
        dpi=args.dpi,
        include_annots=args.annots,
    )
    print(f"Rendered page {args.page} to {out}")
