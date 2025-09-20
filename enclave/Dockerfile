# Main Python application
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ ./src/

# Create necessary directories
RUN mkdir -p ./src/frontend/dist
RUN mkdir -p ./src/blockchain/contracts/compiled

# Copy smart contracts
COPY src/blockchain/contracts/ ./src/blockchain/contracts/

# Create non-root user for security
RUN groupadd -r lottery && useradd -r -g lottery lottery
RUN chown -R lottery:lottery /app
USER lottery

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/api/health || exit 1

# Default command
CMD ["python", "src/main.py"]