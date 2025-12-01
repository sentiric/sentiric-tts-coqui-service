/**
 * SENTIRIC XTTS PRO - MAIN CONTROLLER v1.2
 */

const State = {
    isPlaying: false,
    abortController: null,
    config: null // Backend konfigürasyonu burada saklanır
};

const Controllers = {
    
    async boot() {
        UI.setBootState(true, "Fetching Configuration...");
        try {
            // 1. Config'i Al
            State.config = await API.getConfig();
            if (!State.config) throw new Error("Config unreachable");
            
            // 2. UI'ı Config ile Başlat
            UI.initFromConfig(State.config);
            
            // 3. Hoparlörleri Yükle
            UI.setBootState(true, "Loading Voice Models...");
            await this.loadSpeakers();
            
            // 4. Geçmişi Yükle
            await this.loadHistory();
            
            // 5. Audio Context Hazırla
            if (window.initAudioContext) window.initAudioContext();

            // HAZIR
            UI.setBootState(false);
            UI.showToast("System Ready", "success");

        } catch (e) {
            console.error("Boot Error:", e);
            UI.setBootState(true, "Connection Failed. Retrying...");
            setTimeout(() => this.boot(), 3000); // Auto retry
        }
    },

    async loadSpeakers() {
        try {
            const data = await API.getSpeakers();
            UI.populateSpeakers(data);
        } catch (e) {
            UI.showToast("Speaker list failed", "error");
        }
    },

    async loadHistory() {
        try {
            const data = await API.getHistory();
            UI.renderHistory(data);
        } catch (e) { console.error(e); }
    },

    async rescanSpeakers() {
        UI.setStatus("SCANNING...");
        try {
            const res = await API.refreshSpeakers();
            UI.showToast(`Found ${res.data.total_scanned} files`, "success");
            await this.loadSpeakers();
        } catch (e) {
            UI.showToast(e.message, "error");
        } finally {
            UI.setStatus("READY");
        }
    },

    async clearAllHistory() {
        if (!confirm('Delete all history?')) return;
        try {
            const res = await API.deleteAllHistory();
            UI.showToast(`Deleted ${res.files_deleted} files`, "success");
            await this.loadHistory();
        } catch (e) { UI.showToast("Delete failed", "error"); }
    },

    async deleteHistory(filename) {
        if (!confirm('Delete entry?')) return;
        try {
            await API.deleteHistory(filename);
            // Optimistic update: Listeyi yeniden çekmek yerine DOM'dan sil
            // Ancak basitlik için yeniden yüklüyoruz
            await this.loadHistory(); 
        } catch (e) { UI.showToast("Delete failed", "error"); }
    },

    playHistory(filename) {
        if (State.isPlaying) this.stopPlayback(true);
        const url = `/api/history/audio/${filename}`;
        const player = document.getElementById('classicPlayer');
        if (player) {
            player.src = url;
            player.play();
            UI.setStatus("PLAYING HISTORY");
            player.onended = () => UI.setStatus("READY");
        }
    },

    stopPlayback(isUserInitiated = true) {
        if (isUserInitiated) {
            if (State.abortController) {
                State.abortController.abort();
                State.abortController = null;
            }
            if (window.resetAudioState) window.resetAudioState();
            
            const player = document.getElementById('classicPlayer');
            if (player) { player.pause(); player.currentTime = 0; }
            
            UI.showToast("Stopped", "info");
        }
        UI.setPlayingState(false);
        State.isPlaying = false;
    },

    // --- CLONE HANDLERS ---
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            if (window.clearRecordingData) window.clearRecordingData();
            UI.resetCloneUI(false);
            UI.updateFileName(file.name);
        }
    },

    handleRecordingComplete() {
        UI.resetCloneUI(true); 
        UI.showRecordingSuccess();
    },

    clearCloneData() {
        if (window.clearRecordingData) window.clearRecordingData();
        UI.resetCloneUI(true); 
    },

    // --- GENERATE ---
    async handleGenerate() {
        if (State.isPlaying) {
            this.stopPlayback(true);
            return;
        }

        const text = document.getElementById('textInput').value.trim();
        if (!text) return UI.showToast("Please enter text", "error");

        const isStream = document.getElementById('stream').checked;

        UI.setPlayingState(true);
        State.isPlaying = true;
        
        if (window.resetAudioState) window.resetAudioState();

        const startTime = performance.now();
        let firstChunk = false;

        try {
            State.abortController = new AbortController();
            
            const modePanel = document.getElementById('panel-std');
            const isCloneMode = modePanel.classList.contains('hidden');
            
            // Parametreleri UI'dan al (Varsayılanlar zaten UI'a config'den basılmıştı)
            const params = {
                text: text,
                language: document.getElementById('lang').value,
                temperature: parseFloat(document.getElementById('temp').value),
                speed: parseFloat(document.getElementById('speed').value),
                top_k: parseInt(document.getElementById('topk').value),
                top_p: parseFloat(document.getElementById('topp').value),
                repetition_penalty: parseFloat(document.getElementById('rep').value),
                stream: isStream,
                output_format: document.getElementById('format').value,
                // Sample rate UI'da yoksa config default'u kullan
                sample_rate: State.config ? State.config.defaults.sample_rate : 24000 
            };

            let response;

            if (!isCloneMode) {
                params.speaker_idx = document.getElementById('speaker').value;
                response = await API.generateTTS(params, State.abortController.signal);
            } else {
                const formData = new FormData();
                if (window.recordedBlob) {
                    formData.append('files', window.recordedBlob, 'recording.webm');
                } else {
                    const fileInput = document.getElementById('ref_audio');
                    const file = fileInput ? fileInput.files[0] : null;
                    if (!file) throw new Error("Upload a file or record audio");
                    formData.append('files', file);
                }
                Object.entries(params).forEach(([key, value]) => formData.append(key, value));
                UI.setStatus("CLONING...");
                response = await API.generateClone(formData, State.abortController.signal);
            }

            if (isStream) {
                const reader = response.body.getReader();
                let leftover = new Uint8Array(0);

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    // Buffer alignment fix (copy-paste from audio-core logic)
                    const combined = new Uint8Array(leftover.length + value.length);
                    combined.set(leftover);
                    combined.set(value, leftover.length);
                    const remainder = combined.length % 2;
                    const usableLength = combined.length - remainder;
                    const usableData = combined.subarray(0, usableLength);
                    leftover = combined.subarray(usableLength);

                    if (usableData.length > 0) {
                        if (!firstChunk) {
                            firstChunk = true;
                            UI.updateLatency(Math.round(performance.now() - startTime));
                            UI.setStatus("STREAMING");
                        }
                        
                        // Convert Int16 to Float32
                        const float32Data = new Float32Array(usableData.length / 2);
                        const int16Data = new Int16Array(usableData.buffer, usableData.byteOffset, usableData.length / 2);
                        for (let i = 0; i < int16Data.length; i++) {
                            const v = int16Data[i];
                            float32Data[i] = v >= 0 ? v / 32767 : v / 32768;
                        }
                        
                        // Play
                        await playChunk(float32Data, params.sample_rate);
                    }
                }
                if (window.notifyDownloadFinished) window.notifyDownloadFinished();

            } else {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const player = document.getElementById('classicPlayer');
                player.src = url;
                player.play();
                
                UI.updateLatency(Math.round(performance.now() - startTime));
                UI.setStatus("PLAYING");
                await this.loadHistory();
            }

        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error(err);
                UI.showToast(err.message, "error");
                this.stopPlayback(false);
            }
        }
    }
};

