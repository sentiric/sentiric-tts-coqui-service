// --- GLOBAL DURUM ---
const State = {
    isPlaying: false,
    abortController: null
};

// --- DENETLEYİCİLER (Controllers) ---
const Controllers = {
    
    // 1. Veri Yükleme İşlemleri
    async loadSpeakers() {
        try {
            const data = await API.getSpeakers();
            UI.populateSpeakers(data);
        } catch (e) {
            console.error("Speakers loading failed:", e);
        }
    },

    async loadHistory() {
        const list = document.getElementById('historyList');
        if (list) list.innerHTML = '<div class="text-center text-[10px] text-gray-600 mt-10">Loading...</div>';
        try {
            const data = await API.getHistory();
            UI.renderHistory(data);
        } catch (e) {
            console.error("History loading failed:", e);
        }
    },

    async rescanSpeakers() {
        if (!confirm("This will scan the server disk for new .wav files. Continue?")) return;
        try {
            const res = await API.refreshSpeakers();
            alert(res.message);
            await this.loadSpeakers();
        } catch (e) {
            alert("Error: " + e.message);
        }
    },

    // 2. Geçmiş Yönetimi
    async clearAllHistory() {
        if (!confirm('WARNING: This will delete ALL history and cache permanently.')) return;
        try {
            const res = await API.deleteAllHistory();
            alert(`Cleanup Complete. Deleted Files: ${res.files_deleted}`);
            await this.loadHistory();
        } catch (e) {
            console.error(e);
            alert("Cleanup failed.");
        }
    },

    async deleteHistory(filename) {
        if (!confirm('Delete this entry?')) return;
        try {
            const success = await API.deleteHistory(filename);
            if (success) {
                // UI'dan anında kaldır (Yeniden yükleme yapmadan)
                const btn = document.querySelector(`button[onclick*='${filename}']`);
                if (btn) {
                    btn.closest('.group').remove();
                }
            } else {
                alert("Failed to delete.");
            }
        } catch (e) {
            console.error(e);
        }
    },

    playHistory(filename) {
        if (window.resetAudioState) window.resetAudioState();
        
        const url = `/api/history/audio/${filename}`;
        const player = document.getElementById('classicPlayer');
        if (player) {
            player.src = url;
            player.play();
        }
    },

    // 3. Oynatma Kontrolü
    stopPlayback(isUserInitiated = true) {
        if (isUserInitiated) {
            console.log("Playback stopped by user.");
            
            // İsteği iptal et
            if (State.abortController) {
                State.abortController.abort();
                State.abortController = null;
            }
            
            // Audio Core'u sıfırla
            if (window.resetAudioState) window.resetAudioState();
            
            // HTML Player'ı durdur
            const player = document.getElementById('classicPlayer');
            if (player) {
                player.pause();
                player.currentTime = 0;
            }
        } else {
            console.log("Playback finished naturally.");
        }

        UI.setPlayingState(false);
        State.isPlaying = false;
        UI.setStatus("READY");
    },

    // 4. Klonlama ve Dosya Yönetimi
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            if (window.clearRecordingData) window.clearRecordingData();
            UI.resetCloneUI();
            UI.updateFileName(file.name);
        }
    },

    handleRecordingComplete() {
        // Mikrofon kaydı bittiğinde dosya inputunu temizle
        UI.resetCloneUI(); 
        UI.showRecordingSuccess();
    },

    clearCloneData() {
        if (window.clearRecordingData) window.clearRecordingData();
        UI.resetCloneUI();
    },

    // 5. ANA ÜRETİM FONKSİYONU (GENERATE)
    async handleGenerate() {
        // Eğer zaten çalıyorsa, butona basınca DURDUR
        if (State.isPlaying) {
            this.stopPlayback(true);
            return;
        }

        // Validasyon
        const textInput = document.getElementById('textInput');
        const text = textInput ? textInput.value.trim() : "";
        if (!text) return alert("Please enter text to synthesize.");

        const isStream = document.getElementById('stream').checked;
        if (text.startsWith('<speak>') && isStream) {
            alert("SSML is not supported in Streaming mode.");
            return;
        }

        // Başlatma
        UI.setPlayingState(true);
        State.isPlaying = true;
        const startTime = performance.now();
        let firstChunk = false;

        // Audio Engine Hazırlığı
        if (window.initAudioContext) window.initAudioContext();
        if (window.resetAudioState) window.resetAudioState();

        try {
            State.abortController = new AbortController();
            
            const modePanel = document.getElementById('panel-std');
            const isCloneMode = modePanel.classList.contains('hidden');
            
            // Ortak Parametreler
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

            let response;

            if (!isCloneMode) {
                // STANDARD MODE
                params.speaker_idx = document.getElementById('speaker').value;
                response = await API.generateTTS(params, State.abortController.signal);
            } else {
                // CLONE MODE
                const formData = new FormData();
                
                if (window.recordedBlob) {
                    formData.append('files', window.recordedBlob, 'recording.webm');
                } else {
                    const fileInput = document.getElementById('ref_audio');
                    const file = fileInput ? fileInput.files[0] : null;
                    if (!file) throw new Error("Please upload a file or record audio for cloning.");
                    formData.append('files', file);
                }
                
                // JSON parametreleri FormData'ya ekle
                Object.entries(params).forEach(([key, value]) => formData.append(key, value));
                
                UI.setStatus("ANALYZING VOICE...");
                response = await API.generateClone(formData, State.abortController.signal);
            }

            // YANIT İŞLEME
            if (isStream) {
                // --- STREAMING ---
                const reader = response.body.getReader();
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    if (!firstChunk) {
                        firstChunk = true;
                        UI.updateLatency(Math.round(performance.now() - startTime));
                        UI.setStatus("STREAMING");
                    }
                    
                    // Byte -> Float32 Dönüşümü
                    const float32Data = new Float32Array(value.buffer.byteLength / 2);
                    const int16Data = new Int16Array(value.buffer);
                    
                    for (let i = 0; i < int16Data.length; i++) {
                        const v = int16Data[i];
                        float32Data[i] = v >= 0 ? v / 32767 : v / 32768;
                    }
                    
                    await playChunk(float32Data, 24000);
                }
                
                // İndirme bitti sinyali
                if (window.notifyDownloadFinished) window.notifyDownloadFinished();
                
            } else {
                // --- NON-STREAMING ---
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const player = document.getElementById('classicPlayer');
                
                if (player) {
                    player.src = url;
                    player.play();
                }
                
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

// --- GLOBAL BRIDGE (HTML Bağlantıları) ---
// Bu kısım index.html içindeki onclick="" eventlerinin çalışmasını sağlar.

window.Controllers = Controllers;
window.handleGenerate = () => Controllers.handleGenerate();

// Legacy Toggle Logic (CSS class manipülasyonu içerdiği için burada tutuldu)
window.toggleHistory = () => {
    const drawer = document.getElementById('historyDrawer');
    const overlay = document.getElementById('historyOverlay');
    
    if (!drawer.classList.contains('translate-x-full')) {
        // Kapat
        drawer.classList.add('translate-x-full');
        overlay.classList.remove('opacity-100');
        setTimeout(() => overlay.classList.add('hidden'), 300);
    } else {
        // Aç
        drawer.classList.remove('translate-x-full');
        overlay.classList.remove('hidden');
        void overlay.offsetWidth; // Trigger reflow
        overlay.classList.add('opacity-100');
        Controllers.loadHistory();
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
        btnStd.className = activeClass;
        btnCln.className = inactiveClass;
        pnlStd.classList.remove('hidden');
        pnlCln.classList.add('hidden');
    } else {
        btnCln.className = activeClass;
        btnStd.className = inactiveClass;
        pnlCln.classList.remove('hidden');
        pnlStd.classList.add('hidden');
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

// Audio Core Callback Bağlantıları
window.toggleMicUI = (isRec) => UI.showRecordingState(isRec);
window.onRecordingComplete = () => Controllers.handleRecordingComplete();
window.clearRecordingUI = () => Controllers.clearCloneData();
window.onAudioPlaybackComplete = () => Controllers.stopPlayback(false);

// --- BAŞLATMA (Initialization) ---
document.addEventListener('DOMContentLoaded', () => {
    if (window.initUIEvents) window.initUIEvents();
    
    Controllers.loadSpeakers();
    
    // Dosya Yükleme Event Listener
    const fileInput = document.getElementById('ref_audio');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => Controllers.handleFileSelect(e));
    }
    
    // Klasik Oynatıcı Bitiş Kontrolü
    const player = document.getElementById('classicPlayer');
    if (player) {
        player.onended = () => {
            if (State.isPlaying && !document.getElementById('stream').checked) {
                 Controllers.stopPlayback(false); 
            }
        };
    }
});