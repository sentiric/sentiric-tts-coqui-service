class API {
    static async getConfig() {
        try {
            const response = await fetch('/api/config');
            if (!response.ok) throw new Error(`Config fetch failed: ${response.statusText}`);
            return await response.json();
        } catch (e) {
            console.error("Configuration could not be loaded:", e);
            // Fallback config (Acil durumlar için)
            return null;
        }
    }

    static async getHealth() {
        try {
            const response = await fetch('/health');
            return await response.json();
        } catch { return { status: "down" }; }
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
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(errorData.detail || "TTS Generation Failed");
        }

        this._dispatchVCA(response.headers);
        return response;
    }

    static async generateClone(formData, signal) {
        const response = await fetch('/api/tts/clone', {
            method: 'POST',
            body: formData,
            signal: signal
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(errorData.detail || "Voice Cloning Failed");
        }

        this._dispatchVCA(response.headers);
        return response;
    }

    static _dispatchVCA(headers) {
        const charCount = headers.get("X-VCA-Chars");
        const time = headers.get("X-VCA-Time");
        const rtf = headers.get("X-VCA-RTF");

        if (time) {
            const event = new CustomEvent('vca-update', { 
                detail: { chars: charCount, time: time, rtf: rtf } 
            });
            document.dispatchEvent(event);
        }
    }
}