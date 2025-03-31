"""
Backend integration for distributed-llama management.
This module provides a class for managing distributed-llama
model inference and worker coordination from the backend.
"""

import os
import subprocess
import json
import threading
import time
import asyncio
import logging
import httpx
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator

logger = logging.getLogger(__name__)

class DistributedLlamaManager:
    """Manager class for distributed-llama operations"""
    
    def __init__(self, model_path: str, tokenizer_path: str, worker_urls: List[str]):
        """
        Initialize the manager with model paths and worker information
        
        Args:
            model_path: Path to the distributed-llama model file
            tokenizer_path: Path to the tokenizer file
            worker_urls: List of worker URLs in the format http://worker1:5000
        """
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.worker_urls = worker_urls
        self.process = None
        self.worker_statuses = {}
        self.lock = threading.Lock()
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Check if model and tokenizer exist
        if not os.path.exists(model_path):
            logger.warning(f"Model file not found at {model_path}")
        
        if not os.path.exists(tokenizer_path):
            logger.warning(f"Tokenizer file not found at {tokenizer_path}")
        # Ensure distributed-llama exists
        if not os.path.exists("/app/distributed-llama"):
            logger.info("Cloning distributed-llama repository...")
            subprocess.run(["git", "clone", "https://github.com/b4rtaz/distributed-llama.git", "/app/distributed-llama"], check=True)
            
            # Build binaries
            logger.info("Building dllama...")
            subprocess.run(["make", "dllama"], cwd="/app/distributed-llama", check=True)
            logger.info("Building dllama-api...")
            subprocess.run(["make", "dllama-api"], cwd="/app/distributed-llama", check=True)
    
    async def generate_text(self, prompt: str = None) -> AsyncGenerator[str, None]:
        """
        Start the distributed-llama inference server and stream output
        
        Args:
            prompt: Optional prompt to initialize the server with
            
        Yields:
            str: Output lines from the server
            
        Raises:
            RuntimeError: If server fails to start
        """
        with self.lock:
            if self.process and self.process.poll() is None:
                msg = "Inference server is already running"
                logger.info(msg)
                yield msg
                return

            # Validate and set prompt
            init_prompt = str(prompt) if prompt else "Initializing server"
            
            cmd = [
                "/app/distributed-llama/dllama", 
                "inference",
                "--model", self.model_path,
                "--tokenizer", self.tokenizer_path,
                "--buffer-float-type", "q80",
                "--max-seq-len", "2048",
                "--prompt", init_prompt,
                "--steps", "10",
                "--nthreads", "1", 
                "--port", "9999",
                "--workers", "172.20.0.11:9998", "172.20.0.12:9998", "172.20.0.13:9998"
            ]
            
            logger.info(f"Starting distributed-llama server with command: {' '.join(cmd)}")
            
            try:
                self.process = subprocess.Popen(
                    cmd, 
                    cwd="/app/distributed-llama",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Wait for server to start
                await asyncio.sleep(5)
                
                if self.process.poll() is not None:
                    stderr = self.process.stderr.read()
                    error_msg = f"Failed to start distributed-llama server: {stderr}"
                    logger.error(error_msg)
                    yield error_msg
                    raise RuntimeError(error_msg)

                # Create a queue for output lines on the current event loop
                output_queue = asyncio.Queue()
                # Capture the current (main) event loop
                main_loop = asyncio.get_running_loop()
                
                def capture_output():
                    try:
                        for line in self.process.stdout:
                            output = line
                            logger.info(f"DLlama server output: {output}")
                            logger.info(f"DLlama server output (raw): {repr(output)}")

                            # # Schedule the put operation on the main event loop and wait for it to complete
                            
                            future = asyncio.run_coroutine_threadsafe(output_queue.put(output), main_loop)
                            future.result()  # Wait until the put operation completes
                            logger.info(f"Output enqueued: {output} | Queue size now: {output_queue.qsize()}")
               
                        for line in self.process.stderr:
                            error = line
                            logger.error(f"DLlama server error: {error}")
                            
                    except Exception as thread_exc:
                        logger.exception("Exception in capture_output thread: %s", thread_exc)
                
                threading.Thread(target=capture_output, daemon=True).start()
                
                logger.info("Started thread to capture output from distributed-llama server")
                # Wait briefly to ensure server started
                await asyncio.sleep(1)
                logger.info("Distributed-llama server started successfully")
                
                # Yield lines as they come in
                while True:
                    logger.info("Waiting for output from queue...")
                    while not output_queue.empty():
                        logger.info("Output queue is not empty; processing items...")
                        try:
                            line = output_queue.get_nowait()
                            logger.info(f"Yielding line: {line}")
                            yield f"data: {json.dumps({'text': line})}\n\n"
                        except Exception as e:
                            logger.exception("Error retrieving item from queue: %s", e)
                    
                    # Now wait for the next item.
                    try:
                        # This await will pause until a new item is enqueued.
                        line = await asyncio.wait_for(output_queue.get(), timeout=30)
                        logger.info(f"Yielding line after wait: {line}")
                        yield f"data: {json.dumps({'text': line})}\n\n"
                    except asyncio.TimeoutError:
                        logger.info("Timeout waiting for output; checking process status...")
                        if self.process.poll() is not None:
                            logger.info("Process has ended; breaking out of yield loop.")
                            break
                        else:
                            logger.info("Process still running; continuing to wait for output.")
                            # Optionally yield a heartbeat message:
                            yield "data: {\"heartbeat\": \"keepalive\"}\n\n"
            except Exception as e:
                error_msg = f"Error starting distributed-llama server: {str(e)}"
                logger.exception(error_msg)
                yield error_msg
                raise RuntimeError(error_msg)

    async def stop_inference_server(self) -> bool:
        """
        Stop the distributed-llama server
        
        Returns:
            bool: True if the server was stopped successfully
        """
        with self.lock:
            if self.process and self.process.poll() is None:
                # Try graceful termination first
                self.process.terminate()
                
                try:
                    await asyncio.wait_for(asyncio.create_subprocess_shell(f"sleep {5}"), timeout=5)
                    if self.process.poll() is None:
                        # Force kill if not terminated
                        self.process.kill()
                        logger.warning("Had to force kill server process")
                except asyncio.TimeoutError:
                    # Force kill if timeout
                    self.process.kill()
                    logger.warning("Timeout waiting for server to terminate, killed")
                
                logger.info("Distributed-llama server stopped")
                return True
            
            return False
    
    async def check_worker_status(self) -> Dict[str, Any]:
        """
        Check the status of all worker nodes
        
        Returns:
            Dict containing worker status information
        """
        results = {}
        
        for i, url in enumerate(self.worker_urls):
            worker_id = i + 1
            try:
                response = await self.client.get(f"{url}/status", timeout=5.0)
                if response.status_code == 200:
                    results[worker_id] = response.json()
                else:
                    results[worker_id] = {
                        "worker_id": worker_id,
                        "status": f"error: HTTP {response.status_code}",
                        "is_available": False
                    }
            except Exception as e:
                results[worker_id] = {
                    "worker_id": worker_id,
                    "status": f"error: {str(e)}",
                    "is_available": False
                }
        
        self.worker_statuses = results
        return results
    
    async def ensure_workers_started(self) -> bool:
        """
        Ensure all worker nodes are started
        
        Returns:
            bool: True if all workers are started
        """
        status = await self.check_worker_status()
        
        # Start any workers that aren't running
        for worker_id, worker_status in status.items():
            if not worker_status.get("is_available", False):
                url = self.worker_urls[worker_id - 1]
                try:
                    logger.info(f"Starting worker {worker_id} at {url}")
                    response = await self.client.post(f"{url}/start", timeout=10.0)
                    logger.info(f"Worker {worker_id} start response: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error starting worker {worker_id}: {e}")
        
        # Check status again
        await asyncio.sleep(2)
        status = await self.check_worker_status()
        
        # Count available workers
        available_workers = sum(1 for ws in status.values() if ws.get("is_available", False))
        logger.info(f"{available_workers} out of {len(self.worker_urls)} workers available")
        
        return available_workers > 0
    
    
    async def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information including worker status
        
        Returns:
            Dict containing system information
        """
        worker_status = await self.check_worker_status()
        
        # Get server status
        server_status = "running" if self.process and self.process.poll() is None else "stopped"
        
        # Count available workers
        available_workers = sum(1 for ws in worker_status.values() if ws.get("is_available", False))
        
        return {
            "server_status": server_status,
            "total_workers": len(self.worker_urls),
            "available_workers": available_workers,
            "model_path": self.model_path,
            "tokenizer_path": self.tokenizer_path,
            "worker_status": worker_status
        }
        
    async def restart_workers(self) -> Dict[str, Any]:
        """
        Restart all worker nodes
        
        Returns:
            Dict containing restart results
        """
        results = {}
        
        for i, url in enumerate(self.worker_urls):
            worker_id = i + 1
            try:
                response = await self.client.post(f"{url}/restart", timeout=10.0)
                results[worker_id] = {
                    "worker_id": worker_id,
                    "success": response.status_code == 200,
                    "status": response.status_code
                }
            except Exception as e:
                results[worker_id] = {
                    "worker_id": worker_id,
                    "success": False,
                    "error": str(e)
                }
        
        # Check status after restart
        await asyncio.sleep(2)
        status = await self.check_worker_status()
        
        return {
            "restart_results": results,
            "worker_status": status
        }
    
    async def close(self):
        """Clean up resources"""
        await self.stop_inference_server()
        await self.client.aclose()
