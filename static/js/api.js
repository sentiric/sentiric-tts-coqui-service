class API {
    static async getHealth() {
        const res = await fetch('/health');
        return res.json();
    }

    static async getHistory() {
        const res = await fetch('/api/history');
        return res.json();
    }

    static async getSpeakers() {
        const res = await fetch('/api/speakers');
        return res.json();
    }

    static async refreshSpeakers() {
        const res = await fetch('/api/speakers/refresh', { method: 'POST' });
        return res.json();
    }

    static async deleteHistory(filename) {
        const res = await fetch(`/api/history/${filename}`, { method: 'DELETE' });
        return res.ok;
    }

    static async deleteAllHistory() {
        const res = await fetch('/api/history/all', { method: 'DELETE' });
        return res.json();
    }

    static async generateTTS(params, signal) {
        const response = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params),
            signal: signal
        });
        if (!response.ok) throw new Error(await response.text());
        return response;
    }

    static async generateClone(formData, signal) {
        const response = await fetch('/api/tts/clone', {
            method: 'POST',
            body: formData,
            signal: signal
        });
        if (!response.ok) throw new Error(await response.text());
        return response;
    }
}