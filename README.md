# cs598-final-project
# Simulated Distributed Language Model System

Containerized version of [b4rtaz's dllama repo](https://github.com/b4rtaz/distributed-llama). Made for CS598: FLA, Spring 2025. 

## Prerequisites
- Docker
- Docker Compose
- Python3
- C++ compiler

**NOTE: You need to run the file `model_downloader.py` in `model-downloader/` to ensure there is a model included in `/models` so that it can be copied over to the volume of the root worker (backend). For reference, for the 1B model, the structure should be:

`models/`
-- `llama3_2_1b_instruct_q40/...`

This means the backend needs to have enough memory for the modelfile, tokenizer, etc. 

Additionally, swapping models and number workers means you need to change the `config.py` variables in `backend/` (to point to the correct additional workers, model path, tokenizer path).

To modify the ranges of randomized latency generation, we provide `LATENCY_MIN` and `LATENCY_MAX` in `backend/config.py`. 

TODO: Move these notes to the setup / running instructions to be more clear. 

## Setup and Running Instructions

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd cs598-final-project
   ```

2. Build and start the containers:
   ```bash
   docker compose up --build
   ```

3. To stop the services:
   ```bash
   docker compose down
   ```

4. To view logs:
   ```bash
   docker compose logs -f
   ```

## Service Access
- Frontend: http://localhost:3001
<!-- - Backend API: http://localhost:8000 -->

## Troubleshooting

- If you encounter permission issues, try running the commands with sudo
- To rebuild a specific service:
  ```bash
  docker compose build <service-name>
  ```
- To restart a specific service:
  ```bash
  docker compose restart <service-name>
  ```

## Development

To make changes during development:
1. Modify the source code
2. Rebuild the affected service:
   ```bash
   docker compose up --build <service-name>
   ```
