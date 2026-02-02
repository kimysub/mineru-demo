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

        # Analyze document structure with language parameter
        infer_result = doc_analyze(dataset, lang=lang)

        # Extract content based on classification
        if dataset.classify() == "ocr":
            result = dataset.apply(infer_result, image_writer, md_writer, "ocr")
        else:
            result = dataset.apply(infer_result, image_writer, md_writer, "txt")

        # Get markdown content
        md_content = result.get_markdown()

        # Get content list (structured data)
        content_list = result.get_content_list()

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
