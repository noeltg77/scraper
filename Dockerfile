FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps

# Copy the entire project
COPY . .

# Set Python path to include app directory
ENV PYTHONPATH=/app

# These are default values that will be overridden by runtime environment variables
ENV AIRTABLE_API_KEY=""
ENV AIRTABLE_BASE_ID=""
ENV AIRTABLE_TABLE_NAME=""

# Proxy and server configuration
ENV PORT=8002
ENV WORKERS=4
ENV TIMEOUT=120
ENV FORWARDED_ALLOW_IPS="*"
ENV PROXY_HEADERS=true

# Expose the port the app runs on
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Command to run the application
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8002", "--proxy-headers", "--forwarded-allow-ips", "*", "--workers", "4"] 
