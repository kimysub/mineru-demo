FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    ffmpeg \
    git \
    build-essential \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies in three phases:
# 1. First install torch (required by detectron2's setup.py)
# 2. Then install other dependencies
# 3. Finally install detectron2 with --no-build-isolation (so it can find torch)
RUN pip install --no-cache-dir torch && \
    pip install --no-cache-dir $(grep -v -E '^#|detectron2' requirements.txt | tr '\n' ' ') && \
    pip install --no-cache-dir --no-build-isolation "detectron2 @ git+https://github.com/facebookresearch/detectron2.git"

# Copy application code
COPY . .

# Create output directory
RUN mkdir -p /app/output

# Copy MinerU config
COPY magic-pdf.json /root/magic-pdf.json

# Expose default port (can be overridden)
EXPOSE 8000

# Default command (host and port can be overridden via environment variables)
CMD ["sh", "-c", "uvicorn app.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}"]
