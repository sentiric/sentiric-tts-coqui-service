#!/bin/sh

# Hata durumunda script'i sonlandır
set -e

# Gerekli dizinlerin mevcut ve yazılabilir olduğundan emin ol
# Bu dizinler Docker Volume olarak bağlanacak
mkdir -p /home/appuser/.cache/torch
mkdir -p /home/appuser/.local/share/tts
chown -R appuser:appgroup /home/appuser/.cache
chown -R appuser:appgroup /home/appuser/.local

echo "✅ Cache dizinleri hazırlandı."
echo "🚀 Uvicorn sunucusu başlatılıyor..."

# Ana uygulamayı başlat
exec uvicorn app.main:app --host "0.0.0.0" --port "14030" --timeout-graceful-shutdown 15