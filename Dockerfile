# ======================================================================================
#    SENTIRIC COQUI TTS SERVICE - POETRY & ÜRETİM OPTİMİZASYONLU DOCKERFILE v2.6
# ======================================================================================

# --- GLOBAL BUILD ARGÜMANLARI ---
ARG PYTHON_VERSION=3.11
ARG BASE_IMAGE_TAG=${PYTHON_VERSION}-slim-bullseye
ARG PYTORCH_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"

# ======================================================================================
#    STAGE 1: BUILDER - Python bağımlılıklarını kurar
# ======================================================================================
FROM python:${BASE_IMAGE_TAG} AS builder

ARG PYTORCH_EXTRA_INDEX_URL

WORKDIR /app

ENV PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

# --- Sistem Bağımlılıkları (git dahil) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Poetry'yi kur
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir poetry

# Sadece bağımlılık tanımlarını kopyala
COPY poetry.lock pyproject.toml ./

# --- DÜZELTME BURADA ---
# Bağımlılıkları kur (üretim için, dev bağımlılıkları hariç)
# --no-dev yerine --without dev kullanılıyor.
RUN poetry install --without dev --no-root --sync
# --- DÜZELTME SONU ---


# ======================================================================================
#    STAGE 2: PRODUCTION - Hafif ve temiz imaj
# ======================================================================================
FROM python:${BASE_IMAGE_TAG}

WORKDIR /app

# --- Build zamanı bilgileri ---
ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"
ENV GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE} \
    SERVICE_VERSION=${SERVICE_VERSION} \
    COQUI_TOS_AGREED=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# --- Çalışma zamanı sistem bağımlılıkları ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    ca-certificates \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# --- Bağımlılıkları Kopyala ---
COPY --from=builder /app/.venv ./.venv

# --- Güvenlik ve uygulama kurulumu ---
RUN useradd -m -u 1001 appuser
COPY ./app ./app
COPY ./docs /app/docs
RUN chown -R appuser:appgroup /app

USER appuser

# Model, `/home/appuser/.local/share/tts` altına indirilecek.
# Bu dizin, bir Docker Volume olarak bağlanmalıdır.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "14030", "--timeout-graceful-shutdown", "15"]