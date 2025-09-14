# ======================================================================================
#    SENTIRIC COQUI TTS SERVICE - OPTIMIZE EDİLMİŞ VE ÖLÇEKLENEBİLİR DOCKERFILE v2.0
# ======================================================================================
# HEDEFLER:
# 1. PERFORMANS: Docker katman önbelleklemesini (layer caching) maksimize ederek
#    kod değişikliklerinde yeniden build sürelerini dramatik şekilde düşürmek.
# 2. ÖLÇEKLENEBİLİRLİK: Tek bir build argümanı ile kolayca CPU ve GPU imajları
#    arasında geçiş yapabilme yeteneği.
# 3. GÖZLEMLENEBİLİRLİK: Build zamanındaki versiyon, commit gibi bilgileri
#    çalışma zamanında uygulamaya ortam değişkeni olarak aktarmak.
# ======================================================================================

# --- GLOBAL BUILD ARGÜMANLARI ---
# Bu argümanlar, build komutu sırasında dışarıdan değiştirilebilir.
ARG PYTHON_VERSION=3.11
ARG BASE_IMAGE_TAG=${PYTHON_VERSION}-slim-bullseye
ARG PYTORCH_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"

# Uygulama versiyonu için build argümanları
ARG GIT_COMMIT="unknown"
ARG BUILD_DATE="unknown"
ARG SERVICE_VERSION="0.0.0"


# ======================================================================================
#    STAGE 1: BUILDER - Bağımlılıkları derleyen ve modeli indiren katman
# ======================================================================================
FROM python:${BASE_IMAGE_TAG} AS builder

# --- Ortam Değişkenleri ---
# AÇIKLAMA: Bu değişkenler build işlemi sırasında gereklidir.
# COQUI_TOS_AGREED=1: Coqui TTS'in kullanım koşullarını otomatik olarak kabul eder.
# PIP_NO_CACHE_DIR=1: Gereksiz önbellek dosyalarını imajda tutmayarak boyutu küçültür.
ENV PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_NO_CACHE_DIR=1 \
    COQUI_TOS_AGREED=1

WORKDIR /app

# --- Sistem Bağımlılıkları ---
# AÇIKLAMA: Python paketlerinin derlenmesi için gerekli olan build-essential ve git'i kurar.
# Bu katman sadece bu komut değiştiğinde yeniden çalışır (çok nadir).
RUN apt-get update && apt-get install -y --no-install-recommends build-essential ffmpeg git && rm -rf /var/lib/apt/lists/*

# --- PERFORMANS OPTİMİZASYONU: Katmanları Ayırma ---

# 1. Adım: Sadece bağımlılık listesini kopyala.
# AÇIKLAMA: Bu katman, sadece pyproject.toml dosyası değiştiğinde yeniden çalışır.
COPY pyproject.toml .

# 2. Adım: Python bağımlılıklarını kur.
# AÇIKLAMA: Bu en uzun süren adımlardan biridir. Artık sadece bağımlılıklar
# değiştiğinde çalışacak, kodunuz değiştiğinde önbellekten kullanılacaktır.
# PYTORCH_EXTRA_INDEX_URL argümanı sayesinde CPU/GPU seçimi yapılır.
RUN pip install . --extra-index-url ${PYTORCH_EXTRA_INDEX_URL}

# 3. Adım: Ağır AI modelini indir.
# AÇIKLAMA: Bu da çok uzun süren bir adımdır. Bağımlılıklardan sonra ayrı bir
# katmanda tutarak kod değişikliklerinden etkilenmemesini sağlıyoruz.
RUN python -c "from TTS.api import TTS; TTS(model_name='tts_models/multilingual/multi-dataset/xtts_v2')"

# 4. Adım: Uygulama kodunu en son kopyala.
# AÇIKLAMA: En sık değişen kısım kod olduğu için, onu en sona koyarak Docker'ın
# önceki tüm adımları önbellekten kullanmasını sağlıyoruz.
COPY app ./app
COPY README.md .
COPY docs ./docs


# ======================================================================================
#    STAGE 2: PRODUCTION - Çalıştırılacak olan nihai, hafif imaj
# ======================================================================================
FROM python:${BASE_IMAGE_TAG} AS production

WORKDIR /app

# --- Build Zamanı Bilgilerini Çalışma Zamanına Taşıma ---
# AÇIKLAMA: Global ARG'ları bu katmanda tekrar tanımlayıp ENV'e atayarak
# uygulamanızın (örneğin main.py'deki logger) bu bilgilere erişmesini sağlıyoruz.
ARG GIT_COMMIT
ARG BUILD_DATE
ARG SERVICE_VERSION
ENV GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE} \
    SERVICE_VERSION=${SERVICE_VERSION}

# --- Çalışma Zamanı Ortam Değişkenleri ---
# AÇIKLAMA: Uygulamanın düzgün çalışması için gerekli olan değişkenler.
# PYTHONUNBUFFERED=1: Logların anında konsola düşmesini sağlar, Docker için standarttır.
ENV COQUI_TOS_AGREED=1 \
    PYTHONUNBUFFERED=1

# --- Çalışma Zamanı Sistem Bağımlılıkları ---
# AÇIKLAMA: Sadece uygulamanın çalışması için gerekli olan kütüphaneleri kurarız.
# 'build-essential' gibi derleme araçlarını buraya kurmayarak imajı küçük tutarız.
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 ffmpeg curl && rm -rf /var/lib/apt/lists/*

# --- Builder Katmanından Gerekli Dosyaları Kopyalama ---
# AÇIKLAMA: Kurulmuş Python paketlerini, çalıştırılabilir dosyaları ve indirilmiş AI modelini
# builder imajından nihai imajımıza kopyalıyoruz.
COPY --from=builder /usr/local /usr/local
COPY --from=builder --chown=appuser:appuser /root/.local/share/tts /home/appuser/.local/share/tts

# --- Güvenlik ve Uygulama Kurulumu ---
# AÇIKLAMA: Root olmayan bir kullanıcı oluşturup, uygulama dosyalarını kopyalayıp
# yetkilerini bu kullanıcıya vererek güvenliği artırıyoruz.
RUN useradd -m -u 1001 appuser
COPY ./app ./app
COPY ./docs /app/docs
RUN chown -R appuser:appuser /app

USER appuser

# --- Uygulamayı Başlatma ---
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "14030", "--timeout-graceful-shutdown", "15"]