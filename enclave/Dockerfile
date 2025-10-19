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
RUN mkdir -p ./frontend/dist

# Copy backend source code
COPY --chown=lottery:lottery main.py /app/
COPY --chown=lottery:lottery web_server.py /app/
COPY --chown=lottery:lottery blockchain/ /app/blockchain/
COPY --chown=lottery:lottery lottery/ /app/lottery/
COPY --chown=lottery:lottery contracts/ /app/contracts/
COPY --chown=lottery:lottery utils/ /app/utils/
COPY --chown=lottery:lottery aws_nsm_interface/ /app/aws_nsm_interface/
COPY --chown=lottery:lottery lottery.conf /app/lottery.conf

# Copy only the compiled frontend assets (not source)
COPY --chown=lottery:lottery frontend/dist/ /app/frontend/dist/

# Expose port
EXPOSE 6080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:6080/api/health || exit 1

# Default command
CMD ["python", "/app/main.py"]