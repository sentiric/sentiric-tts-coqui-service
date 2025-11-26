class API {
    /**
     * Sunucu sağlık durumunu kontrol eder.
     */
    static async getHealth() {
        const response = await fetch('/health');
        return await response.json();
    }

    /**
     * Geçmiş kayıtlarını getirir.
     */
    static async getHistory() {
        const response = await fetch('/api/history');
        return await response.json();
    }

    /**
     * Mevcut konuşmacı listesini getirir.
     */
    static async getSpeakers() {
        const response = await fetch('/api/speakers');
        return await response.json();
    }

    /**
     * Sunucudaki konuşmacı listesini diskten tekrar tarar.
     */
    static async refreshSpeakers() {
        const response = await fetch('/api/speakers/refresh', {
            method: 'POST'
        });
        return await response.json();
    }

    /**
     * Tekil bir geçmiş kaydını siler.
     */
    static async deleteHistory(filename) {
        const response = await fetch(`/api/history/${filename}`, {
            method: 'DELETE'
        });
        return response.ok;
    }

    /**
     * Tüm geçmişi ve önbelleği temizler.
     */
    static async deleteAllHistory() {
        const response = await fetch('/api/history/all', {
            method: 'DELETE'
        });
        return await response.json();
    }

    /**
     * Standart TTS isteği gönderir.
     */
    static async generateTTS(params, signal) {
        const response = await fetch('/api/tts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(params),
            signal: signal // İptal (Abort) sinyali için
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText);
        }
        return response;
    }

    /**
     * Ses Klonlama isteği gönderir (FormData kullanır).
     */
    static async generateClone(formData, signal) {
        const response = await fetch('/api/tts/clone', {
            method: 'POST',
            body: formData,
            signal: signal
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText);
        }
        return response;
    }
}