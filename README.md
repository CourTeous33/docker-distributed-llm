# cs598-final-project
# Distributed Language Model System

## Prerequisites
- Docker
- Docker Compose

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

3. To run in detached mode (background):
   ```bash
   docker compose up -d
   ```

4. To stop the services:
   ```bash
   docker compose down
   ```

5. To view logs:
   ```bash
   docker compose logs -f
   ```

## Service Access
- Frontend: http://localhost
- Backend API: http://localhost:8000

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
