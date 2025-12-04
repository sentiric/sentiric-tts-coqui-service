/**
 * SENTIRIC XTTS PRO - MAIN CONTROLLER v2.5 (Playback Stability Fix)
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
            
            // Kullanıcı etkileşimi olmadan context başlatılamaz, burada sadece tanımlıyoruz
            // if (window.initAudioContext) window.initAudioContext(); 

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
            player.load(); // Explicit load
            player.play().catch(e => console.error("History playback failed:", e));
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
            if (player) { 
                player.pause(); 
                player.currentTime = 0; 
                player.removeAttribute('src'); // Kaynağı temizle
                player.load();
            }
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

        // 1. Audio Context Resume (Kullanıcı Tıklamasıyla)
        if (window.initAudioContext) {
            window.initAudioContext();
            if (window._audioContext && window._audioContext.state === 'suspended') {
                await window._audioContext.resume();
            }
        }

        UI.setPlayingState(true);
        State.isPlaying = true;
        
        if (window.resetAudioState) window.resetAudioState();

        try {
            State.abortController = new AbortController();
            
            const spkName = document.getElementById('speaker').value;
            const styleSelect = document.getElementById('style-select');
            const styleContainer = document.getElementById('style-container');
            let finalSpeaker = spkName;
            
            if (!styleContainer.classList.contains('hidden') && styleSelect.value && styleSelect.value !== 'default') {
                finalSpeaker = `${spkName}/${styleSelect.value}`;
            }

            const params = {
                text: text,
                language: document.getElementById('global-lang').value || 'en',
                temperature: parseFloat(document.getElementById('temp').value),
                speed: parseFloat(document.getElementById('speed').value),
                top_k: parseInt(document.getElementById('top_k').value) || 50,
                top_p: parseFloat(document.getElementById('top_p').value) || 0.8,
                repetition_penalty: parseFloat(document.getElementById('rep_pen').value) || 2.0,
                stream: document.getElementById('stream').checked,
                output_format: 'wav',
                speaker_idx: finalSpeaker,
                sample_rate: State.config ? State.config.defaults.sample_rate : 24000 
            };

            const response = await API.generateTTS(params, State.abortController.signal);
            
            // CACHE & STREAM DETECTION FIX
            const isCacheHit = response.headers.get("X-Cache") === "HIT";
            const contentType = response.headers.get("Content-Type");
            
            // Gerçekten stream mi yapılıyor yoksa cache mi döndü?
            const isActuallyStreaming = params.stream && !isCacheHit && contentType && contentType.includes("octet-stream");

            if (isActuallyStreaming) {
                 const reader = response.body.getReader();
                 let leftover = new Uint8Array(0);

                 while (true) {
                     const { done, value } = await reader.read();
                     if (done) break;
                     if (value && value.length > 0) {
                         const chunk = new Uint8Array(leftover.length + value.length);
                         chunk.set(leftover);
                         chunk.set(value, leftover.length);
                         const remainder = chunk.length % 2;
                         const processData = chunk.subarray(0, chunk.length - remainder);
                         leftover = chunk.subarray(chunk.length - remainder);
                         const int16Data = new Int16Array(processData.buffer);
                         const float32Data = new Float32Array(int16Data.length);
                         for (let i = 0; i < int16Data.length; i++) {
                             float32Data[i] = int16Data[i] / 32768.0;
                         }
                         if (window.playChunk) await window.playChunk(float32Data, params.sample_rate);
                     }
                 }
                 await this.loadHistory();
                 
            } else {
                // CACHE HIT veya NON-STREAM
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const player = document.getElementById('classicPlayer');
                
                // Eski kaynağı temizle ve yenisini yükle
                player.pause();
                player.src = url;
                player.load(); 

                try {
                    await player.play();
                } catch (e) {
                    console.warn("Auto-play prevented by browser policy. Retrying in 100ms...", e);
                    setTimeout(() => {
                        player.play().catch(err => UI.showToast("Click 'Play' on History", "error"));
                    }, 100);
                }

                await this.loadHistory();
            }

        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error(err);
                UI.showToast(err.message, "error");
            }
        } finally {
            this.stopPlayback(false);
        }
    }
};

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
        vClassic.classList.remove('hidden'); vStudio.classList.add('hidden');
        tClassic.className = activeClass; tStudio.className = inactiveClass;
    } else {
        vStudio.classList.remove('hidden'); vClassic.classList.add('hidden');
        tStudio.className = activeClass; tClassic.className = inactiveClass;
        if(window.Studio) Studio.init();
    }
};
document.addEventListener('DOMContentLoaded', () => Controllers.boot());