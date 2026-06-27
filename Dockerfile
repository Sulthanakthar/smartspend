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
                COPY requirements.txt /app/
                RUN pip install --no-cache-dir -r requirements.txt

                # Copy project files
                COPY . /app/

                # Make entrypoint script executable
                RUN chmod +x /app/entrypoint.sh

                # Expose port
                EXPOSE 8000

                # Run entrypoint script
                ENTRYPOINT ["/app/entrypoint.sh"]
                
