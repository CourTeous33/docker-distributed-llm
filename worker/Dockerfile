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

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt

# Clone and build distributed-llama
RUN git clone https://github.com/b4rtaz/distributed-llama.git /app/distributed-llama
WORKDIR /app/distributed-llama
RUN make dllama
WORKDIR /app

# Copy worker files
COPY . /app/

# Expose ports
EXPOSE 5000
EXPOSE 9998

# Start the Flask server
CMD ["python3", "worker_wrapper.py"]