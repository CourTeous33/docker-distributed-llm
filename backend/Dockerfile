FROM ubuntu:22.04

# Install dependencies for distributed-llama (make sure these are comprehensive)
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

# Copy requirements first to leverage Docker caching
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Clone distributed-llama with explicit error checking
RUN git clone https://github.com/b4rtaz/distributed-llama.git /app/distributed-llama || \
    (echo "Failed to clone distributed-llama repository" && exit 1)

# Build the distributed-llama binaries with error checking
WORKDIR /app/distributed-llama
RUN make dllama || (echo "Failed to build dllama" && exit 1)
RUN make dllama-api || (echo "Failed to build dllama-api" && exit 1)
RUN ls -la # Debug: list files to verify binaries exist

# Return to app directory and copy the rest of the code
WORKDIR /app
COPY . /app/

# Expose the port your FastAPI app will run on
EXPOSE 8000

# Start the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]