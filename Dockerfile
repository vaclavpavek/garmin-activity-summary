FROM python:3.11-slim

# Install fonts for image generation
RUN apt-get update && apt-get install -y \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY generate_summary.py .

# Create data directory
RUN mkdir -p /app/data

# Run the application
CMD ["python", "generate_summary.py"]
