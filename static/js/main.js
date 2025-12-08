/**
 * SENTIRIC XTTS PRO - MAIN CONTROLLER v2.8 (Async Logic Fix)
 */

const State = {
    isPlaying: false,
    abortController: null,
    config: null 
};

// Playback bittiğinde bu fonksiyon çağrılacak
window.onAudioPlaybackComplete = function() {
    console.log("Main controller notified: Playback finished.");
    // isUserInitiated=false, çünkü bu sistem tarafından tetiklenen bir durdurma.
    Controllers.stopPlayback(false); 
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
            player.load();
            player.play().catch(e => console.error("History playback failed:", e));
            player.onended = () => this.stopPlayback(false);
            State.isPlaying = true;
            UI.setPlayingState(true, true);
        }
    },

    stopPlayback(isUserInitiated = true) {
        if (isUserInitiated) {
            console.log("Playback stopped by user.");
            if (State.abortController) {
                State.abortController.abort();
                State.abortController = null;
            }
        }
        
        if (window.resetAudioState) window.resetAudioState();
        
        const player = document.getElementById('classicPlayer');
        if (player && !player.paused) { 
            player.pause(); 
            player.currentTime = 0;
            player.removeAttribute('src');
            player.load();
        }
        
        State.isPlaying = false;
        UI.setPlayingState(false);
    },

    async handleGenerate() {
        if (State.isPlaying) {
            this.stopPlayback(true);
            return;
        }

        const text = document.getElementById('textInput').value.trim();
        if (!text) return UI.showToast("Please enter text", "error");

        if (window.initAudioContext) window.initAudioContext();
        
        State.isPlaying = true;
        UI.setPlayingState(true);
        if (window.resetAudioState) window.resetAudioState();
        
        let isActuallyStreaming = false; // Scope'u genişlet

        try {
            State.abortController = new AbortController();
            const spkName = document.getElementById('speaker').value;
            const styleSelect = document.getElementById('style-select');
            const styleContainer = document.getElementById('style-container');
            let finalSpeaker = spkName;
            if (!styleContainer.classList.contains('hidden') && styleSelect.value && styleSelect.value !== 'default') {
                finalSpeaker = `${spkName}/${styleSelect.value}`;
            }

            const nativeSampleRate = State.config.defaults.sample_rate || 24000;
            const params = {
                text: text, language: document.getElementById('global-lang').value || 'en',
                temperature: parseFloat(document.getElementById('temp').value),
                speed: parseFloat(document.getElementById('speed').value),
                top_k: parseInt(document.getElementById('top_k').value) || 50,
                top_p: parseFloat(document.getElementById('top_p').value) || 0.8,
                repetition_penalty: parseFloat(document.getElementById('rep_pen').value) || 2.0,
                stream: document.getElementById('stream').checked, output_format: 'pcm', 
                speaker_idx: finalSpeaker, sample_rate: nativeSampleRate
            };
            
            if (!params.stream) params.output_format = 'mp3';

            const response = await API.generateTTS(params, State.abortController.signal);
            const isCacheHit = response.headers.get("X-Cache") === "HIT";
            isActuallyStreaming = params.stream && !isCacheHit;

            if (isActuallyStreaming) {
                 const reader = response.body.getReader();
                 let leftover = new Uint8Array(0);
                 
                 while (true) {
                     if (isStopRequested) { console.log("Stream reading aborted."); break; }
                     const { done, value } = await reader.read();
                     if (done) break;
                     
                     if (value && value.length > 0) {
                         const combined = new Uint8Array(leftover.length + value.length);
                         combined.set(leftover);
                         combined.set(value, leftover.length);
                         const remainder = combined.length % 2;
                         const processData = combined.subarray(0, combined.length - remainder);
                         leftover = combined.subarray(combined.length - remainder);
                         const int16Data = new Int16Array(processData.buffer);
                         const float32Data = new Float32Array(int16Data.length);
                         for (let i = 0; i < int16Data.length; i++) float32Data[i] = int16Data[i] / 32768.0;
                         if (window.playChunk) await window.playChunk(float32Data, params.sample_rate);
                     }
                 }
                 if (window.notifyDownloadFinished) window.notifyDownloadFinished();
                 await this.loadHistory();
            } else { // Non-streaming
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const player = document.getElementById('classicPlayer');
                player.src = url;
                player.load(); 
                player.onended = () => this.stopPlayback(false);
                try { await player.play(); } 
                catch (e) { 
                    console.warn("Auto-play prevented", e);
                    this.stopPlayback(false);
                }
                await this.loadHistory();
            }

        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error(err);
                UI.showToast(err.message, "error");
                this.stopPlayback(false); // Sadece hata durumunda durdur
            }
        } finally {
            // *** KRİTİK DÜZELTME ***
            // `stopPlayback` çağrısı buradan kaldırıldı. Stream'in bitmesini beklemeden
            // ses motorunu resetliyordu, bu da periyodik takılmalara neden oluyordu.
            // Durdurma işlemi artık sadece `onAudioPlaybackComplete` callback'i,
            // kullanıcı müdahalesi veya bir hata ile tetiklenir.
            if (!isActuallyStreaming) {
                // Eğer stream değilse, `onended` olayı zaten `stopPlayback`'i çağırır.
                // Ama play() hatası verirse diye burada bir fallback olabilir,
                // şimdilik temiz tutalım. `stopPlayback` hata catch bloğunda var.
            }
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