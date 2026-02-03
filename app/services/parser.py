import tempfile
import os
import shutil
from pathlib import Path
import asyncio
from functools import partial
from datetime import datetime
import io

from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

# MarkItDown for Office formats
from markitdown import MarkItDown

# Output directory for saved markdown files
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _table_to_markdown(table) -> str:
    """Convert a PyMuPDF table to markdown format."""
    data = table.extract()
    if not data or not data[0]:
        return ""

    md_lines = []
    # Header row
    header = data[0]
    header_cells = [str(cell) if cell else "" for cell in header]
    md_lines.append("| " + " | ".join(header_cells) + " |")
    md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")

    # Data rows
    for row in data[1:]:
        cells = [str(cell) if cell else "" for cell in row]
        # Escape pipe characters in cell content
        cells = [c.replace("|", "\\|").replace("\n", " ") for c in cells]
        md_lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(md_lines)


def _list_table_to_markdown(data: list) -> str:
    """Convert a list-based table (from pdfplumber) to markdown format."""
    if not data or not data[0]:
        return ""

    # Filter out empty rows
    data = [row for row in data if row and any(cell for cell in row)]
    if not data:
        return ""

    md_lines = []
    # Determine column count from the widest row
    max_cols = max(len(row) for row in data)

    # Header row (first row)
    header = data[0]
    header_cells = []
    for i in range(max_cols):
        cell = header[i] if i < len(header) else ""
        cell = str(cell) if cell else ""
        cell = cell.replace("|", "\\|").replace("\n", " ").strip()
        header_cells.append(cell)

    md_lines.append("| " + " | ".join(header_cells) + " |")
    md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    # Data rows
    for row in data[1:]:
        cells = []
        for i in range(max_cols):
            cell = row[i] if i < len(row) else ""
            cell = str(cell) if cell else ""
            cell = cell.replace("|", "\\|").replace("\n", " ").strip()
            cells.append(cell)
        md_lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(md_lines)


async def parse_pdf(content: bytes, filename: str, lang: str = "en") -> dict:
    """
    Parse PDF content using MineRU.

    Args:
        content: PDF file content as bytes
        filename: Original filename
        lang: Language for OCR (e.g., 'en', 'korean', 'ch', 'japan')

    Returns:
        Dictionary containing extracted content
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_parse_pdf_sync, content, filename, lang))


def _parse_pdf_sync(content: bytes, filename: str, lang: str = "en") -> dict:
    """Synchronous PDF parsing implementation."""
    import fitz  # PyMuPDF

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / filename
        output_dir = temp_path / "output"
        output_dir.mkdir(exist_ok=True)

        # Write PDF to temp file
        input_path.write_bytes(content)

        # Initialize MineRU components
        image_dir = output_dir / "images"
        image_dir.mkdir(exist_ok=True)

        image_writer = FileBasedDataWriter(str(image_dir))
        md_writer = FileBasedDataWriter(str(output_dir))
        reader = FileBasedDataReader("")

        # Read and process the PDF
        pdf_bytes = reader.read(str(input_path))

        # Create dataset with language parameter
        dataset = PymuDocDataset(pdf_bytes, lang=lang)

        # Try magic-pdf with full analysis, fall back to basic PyMuPDF extraction
        try:
            infer_result = doc_analyze(dataset, lang=lang)
            if dataset.classify() == "ocr":
                result = dataset.apply(infer_result, image_writer, md_writer, "ocr")
            else:
                result = dataset.apply(infer_result, image_writer, md_writer, "txt")
            md_content = result.get_markdown()
            content_list = result.get_content_list()
        except FileNotFoundError as e:
            # Fallback: use pdfplumber for enhanced table extraction
            print(f"Warning: Using fallback text extraction due to missing model: {e}")
            import pdfplumber

            md_content = ""
            content_list = []

            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_content = f"## Page {page_num + 1}\n\n"
                    page_data = {"page": page_num + 1, "text": "", "tables": []}

                    # Extract tables with pdfplumber (better detection)
                    # Use "lines" strategy for more accurate table detection (fewer false positives)
                    tables = page.extract_tables(table_settings={
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "snap_tolerance": 5,
                        "join_tolerance": 5,
                        "edge_min_length": 10,
                        "min_words_vertical": 3,
                        "min_words_horizontal": 1,
                    })

                    # If no tables found with lines strategy, try text strategy for borderless tables
                    if not tables:
                        tables = page.extract_tables(table_settings={
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text",
                            "snap_tolerance": 5,
                            "join_tolerance": 5,
                            "min_words_vertical": 3,
                            "min_words_horizontal": 2,
                        })

                    table_bboxes = []
                    if tables:
                        for table_idx, table_data in enumerate(tables):
                            if table_data and len(table_data) > 0:
                                # Convert table to markdown
                                table_md = _list_table_to_markdown(table_data)
                                if table_md:
                                    page_content += f"### Table {table_idx + 1}\n\n{table_md}\n\n"
                                    page_data["tables"].append({
                                        "index": table_idx + 1,
                                        "markdown": table_md,
                                        "data": table_data
                                    })

                    # Also try to find tables using find_tables for better bbox detection
                    found_tables = page.find_tables(table_settings={
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                    })
                    for t in found_tables:
                        table_bboxes.append(t.bbox)

                    # Extract text excluding table areas
                    if table_bboxes:
                        # Filter out text within table regions
                        chars = page.chars
                        filtered_chars = []
                        for char in chars:
                            in_table = False
                            for bbox in table_bboxes:
                                if (bbox[0] <= char['x0'] <= bbox[2] and
                                    bbox[1] <= char['top'] <= bbox[3]):
                                    in_table = True
                                    break
                            if not in_table:
                                filtered_chars.append(char)
                        # Recreate text from filtered chars
                        if filtered_chars:
                            text = pdfplumber.utils.extract_text(filtered_chars)
                        else:
                            text = ""
                    else:
                        text = page.extract_text() or ""

                    if text.strip():
                        page_content += text + "\n\n"
                        page_data["text"] = text.strip()

                    md_content += page_content
                    content_list.append(page_data)

        # Generate output filename with timestamp
        base_name = Path(filename).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_filename = f"{base_name}_{timestamp}.md"
        md_output_path = OUTPUT_DIR / md_filename

        # Save markdown file
        md_output_path.write_text(md_content, encoding="utf-8")

        # Create images subdirectory and copy images
        images = []
        if image_dir.exists():
            images_output_dir = OUTPUT_DIR / f"{base_name}_{timestamp}_images"
            images_output_dir.mkdir(exist_ok=True)
            for img_file in image_dir.iterdir():
                shutil.copy(img_file, images_output_dir / img_file.name)
                images.append(img_file.name)

        return {
            "filename": filename,
            "markdown": md_content,
            "markdown_file": str(md_output_path),
            "content_list": content_list,
            "images": images,
            "page_count": len(dataset)
        }


async def parse_image(content: bytes, filename: str) -> dict:
    """
    Parse image content using MineRU OCR.

    Args:
        content: Image file content as bytes
        filename: Original filename

    Returns:
        Dictionary containing extracted content
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_parse_image_sync, content, filename))


