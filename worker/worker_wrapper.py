#!/usr/bin/env python3
"""
Worker wrapper for distributed-llama integration
This script manages the distributed-llama worker process and provides a Flask API
for status monitoring and control.
"""

import os
import subprocess
import threading
import time
import logging
import signal
import sys
import psutil
from flask import Flask, jsonify, request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Get worker ID and port configuration from environment variables
worker_id = int(os.environ.get("WORKER_ID", "1"))
dllama_worker_port = int(os.environ.get("DLLAMA_WORKER_PORT", "9998"))
api_port = int(os.environ.get("DLLAMA_API_PORT", "5000"))

# Global variable to track the worker process
dllama_worker_process = None
worker_status = {
    "status": "initializing",
    "memory_usage": 0,
    "cpu_usage": 0,
    "start_time": None,
    "is_available": False
}

def monitor_resource_usage():
    """Monitor resource usage of the worker process"""
    global dllama_worker_process, worker_status
    
    while True:
        if dllama_worker_process and dllama_worker_process.poll() is None:
            try:
                # Get process information
                process = psutil.Process(dllama_worker_process.pid)
                
                # Update status
                worker_status["memory_usage"] = process.memory_info().rss / (1024 * 1024)  # MB
                worker_status["cpu_usage"] = process.cpu_percent(interval=0.1)
                worker_status["is_available"] = True
                worker_status["status"] = "online"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                worker_status["is_available"] = False
                worker_status["status"] = "error"
        else:
            worker_status["is_available"] = False
            worker_status["status"] = "stopped" if dllama_worker_process else "not_started"
        
        time.sleep(5)  # Update every 5 seconds

def start_dllama_worker():
    """Start the distributed-llama worker process"""
    global dllama_worker_process, worker_status
    
    cmd = [
        "./dllama", 
        "worker",
        "--port", str(dllama_worker_port),
        "--nthreads", "4"
    ]
    
    logger.info(f"Starting distributed-llama worker with command: {' '.join(cmd)}")
    
    # Set the working directory to the distributed-llama folder
    dllama_worker_process = subprocess.Popen(
        cmd, 
        cwd="/app/distributed-llama",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Update worker status
    worker_status["start_time"] = time.time()
    
    # Check if the process started successfully
    time.sleep(3)
    if dllama_worker_process.poll() is not None:
        stderr = dllama_worker_process.stderr.read()
        logger.error(f"Failed to start distributed-llama worker: {stderr}")
        worker_status["status"] = "error"
        worker_status["is_available"] = False
        raise RuntimeError(f"Failed to start distributed-llama worker: {stderr}")
    
    logger.info("Distributed-llama worker started successfully")
    worker_status["status"] = "online"
    worker_status["is_available"] = True
    
    # Set up a thread to log output
    def log_output():
        for line in dllama_worker_process.stdout:
            logger.info(f"DLlama worker output: {line.strip()}")
        for line in dllama_worker_process.stderr:
            logger.error(f"DLlama worker error: {line.strip()}")
    
    threading.Thread(target=log_output, daemon=True).start()
    return True

@app.route("/status", methods=["GET"])
def status():
    """Return the status of the worker"""
    global dllama_worker_process, worker_status
    
    # Check if process is still running
    if dllama_worker_process and dllama_worker_process.poll() is None:
        is_running = True
    else:
        is_running = False
        worker_status["is_available"] = False
        worker_status["status"] = "stopped" if dllama_worker_process else "not_started"
    
    return jsonify({
        "worker_id": worker_id,
        "status": worker_status["status"],
        "is_available": worker_status["is_available"],
        "process_running": is_running,
        "memory_usage_mb": worker_status["memory_usage"],
        "cpu_usage_percent": worker_status["cpu_usage"],
        "uptime_seconds": time.time() - worker_status["start_time"] if worker_status["start_time"] else 0
    })

@app.route("/metrics", methods=["GET"])
def metrics():
    """Return detailed metrics for the worker"""
    global dllama_worker_process, worker_status
    
    if not dllama_worker_process or dllama_worker_process.poll() is not None:
        return jsonify({
            "worker_id": worker_id,
            "status": "offline",
            "error": "Worker process is not running"
        }), 404
    
    try:
        # Get detailed process information
        process = psutil.Process(dllama_worker_process.pid)
        
        return jsonify({
            "worker_id": worker_id,
            "status": worker_status["status"],
            "memory": {
                "rss_mb": process.memory_info().rss / (1024 * 1024),
                "vms_mb": process.memory_info().vms / (1024 * 1024),
            },
            "cpu": {
                "usage_percent": process.cpu_percent(interval=0.1),
                "num_threads": process.num_threads(),
            },
            "io": {
                "read_count": process.io_counters().read_count if hasattr(process.io_counters(), 'read_count') else 0,
                "write_count": process.io_counters().write_count if hasattr(process.io_counters(), 'write_count') else 0,
            },
            "uptime_seconds": time.time() - worker_status["start_time"] if worker_status["start_time"] else 0
        })
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        return jsonify({
            "worker_id": worker_id,
            "status": "error",
            "error": str(e)
        }), 500

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
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the resource monitoring thread
    threading.Thread(target=monitor_resource_usage, daemon=True).start()
    
    # Start the distributed-llama worker in a separate thread
    threading.Thread(target=start_dllama_worker).start()
    
    # Start the Flask app
    logger.info(f"Starting Flask app on port {api_port}")
    app.run(host="0.0.0.0", port=api_port)