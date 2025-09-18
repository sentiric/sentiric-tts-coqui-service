# ======================================================================================
#    SENTIRIC COQUI TTS SERVICE - RUNTIME INSTALL DOCKERFILE v3.0
# ======================================================================================

ARG PYTHON_VERSION=3.11
ARG BASE_IMAGE_TAG=${PYTHON_VERSION}-slim-bullseye
ARG PYTORCH_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"

# --- Production imajı artık tek aşamalı ---
FROM python:${BASE_IMAGE_TAG}

WORKDIR /app

# --- Build zamanı bilgileri ---
ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"
ARG PYTORCH_EXTRA_INDEX_URL
ENV GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE} \
    SERVICE_VERSION=${SERVICE_VERSION} \
    COQUI_TOS_AGREED=1 \
    PYTHONUNBUFFERED=1 \
    # ÖNEMLİ: Cache dizinlerini appuser'ın home dizinine yönlendir
    HF_HOME="/home/appuser/.cache/huggingface" \
    TORCH_HOME="/home/appuser/.cache/torch"

# --- Çalışma zamanı ve kurulum için sistem bağımlılıkları ---
# git, build-essential ve pip artık runtime'da gerekli
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    ca-certificates \
    libsndfile1 \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# --- Uygulama dosyalarını kopyala ---
COPY pyproject.toml poetry.lock ./
COPY app ./app
COPY docs ./docs
COPY scripts/entrypoint.sh /entrypoint.sh

# --- Kurulum ve İzinler ---
# Önce kullanıcıyı oluştur, sonra dosyaları kopyala ve izinleri ayarla
RUN useradd -m -u 1001 appuser && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-root --sync --extra-index-url "${PYTORCH_EXTRA_INDEX_URL}" && \
    chmod +x /entrypoint.sh && \
    chown -R appuser:appgroup /app /home/appuser

USER appuser

ENTRYPOINT ["/entrypoint.sh"]