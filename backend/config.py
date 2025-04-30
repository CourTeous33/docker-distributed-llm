# Depends on what model you downloaded using the `model-downloader`
MODEL_PATH = "/models/llama3_2_3b_instruct_q40/dllama_model_llama3_2_3b_instruct_q40.m"
TOKENIZER_PATH = "/models/llama3_2_3b_instruct_q40/dllama_tokenizer_llama3_2_3b_instruct_q40.t"
# Depends on the docker-compose structure and how many workers you want to support (note the backend itself is also a worker, so there should be 2^N - 1 workers)
WORKER_URLS = []
# IPs are passed directly to the dllama_mananger.py to ensure running the dllama command works
WORKER_IPS = []

# Estimated range to simulate 
LATENCY_MIN = 0 # ex: 0.01 = 10 milliseconds
LATENCY_MAX = 0.01 # ex: 0.05 = 50 milliseconds

N_THREADS = 1 # CPU threads to use for the root node (availability depends on docker compose and your machine)