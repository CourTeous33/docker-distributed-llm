#!/usr/bin/env python3
"""
Interactive Model Downloader for Distributed-Llama

This script downloads and prepares the model and tokenizer files required
for the distributed-llama system. It provides an interactive interface
for selecting models when no model is specified.
"""

import os
import sys
import subprocess
import logging
import shutil
import time
import argparse
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Available models - updated based on the distributed-llama README
AVAILABLE_MODELS = {
    "llama3_1_8b_instruct_q40": {
        "description": "Llama 3.1 8B Instruct Q40",
        "model_file": "dllama_model_llama31_8b_instruct_q40.m",
        "tokenizer_file": "dllama_tokenizer_llama_3_1.t",
        "size_gb": "6.32",
        "recommended_ram": "8GB per node"
    },
    "llama3_1_405b_instruct_q40": {
        "description": "Llama 3.1 405B Instruct Q40",
        "model_file": "dllama_model_llama31_405b_instruct_q40.m",
        "tokenizer_file": "dllama_tokenizer_llama_3_1.t",
        "size_gb": "238",
        "recommended_ram": "480GB total, can be distributed"
    },
    "llama3_2_1b_instruct_q40": {
        "description": "Llama 3.2 1B Instruct Q40",
        "model_file": "dllama_model_llama32_1b_instruct_q40.m",
        "tokenizer_file": "dllama_tokenizer_llama_3_2.t",
        "size_gb": "1.7",
        "recommended_ram": "4GB per node"
    },
    "llama3_2_3b_instruct_q40": {
        "description": "Llama 3.2 3B Instruct Q40",
        "model_file": "dllama_model_llama32_3b_instruct_q40.m",
        "tokenizer_file": "dllama_tokenizer_llama_3_2.t",
        "size_gb": "3.4",
        "recommended_ram": "6GB per node"
    },
    "llama3_3_70b_instruct_q40": {
        "description": "Llama 3.3 70B Instruct Q40",
        "model_file": "dllama_model_llama33_70b_instruct_q40.m",
        "tokenizer_file": "dllama_tokenizer_llama_3_3.t",
        "size_gb": "40",
        "recommended_ram": "80GB total, can be distributed"
    },
    "deepseek_r1_distill_llama_8b_q40": {
        "description": "DeepSeek R1 Distill Llama 8B Q40",
        "model_file": "dllama_model_deepseek_r1_distill_llama_8b_q40.m",
        "tokenizer_file": "dllama_tokenizer_deepseek_r1.t",
        "size_gb": "6.32",
        "recommended_ram": "8GB per node"
    }
}

def interactive_model_selection() -> str:
    """
    Interactively select a model from the available options
    
    Returns:
        str: The selected model name
    """
    print("\n=== Distributed Llama Model Selection ===\n")
    print("Available models:")
    
    # Display models in a formatted table
    print(f"{'#':<3} {'Model Name':<35} {'Size':<10} {'RAM Needed':<20} Description")
    print("-" * 100)
    
    for i, (name, info) in enumerate(AVAILABLE_MODELS.items(), 1):
        print(f"{i:<3} {name:<35} {info['size_gb']+' GB':<10} {info['recommended_ram']:<20} {info['description']}")
    
    print("\nChoose a model based on your available resources.")
    print("Larger models provide better quality but require more memory.")
    print("With distributed-llama, memory requirements can be split across multiple nodes.")
    
    while True:
        choice = input("\nSelect model number or enter model name (q to quit): ")
        
        if choice.lower() == 'q':
            print("Exiting...")
            sys.exit(0)
        
        # Try to interpret as a number first
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(AVAILABLE_MODELS):
                selected_model = list(AVAILABLE_MODELS.keys())[idx]
                break
            else:
                print(f"Error: Please enter a number between 1 and {len(AVAILABLE_MODELS)}")
        except ValueError:
            # Try to interpret as a model name
            if choice in AVAILABLE_MODELS:
                selected_model = choice
                break
            else:
                print(f"Error: Unknown model '{choice}'")
    
    # Confirm selection
    model_info = AVAILABLE_MODELS[selected_model]
    print(f"\nYou selected: {selected_model}")
    print(f"Description: {model_info['description']}")
    print(f"Size: {model_info['size_gb']} GB")
    print(f"RAM Requirements: {model_info['recommended_ram']}")
    
    confirm = input("\nProceed with this model? (y/n): ")
    if confirm.lower() != 'y':
        print("Let's select again...")
        return interactive_model_selection()
    
    return selected_model

