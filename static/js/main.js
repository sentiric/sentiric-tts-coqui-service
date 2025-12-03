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
            UI.showToast(`Found ${res.data.total} speakers`, "success");
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

    // --- GENERATE (CLASSIC) ---
    async handleGenerate() {
        if (State.isPlaying) {
            this.stopPlayback(true);
            return;
        }

        const text = document.getElementById('textInput').value.trim();
        if (!text) return UI.showToast("Please enter text", "error");

        UI.setPlayingState(true);
        State.isPlaying = true;
        
        if (window.resetAudioState) window.resetAudioState();

        const startTime = performance.now();
        let firstChunk = false;

        try {
            State.abortController = new AbortController();
            
            const modePanel = document.getElementById('panel-std');
            const isCloneMode = modePanel.classList.contains('hidden');
            
            // Params
            const params = {
                text: text,
                language: 'tr', // Default lang for classic mode, can be improved to have select
                temperature: parseFloat(document.getElementById('temp').value),
                speed: parseFloat(document.getElementById('speed').value),
                top_k: 50,
                top_p: 0.8,
                repetition_penalty: 2.0,
                stream: false, // Default false for now
                output_format: 'wav',
                sample_rate: State.config ? State.config.defaults.sample_rate : 24000 
            };

            let response;

            if (!isCloneMode) {
                // Speaker Logic Updated for Multi-Style
                const spkName = document.getElementById('speaker').value;
                const styleSelect = document.getElementById('style-select');
                const styleContainer = document.getElementById('style-container');
                let finalSpeaker = spkName;
                
                if (!styleContainer.classList.contains('hidden') && styleSelect.value && styleSelect.value !== 'default') {
                    finalSpeaker = `${spkName}/${styleSelect.value}`;
                }
                params.speaker_idx = finalSpeaker;

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

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const player = document.getElementById('classicPlayer');
            player.src = url;
            player.play();
            
            UI.updateLatency(Math.round(performance.now() - startTime));
            UI.setStatus("PLAYING");
            await this.loadHistory();
            

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
        Controllers.loadHistory();
    } else {
        drawer.classList.add('translate-x-full');
        overlay.classList.add('hidden');
    }
};
window.setMode = (mode) => {
    const btnStd = document.getElementById('btn-std');
    const btnCln = document.getElementById('btn-cln');
    const pnlStd = document.getElementById('panel-std');
    const pnlCln = document.getElementById('panel-cln');
    
    const activeClass = 'flex-1 py-2 text-[10px] font-bold uppercase rounded bg-blue-600 text-white';
    const inactiveClass = 'flex-1 py-2 text-[10px] font-bold uppercase rounded text-gray-500';

    if (mode === 'standard') {
        btnStd.className = activeClass; btnCln.className = inactiveClass;
        pnlStd.classList.remove('hidden'); pnlCln.classList.add('hidden');
    } else {
        btnCln.className = activeClass; btnStd.className = inactiveClass;
        pnlCln.classList.remove('hidden'); pnlStd.classList.add('hidden');
    }
};

window.switchTab = (tab) => {
    const vClassic = document.getElementById('view-classic');
    const vStudio = document.getElementById('view-studio');
    const tClassic = document.getElementById('tab-classic');
    const tStudio = document.getElementById('tab-studio');

    if (tab === 'classic') {
        vClassic.classList.remove('hidden');
        vStudio.classList.add('hidden');
        tClassic.classList.replace('text-gray-400', 'text-white');
        tClassic.classList.add('bg-blue-600');
        tStudio.classList.remove('bg-blue-600', 'text-white');
        tStudio.classList.add('text-gray-400');
    } else {
        vStudio.classList.remove('hidden');
        vClassic.classList.add('hidden');
        tStudio.classList.replace('text-gray-400', 'text-white');
        tStudio.classList.add('bg-blue-600');
        tClassic.classList.remove('bg-blue-600', 'text-white');
        tClassic.classList.add('text-gray-400');
        
        if(window.Studio) Studio.init();
    }
};

document.addEventListener('DOMContentLoaded', () => Controllers.boot());