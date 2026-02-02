# MinerU Document Parser API Guide

A document parsing service that converts PDF, images, and Microsoft Office files to Markdown.

## Quick Start

### Using Docker Compose

```bash
# Default configuration (port 8000)
docker compose up -d

# Custom port
HOST_PORT=9000 docker compose up -d

# With .env file
cp .env.example .env
# Edit .env as needed
docker compose up -d
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | API server bind address |
| `API_PORT` | `8000` | API server port (inside container) |
| `HOST_PORT` | `8000` | Port exposed on host machine |

### Examples

```bash
# Run on port 3000
HOST_PORT=3000 docker compose up -d

# Run with all custom settings
API_HOST=0.0.0.0 API_PORT=8080 HOST_PORT=8080 docker compose up -d
```

---

## API Endpoints

### Health Check

Check if the service is running.

```
GET /health
```

**Response:**
```json
{
  "status": "healthy"
}
```

---

### Parse PDF

Extract content from PDF files using MinerU with OCR support.

```
POST /parse/pdf
```

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - PDF file

**Response:**
```json
{
  "filename": "document.pdf",
  "markdown": "# Document Title\n\nContent here...",
  "markdown_file": "/app/output/document_20240101_120000.md",
  "content_list": [...],
  "images": ["image_0.png", "image_1.png"],
  "page_count": 5
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/parse/pdf \
  -F "file=@document.pdf"
```

---

### Parse Image

Extract text from images using OCR.

```
POST /parse/image
```

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - Image file (PNG, JPG, JPEG, WEBP, BMP)

**Response:**
```json
{
  "filename": "screenshot.png",
  "markdown": "Extracted text content...",
  "markdown_file": "/app/output/screenshot_20240101_120000.md",
  "image_size": {"width": 1920, "height": 1080},
  "format": "PNG"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/parse/image \
  -F "file=@screenshot.png"
```

---

### Parse Word Document (DOCX)

Convert Word documents to Markdown using MarkItDown.

```
POST /parse/docx
```

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - DOCX file

**Response:**
```json
{
  "filename": "report.docx",
  "markdown": "# Report Title\n\nContent here...",
  "markdown_file": "/app/output/report_20240101_120000.md",
  "word_count": 1500,
  "converter": "markitdown"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/parse/docx \
  -F "file=@report.docx"
```

---

### Parse PowerPoint (PPTX)

Convert PowerPoint presentations to Markdown.

```
POST /parse/pptx
```

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - PPTX file

**Response:**
```json
{
  "filename": "presentation.pptx",
  "markdown": "<!-- Slide number: 1 -->\n# Slide Title\n\nBullet points...",
  "markdown_file": "/app/output/presentation_20240101_120000.md",
  "word_count": 500,
  "converter": "markitdown"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/parse/pptx \
  -F "file=@presentation.pptx"
```

---

### Parse Excel (XLSX)

Convert Excel spreadsheets to Markdown tables.

```
POST /parse/xlsx
```

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - XLSX file

**Response:**
```json
{
  "filename": "data.xlsx",
  "markdown": "## Sheet1\n| Col A | Col B |\n| --- | --- |\n| 1 | 2 |",
  "markdown_file": "/app/output/data_20240101_120000.md",
  "word_count": 100,
  "converter": "markitdown"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/parse/xlsx \
  -F "file=@data.xlsx"
```

---

### List Outputs

List all generated Markdown files.

```
GET /outputs
```

**Response:**
```json
{
  "files": [
    {
      "filename": "document_20240101_120000.md",
      "path": "/app/output/document_20240101_120000.md",
      "size": 2048,
      "download_url": "/outputs/document_20240101_120000.md"
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:8000/outputs
```

---

### Download Output File

Download a generated Markdown file.

```
GET /outputs/{filename}
```

**Example:**
```bash
curl -O http://localhost:8000/outputs/document_20240101_120000.md
```

---

## Response Fields

### Common Fields

| Field | Type | Description |
|-------|------|-------------|
| `filename` | string | Original uploaded filename |
| `markdown` | string | Extracted content in Markdown format |
| `markdown_file` | string | Path to saved Markdown file |

### PDF-specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `content_list` | array | Structured content with bounding boxes |
| `images` | array | List of extracted image filenames |
| `page_count` | integer | Number of pages in PDF |

### Office-specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `word_count` | integer | Approximate word count |
| `converter` | string | Converter used (`markitdown`) |

---

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message here"
}
```

### Common HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid file type) |
| 404 | File not found |
| 500 | Internal server error |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   FastAPI Server                     │
├─────────────────────────────────────────────────────┤
│  /parse/pdf, /parse/image  │  /parse/docx, pptx,   │
│         ↓                  │        xlsx            │
│      MinerU                │         ↓              │
│   (magic-pdf)              │     MarkItDown         │
│   - OCR support            │   - Office formats     │
│   - Layout analysis        │   - Simple conversion  │
│   - Image extraction       │                        │
└─────────────────────────────────────────────────────┘
                        ↓
              /app/output/*.md
```

---

## Development

### Run without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### View Logs

```bash
docker compose logs -f parser
```

### Rebuild Container

```bash
docker compose build --no-cache
docker compose up -d
```
