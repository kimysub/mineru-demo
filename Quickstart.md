# MinerU Document Parsing - Quickstart

## Installation

```bash
pip install mineru
pip install fastapi uvicorn python-multipart
pip install python-docx python-pptx openpyxl
```

## Method 1: CLI (Direct)

```bash
# Parse Korean PDF
mineru -p your_document.pdf -o ./output -b pipeline -d mps -l korean

# Parse Korean image (PNG/JPG)
mineru -p your_image.png -o ./output -b pipeline -d mps -l korean
```

### Options
| Flag | Description |
|------|-------------|
| `-p` | Input file path |
| `-o` | Output directory |
| `-b` | Backend: `pipeline`, `vlm-auto-engine`, `hybrid-auto-engine` |
| `-d` | Device: `cpu`, `cuda`, `mps` (Apple Silicon) |
| `-l` | Language: `korean` |

## Method 2: API Server

### Start Server
```bash
python server.py
```

Server runs at http://localhost:8000

### Parse PDF
```bash
curl -X POST "http://localhost:8000/parse/pdf" \
  -F "file=@your_document.pdf"
```

### Parse Image (PNG/JPG)
```bash
curl -X POST "http://localhost:8000/parse/image" \
  -F "file=@your_image.png"
```

### Parse Word Document (DOCX)
```bash
curl -X POST "http://localhost:8000/parse/docx" \
  -F "file=@your_document.docx"
```

### Parse PowerPoint (PPTX)
```bash
curl -X POST "http://localhost:8000/parse/pptx" \
  -F "file=@your_presentation.pptx"
```

### Parse Excel (XLSX)
```bash
curl -X POST "http://localhost:8000/parse/xlsx" \
  -F "file=@your_spreadsheet.xlsx"
```

### Response Examples

**PDF/Image Response:**
```json
{
  "filename": "document.pdf",
  "markdown": "# Extracted content...",
  "markdown_file": "./output/document_20240129_143022.md",
  "images": [...],
  "page_count": 5
}
```

**DOCX Response:**
```json
{
  "filename": "document.docx",
  "markdown": "# Extracted content...",
  "markdown_file": "./output/document_20240129_143022.md",
  "images": [...],
  "word_count": 1500,
  "paragraph_count": 45
}
```

**PPTX Response:**
```json
{
  "filename": "presentation.pptx",
  "markdown": "## Slide 1\n...",
  "markdown_file": "./output/presentation_20240129_143022.md",
  "images": [...],
  "slide_count": 10
}
```

**XLSX Response:**
```json
{
  "filename": "spreadsheet.xlsx",
  "markdown": "## Sheet: Sheet1\n| Col1 | Col2 |...",
  "markdown_file": "./output/spreadsheet_20240129_143022.md",
  "sheet_names": ["Sheet1", "Sheet2"],
  "sheet_count": 2
}
```

## Output Files

Generated in `./output/`:

| File | Description |
|------|-------------|
| `*_TIMESTAMP.md` | Extracted text in Markdown format |
| `*_TIMESTAMP_images/` | Extracted images (if any) |

## Supported Formats

| Format | Endpoint | Features |
|--------|----------|----------|
| PDF | `/parse/pdf` | Full OCR, tables, images |
| Image | `/parse/image` | OCR text extraction |
| DOCX | `/parse/docx` | Text, headings, tables, images |
| PPTX | `/parse/pptx` | Slides, bullet points, tables, images |
| XLSX | `/parse/xlsx` | All sheets as markdown tables |

## Tips

1. **Scanned documents**: MinerU auto-detects and uses OCR for PDFs/images
2. **Apple Silicon**: Use `-d mps` for faster CLI processing
3. **Large files**: Processing may take time; check `./output` for results
4. **MS Office files**: Extracts embedded images to `*_images/` folder

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
