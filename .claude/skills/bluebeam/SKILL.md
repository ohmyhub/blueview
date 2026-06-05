# Bluebeam Revu PDF skill

Use this skill when the user wants to:
- Summarize, extract, or search Bluebeam Revu markups/comments from a PDF
- Export the Markups List to Excel, CSV, or JSON
- Read markup authors, statuses, subjects, custom columns, or measurement values
- List Bluebeam Spaces defined in a drawing
- Get document metadata (page sizes, page count, measurement scale) from a PDF
- Render a PDF page to an image so Claude can inspect it
- Search for text or a pattern within a PDF file

## CLI reference

The tool is a Python package. Invoke it via PowerShell using:

```powershell
python -m blueview.cli <subcommand> [options]
```

> **Note:** This runs against the system Python where `blueview` is installed (editable install
> in `C:\Users\kward\projects\blueview`). If the system Python is not on `PATH`, use:
> `& "C:\Users\kward\AppData\Local\Programs\Python\Python313\python.exe" -m blueview.cli ...`

### Subcommands

**`info FILE.pdf`** — page count, sizes (pts), rotation, markup count per page, measurement scales.
```powershell
python -m blueview.cli info "C:\path\to\drawing.pdf"
python -m blueview.cli info "C:\path\to\drawing.pdf" --format json
```

**`markups FILE.pdf`** — extract the full Markups List.
```powershell
# Default table view
python -m blueview.cli markups "drawing.pdf"

# Filter options (all accept multiple values, substring match):
#   --page N          0-based page index
#   --status pending  filter by status
#   --author "John"   filter by author
#   --subject Cloud   filter by markup type/subject

# Export formats:
python -m blueview.cli markups "drawing.pdf" --format csv --output markups.csv
python -m blueview.cli markups "drawing.pdf" --format json
python -m blueview.cli markups "drawing.pdf" --format xlsx --output markups.xlsx
```

**`spaces FILE.pdf`** — list Bluebeam Spaces.
```powershell
python -m blueview.cli spaces "drawing.pdf"
python -m blueview.cli spaces "drawing.pdf" --format json
```

**`text FILE.pdf`** — extract raw page text (useful for title block data, sheet numbers).
```powershell
python -m blueview.cli text "drawing.pdf"
python -m blueview.cli text "drawing.pdf" --page 0
```

**`search FILE.pdf "PATTERN"`** — search for text or a regex pattern, returns matches with bounding boxes.
```powershell
python -m blueview.cli search "drawing.pdf" "catch basin"
python -m blueview.cli search "drawing.pdf" "CB-\d+" --format json
```

**`render FILE.pdf --page N --output out.png`** — render a page to PNG so Claude can inspect it with the Read tool.
```powershell
python -m blueview.cli render "drawing.pdf" --page 0 --output page0.png --dpi 150
# After rendering, use Read to view the image:
# Read("C:\path\to\page0.png")
```

## Common workflows

### Summarize markups in a drawing
```powershell
python -m blueview.cli info "drawing.pdf"
python -m blueview.cli markups "drawing.pdf" --format table
```

### Export to Excel for the user
```powershell
python -m blueview.cli markups "drawing.pdf" --format xlsx --output "drawing_markups.xlsx"
```

### Find all markups with a specific status
```powershell
python -m blueview.cli markups "drawing.pdf" --status "pending" --status "in review"
```

### Inspect a drawing visually
```powershell
python -m blueview.cli render "drawing.pdf" --page 0 --output "C:\Temp\page0.png" --dpi 150
# Then: Read("C:\Temp\page0.png")
```

### Get markup counts by author or subject
Run `markups --format json`, then summarize the JSON.

## Notes
- Standard annotation fields (author, subject, contents, color, date, geometry) are always available.
- Bluebeam-private fields (status, custom columns, spaces, measurement values) require the PDF to
  have been authored in Bluebeam Revu. They are absent from generic PDFs.
- Write operations are not supported. This tool is read-only.
- If the package isn't installed yet: `python -m pip install -e C:\Users\kward\projects\blueview`
