from flask import Flask, jsonify
import os
import logging

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
        "status": "online",
        "is_available": True
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)