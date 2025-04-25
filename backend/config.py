# Depends on what model you downloaded using the `model-downloader`
MODEL_PATH = "/models/llama3_2_1b_instruct_q40/dllama_model_llama3_2_1b_instruct_q40.m"
TOKENIZER_PATH = "/models/llama3_2_1b_instruct_q40/dllama_tokenizer_llama3_2_1b_instruct_q40.t"
# Depends on the docker-compose structure and how many workers you want to support (note the backend itself is also a worker, so there should be 2^N - 1 workers)
WORKER_URLS = [
    "http://worker1:5000",
    "http://worker2:5000",
    "http://worker3:5000"
]
# IPs are passed directly to the dllama_mananger.py to ensure running the dllama command works
WORKER_IPS = ["172.20.0.11:9998", "172.20.0.12:9998", "172.20.0.13:9998"]

# Estimated range to simulate 
LATENCY_MIN = 0.06 # ex: 0.01 = 10 milliseconds
LATENCY_MAX = 0.12 # ex: 0.05 = 50 milliseconds

N_THREADS = 2 # CPU threads to use for the root node (availability depends on docker compose and your machine)