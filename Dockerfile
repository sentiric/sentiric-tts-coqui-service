# 1️⃣ Base Image
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# 2️⃣ Sistem bağımlılıkları
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

# 3️⃣ UV Installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Python alias
RUN ln -s /usr/bin/python3.10 /usr/bin/python

# 4️⃣ Virtual environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN uv venv $VIRTUAL_ENV --python /usr/bin/python3.10

# 5️⃣ Dependencies
# PyTorch (CUDA)
RUN uv pip install --no-cache \
    torch==2.1.2 \
    torchaudio==2.1.2 \
    --index-url https://download.pytorch.org/whl/cu121

# Diğer bağımlılıklar
COPY requirements.txt .
RUN uv pip install --no-cache -r requirements.txt

# 6️⃣ Copy uygulama kodu
COPY . .

# 7️⃣ Cache & speakers dizinleri
RUN mkdir -p /root/.local/share/tts && mkdir -p /app/speakers

# 8️⃣ Environment değişkenleri
# Python warningleri bastır
ENV PYTHONWARNINGS="ignore"

# 9️⃣ Portlar
EXPOSE 14030 14031 14032

# 10️⃣ CMD
# --no-access-log ile HTTP istek loglarını kapatıyoruz
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "14030", "--no-access-log"]
