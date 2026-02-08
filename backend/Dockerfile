FROM docker.m.daocloud.io/library/python:3.11-slim

WORKDIR /app

# Replace apt sources with Aliyun mirrors for faster downloads
RUN sed -i 's|http://[^ ]*\.debian\.org|http://mirrors.cloud.aliyuncs.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://[^ ]*\.debian\.org|http://mirrors.cloud.aliyuncs.com|g' /etc/apt/sources.list 2>/dev/null || true

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
