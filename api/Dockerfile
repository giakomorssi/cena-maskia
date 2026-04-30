# Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN useradd -m -u 1000 appuser

# Copy Python dependencies from builder to appuser's home
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY . .

# Generate BAML client (before changing to non-root user)
ENV PYTHONPATH=/home/appuser/.local/lib/python3.12/site-packages
RUN /home/appuser/.local/bin/baml-cli generate

# Copy and make entrypoint script executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Change ownership
RUN chown -R appuser:appuser /app && \
    chown -R appuser:appuser /home/appuser/.local && \
    chown appuser:appuser /entrypoint.sh

# Switch to non-root user
USER appuser

# Make sure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH

# Expose port
EXPOSE 8000

# Use entrypoint script to run migrations and setup before starting the app
ENTRYPOINT ["/entrypoint.sh"]

# Run the application - use $PORT if set (Railway), otherwise default to 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]