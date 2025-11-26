// Global State
const State = {
    isPlaying: false,
    abortController: null
};

// --- CONTROLLERS (HTML'den çağrılan fonksiyonlar) ---
const Controllers = {
    async loadSpeakers() {
        try {
            const data = await API.getSpeakers();
            UI.populateSpeakers(data);
        } catch (e) { console.error("Speakers error:", e); }
    },

    async loadHistory() {
        const list = document.getElementById('historyList');
        if(list) list.innerHTML = '<div class="text-center text-[10px] text-gray-600 mt-10">Loading...</div>';
        try {
            const data = await API.getHistory();
            UI.renderHistory(data);
        } catch (e) { console.error("History error:", e); }
    },

    async rescanSpeakers() {
        if(!confirm("Rescan disk for new speakers?")) return;
        try {
            const res = await API.refreshSpeakers();
            alert(res.message);
            await this.loadSpeakers();
        } catch (e) { alert("Error: " + e.message); }
    },

    async clearAllHistory() {
        if(!confirm('WARNING: This will delete ALL history and cache.')) return;
        try {
            const res = await API.deleteAllHistory();
            alert(`Cleanup Complete. Deleted: ${res.files_deleted}`);
            await this.loadHistory();
        } catch (e) { console.error(e); }
    },

    async deleteHistory(filename) {
        if(!confirm('Delete this entry?')) return;
        try {
            const success = await API.deleteHistory(filename);
            if(success) {
                // UI'dan siliyoruz, tüm listeyi çekmeye gerek yok (Optimistic Update)
                const btn = document.querySelector(`button[onclick="Controllers.deleteHistory('${filename}')"]`);
                if(btn) {
                    const row = btn.closest('.group');
                    if(row) row.remove();
                }
            } else { alert("Failed to delete."); }
        } catch (e) { console.error(e); }
    },

    playHistory(filename) {
        if(window.resetAudioState) window.resetAudioState();
        const url = `/api/history/audio/${filename}`;
        const player = document.getElementById('classicPlayer');
        if(player) { 
            player.src = url; 
            player.play(); 
        }
    },

    stopPlayback(isUserInitiated = true) {
        if (isUserInitiated) {
            console.log("User stopped playback.");
            if (State.abortController) { 
                State.abortController.abort(); 
                State.abortController = null; 
            }
            if(window.resetAudioState) window.resetAudioState();
            const player = document.getElementById('classicPlayer');
            if(player) { player.pause(); player.currentTime = 0; }
        } else {
            console.log("Playback finished naturally.");
        }

        UI.setPlayingState(false);
        State.isPlaying = false;
        UI.setStatus("READY");
    },

    async handleGenerate() {
        if (State.isPlaying) { 
            this.stopPlayback(true); 
            return; 
        }

        const text = document.getElementById('textInput').value.trim();
        if (!text) return alert("Please enter text.");
        
        let isStream = document.getElementById('stream').checked;
        if (text.startsWith('<speak>') && isStream) { 
            alert("SSML does not support streaming."); 
            isStream = false; 
        }

        UI.setPlayingState(true);
        State.isPlaying = true;
        const startTime = performance.now();
        let firstChunk = false;

        if(window.initAudioContext) window.initAudioContext();
        if(window.resetAudioState) window.resetAudioState();

        try {
            State.abortController = new AbortController();
            
            // Parametreleri topla
            const modePanel = document.getElementById('panel-std');
            const mode = (modePanel && !modePanel.classList.contains('hidden')) ? 'standard' : 'clone';
            
            const params = {
                text: text, 
                language: document.getElementById('lang').value, 
                temperature: document.getElementById('temp').value,
                speed: document.getElementById('speed').value, 
                top_k: document.getElementById('topk').value, 
                top_p: document.getElementById('topp').value,
                repetition_penalty: document.getElementById('rep').value, 
                stream: isStream,
                output_format: document.getElementById('format').value,
                sample_rate: parseInt(document.getElementById('sampleRate').value)
            };

            // İsteği yap
            let response;
            if (mode === 'standard') {
                params.speaker_idx = document.getElementById('speaker').value;
                response = await API.generateTTS(params, State.abortController.signal);
            } else {
                const fd = new FormData();
                if (window.recordedBlob) { fd.append('files', window.recordedBlob, 'recording.webm'); } 
                else {
                    const f = document.getElementById('ref_audio').files[0];
                    if (!f) throw new Error("No file uploaded.");
                    fd.append('files', f);
                }
                Object.entries(params).forEach(([k,v]) => fd.append(k,v));
                UI.setStatus("ANALYZING...");
                response = await API.generateClone(fd, State.abortController.signal);
            }

            // Yanıtı İşle
            if (isStream) {
                const reader = response.body.getReader();
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    if (!firstChunk) {
                        firstChunk = true;
                        UI.updateLatency(Math.round(performance.now() - startTime));
                        UI.setStatus("STREAMING");
                    }
                    const float32 = convertInt16ToFloat32(new Int16Array(value.buffer, value.byteOffset, value.byteLength / 2));
                    await playChunk(float32, 24000);
                }
                if(window.notifyDownloadFinished) window.notifyDownloadFinished();
                
            } else {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const player = document.getElementById('classicPlayer');
                if(player) { player.src = url; player.play(); }
                
                UI.updateLatency(Math.round(performance.now() - startTime));
                UI.setStatus("PLAYING");
                await this.loadHistory(); 
            }

        } catch (err) {
            if (err.name !== 'AbortError') { 
                alert("Error: " + err.message); 
                this.stopPlayback(false); 
            }
        }
    }
};

// --- EVENT LISTENERS & INIT ---
// Global scope'a açıyoruz ki HTML onclick'ler erişebilsin
window.Controllers = Controllers;
window.handleGenerate = () => Controllers.handleGenerate(); // Legacy support
// setMode, toggleHistory gibi basit UI fonksiyonları ui.js içinde veya html içinde kalabilir
// veya buraya taşınabilir. Şimdilik temel butonları bağlıyoruz.

document.addEventListener('DOMContentLoaded', () => {
    if(window.initUIEvents) window.initUIEvents(); // Slider eventleri
    Controllers.loadSpeakers();
    
    const player = document.getElementById('classicPlayer');
    if(player) {
        player.onended = () => {
            if(State.isPlaying && !document.getElementById('stream').checked) {
                 Controllers.stopPlayback(false); 
            }
        };
    }
});

window.onAudioPlaybackComplete = function() {
    console.log("Stream ended.");
    Controllers.stopPlayback(false);
};