# ======================================================================================
#    SENTIRIC COQUI TTS SERVICE - POETRY & ÜRETİM OPTİMİZASYONLU DOCKERFILE v2.7
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

# Bağımlılıkları kur
RUN poetry install --without dev --no-root --sync

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

# --- DÜZELTME BURADA BAŞLIYOR ---
# Önce kullanıcı ve grubu oluştur
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --no-create-home --uid 1001 --ingroup appgroup appuser

# Bağımlılıkları kopyala
COPY --from=builder /app/.venv ./.venv

# Uygulama kodunu kopyala
COPY ./app ./app
COPY ./docs /app/docs

# Tüm dosyaların sahipliğini tek seferde değiştir
RUN chown -R appuser:appgroup /app
# --- DÜZELTME SONU ---

USER appuser

# Model, `/home/appuser/.local/share/tts` altına indirilecek.
# Bu dizin, bir Docker Volume olarak bağlanmalıdır.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "14030", "--timeout-graceful-shutdown", "15"]