def check_distributed_llama_installed():
    """Check if distributed-llama is already installed"""
    if os.path.exists("distributed-llama"):
        print("Found existing distributed-llama directory")
        return True
    
    # Clone the repository
    print("Cloning distributed-llama repository...")
    try:
        subprocess.run(
            ["git", "clone", "https://github.com/b4rtaz/distributed-llama.git"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e}")
        return False

def build_distributed_llama():
    """Build the distributed-llama binaries"""
    if not os.path.exists("distributed-llama"):
        print("distributed-llama directory not found")
        return False
    
    try:
        # Change to distributed-llama directory
        os.chdir("distributed-llama")
        
        # Build dllama
        print("Building distributed-llama (this may take a few minutes)...")
        subprocess.run(["make", "dllama"], check=True)
        
        # Build dllama-api
        print("Building dllama-api...")
        subprocess.run(["make", "dllama-api"], check=True)
        
        # Change back to original directory
        os.chdir("..")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error building distributed-llama: {e}")
        return False

def download_model(model_name: str, output_dir: str) -> bool:
    """
    Download a model using distributed-llama's launch.py script
    
    Args:
        model_name: Name of the model to download
        output_dir: Directory to save the model files
        
    Returns:
        bool: True if successful, False otherwise
    """
    if model_name not in AVAILABLE_MODELS:
        logger.error(f"Unknown model: {model_name}")
        print(f"Available models: {', '.join(AVAILABLE_MODELS.keys())}")
        return False
    
    # Get model info
    model_info = AVAILABLE_MODELS[model_name]
    model_file = model_info["model_file"]
    tokenizer_file = model_info["tokenizer_file"]
    
    # Check if model already exists in the output directory
    model_path = os.path.join(output_dir, model_file)
    tokenizer_path = os.path.join(output_dir, tokenizer_file)
    
    if os.path.exists(model_path) and os.path.exists(tokenizer_path):
        logger.info(f"Model files already exist in {output_dir}")
        print(f"Model files already exist in {output_dir}")
        overwrite = input("Do you want to re-download the model? (y/n): ")
        if overwrite.lower() != 'y':
            print("Using existing model files.")
            return True
    
    # Make sure distributed-llama is installed
    if not check_distributed_llama_installed():
        logger.error("Failed to set up distributed-llama")
        return False
    
    # Build the binaries if needed
    if not os.path.exists("distributed-llama/dllama") or not os.path.exists("distributed-llama/dllama-api"):
        if not build_distributed_llama():
            logger.error("Failed to build distributed-llama")
            return False
    
    # Change to distributed-llama directory
    os.chdir("distributed-llama")
    
    # Download the model
    logger.info(f"Downloading model: {model_name}")
    print(f"\nDownloading model: {model_name}")
    print(f"This may take a while depending on your internet connection.")
    print(f"Model size: {model_info['size_gb']} GB\n")
    
    try:
        # Run the launch.py script with the model name
        cmd = ["python", "launch.py", model_name]
        print(f"Running command: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Print output in real-time
        for line in process.stdout:
            print(line, end='')
        
        process.wait()
        
        if process.returncode != 0:
            stderr = process.stderr.read()
            logger.error(f"Failed to download model: {stderr}")
            print(f"Error: Failed to download model: {stderr}")
            return False
        
    except Exception as e:
        logger.error(f"Error running launch.py: {e}")
        print(f"Error: Failed to run launch.py: {e}")
        return False
    
    # Check if files exist
    if not os.path.exists(model_file):
        logger.error(f"Model file not found: {model_file}")
        print(f"Error: Model file not found: {model_file}")
        return False
    
    if not os.path.exists(tokenizer_file):
        logger.error(f"Tokenizer file not found: {tokenizer_file}")
        print(f"Error: Tokenizer file not found: {tokenizer_file}")
        return False
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Copy files
    logger.info(f"Copying model files to {output_dir}")
    print(f"Copying model files to {output_dir}...")
    
    # Calculate full paths
    source_model_path = os.path.join(os.getcwd(), model_file)
    source_tokenizer_path = os.path.join(os.getcwd(), tokenizer_file)
    
    # Copy the files
    shutil.copy(source_model_path, model_path)
    shutil.copy(source_tokenizer_path, tokenizer_path)
    
    # Go back to original directory
    os.chdir("..")
    
    logger.info("Model download and preparation complete")
    print("\nModel download and preparation complete!")
    print(f"Model file: {model_path}")
    print(f"Tokenizer file: {tokenizer_path}")
    
    return True

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Download and prepare models for distributed-llama")
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", ""),
                      help="Model to download")
    parser.add_argument("--output-dir", default=os.environ.get("OUTPUT_DIR", "/models"),
                      help="Directory to save model files (default: /models)")
    parser.add_argument("--interactive", action="store_true",
                      help="Force interactive mode even if model is specified")
    parser.add_argument("--list", action="store_true",
                      help="List available models and exit")
    
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable models for distributed-llama:")
        print(f"{'Model Name':<35} {'Size':<10} {'RAM Needed':<20} Description")
        print("-" * 100)
        for name, info in AVAILABLE_MODELS.items():
            print(f"{name:<35} {info['size_gb']+' GB':<10} {info['recommended_ram']:<20} {info['description']}")
        sys.exit(0)
    
    # Use interactive selection if no model specified or interactive flag is set
    if not args.model or args.interactive:
        args.model = interactive_model_selection()
    
    # Download the requested model
    success = download_model(args.model, args.output_dir)
    
    if not success:
        logger.error("Failed to download model")
        sys.exit(1)
    
    print(f"\nModel {args.model} successfully prepared in {args.output_dir}")
    print("\nYou can now use it with your distributed-llama setup!")
    print("\nExample usage:")
    print(f"./dllama inference --model {args.output_dir}/{AVAILABLE_MODELS[args.model]['model_file']} --tokenizer {args.output_dir}/{AVAILABLE_MODELS[args.model]['tokenizer_file']} --buffer-float-type q80 --prompt \"Hello world\" --steps 16 --nthreads 4")
    
if __name__ == "__main__":
    main()