FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Set Python path to include app directory
ENV PYTHONPATH=/app

# These are default values that will be overridden by runtime environment variables
ENV AIRTABLE_API_KEY=""
ENV AIRTABLE_BASE_ID=""
ENV AIRTABLE_TABLE_NAME=""

# Expose the port the app runs on
EXPOSE 8002

# Command to run the application
CMD ["python", "-m", "app.api"] 
