"""
Enhanced main.py for CS598 project with distributed-llama integration.
This file extends the original FastAPI backend to integrate with
distributed-llama for distributed inference across worker nodes.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import asyncio
from typing import List, Dict, Any, Optional
import logging
import time
from pydantic import BaseModel

from dllama_manager import DistributedLlamaManager

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

# Get worker URLs from environment variable
worker_urls = os.environ.get("WORKER_URLS", "").split(",")
if not worker_urls or worker_urls[0] == "":
    worker_urls = [
        "http://worker1:5000",
        "http://worker2:5000",
        "http://worker3:5000",
        "http://worker4:5000",
        "http://worker5:5000"
    ]

# Get model paths from environment variables
model_path = os.environ.get("DLLAMA_MODEL_PATH", "/models/dllama_model_meta-llama-3-8b_q40.m")
tokenizer_path = os.environ.get("DLLAMA_TOKENIZER_PATH", "/models/dllama_tokenizer_llama3.t")

# Initialize the distributed-llama manager
dllama_manager = DistributedLlamaManager(model_path, tokenizer_path, worker_urls)

# Client for making requests to workers
client = httpx.AsyncClient(timeout=60.0)

# Define request models
class GenerateTextRequest(BaseModel):
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.7
    top_p: float = 0.9

# Define response models
class GenerateTextResponse(BaseModel):
    generated_text: str
    prompt: str
    generation_time: float
    total_tokens: int

# Health check endpoint
@app.get("/")
async def read_root():
    """Root endpoint for health check"""
    return {"message": "LLM Backend Service with Distributed-Llama", "workers": len(worker_urls)}

# Worker status endpoint
@app.get("/workers/status")
async def get_workers_status():
    """Get status of all worker LLMs"""
    print("Starting worker status check for all workers")
    
    tasks = []
    
    for i, url in enumerate(worker_urls):
        print(f"Creating status check task for worker {i+1} at {url}")
        tasks.append(get_worker_status(i + 1, url))
    
    print(f"Gathering results from {len(tasks)} worker status checks")

    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    processed_results = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"Worker {i+1} check resulted in exception: {str(r)}")
            processed_results.append({"worker_id": i+1, "status": "error", "is_available": False})
        else:
            print(f"Worker {i+1} check completed successfully: {r}")
            processed_results.append(r)
            
    print(f"Completed all worker status checks. Results: {processed_results}")
    return processed_results



async def get_worker_status(worker_id: int, url: str) -> dict:
    """Get status of a specific worker"""
    print(f"Checking status of worker {worker_id} at {url}")
    try:
        response = await client.get(f"{url}/status")
        print(f"Worker {worker_id} response status code: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Worker {worker_id} returned error status code {response.status_code}")
            return {
                "worker_id": worker_id,
                "status": f"error: {response.status_code}",
                "is_available": False
            }
    except Exception as e:
        print(f"Error checking worker {worker_id} status: {str(e)}")
        return {
            "worker_id": worker_id,
            "status": f"error: {str(e)}",
            "is_available": False
        }

# System status endpoint
@app.get("/system/status")
async def get_system_status():
    """Get comprehensive system status"""
    try:
        return await dllama_manager.get_system_info()
    except Exception as e:
        logger.exception("Error getting system status")
        raise HTTPException(status_code=500, detail=str(e))

# Text generation endpoint
@app.post("/generate", response_model=GenerateTextResponse)
async def generate_text(request: GenerateTextRequest):
    """Generate text using the distributed-llama model"""
    try:
        start_time = time.time()
        
        # Generate text
        generated_text = await dllama_manager.generate_text(
            prompt=request.prompt,
            max_tokens=request.max_tokens
        )
        
        generation_time = time.time() - start_time
        
        # Simple token count (approximation)
        total_tokens = len(request.prompt.split()) + len(generated_text.split())
        
        return GenerateTextResponse(
            generated_text=generated_text,
            prompt=request.prompt,
            generation_time=generation_time,
            total_tokens=total_tokens
        )
    except Exception as e:
        logger.exception("Error generating text")
        raise HTTPException(status_code=500, detail=str(e))

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
    
    for i, url in enumerate(worker_urls):
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
            "total_workers": len(worker_urls),
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
    logger.info(f"Request: {request.method} {request.url.path} - Completed in {process_time:.2f}ms")
    return response

# Startup event
@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("Starting up the backend service")
    
    # Start the distributed-llama server
    try:
        await dllama_manager.start_inference_server()
    except Exception as e:
        logger.error(f"Error starting distributed-llama server: {e}")
        # Continue anyway, we'll try to start it again when needed

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info("Shutting down the backend service")
    
    # Stop the distributed-llama server
    await dllama_manager.stop_inference_server()
    
    # Close the HTTP client
    await client.aclose()
    
    # Close the dllama manager
    await dllama_manager.close()