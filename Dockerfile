# Multi-stage Dockerfile for QR Bot
# Optimized for production with security and performance

# Build stage
FROM python:3.9-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    libtiff-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtk8.6 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxss1 \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies
COPY requirements.txt requirements_phase2_3_4.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r requirements_phase2_3_4.txt

# Production stage
FROM python:3.9-slim

# Create non-root user for security
RUN groupadd -r qrbot && useradd -r -g qrbot qrbot

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libjpeg62-turbo \
    libpng16-16 \
    libwebp6 \
    libtiff5 \
    libfreetype6 \
    liblcms2-2 \
    libopenjp2-7 \
    libtk8.6 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxss1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app"

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create application directories
WORKDIR /app
RUN mkdir -p /app/logs /app/qr_codes /app/temp && \
    chown -R qrbot:qrbot /app

# Copy application code
COPY --chown=qrbot:qrbot . .

# Set permissions
RUN chmod +x /app/docker-entrypoint.sh

# Switch to non-root user
USER qrbot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose ports
EXPOSE 8000 5000

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command
CMD ["python", "bot.py"]
