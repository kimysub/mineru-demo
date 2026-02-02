from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional
import tempfile
import subprocess
import os
import glob
import json
import shutil

app = FastAPI(title="MinerU PDF Parser API")

# Persistent output directory
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Supported languages
SUPPORTED_LANGUAGES = [
    "ch", "ch_server", "ch_lite", "en", "korean", "japan",
    "chinese_cht", "ta", "te", "ka", "th", "el", "latin",
    "arabic", "east_slavic", "cyrillic", "devanagari"
]

@app.post("/parse/pdf")
async def parse_pdf(
    file: UploadFile = File(...),
    lang: Optional[str] = Form(default="korean", description="Language for OCR: korean, en, ch, japan, etc.")
):
    """Parse a PDF file and return the extracted content.

    Args:
        file: PDF file to parse
        lang: Language for OCR accuracy. Options: korean, en, ch, japan, etc.
              Default is 'korean' for Korean/English mixed documents.
    """

    # Validate language
    if lang not in SUPPORTED_LANGUAGES:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unsupported language: {lang}. Supported: {SUPPORTED_LANGUAGES}"}
        )

    # Create temp directory for input file
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save uploaded file
        input_path = os.path.join(tmpdir, file.filename)

        with open(input_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Run mineru (v2) with language option
        result = subprocess.run(
            ["mineru", "-p", input_path, "-o", OUTPUT_DIR, "-b", "pipeline", "-d", "mps", "-l", lang],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return JSONResponse(
                status_code=500,
                content={"error": result.stderr or "Failed to parse PDF", "stdout": result.stdout}
            )

        # Find output files for this PDF (based on filename without extension)
        base_name = os.path.splitext(file.filename)[0]
        pdf_output_dir = os.path.join(OUTPUT_DIR, base_name)

        output_content = {}

        # Find markdown files
        md_files = glob.glob(os.path.join(pdf_output_dir, "**/*.md"), recursive=True)
        for md_file in md_files:
            with open(md_file, "r", encoding="utf-8") as f:
                output_content["markdown"] = f.read()
                output_content["markdown_file"] = md_file
                break

        # Find JSON content list files
        json_files = glob.glob(os.path.join(pdf_output_dir, "**/*_content_list.json"), recursive=True)
        for json_file in json_files:
            with open(json_file, "r", encoding="utf-8") as f:
                output_content["content_list"] = json.load(f)
                break

        # List all generated files
        all_files = []
        if os.path.exists(pdf_output_dir):
            for root, dirs, files in os.walk(pdf_output_dir):
                for fname in files:
                    rel_path = os.path.relpath(os.path.join(root, fname), OUTPUT_DIR)
                    all_files.append(rel_path)
        output_content["generated_files"] = all_files

        return {
            "status": "success",
            "filename": file.filename,
            "output_dir": pdf_output_dir,
            "output": output_content
        }

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
