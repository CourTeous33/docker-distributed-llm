"""Backend integration for distributed-llama management."""
import os
import json
import asyncio
import logging
import httpx
import subprocess
from typing import List, Dict, Any, AsyncGenerator

logger = logging.getLogger(__name__)

class DistributedLlamaManager:
    """Manager class for distributed-llama operations"""
    
    def __init__(self, model_path: str, tokenizer_path: str, worker_urls: List[str]):
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.worker_urls = worker_urls
        self.client = httpx.AsyncClient(timeout=30.0)
        self.active_process = None

        # Validate paths and dependencies
        self._validate_paths()
        self._ensure_dllama_built()

    def _validate_paths(self):
        """Ensure required files exist."""
        if not os.path.exists(self.model_path):
            logger.warning(f"Model file not found at {self.model_path}")
        if not os.path.exists(self.tokenizer_path):
            logger.warning(f"Tokenizer file not found at {self.tokenizer_path}")

    def _ensure_dllama_built(self):
        """Build distributed-llama if missing."""
        if not os.path.exists("/app/distributed-llama/dllama"):
            logger.info("Building distributed-llama...")
            subprocess.run([
                "git", "clone", 
                "https://github.com/b4rtaz/distributed-llama.git",
                "/app/distributed-llama"
            ], check=True)
            subprocess.run(["make", "dllama"], cwd="/app/distributed-llama", check=True)

    async def generate_text(self, prompt: str = None, max_tokens: int = 256) -> AsyncGenerator[str, None]:
        """Stream generated text from distributed-llama inference."""
        process = await self._start_inference_process(prompt, max_tokens)
        
        try:
            async for line in self._stream_process_output(process):
                yield line
        finally:
            await self._cleanup_process(process)

    async def _start_inference_process(self, prompt: str, max_tokens: int) -> asyncio.subprocess.Process:
        """Start a new inference process per request."""
        cmd = [
            "/app/distributed-llama/dllama", "inference",
            "--model", self.model_path,
            "--tokenizer", self.tokenizer_path,
            "--buffer-float-type", "q80",
            "--max-seq-len", "2048",
            "--prompt", prompt or "Initializing server",
            "--steps",  str(max_tokens),
            "--nthreads", "1",
            "--port", "9999",
            "--workers", "172.20.0.11:9998", "172.20.0.12:9998", "172.20.0.13:9998"
        ]
        
        logger.info(f"Starting inference: {' '.join(cmd)}")
        return await asyncio.create_subprocess_exec(
            *cmd,
            cwd="/app/distributed-llama",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            bufsize=0  # Unbuffered output
        )

    async def _stream_process_output(self, process: asyncio.subprocess.Process) -> AsyncGenerator[str, None]:
        """Stream and filter process output."""
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            decoded = line.decode().strip()
            if self._is_debug_output(decoded):
                continue

            yield f"data: {json.dumps({'text': decoded})}\n\n"

        yield "data: [DONE]\n\n"

    def _is_debug_output(self, text: str) -> bool:
        """Filter system messages from output."""
        debug_terms = ["🔷", "Evaluation", "nBatches", "tokens/s", "Prediction"]
        return any(term in text for term in debug_terms)

    async def _cleanup_process(self, process: asyncio.subprocess.Process):
        """Ensure proper process termination."""
        if process and process.returncode is None:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except (ProcessLookupError, asyncio.TimeoutError):
                pass
            finally:
                if process.returncode is None:
                    process.kill()

    async def check_worker_status(self) -> Dict[str, Any]:
        """Check status of all worker nodes."""
        status = {}
        
        for idx, url in enumerate(self.worker_urls):
            worker_id = idx + 1
            try:
                response = await self.client.get(f"{url}/status", timeout=5)
                status[worker_id] = response.json()
            except Exception as e:
                status[worker_id] = {
                    "worker_id": worker_id,
                    "status": "error",
                    "error": str(e)
                }
        
        return status

    async def ensure_workers_started(self) -> bool:
        """Ensure all worker nodes are operational."""
        status = await self.check_worker_status()
        
        # Restart any failed workers
        for worker_id, info in status.items():
            if not info.get("is_available", False):
                try:
                    await self.client.post(f"{self.worker_urls[worker_id-1]}/start")
                except Exception as e:
                    logger.error(f"Failed to start worker {worker_id}: {str(e)}")
        
        # Verify restart
        await asyncio.sleep(2)
        return len([w for w in (await self.check_worker_status()).values() 
                  if w.get("is_available")]) > 0

    async def get_system_info(self) -> Dict[str, Any]:
        """Get complete system status."""
        workers = await self.check_worker_status()
        return {
            "server_status": "running",
            "model_path": os.path.basename(self.model_path),
            "available_workers": sum(1 for w in workers.values() if w["is_available"]),
            "total_workers": len(self.worker_urls),
            "tokenizer_path": os.path.basename(self.tokenizer_path)
        }

    async def close(self):
        """Cleanup resources."""
        await self.client.aclose()
