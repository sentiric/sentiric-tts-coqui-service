/**
 * SENTIRIC XTTS PRO - MAIN CONTROLLER v2.0
 */

const State = {
    isPlaying: false,
    abortController: null,
    config: null 
};

const Controllers = {
    
    async boot() {
        UI.setBootState(true, "Fetching Configuration...");
        try {
            State.config = await API.getConfig();
            if (!State.config) throw new Error("Config unreachable");
            
            UI.initFromConfig(State.config);
            UI.setBootState(true, "Loading Voice Models...");
            await this.loadSpeakers();
            await this.loadHistory();
            
            if (window.initAudioContext) window.initAudioContext();

            UI.setBootState(false);

        } catch (e) {
            console.error("Boot Error:", e);
            UI.setBootState(true, "Connection Failed. Retrying...");
            setTimeout(() => this.boot(), 3000); 
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
        UI.showToast("Scanning assets...", "info");
        try {
            const res = await API.refreshSpeakers();
            UI.showToast(`Found ${res.data.total} speakers`, "success");
            await this.loadSpeakers();
        } catch (e) {
            UI.showToast(e.message, "error");
        }
    },

    async clearAllHistory() {
        if (!confirm('Delete all history?')) return;
        try {
            await API.deleteAllHistory();
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
        }
        UI.setPlayingState(false);
        State.isPlaying = false;
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

        try {
            State.abortController = new AbortController();
            
            // Speaker Logic
            const spkName = document.getElementById('speaker').value;
            const styleSelect = document.getElementById('style-select');
            const styleContainer = document.getElementById('style-container');
            let finalSpeaker = spkName;
            
            if (!styleContainer.classList.contains('hidden') && styleSelect.value && styleSelect.value !== 'default') {
                finalSpeaker = `${spkName}/${styleSelect.value}`;
            }

            // Params
            const params = {
                text: text,
                language: document.getElementById('global-lang').value || 'en', // Global Lang Selector
                temperature: parseFloat(document.getElementById('temp').value),
                speed: parseFloat(document.getElementById('speed').value),
                top_k: 50,
                top_p: 0.8,
                repetition_penalty: 2.0,
                stream: document.getElementById('stream').checked, // Stream Toggle
                output_format: 'wav',
                speaker_idx: finalSpeaker,
                sample_rate: State.config ? State.config.defaults.sample_rate : 24000 
            };

            let response;
            
            // Streaming Logic
            if (params.stream) {
                 response = await API.generateTTS(params, State.abortController.signal);
                 const reader = response.body.getReader();
                 // ... Audio Core Streaming Logic would be handled here ... 
                 // For now reusing the simpler logic for robustness:
                 // Note: Real streaming implementation requires more code in audio-core.js
                 // Using blob fallback if user selected stream but UI logic simplifies it
            } 
            
            // Standard (Non-Stream for now to ensure stability as requested)
            // Override stream to false until audio-core streaming is fully robust
            params.stream = false; 
            response = await API.generateTTS(params, State.abortController.signal);

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const player = document.getElementById('classicPlayer');
            player.src = url;
            player.play();
            
            await this.loadHistory();

        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error(err);
                UI.showToast(err.message, "error");
            }
        } finally {
            // CRITICAL FIX: Ensure button is reset
            this.stopPlayback(false);
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
window.switchTab = (tab) => {
    const vClassic = document.getElementById('view-classic');
    const vStudio = document.getElementById('view-studio');
    const tClassic = document.getElementById('tab-classic');
    const tStudio = document.getElementById('tab-studio');

    const activeClass = "px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded transition-all bg-blue-600 text-white shadow-[0_0_15px_rgba(37,99,235,0.3)]";
    const inactiveClass = "px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded text-gray-500 hover:text-white transition-all";

    if (tab === 'classic') {
        vClassic.classList.remove('hidden');
        vStudio.classList.add('hidden');
        tClassic.className = activeClass;
        tStudio.className = inactiveClass;
    } else {
        vStudio.classList.remove('hidden');
        vClassic.classList.add('hidden');
        tStudio.className = activeClass;
        tClassic.className = inactiveClass;
        if(window.Studio) Studio.init();
    }
};

document.addEventListener('DOMContentLoaded', () => Controllers.boot());