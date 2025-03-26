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
            print(f"Worker {worker_id} is online and available")
            return {
                "worker_id": worker_id,
                "status": "online",
                "is_available": True
            }
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

@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()