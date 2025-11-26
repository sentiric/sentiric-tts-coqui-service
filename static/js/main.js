/**
 * SENTIRIC XTTS PRO - MAIN CONTROLLER
 * Bu dosya uygulamanın mantıksal süreçlerini yönetir.
 */

// Global Durum Yönetimi
const State = {
    isPlaying: false,
    abortController: null
};

// --- DENETLEYİCİLER (CONTROLLERS) ---
const Controllers = {
    
    /**
     * Sunucudan hoparlör listesini çeker ve UI'a gönderir.
     */
    async loadSpeakers() {
        try {
            const data = await API.getSpeakers();
            UI.populateSpeakers(data);
        } catch (e) {
            console.error("Speakers loading failed:", e);
        }
    },

    /**
     * Geçmiş kayıtlarını çeker ve UI'a gönderir.
     */
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

    /**
     * Sunucudaki hoparlör dosya sistemini yeniden tarar.
     */
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

    /**
     * Tüm geçmişi ve önbelleği temizler.
     */
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

    /**
     * Tekil bir kaydı siler.
     */
    async deleteHistory(filename) {
        if (!confirm('Delete this entry?')) return;
        try {
            const success = await API.deleteHistory(filename);
            if (success) {
                // UI'dan anında kaldır (Optimistic UI)
                const btn = document.querySelector(`button[onclick*='${filename}']`);
                if (btn) {
                    const group = btn.closest('.group');
                    if (group) group.remove();
                }
            } else {
                alert("Failed to delete.");
            }
        } catch (e) {
            console.error(e);
        }
    },

    /**
     * Geçmişten bir ses dosyasını oynatır.
     */
    playHistory(filename) {
        // Stream motorunu sıfırla ki çakışma olmasın
        if (window.resetAudioState) window.resetAudioState();
        
        const url = `/api/history/audio/${filename}`;
        const player = document.getElementById('classicPlayer');
        if (player) {
            player.src = url;
            player.play();
        }
    },

    /**
     * Oynatmayı durdurur ve durumu sıfırlar.
     * @param {boolean} isUserInitiated - Kullanıcı mı durdurdu yoksa şarkı mı bitti?
     */
    stopPlayback(isUserInitiated = true) {
        if (isUserInitiated) {
            console.log("Playback stopped by user.");
            
            // Fetch isteğini iptal et
            if (State.abortController) {
                State.abortController.abort();
                State.abortController = null;
            }
            
            // Audio Engine'i sıfırla
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

    // --- SES KLONLAMA YÖNETİMİ ---

    /**
     * Dosya seçildiğinde çağrılır.
     */
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            // Önceki mikrofon kaydını temizle
            if (window.clearRecordingData) window.clearRecordingData();
            
            // UI'ı temizle ama INPUT'U SİLME (false parametresi kritik)
            UI.resetCloneUI(false);
            
            // Dosya ismini göster
            UI.updateFileName(file.name);
        }
    },

    /**
     * Mikrofon kaydı bittiğinde çağrılır.
     */
    handleRecordingComplete() {
        // Input'u temizleyebiliriz çünkü mikrofon kullanacağız (true)
        UI.resetCloneUI(true); 
        UI.showRecordingSuccess();
    },

    /**
     * X butonuna basıldığında her şeyi temizler.
     */
    clearCloneData() {
        if (window.clearRecordingData) window.clearRecordingData();
        UI.resetCloneUI(true); 
    },

    // --- ANA İŞLEM: SES ÜRETİMİ ---
    async handleGenerate() {
        // Eğer zaten çalıyorsa, butona basınca durdur
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

        // UI Başlatma
        UI.setPlayingState(true);
        State.isPlaying = true;
        const startTime = performance.now();
        let firstChunk = false;

        // Audio Motorunu Hazırla
        if (window.initAudioContext) window.initAudioContext();
        if (window.resetAudioState) window.resetAudioState();

        try {
            State.abortController = new AbortController();
            
            // Hangi moddayız? (Standart vs Clone)
            const modePanel = document.getElementById('panel-std');
            const isCloneMode = modePanel.classList.contains('hidden');
            
            // Ortak parametreler
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
                // STANDART MOD
                params.speaker_idx = document.getElementById('speaker').value;
                response = await API.generateTTS(params, State.abortController.signal);
            } else {
                // KLON MODU
                const formData = new FormData();
                
                if (window.recordedBlob) {
                    formData.append('files', window.recordedBlob, 'recording.webm');
                } else {
                    const fileInput = document.getElementById('ref_audio');
                    const file = fileInput ? fileInput.files[0] : null;
                    if (!file) throw new Error("Please upload a file or record audio for cloning.");
                    formData.append('files', file);
                }
                
                // Parametreleri FormData'ya ekle
                Object.entries(params).forEach(([key, value]) => formData.append(key, value));
                
                UI.setStatus("ANALYZING VOICE...");
                response = await API.generateClone(formData, State.abortController.signal);
            }

            // --- STREAM İŞLEME (BUFFER ALIGNMENT FIX) ---
            if (isStream) {
                const reader = response.body.getReader();
                
                // Artan byte'ları saklamak için tampon
                let leftover = new Uint8Array(0);

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    // 1. Yeni gelen veriyi önceki artanla birleştir
                    const combined = new Uint8Array(leftover.length + value.length);
                    combined.set(leftover);
                    combined.set(value, leftover.length);

                    // 2. Çift sayı kontrolü (16-bit ses için zorunlu)
                    const remainder = combined.length % 2;
                    const usableLength = combined.length - remainder;

                    // 3. Kullanılabilir kısmı al
                    const usableData = combined.subarray(0, usableLength);
                    
                    // 4. Artanı sakla
                    leftover = combined.subarray(usableLength);

                    if (usableData.length > 0) {
                        if (!firstChunk) {
                            firstChunk = true;
                            UI.updateLatency(Math.round(performance.now() - startTime));
                            UI.setStatus("STREAMING");
                        }
                        
                        // Güvenli Dönüşüm (Hata vermez)
                        const float32Data = new Float32Array(usableData.length / 2);
                        const int16Data = new Int16Array(usableData.buffer, usableData.byteOffset, usableData.length / 2);
                        
                        for (let i = 0; i < int16Data.length; i++) {
                            // Int16 (-32768..32767) -> Float32 (-1.0..1.0)
                            const v = int16Data[i];
                            float32Data[i] = v >= 0 ? v / 32767 : v / 32768;
                        }
                        
                        await playChunk(float32Data, 24000);
                    }
                }
                
                // İndirme bittiğinde Audio Core'a haber ver
                if (window.notifyDownloadFinished) window.notifyDownloadFinished();
                
            } else {
                // --- NON-STREAM İŞLEME ---
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

// --- GLOBAL BRIDGE (HTML Etkileşimi) ---
// HTML'deki onclick="fonksiyon()" çağrıları için global tanımlamalar

window.Controllers = Controllers;
window.handleGenerate = () => Controllers.handleGenerate();

// Legacy Toggle Logic (CSS class manipülasyonu içerdiği için burada)
window.toggleHistory = () => {
    const drawer = document.getElementById('historyDrawer');
    const overlay = document.getElementById('historyOverlay');
    if (!drawer.classList.contains('translate-x-full')) {
        drawer.classList.add('translate-x-full');
        overlay.classList.remove('opacity-100');
        setTimeout(() => overlay.classList.add('hidden'), 300);
    } else {
        drawer.classList.remove('translate-x-full');
        overlay.classList.remove('hidden');
        void overlay.offsetWidth;
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

// Callback Bağlantıları
window.toggleMicUI = (isRec) => UI.showRecordingState(isRec);
window.onRecordingComplete = () => Controllers.handleRecordingComplete();
window.clearRecordingUI = () => Controllers.clearCloneData();
window.onAudioPlaybackComplete = () => Controllers.stopPlayback(false);

// --- BAŞLATMA ---
document.addEventListener('DOMContentLoaded', () => {
    if (window.initUIEvents) window.initUIEvents();
    Controllers.loadSpeakers();
    
    // Dosya seçimi olayını dinle
    const fileInput = document.getElementById('ref_audio');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => Controllers.handleFileSelect(e));
    }
    
    // Klasik oynatıcı bitiş kontrolü
    const player = document.getElementById('classicPlayer');
    if (player) {
        player.onended = () => {
            // Sadece non-stream modda bitişi buradan yönet
            if (State.isPlaying && !document.getElementById('stream').checked) {
                 Controllers.stopPlayback(false); 
            }
        };
    }
});