// Global Assignments
window.Controllers = Controllers;
window.handleGenerate = () => Controllers.handleGenerate();
window.toggleHistory = () => {
    const drawer = document.getElementById('historyDrawer');
    const overlay = document.getElementById('historyOverlay');
    if (drawer.classList.contains('translate-x-full')) {
        drawer.classList.remove('translate-x-full');
        overlay.classList.remove('hidden');
        setTimeout(() => overlay.classList.add('opacity-100'), 10);
        Controllers.loadHistory();
    } else {
        drawer.classList.add('translate-x-full');
        overlay.classList.remove('opacity-100');
        setTimeout(() => overlay.classList.add('hidden'), 300);
    }
};
window.setMode = (mode) => {
    const btnStd = document.getElementById('btn-std');
    const btnCln = document.getElementById('btn-cln');
    const pnlStd = document.getElementById('panel-std');
    const pnlCln = document.getElementById('panel-cln');
    
    const activeClass = 'flex-1 py-2 text-[10px] font-bold uppercase tracking-wider rounded-md bg-blue-600 text-white shadow-lg transition-all';
    const inactiveClass = 'flex-1 py-2 text-[10px] font-bold uppercase tracking-wider rounded-md text-gray-500 hover:text-white transition-all';

    if (mode === 'standard') {
        btnStd.className = activeClass; btnCln.className = inactiveClass;
        pnlStd.classList.remove('hidden'); pnlCln.classList.add('hidden');
    } else {
        btnCln.className = activeClass; btnStd.className = inactiveClass;
        pnlCln.classList.remove('hidden'); pnlStd.classList.add('hidden');
    }
};
window.toggleAdvanced = () => {
    const panel = document.getElementById('advanced-panel');
    const icon = document.getElementById('adv-icon');
    if (panel.classList.contains('accordion-open')) {
        panel.classList.remove('accordion-open');
        icon.style.transform = 'rotate(0deg)';
    } else {
        panel.classList.add('accordion-open');
        icon.style.transform = 'rotate(180deg)';
    }
};

window.insertSSMLTag = (type) => {
    const area = document.getElementById('textInput');
    const start = area.selectionStart;
    const end = area.selectionEnd;
    const text = area.value;
    let tag = "";
    
    if (type === 'pause') tag = '<break time="1s" />';
    else if (type === 'emphasize') tag = `<emphasis level="strong">${text.substring(start, end) || 'text'}</emphasis>`;
    
    area.value = text.substring(0, start) + tag + text.substring(end);
};

// VCA Listener
document.addEventListener('vca-update', (e) => {
    const m = e.detail;
    const panel = document.getElementById('vca-panel');
    if(m.time) {
        panel.classList.remove('hidden');
        document.getElementById('vca-time').innerText = `${m.time}s`;
        document.getElementById('vca-chars').innerText = m.chars;
        const rtfEl = document.getElementById('vca-rtf');
        rtfEl.innerText = m.rtf;
        const rtfVal = parseFloat(m.rtf);
        rtfEl.className = rtfVal < 0.3 ? "font-bold text-green-400" : "font-bold text-yellow-400";
        panel.classList.add('animate-pulse');
        setTimeout(() => panel.classList.remove('animate-pulse'), 500);
    }
});

// Boot
document.addEventListener('DOMContentLoaded', () => Controllers.boot());