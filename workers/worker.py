from flask import Flask, request, jsonify
import time
import os
import logging
import threading

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get worker ID from environment variable
worker_id = int(os.environ.get("WORKER_ID", "1"))

@app.route("/status", methods=["GET"])
def status():
    """Return the status of the worker"""
    
    return jsonify({
        "worker_id": worker_id,
        "device": "cuda" if torch.cuda.is_available() else "cpu"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)