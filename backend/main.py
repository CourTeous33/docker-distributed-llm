"""
Enhanced main.py for CS598 project with distributed-llama integration.
This file extends the original FastAPI backend to integrate with
distributed-llama for distributed inference across worker nodes.
"""

from fastapi import FastAPI, HTTPException, Request
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

worker_urls = [
    "http://worker1:5000",
    "http://worker2:5000",
    "http://worker3:5000"
]

# Initialize manager
dllama_manager = DistributedLlamaManager(
    model_path="/models/llama3_2_1b_instruct_q40/dllama_model_llama3_2_1b_instruct_q40.m",
    tokenizer_path="/models/llama3_2_1b_instruct_q40/dllama_tokenizer_llama3_2_1b_instruct_q40.t",
    worker_urls=worker_urls
)

client = httpx.AsyncClient(timeout=60.0)

class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 256

class GenerateResponse(BaseModel):
    success: bool
    generated_text: str
    generation_time: float

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

@app.post("/generate", response_model=GenerateResponse)
async def generate_text(request: GenerateRequest):
    """Generate text by starting inference server with prompt"""
    start_time = time.time()
    
    try:
        success, output = await dllama_manager.start_inference_server(request.prompt)
        generation_time = time.time() - start_time
        
        if not success:
            return GenerateResponse(
                success=False,
                generated_text=f"Error: {output}",
                generation_time=generation_time
            )
            
        # Extract generated text from server output
        generated_text = output.split(request.prompt)[-1].strip()
        
        return GenerateResponse(
            success=True,
            generated_text=generated_text,
            generation_time=generation_time
        )
        
    except Exception as e:
        logger.exception("Generation failed")
        raise HTTPException(500, str(e))

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
    # logger.info(f"Request: {request.method} {request.url.path} - Completed in {process_time:.2f}ms")
    return response

# Startup event
@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("Starting up the backend service")
    logger.info("Inference server will start on first generation request")

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
