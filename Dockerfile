# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Install system dependencies and LaTeX in a single layer with caching
# This layer only rebuilds if system packages change
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-lang-english \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
# This layer only rebuilds if requirements.txt changes
COPY requirements.txt .

# Install Python dependencies with pip cache mount
# Cache persists across builds, speeding up reinstalls
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy static files that rarely change (better cache hits)
# These layers rebuild less frequently
COPY latex/ latex/
COPY templates/ templates/
COPY static/ static/

# Copy application code last (changes most frequently)
# Only this layer rebuilds when code changes
COPY app.py .
COPY create_form.py .
COPY gemini_ai.py .

# Create necessary directories
RUN mkdir -p /tmp/uploads /tmp/outputs

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Run the application
CMD ["python", "app.py"]
