# ======================================================================================
#    SENTIRIC COQUI TTS SERVICE - OPTIMIZE EDİLMİŞ VE ÖLÇEKLENEBİLİR DOCKERFILE v2.1
# ======================================================================================

# --- GLOBAL BUILD ARGÜMANLARI ---
ARG PYTHON_VERSION=3.11
ARG BASE_IMAGE_TAG=${PYTHON_VERSION}-slim-bullseye
ARG PYTORCH_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"
ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"

# ======================================================================================
#    STAGE 1: BUILDER
# ======================================================================================
FROM python:${BASE_IMAGE_TAG} AS builder

ENV PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_NO_CACHE_DIR=1 \
    COQUI_TOS_AGREED=1 \
    NUMBA_CACHE_DIR=/tmp/numba_cache \
    MPLCONFIGDIR=/tmp/matplotlib \
    TRANSFORMERS_CACHE=/tmp/transformers_cache \
    HF_HOME=/tmp/transformers_cache \
    TORCH_HOME=/tmp/torch_cache

WORKDIR /app

# --- Cache dizinlerini oluştur ---
RUN mkdir -p /tmp/numba_cache /tmp/matplotlib /tmp/transformers_cache /tmp/torch_cache && \
    chmod 777 /tmp/numba_cache /tmp/matplotlib /tmp/transformers_cache /tmp/torch_cache

# --- Sistem Bağımlılıkları ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install . --extra-index-url "${PYTORCH_EXTRA_INDEX_URL}"
# --- Modeli önceden indir --- + 1.8 GB
RUN python -c "from TTS.api import TTS; TTS(model_name='tts_models/multilingual/multi-dataset/xtts_v2')"

# ======================================================================================
#    STAGE 2: PRODUCTION
# ======================================================================================
FROM python:${BASE_IMAGE_TAG} AS production

WORKDIR /app

# --- Build zamanı bilgileri ---
ARG GIT_COMMIT
ARG BUILD_DATE
ARG SERVICE_VERSION
ENV GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE} \
    SERVICE_VERSION=${SERVICE_VERSION} \
    COQUI_TOS_AGREED=1 \
    PYTHONUNBUFFERED=1 \
    NUMBA_CACHE_DIR=/tmp/numba_cache \
    MPLCONFIGDIR=/tmp/matplotlib \
    TRANSFORMERS_CACHE=/tmp/transformers_cache \
    HF_HOME=/tmp/transformers_cache \
    TORCH_HOME=/tmp/torch_cache \
    XDG_CACHE_HOME=/tmp

# --- Cache dizinlerini oluştur ---
RUN mkdir -p /tmp/numba_cache /tmp/matplotlib /tmp/transformers_cache /tmp/torch_cache && \
    chmod 777 /tmp/numba_cache /tmp/matplotlib /tmp/transformers_cache /tmp/torch_cache

# --- Çalışma zamanı sistem bağımlılıkları ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    ca-certificates \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*


# --- Builder'dan dosyaları kopyala ---
# 7.45 GB
COPY --from=builder /usr/local /usr/local
# 1.8 GB
COPY --from=builder --chown=appuser:appuser /root/.local/share/tts /home/appuser/.local/share/tts
# 9.30 GB ~

# --- Güvenlik ve uygulama kurulumu ---
RUN useradd -m -u 1001 appuser
COPY ./app ./app
COPY ./docs /app/docs
RUN chown -R appuser:appuser /app

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "14030", "--timeout-graceful-shutdown", "15"]