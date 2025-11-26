# 1. Base Image
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# 2. System Deps
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-dev \
    python3-pip \
    python3-venv \
    libsndfile1 \
    curl \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 3. UV Installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Python alias
RUN ln -s /usr/bin/python3.10 /usr/bin/python

# 4. Env Setup
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Venv oluştur
RUN uv venv $VIRTUAL_ENV --python /usr/bin/python3.10

# 5. Dependencies
# Phase 1: PyTorch (CUDA için özel index-url gerektiğinden burayı manuel yapıyoruz)
RUN uv pip install --no-cache \
    torch==2.1.2 \
    torchaudio==2.1.2 \
    --index-url https://download.pytorch.org/whl/cu121

# Phase 2: Tüm diğer bağımlılıklar requirements.txt'den okunur
COPY requirements.txt .
RUN uv pip install --no-cache -r requirements.txt

# Copy Code
COPY . .

# Create cache & speakers dir
RUN mkdir -p /root/.local/share/tts && mkdir -p /app/speakers

EXPOSE 14030 14031 14032

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "14030"]