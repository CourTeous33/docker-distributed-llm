FROM ubuntu:22.04

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

WORKDIR /app

#COPY ../models/. /models/
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r /app/requirements.txt

RUN git clone https://github.com/b4rtaz/distributed-llama.git /app/distributed-llama
WORKDIR /app/distributed-llama
RUN make dllama && make dllama-api

WORKDIR /app
COPY . /app/

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
