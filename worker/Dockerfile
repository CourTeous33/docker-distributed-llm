FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    python3 \
    python3-pip \
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone distributed-llama
RUN git clone https://github.com/b4rtaz/distributed-llama.git
WORKDIR /app/distributed-llama

# Build the distributed-llama binaries
RUN make dllama

# Install Python dependencies for Flask API
WORKDIR /app
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Copy the worker wrapper and other necessary files
COPY worker.py /app/
COPY worker_wrapper.py /app/

# Set environment variables
ENV WORKER_ID=1
ENV DLLAMA_WORKER_PORT=9998
ENV DLLAMA_API_PORT=5000

# Expose ports (Flask API port and dllama worker port)
EXPOSE 5000
EXPOSE 9998

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/status || exit 1

# Set entrypoint
CMD ["python3", "/app/worker_wrapper.py"]