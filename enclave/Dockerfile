# Main Python application
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user early to avoid permission issues
RUN groupadd -r lottery && useradd -r -g lottery lottery -m

# Set working directory and change ownership
WORKDIR /app
RUN chown lottery:lottery /app

# Copy requirements first for better caching
COPY --chown=lottery:lottery requirements.txt .

# Install Python dependencies as root for system-wide installation
RUN pip install --no-cache-dir -r requirements.txt

# Switch to non-root user for subsequent operations
USER lottery

# Create necessary directories
RUN mkdir -p ./src/frontend/dist ./src/blockchain/contracts/compiled

# Copy backend source code
COPY --chown=lottery:lottery src/main.py /app/src/
COPY --chown=lottery:lottery src/web_server.py /app/src/
COPY --chown=lottery:lottery src/blockchain/ /app/src/blockchain/
COPY --chown=lottery:lottery src/lottery/ /app/src/lottery/
COPY --chown=lottery:lottery src/utils/ /app/src/utils/

# Copy only the compiled frontend assets (not source)
COPY --chown=lottery:lottery src/frontend/dist/ /app/src/frontend/dist/

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/api/health || exit 1

# Default command
CMD ["python", "src/main.py"]