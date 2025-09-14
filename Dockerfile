# --- STAGE 1: Builder ---
FROM python:3.11-slim-bullseye AS builder

# Build argümanlarını build aşamasında kullanılabilir yap
ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"

WORKDIR /app

ENV PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_NO_CACHE_DIR=1 \
    COQUI_TOS_AGREED=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential ffmpeg git && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY app ./app
COPY README.md .
COPY docs ./docs
RUN pip install . --extra-index-url https://download.pytorch.org/whl/cpu
RUN python -c "from TTS.api import TTS; TTS(model_name='tts_models/multilingual/multi-dataset/xtts_v2')"

# --- STAGE 2: Production ---
FROM python:3.11-slim-bullseye

WORKDIR /app

ENV COQUI_TOS_AGREED=1

RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 ffmpeg curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Güvenlik için root olmayan bir kullanıcı oluştur
RUN useradd -m -u 1001 appuser

# --- EN KRİTİK DEĞİŞİKLİK BURADA ---
# Modelleri, builder'daki /root/.local/share/tts klasöründen,
# final imajdaki /home/appuser/.local/share/tts klasörüne kopyalıyoruz.
COPY --from=builder --chown=appuser:appuser /root/.local/share/tts /home/appuser/.local/share/tts

# Uygulama kodunu ve referans ses dosyasını kopyala
COPY ./app ./app
COPY ./docs /app/docs

# Dosya sahipliğini yeni kullanıcıya ver (sadece /app için yeterli)
RUN chown -R appuser:appuser /app

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "14030"]