FROM python:3.9-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the interactive model downloader script
COPY model_downloader.py /app/

# Set environment variables
ENV MODEL_NAME=""
ENV OUTPUT_DIR=/models

# Set up the interactive terminal
ENV PYTHONUNBUFFERED=1

# Run the interactive model downloader
CMD ["python3", "model_downloader.py", "--interactive"]