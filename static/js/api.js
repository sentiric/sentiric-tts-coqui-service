// Dosya: static/js/api.js

function getHeaders() {
    return {
        'Content-Type': 'application/json',
        //[ARCH-COMPLIANCE] Strict Tenant Isolation ve Tracing gereksinimleri
        'x-tenant-id': 'sentiric_studio', 
        'x-trace-id': 'ui-req-' + Date.now()
    };
}

class API {
    static async getConfig() {
        try {
            const response = await fetch('/api/config', { headers: getHeaders() });
            if (!response.ok) throw new Error(`Config fetch failed: ${response.statusText}`);
            return await response.json();
        } catch (e) {
            console.error("Configuration could not be loaded:", e);
            return null;
        }
    }

    static async getHealth() {
        try {
            const response = await fetch('/health', { headers: getHeaders() });
            return await response.json();
        } catch { return { status: "down" }; }
    }

    static async getHistory() {
        const response = await fetch('/api/history', { headers: getHeaders() });
        return await response.json();
    }

    static async getSpeakers() {
        const response = await fetch('/api/speakers', { headers: getHeaders() });
        return await response.json();
    }

    static async refreshSpeakers() {
        const response = await fetch('/api/speakers/refresh', { method: 'POST', headers: getHeaders() });
        return await response.json();
    }

    static async deleteHistory(filename) {
        const response = await fetch(`/api/history/${filename}`, { method: 'DELETE', headers: getHeaders() });
        return response.ok;
    }

    static async deleteAllHistory() {
        const response = await fetch('/api/history/all', { method: 'DELETE', headers: getHeaders() });
        return await response.json();
    }

    static async generateTTS(params, signal) {
        const response = await fetch('/api/tts', {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(params),
            signal: signal
        });

        if (!response.ok) {
            let detail = response.statusText;
            try {
                const errorData = await response.json();
                detail = errorData.error || errorData.detail || detail;
            } catch (e) {}
            throw new Error(detail || "TTS Generation Failed");
        }

        this._dispatchVCA(response.headers);
        return response;
    }

    static async generateClone(formData, signal) {
        const response = await fetch('/api/tts/clone', {
            method: 'POST',
            headers: {
                'x-tenant-id': 'sentiric_studio',
                'x-trace-id': 'ui-req-' + Date.now()
            },
            body: formData,
            signal: signal
        });

        if (!response.ok) {
            let detail = response.statusText;
            try {
                const errorData = await response.json();
                detail = errorData.error || errorData.detail || detail;
            } catch (e) {}
            throw new Error(detail || "Voice Cloning Failed");
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