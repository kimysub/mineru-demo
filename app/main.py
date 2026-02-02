from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import tempfile
import os
from pathlib import Path

from app.services.parser import parse_pdf, parse_image, parse_docx, parse_pptx, parse_xlsx, OUTPUT_DIR

# Supported languages for OCR
SUPPORTED_LANGUAGES = [
    "en", "ch", "korean", "japan", "chinese_cht", "ta", "te", "ka",
    "th", "el", "latin", "arabic", "cyrillic", "devanagari"
]

app = FastAPI(
    title="MineRU Document Parser",
    description="PDF, Image, and MS Office document parsing service using MineRU",
    version="1.1.0"
)

# Mount static files for output directory
app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="files")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/parse/pdf")
async def parse_pdf_endpoint(
    file: UploadFile = File(...),
    lang: Optional[str] = Form(default="en", description="Language for OCR: en, korean, ch, japan, etc.")
):
    """
    Parse a PDF file and extract content.

    Args:
        file: PDF file to parse
        lang: Language for OCR accuracy (default: en)

    Returns:
        Extracted content from the PDF
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {lang}. Supported: {SUPPORTED_LANGUAGES}"
        )

    try:
        content = await file.read()
        result = await parse_pdf(content, file.filename, lang=lang)
        return JSONResponse(content=result)
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)


@app.post("/parse/image")
async def parse_image_endpoint(file: UploadFile = File(...)):
    """
    Parse an image file and extract content.

    Args:
        file: Image file to parse (PNG, JPG, JPEG)

    Returns:
        Extracted content from the image
    """
    allowed_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"File must be an image ({', '.join(allowed_extensions)})"
        )

    try:
        content = await file.read()
        result = await parse_image(content, file.filename)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse/docx")
async def parse_docx_endpoint(file: UploadFile = File(...)):
    """
    Parse a Word document (DOCX) and extract content.

    Args:
        file: DOCX file to parse

    Returns:
        Extracted content including text, tables, and images
    """
    if not file.filename.lower().endswith('.docx'):
        raise HTTPException(status_code=400, detail="File must be a DOCX")

    try:
        content = await file.read()
        result = await parse_docx(content, file.filename)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse/pptx")
async def parse_pptx_endpoint(file: UploadFile = File(...)):
    """
    Parse a PowerPoint presentation (PPTX) and extract content.

    Args:
        file: PPTX file to parse

    Returns:
        Extracted content including text, tables, and images from slides
    """
    if not file.filename.lower().endswith('.pptx'):
        raise HTTPException(status_code=400, detail="File must be a PPTX")

    try:
        content = await file.read()
        result = await parse_pptx(content, file.filename)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse/xlsx")
async def parse_xlsx_endpoint(file: UploadFile = File(...)):
    """
    Parse an Excel spreadsheet (XLSX) and extract content.

    Args:
        file: XLSX file to parse

    Returns:
        Extracted content with all sheets as markdown tables
    """
    if not file.filename.lower().endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="File must be an XLSX")

    try:
        content = await file.read()
        result = await parse_xlsx(content, file.filename)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/outputs")
async def list_outputs():
    """List all generated markdown files."""
    files = []
    for f in OUTPUT_DIR.glob("*.md"):
        files.append({
            "filename": f.name,
            "path": str(f),
            "size": f.stat().st_size,
            "download_url": f"/outputs/{f.name}"
        })
    return {"files": sorted(files, key=lambda x: x["filename"], reverse=True)}


@app.get("/outputs/{filename}")
async def download_output(filename: str):
    """Download a generated markdown file."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="text/markdown"
    )
