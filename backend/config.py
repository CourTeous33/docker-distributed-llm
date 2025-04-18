# Depends on what model you downloaded using the `model-downloader`
MODEL_PATH = "/models/llama3_2_1b_instruct_q40/dllama_model_llama3_2_1b_instruct_q40.m"
TOKENIZER_PATH = "/models/llama3_2_1b_instruct_q40/dllama_tokenizer_llama3_2_1b_instruct_q40.t"
# Depends on the docker-compose structure and how many workers you want to support (note the backend itself is also a worker, so there should be 2^N - 1 workers)
WORKER_URLS = [
    "http://worker1:5000",
    "http://worker2:5000",
    "http://worker3:5000"
]

LATENCY_MIN = 0.01 # 10 milliseconds
LATENCY_MAX = 0.05 # 50 milliseconds