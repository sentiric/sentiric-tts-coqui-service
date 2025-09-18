# ======================================================================================
#    SENTIRIC COQUI TTS SERVICE - CI/CD & ÜRETİM OPTİMİZASYONLU DOCKERFILE v2.2
# ======================================================================================

# --- GLOBAL BUILD ARGÜMANLARI ---
ARG PYTHON_VERSION=3.11
ARG BASE_IMAGE_TAG=${PYTHON_VERSION}-slim-bullseye
ARG PYTORCH_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"
ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"

# ======================================================================================
#    STAGE 1: BUILDER - Sadece Python bağımlılıklarını kurar
# ======================================================================================
FROM python:${BASE_IMAGE_TAG} AS builder

WORKDIR /app

ENV PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_NO_CACHE_DIR=1

# --- Sistem Bağımlılıkları (Sadece build için gerekenler) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml setup.py README.md ./
COPY app ./app

# Sadece bağımlılıkları kur, projeyi kurma
RUN pip install --prefix=/install . --no-deps --extra-index-url "${PYTORCH_EXTRA_INDEX_URL}"

# ======================================================================================
#    STAGE 2: PRODUCTION - Hafif ve temiz imaj
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
    PYTHONUNBUFFERED=1

# --- Çalışma zamanı sistem bağımlılıkları ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    ca-certificates \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# --- Bağımlılıkları Kopyala ---
COPY --from=builder /install /usr/local

# --- Güvenlik ve uygulama kurulumu ---
RUN useradd -m -u 1001 appuser
COPY ./app ./app
COPY ./docs /app/docs
RUN chown -R appuser:appuser /app

USER appuser

# Model, `/home/appuser/.local/share/tts` altına indirilecek.
# Bu dizin, bir Docker Volume olarak bağlanmalıdır.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "14030", "--timeout-graceful-shutdown", "15"]