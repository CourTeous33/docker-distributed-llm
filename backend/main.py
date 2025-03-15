from fastapi import FastAPI, HTTPException
import httpx
import os
import asyncio
from typing import List

app = FastAPI(title="LLM Backend Service")

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

# Client for making requests to workers
client = httpx.AsyncClient(timeout=60.0)

@app.get("/")
async def read_root():
    return {"message": "LLM Backend Service", "workers": len(worker_urls)}

@app.get("/workers/status")
async def get_workers_status():
    """Get status of all worker LLMs"""
    tasks = []
    
    for i, url in enumerate(worker_urls):
        tasks.append(get_worker_status(i + 1, url))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r if not isinstance(r, Exception) else 
            {"worker_id": i+1, "status": "error", "is_available": False} 
            for i, r in enumerate(results)]

async def get_worker_status(worker_id: int, url: str) -> dict:
    """Get status of a specific worker"""
    try:
        response = await client.get(f"{url}/status")
        if response.status_code == 200:
            return {
                "worker_id": worker_id,
                "status": "online",
                "is_available": True
            }
        else:
            return {
                "worker_id": worker_id,
                "status": f"error: {response.status_code}",
                "is_available": False
            }
    except Exception as e:
        return {
            "worker_id": worker_id,
            "status": f"error: {str(e)}",
            "is_available": False
        }

@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()