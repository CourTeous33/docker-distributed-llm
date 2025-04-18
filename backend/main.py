"""
Enhanced main.py for CS598 project with distributed-llama integration.
This file extends the original FastAPI backend to integrate with
distributed-llama for distributed inference across worker nodes.
"""

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
import os
import asyncio
import json
from typing import List, Dict, Any, Optional
import logging
import time
import random
from pydantic import BaseModel
from config import LATENCY_MIN, LATENCY_MAX, MODEL_PATH, TOKENIZER_PATH, WORKER_URLS

from dllama_manager import DistributedLlamaManager

import docker 
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="LLM Backend Service with Distributed-Llama")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

# Initialize manager
dllama_manager = DistributedLlamaManager(
    model_path=MODEL_PATH,
    tokenizer_path=TOKENIZER_PATH,
    worker_urls=WORKER_URLS
)

client = httpx.AsyncClient(timeout=60.0)

docker_client = docker.from_env()
class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 256

class WorkerStatus(BaseModel):
    worker_id: int
    status: str
    is_available: bool

class SystemStatus(BaseModel):
    server_status: str
    total_workers: int
    available_workers: int
    model_path: str
    tokenizer_path: str

@app.get("/workers/status")
async def get_workers_status():
    """Get status of all workers"""
    try:
        status = await dllama_manager.check_worker_status()
        return [WorkerStatus(
            worker_id=k,
            status=v.get("status", "unknown"),
            is_available=v.get("is_available", False)
        ) for k, v in status.items()]
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/system/status")
async def get_system_status():
    """Get overall system status"""
    try:
        info = await dllama_manager.get_system_info()
        return SystemStatus(
            server_status=info["server_status"],
            total_workers=info["total_workers"],
            available_workers=info["available_workers"],
            model_path=info["model_path"],
            tokenizer_path=info["tokenizer_path"]
        )
    except Exception as e:
        raise HTTPException(500, str(e))

def start_docker_monitoring():
    """Start Docker stats collection in a background thread"""
    def monitor():
        logger.info("Starting Docker stats monitoring")
        client = docker.from_env()
        containers = ["backend", "worker1", "worker2", "worker3"]
        
        while not app.state.monitoring_stopped.is_set():
            try:
                for name in containers:
                    container = client.containers.get(name)
                    stats = container.stats(stream=False)
                    
                    # CPU calculation
                    cpu_stats = stats["cpu_stats"]
                    precpu_stats = stats["precpu_stats"]
                    cpu_delta = cpu_stats["cpu_usage"]["total_usage"] - precpu_stats["cpu_usage"]["total_usage"]
                    system_delta = cpu_stats["system_cpu_usage"] - precpu_stats["system_cpu_usage"]
                    
                    cpu_percent = 0.0
                    if system_delta > 0 and cpu_delta > 0:
                        cpu_cores = len(cpu_stats["cpu_usage"].get("percpu_usage", [1]))
                        cpu_percent = (cpu_delta / system_delta) * cpu_cores * 100
                    
                    # Memory calculation
                    mem_stats = stats["memory_stats"]
                    mem_usage = mem_stats.get("usage", 0)
                    mem_limit = mem_stats.get("limit", 1)
                    mem_percent = (mem_usage / mem_limit) * 100 if mem_limit else 0
                    
                    logger.info(
                        f"Docker stats [{name}] "
                        f"CPU: {cpu_percent:.2f}% | "
                        f"Mem: {mem_usage/1024/1024:.2f}MB ({mem_percent:.2f}%)"
                    )
                
                time.sleep(0.1)  # Collect every 100ms
                
            except Exception as e:
                logger.error(f"Docker monitoring error: {str(e)}")
                break

    # Start monitoring thread
    app.state.monitoring_stopped = threading.Event()
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

# Stream text generation up and handle simulated network
@app.get("/stream")
async def generate_text(
    prompt: str = Query(..., description="Prompt for generation"),
    max_tokens: int = Query(256, gt=0, le=1024, description="Maximum tokens to generate")
):
    """Stream predicted text tokens with proper max_tokens handling"""
    logger.info(f"Starting generation with {max_tokens} max tokens")
    async def generate_stream():
        total_delay = 0.0
        first_token = True
        start_time = time.time() 
        ttft = 0.0

        try:
            start_docker_monitoring()
            async for line in dllama_manager.generate_text(prompt=prompt, max_tokens=max_tokens):
                if "Pred" in line:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        predicted_text = parts[-1].strip()
                        if predicted_text:
                            # TTFT logic
                            if first_token:
                                first_token = False
                                ttft = time.time() - start_time
                                logger.info(f"TTFT: {ttft:.2f}s")

                            # Add some delay to simulate network when we yield the text up to the frontend
                            delay = random.uniform(LATENCY_MIN, LATENCY_MAX) # defined in config.py for simpler modification
                            # logger.info(f"Simulating delay: {delay:.2f}s")
                            await asyncio.sleep(delay)
                            total_delay += delay 

                            logger.debug(f"Yielding token: {predicted_text}")
                            yield f"data: {json.dumps({'text': predicted_text})}\n\n"
            
            # Stop monitoring after generation completes
            app.state.monitoring_stopped.set()  
            # Generation is done, send metrics back to frontend              
            logger.info(f"Generation completed with {max_tokens} tokens")
            # Send the simulated metrics 
            logger.info(f"TTFT: {ttft:.2f}s")
            logger.info(f"Total Delay: {total_delay:.2f}s")
            yield f"data: {json.dumps({'ttft': ttft, 'total_delay': total_delay})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Generation failed for {max_tokens} tokens: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )


# Worker restart endpoint
@app.post("/workers/restart")
async def restart_workers():
    """Restart all worker nodes"""
    try:
        return await dllama_manager.restart_workers()
    except Exception as e:
        logger.exception("Error restarting workers")
        raise HTTPException(status_code=500, detail=str(e))

# Performance metrics endpoint
@app.get("/performance/metrics")
async def get_performance_metrics():
    """Get performance metrics for all workers"""
    metrics = []
    
    for i, url in enumerate(WORKER_URLS):
        try:
            response = await client.get(f"{url}/metrics")
            if response.status_code == 200:
                metrics.append(response.json())
            else:
                metrics.append({
                    "worker_id": i+1,
                    "status": "error",
                    "error": f"HTTP {response.status_code}"
                })
        except Exception as e:
            metrics.append({
                "worker_id": i+1,
                "status": "error",
                "error": str(e)
            })
    
    # Get active workers count
    active_workers = sum(1 for m in metrics if m.get("status") != "error")
    
    return {
        "system": {
            "total_workers": len(WORKER_URLS),
            "active_workers": active_workers,
            "timestamp": time.time()
        },
        "worker_metrics": metrics
    }

# Middleware to log requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests and their processing time"""
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    # logger.info(f"Request: {request.method} {request.url.path} - Completed in {process_time:.2f}ms")
    return response

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("Starting up the backend service")
    app.state.monitoring_stopped = threading.Event()
    
    try:
        # Initialize Docker client
        app.state.docker_client = docker.from_env()
        logger.info("Docker client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Docker client: {str(e)}")
        app.state.docker_client = None

# Shutdown event 
@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info("Shutting down the backend service")
    app.state.monitoring_stopped.set()
    if app.state.docker_client:
        app.state.docker_client.close()