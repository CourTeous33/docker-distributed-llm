#!/usr/bin/env python3
"""
Minimal worker wrapper for distributed-llama integration (since we move tracking to the backend with docker-stats)
"""

import os
import subprocess
import threading
import time
import logging
import signal
import sys
from flask import Flask, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration from environment
worker_id = int(os.environ.get("WORKER_ID", "1"))
api_port = int(os.environ.get("DLLAMA_API_PORT", "5000"))
dllama_worker_process = None
process_start_time = None

def start_dllama_worker():
    """Start the worker process"""
    global dllama_worker_process, process_start_time
    cmd = [
        "/dllama-app/distributed-llama/dllama", 
        "worker",
        "--port", "9998",
        "--nthreads", "1"
    ]
    
    logger.info(f"Starting worker: {' '.join(cmd)}")
    dllama_worker_process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    process_start_time = time.time()
    
    # Log output thread
    def log_output():
        while True:
            line = dllama_worker_process.stderr.readline()
            if line: logger.error(f"Worker error: {line.strip()}")

    threading.Thread(target=log_output, daemon=True).start()

@app.route("/status", methods=["GET"])
def status():
    """Return worker status with availability"""
    is_running = bool(dllama_worker_process and dllama_worker_process.poll() is None)
    return jsonify({
        "worker_id": worker_id,
        "status": "online" if is_running else "offline",
        "is_available": is_running,  
        "uptime_seconds": time.time() - process_start_time if process_start_time else 0
    })

@app.route("/start", methods=["POST"])
def start_worker():
    """Start the distributed-llama worker"""
    global dllama_worker_process, worker_status
    
    if dllama_worker_process and dllama_worker_process.poll() is None:
        return jsonify({
            "status": "already_running",
            "worker_id": worker_id
        })
    
    try:
        start_dllama_worker()
        return jsonify({
            "status": "started",
            "worker_id": worker_id
        })
    except Exception as e:
        logger.exception("Error starting worker")
        return jsonify({
            "status": "error",
            "message": str(e),
            "worker_id": worker_id
        }), 500

@app.route("/stop", methods=["POST"])
def stop_worker():
    """Stop the distributed-llama worker"""
    global dllama_worker_process, worker_status
    
    if dllama_worker_process and dllama_worker_process.poll() is None:
        # Try graceful termination first
        dllama_worker_process.terminate()
        
        # Wait up to 5 seconds for process to terminate
        try:
            dllama_worker_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force kill if not terminated
            dllama_worker_process.kill()
            logger.warning("Had to force kill worker process")
        
        # Update status
        dllama_worker_process = None
        worker_status["status"] = "stopped"
        worker_status["is_available"] = False
        worker_status["start_time"] = None
        
        return jsonify({
            "status": "stopped",
            "worker_id": worker_id
        })
    
    return jsonify({
        "status": "not_running",
        "worker_id": worker_id
    })

@app.route("/restart", methods=["POST"])
def restart_worker():
    """Restart the distributed-llama worker"""
    stop_worker()
    return start_worker()

def signal_handler(sig, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {sig}, shutting down")
    
    if dllama_worker_process and dllama_worker_process.poll() is None:
        dllama_worker_process.terminate()
        try:
            dllama_worker_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            dllama_worker_process.kill()
    
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    threading.Thread(target=start_dllama_worker).start()
    app.run(host="0.0.0.0", port=api_port)