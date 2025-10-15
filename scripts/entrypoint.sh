### 📄 File: tts-coqui-service/scripts/entrypoint.sh (DÜZELTİLMİŞ)

#!/bin/sh

# Hata durumunda script'i sonlandır
set -e

# Gerekli dizinlerin mevcut ve yazılabilir olduğundan emin ol
mkdir -p /home/appuser/.cache/torch
mkdir -p /home/appuser/.local/share/tts
chown -R appuser:appgroup /home/appuser/.cache
chown -R appuser:appgroup /home/appuser/.local

echo "✅ Cache dizinleri hazırlandı."
echo "🚀 Uvicorn sunucusu başlatılıyor..."

# --- DÜZELTME: uvicorn komutunu tam yoluyla çağırıyoruz ---
exec /app/.venv/bin/uvicorn app.main:app --host "0.0.0.0" --port "14030" --timeout-graceful-shutdown 15 --log-config null