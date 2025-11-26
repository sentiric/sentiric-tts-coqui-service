class API {
    static async getHealth() {
        const response = await fetch('/health');
        return await response.json();
    }

    static async getHistory() {
        const response = await fetch('/api/history');
        return await response.json();
    }

    static async getSpeakers() {
        const response = await fetch('/api/speakers');
        return await response.json();
    }

    static async refreshSpeakers() {
        const response = await fetch('/api/speakers/refresh', { method: 'POST' });
        return await response.json();
    }

    static async deleteHistory(filename) {
        const response = await fetch(`/api/history/${filename}`, { method: 'DELETE' });
        return response.ok;
    }

    static async deleteAllHistory() {
        const response = await fetch('/api/history/all', { method: 'DELETE' });
        return await response.json();
    }

    static async generateTTS(params, signal) {
        const response = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params),
            signal: signal
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText);
        }

        this._dispatchVCA(response.headers);
        return response;
    }

    static async generateClone(formData, signal) {
        // ... (Aynı kalıyor) ...
        const response = await fetch('/api/tts/clone', {
            method: 'POST',
            body: formData,
            signal: signal
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText);
        }

        this._dispatchVCA(response.headers);
        return response;
    }

    // Özel Yardımcı: VCA Olayını Tetikle
    static _dispatchVCA(headers) {
        const charCount = headers.get("X-VCA-Chars");
        const time = headers.get("X-VCA-Time");
        const rtf = headers.get("X-VCA-RTF");

        // DEBUG LOG (Konsolu kontrol et)
        console.log("📊 VCA Headers:", { charCount, time, rtf });

        if (time) {
            const event = new CustomEvent('vca-update', { 
                detail: { chars: charCount, time: time, rtf: rtf } 
            });
            document.dispatchEvent(event);
        } else {
            console.warn("⚠️ VCA Headers not found! Check Backend CORS settings.");
        }
    }
}