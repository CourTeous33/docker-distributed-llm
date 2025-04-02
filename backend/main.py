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

@app.get("/stream")
async def generate_text(
    prompt: str = Query(..., description="Prompt for generation"),
    max_tokens: int = Query(256, gt=0, le=1024, description="Maximum tokens to generate")
):
    """Stream predicted text tokens with proper max_tokens handling"""
    logger.info(f"Starting generation with {max_tokens} max tokens")
    async def generate_stream():
        try:
            async for line in dllama_manager.generate_text(prompt=prompt, max_tokens=max_tokens):
                if "Pred" in line:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        predicted_text = parts[-1].strip()
                        if predicted_text:
                            logger.debug(f"Yielding token: {predicted_text}")
                            yield f"data: {json.dumps({'text': predicted_text})}\n\n"
            logger.info(f"Generation completed with {max_tokens} tokens")
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
