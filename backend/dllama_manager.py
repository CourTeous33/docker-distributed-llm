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
from typing import List, Dict, Any, Optional, Tuple

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
    
    async def start_inference_server(self) -> bool:
        """
        Start the distributed-llama inference server
        
        Returns:
            bool: True if the server started successfully
        """
        with self.lock:
            if self.process and self.process.poll() is None:
                logger.info("Inference server is already running")
                return True
            
            
            cmd = [
                "/app/distributed-llama/dllama", 
                "inference",
                "--model", "/models/llama3_2_1b_instruct_q40/dllama_model_llama3_2_1b_instruct_q40.m",
                "--tokenizer", "/models/llama3_2_1b_instruct_q40/dllama_tokenizer_llama3_2_1b_instruct_q40.t",
                "--buffer-float-type", "q80",
                "--max-seq-len", "2048",
                "--prompt", "Hi there how are you?",
                "--steps", "10",
                "--nthreads", "1", 
                "--port", "9999",
            ]

            # worker_ips = ["172.20.0.11:9998", "172.20.0.12:9998", "172.20.0.13:9998", "172.20.0.14:9998", "172.20.0.15:9998"]
            worker_ips = ["172.20.0.11:9998", "172.20.0.12:9998", "172.20.0.13:9998"]
            cmd.append("--workers")
            cmd.extend(worker_ips)  # Add each worker as a separate argument
            
           
            
            logger.info(f"Starting distributed-llama server with command: {' '.join(cmd)}")
            # Rest of the method remains the same
            
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
                    if stderr is None:
                        logger.error(f"Failed to start distributed-llama server: {stderr}")
                        raise RuntimeError(f"Failed to start distributed-llama server: {stderr}")
                    
                # Set up a thread to log output
                def log_output():
                    for line in self.process.stdout:
                        logger.info(f"DLlama server output: {line.strip()}")
                    for line in self.process.stderr:
                        logger.error(f"DLlama server error: {line.strip()}")
                
                threading.Thread(target=log_output, daemon=True).start()
                
                logger.info("Distributed-llama server started successfully")
                return True
                
            except Exception as e:
                logger.exception("Error starting distributed-llama server")
                raise
    
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
    
    async def generate_text(self, prompt: str, max_tokens: int = 256) -> str:
        """
        Generate text using the distributed-llama model
        
        Args:
            prompt: The input prompt to generate from
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            str: Generated text
        """
        # First, make sure workers are running
        await self.ensure_workers_started()
        
        # Check if server is running, if not start it
        if not self.process or self.process.poll() is not None:
            await self.start_inference_server()
        
        try:
            # Use dllama inference command to generate text
            cmd = [
                "/app/distributed-llama/dllama", "inference",
                "--model", "/models/llama3_2_1b_instruct_q40/dllama_model_llama3_2_1b_instruct_q40.m",
                "--tokenizer", "/models/llama3_2_1b_instruct_q40/dllama_tokenizer_llama3_2_1b_instruct_q40.t",
                "--buffer-float-type", "q80",
                "--prompt", prompt,
                "--steps", str(max_tokens),
                "--nthreads", "1",
                "--workers", "172.20.0.11:9998 172.20.0.12:9998 172.20.0.13:9998",
                "--debug"
            ]
            
            logger.info(f"Generating text with command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, 
                cwd="/app/distributed-llama",
                capture_output=True,
                text=True,
                check=False
            )
            
            logger.info(f"Command exit code: {result.returncode}")
            
            if result.returncode != 0:
                logger.error(f"Command stderr: {result.stdout}")
                return f"Error generating text: {result.stderr}"
            
            # Parse and clean the output
            output = result.stdout.strip()
            # Remove the prompt from the output if it appears
            if output.startswith(prompt):
                output = output[len(prompt):].strip()
            
            return output
        except Exception as e:
            logger.exception("Error during text generation")
            return f"Exception during text generation: {str(e)}"
    
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