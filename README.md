# Sentiric XTTS v2 Microservice

Production-ready, GPU-accelerated Text-to-Speech microservice based on Coqui XTTS v2. Supports multilingual synthesis, voice cloning, and streaming capabilities via REST API and Gradio UI.

## Features

- 🚀 **High Performance:** Async inference engine with GPU locking mechanisms.
- 🐳 **Docker Ready:** Full NVIDIA GPU passthrough support with `docker-compose`.
- 🔄 **API & UI:** FastAPI for service-to-service communication, Gradio for human interaction.
- 💾 **Persistent Caching:** Models are downloaded once and persisted via volumes.
- 🛡️ **Product Ready:** Structured architecture, type checking, and health monitoring.

## Prerequisites

- **Docker** & **Docker Compose**
- **NVIDIA Drivers** & **NVIDIA Container Toolkit** (for GPU support)
- *Optional:* Python 3.10+ (for local development)

## Quick Start (Docker)

1. **Clone & Config:**
   ```bash
   git clone <repo_url>
   cd sentiric-tts-coqui-service-proto-1
   cp .env.example .env
   ```

2. **Run Service:**
   ```bash
   make build
   make up
   ```
   *Note: First run will download ~3GB model data. Check logs:* `make logs`

3. **Access:**
   - **Swagger API:** [http://localhost:14030/docs](http://localhost:14030/docs)
   - **Gradio UI:** [http://localhost:14030/ui](http://localhost:14030/ui)

## API Usage

### 1. Health Check
```bash
curl -X GET http://localhost:14030/health
```

### 2. Basic TTS (Standard Voice)
```bash
curl -X POST "http://localhost:14030/api/tts" \
     -H "Content-Type: application/json" \
     -d '{
           "text": "Hello, this is a production ready service.",
           "language": "en",
           "speaker_idx": "Ana Florence",
           "temperature": 0.7
         }' \
     --output output.wav
```

### 3. Voice Cloning
```bash
curl -X POST "http://localhost:14030/api/tts/clone" \
     -F "text=I am speaking with your voice now." \
     -F "language=en" \
     -F "files=@/path/to/your/sample_voice.wav" \
     --output cloned_output.wav
```

## Local Development Setup

If you want to run without Docker:

1. **Install Dependencies:**
   ```bash
   # Create venv
   python3 -m venv venv
   source venv/bin/activate
   
   # Install Core with CUDA support
   pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu118
   ```

2. **Run Server:**
   ```bash
   make run-local
   ```

## Architecture

- **Engine (`app/core/engine.py`):** Singleton class handling Model memory management and Thread-Safe inference locking.
- **API (`app/main.py`):** FastAPI endpoints exposing the engine.
- **UI:** Gradio Interface mounted within FastAPI application.

## Troubleshooting

- **CUDA Error:** Ensure `nvidia-smi` works on host and `nvidia-container-toolkit` is installed.
- **Download Stuck:** Check internet connection. Models are saved in `./data/models`. You can manually clear this folder to retry.

---