def _parse_image_sync(content: bytes, filename: str) -> dict:
    """Synchronous image parsing implementation."""
    from PIL import Image
    import io

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / filename
        output_dir = temp_path / "output"
        output_dir.mkdir(exist_ok=True)

        # Write image to temp file
        input_path.write_bytes(content)

        # Get image info
        img = Image.open(io.BytesIO(content))
        width, height = img.size

        # For single images, use OCR pipeline
        image_writer = FileBasedDataWriter(str(output_dir))
        md_writer = FileBasedDataWriter(str(output_dir))

        # Use MineRU's image OCR capabilities
        from magic_pdf.pipe.OCRPipe import OCRPipe
        from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter

        disk_rw = DiskReaderWriter(str(temp_path))

        # Process image through OCR
        pipe = OCRPipe(content, [], image_writer, md_writer)
        pipe.pipe_classify()
        pipe.pipe_analyze()
        pipe.pipe_parse()

        md_content = pipe.pipe_mk_markdown()

        # Generate output filename with timestamp
        base_name = Path(filename).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_filename = f"{base_name}_{timestamp}.md"
        md_output_path = OUTPUT_DIR / md_filename

        # Save markdown file
        md_output_path.write_text(md_content, encoding="utf-8")

        return {
            "filename": filename,
            "markdown": md_content,
            "markdown_file": str(md_output_path),
            "image_size": {"width": width, "height": height},
            "format": img.format
        }


# Initialize MarkItDown converter (singleton)
_markitdown = MarkItDown()


async def parse_docx(content: bytes, filename: str) -> dict:
    """
    Parse DOCX content using MarkItDown.

    Args:
        content: DOCX file content as bytes
        filename: Original filename

    Returns:
        Dictionary containing extracted content
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_parse_office_sync, content, filename, "docx"))


def _parse_office_sync(content: bytes, filename: str, file_type: str) -> dict:
    """
    Unified Office file parsing using MarkItDown.

    Supports DOCX, PPTX, and XLSX formats.
    """
    with tempfile.NamedTemporaryFile(suffix=f".{file_type}", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Convert using MarkItDown
        result = _markitdown.convert(tmp_path)
        md_content = result.text_content

        # Generate output filename with timestamp
        base_name = Path(filename).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_filename = f"{base_name}_{timestamp}.md"
        md_output_path = OUTPUT_DIR / md_filename

        # Save markdown file
        md_output_path.write_text(md_content, encoding="utf-8")

        # Calculate basic stats
        word_count = len(md_content.split())

        return {
            "filename": filename,
            "markdown": md_content,
            "markdown_file": str(md_output_path),
            "word_count": word_count,
            "converter": "markitdown"
        }
    finally:
        # Clean up temp file
        os.unlink(tmp_path)


async def parse_pptx(content: bytes, filename: str) -> dict:
    """
    Parse PPTX content using MarkItDown.

    Args:
        content: PPTX file content as bytes
        filename: Original filename

    Returns:
        Dictionary containing extracted content
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_parse_office_sync, content, filename, "pptx"))


async def parse_xlsx(content: bytes, filename: str) -> dict:
    """
    Parse XLSX content using MarkItDown.

    Args:
        content: XLSX file content as bytes
        filename: Original filename

    Returns:
        Dictionary containing extracted content
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_parse_office_sync, content, filename, "xlsx"))
