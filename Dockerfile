# ======================================================================================
#    SENTIRIC COQUI TTS SERVICE - POETRY VENV & PRODUCTION-READY DOCKERFILE v3.2
# ======================================================================================

# --- GLOBAL BUILD ARGÜMANLARI ---
ARG PYTHON_VERSION=3.11
ARG BASE_IMAGE_TAG=${PYTHON_VERSION}-slim-bullseye
ARG PYTORCH_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"

# ======================================================================================
#    STAGE 1: BUILDER - İzole sanal ortamda bağımlılıkları kurar
# ======================================================================================
FROM python:${BASE_IMAGE_TAG} AS builder

ARG PYTORCH_EXTRA_INDEX_URL

WORKDIR /app

ENV PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_NO_INTERACTION=1 \
    # --- DÜZELTME: Sanal ortamı proje klasörü içinde oluşturmaya ZORLUYORUZ ---
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

# Bağımlılıkları .venv klasörü içinde izole bir şekilde kur
RUN poetry install --without dev --no-root --sync --extra-index-url "${PYTORCH_EXTRA_INDEX_URL}"

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
    # --- DÜZELTME: PATH'i sanal ortamı kullanacak şekilde ayarla ---
    PATH="/app/.venv/bin:$PATH"

# --- Çalışma zamanı sistem bağımlılıkları ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    ca-certificates \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# --- DÜZELTME: Kullanıcı ve grup oluşturma ---
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --no-create-home --uid 1001 --ingroup appgroup appuser

# --- Bağımlılıkları ve uygulama kodunu kopyala ---
COPY --from=builder --chown=appuser:appgroup /app/.venv ./.venv
COPY --chown=appuser:appgroup ./app ./app
COPY --chown=appuser:appgroup ./docs ./docs
COPY --chown=appuser:appgroup scripts/entrypoint.sh /entrypoint.sh

# --- İzinleri ayarla ---
RUN chmod +x /entrypoint.sh

USER appuser

ENTRYPOINT ["/entrypoint.sh"]