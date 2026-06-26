# Use official Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir \
    django \
    reportlab \
    openpyxl \
    daphne \
    channels \
    channels-redis \
    celery \
    redis \
    psutil \
    boto3 \
    django-storages \
    requests

# Copy project files
COPY . /app/

# Expose port
EXPOSE 8000

# Run django server
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "smartspend_project.asgi:application"]
