# Project Akka Dockerfile
# Targeting NVIDIA Jetson Orin Nano

# Base image for Jetson with Python support
FROM dustynv/jetson-inference:r36.2.0

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Set working directory
WORKDIR /app

# Install Python 3.12 if not present (or use system Python)
# Note: The base image may already include Python 3.10/3.11
# Adjust as needed based on actual base image contents
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY config/ ./config/
COPY data/ ./data/
COPY src/ ./src/

# Create logs directory
RUN mkdir -p logs

# Expose the API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the FastAPI application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
