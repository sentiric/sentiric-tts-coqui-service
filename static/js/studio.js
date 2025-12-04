/**
 * SENTIRIC STUDIO CORE v2.1 (Director Edition)
 * Features: Screenplay Parser, Block-level settings, Audio Mixing, Drag & Drop
 */

const Studio = {
    blocks: [],
    generatedBlobs: {}, // Mix işlemi için sesleri tutar
    sortable: null,

    init() {
        const container = document.getElementById('script-container');
        if(container && !this.sortable) {
            // SortableJS kütüphanesi yüklü olmalı (index.html içinde CDN var)
            this.sortable = new Sortable(container, {
                animation: 150,
                handle: '.drag-handle',
                ghostClass: 'opacity-50',
                onEnd: () => {
                    // Sürükleme bitince array sırasını güncellememiz gerekebilir
                    // Şimdilik görsel yeterli, render sırasında DOM sırasını baz alacağız
                }
            });
        }
    },

    // --- SCREENPLAY PARSER ENGINE ---
    
    parseFromEditor() {
        const text = document.getElementById('script-source').value;
        if(!text.trim()) return UI.showToast("Script is empty!", "error");

        // Mevcut blokları temizle
        this.clearAll(false); // false: confirm sorma

        const lines = text.split('\n');
        let addedCount = 0;

        lines.forEach(line => {
            line = line.trim();
            if(!line) return;

            // Regex: Name (Style): Text 
            // Örn: "M_Zephyr (Happy): Merhaba dünya"
            const match = line.match(/^([a-zA-Z0-9_ ]+)(?:\((.+?)\))?\s*:\s*(.+)$/);
            
            if(match) {
                let speakerRaw = match[1].trim();
                let styleRaw = match[2] ? match[2].trim().toLowerCase() : 'default';
                let content = match[3].trim();

                // Eşleştirme Mantığı
                const foundSpeaker = this.findBestSpeakerMatch(speakerRaw);
                const finalStyle = this.findBestStyleMatch(foundSpeaker, styleRaw);

                this.addBlock(foundSpeaker, finalStyle, content);
                addedCount++;
            }
        });
        
        UI.showToast(`${addedCount} blocks generated from script.`, "success");
    },

    findBestSpeakerMatch(inputName) {
        if(!window.CurrentSpeakersMap) return '';
        const keys = Object.keys(window.CurrentSpeakersMap);
        // Case-insensitive içerik araması
        const match = keys.find(k => k.toLowerCase().includes(inputName.toLowerCase()));
        return match || ''; // Bulamazsa boş döner (Dropdown'da seçilmez)
    },

    findBestStyleMatch(speaker, inputStyle) {
        if(!speaker || !window.CurrentSpeakersMap) return 'default';
        const styles = window.CurrentSpeakersMap[speaker] || [];
        // Tam eşleşme ara, yoksa default
        // inputStyle örn: "happy", styles örn: ["neutral", "happy", "sad"]
        const match = styles.find(s => s.toLowerCase() === inputStyle.toLowerCase());
        return match || styles[0] || 'default';
    },

    // --- BLOCK MANAGEMENT ---

    addBlock(preSpeaker='', preStyle='default', preText='') {
        const container = document.getElementById('script-container');
        
        // Empty state varsa kaldır
        const emptyState = container.querySelector('.text-center');
        if(emptyState && emptyState.innerText.includes("EMPTY")) emptyState.remove();

        const id = Date.now().toString() + Math.random().toString(16).slice(2);
        
        // Veri yapısına ekle
        this.blocks.push({ 
            id: id, 
            text: preText, 
            speaker: preSpeaker, 
            style: preStyle, 
            speed: 1.0 
        });

        // HTML Oluştur
        const div = document.createElement('div');
        div.id = `block-${id}`;
        div.className = "studio-block bg-[#131315] border border-white/5 rounded-xl p-3 mb-3 relative animate-slideUp group hover:border-blue-500/30 transition-all";
        
        div.innerHTML = `
            <div class="flex items-start gap-3">
                <div class="mt-2 text-gray-600 cursor-move drag-handle hover:text-blue-500"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8h16M4 16h16"></path></svg></div>
                
                <div class="flex-1 space-y-2">
                    <div class="flex items-center gap-2">
                        <!-- Speaker Select -->
                        <div class="flex-1 min-w-[120px]">
                            <select onchange="Studio.updateBlock('${id}', 'speaker', this.value)" class="w-full bg-[#18181b] border border-white/10 rounded px-2 py-1 text-xs font-bold text-gray-200 outline-none focus:border-blue-500 studio-speaker-select h-8">
                                <option value="">Select Speaker...</option>
                            </select>
                        </div>
                        
                        <!-- Style Select -->
                        <div class="w-28">
                            <select onchange="Studio.updateBlock('${id}', 'style', this.value)" id="style-${id}" class="w-full bg-[#18181b] border border-white/10 rounded px-2 py-1 text-xs text-gray-400 outline-none focus:border-blue-500 h-8" disabled>
                                <option value="default">Def</option>
                            </select>
                        </div>
                        
                        <!-- Speed Control -->
                        <div class="w-14 flex items-center bg-[#18181b] rounded border border-white/10 px-1 h-8" title="Speed">
                            <span class="text-[9px] text-gray-500 mr-1">x</span>
                            <input type="number" step="0.1" min="0.5" max="2.0" value="1.0" onchange="Studio.updateBlock('${id}', 'speed', this.value)" class="w-full bg-transparent text-xs text-white outline-none text-center">
                        </div>

                        <!-- Single Play -->
                        <button onclick="Studio.playSingle('${id}')" class="w-8 h-8 rounded bg-gray-800 hover:bg-green-600 hover:text-white text-gray-400 flex items-center justify-center transition-colors border border-white/5">
                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                        </button>
                    </div>
                    
                    <textarea oninput="Studio.updateBlock('${id}', 'text', this.value)" class="w-full bg-black/30 rounded p-3 text-sm text-gray-200 placeholder-gray-700 outline-none resize-none h-16 border border-transparent focus:border-white/10 focus:bg-black/50 transition-all font-mono leading-tight">${preText}</textarea>
                </div>

                <button onclick="Studio.removeBlock('${id}')" class="text-gray-700 hover:text-red-500 self-start mt-2 ml-1"><span class="text-lg font-bold">×</span></button>
            </div>
        `;

        container.appendChild(div);
        
        // Speakerları doldur ve varsayılanları seç
        this.populateBlockSpeakers(id, preSpeaker, preStyle);
    },

    removeBlock(id) {
        const el = document.getElementById(`block-${id}`);
        if(el) {
            el.style.transform = 'scale(0.95)';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 200);
        }
        this.blocks = this.blocks.filter(b => b.id !== id);
        delete this.generatedBlobs[id];
    },

    updateBlock(id, key, value) {
        const block = this.blocks.find(b => b.id === id);
        if(block) {
            block[key] = value;
            // Speaker değişirse stili de güncelle
            if(key === 'speaker') {
                this.updateBlockStyles(id, value); 
            }
        }
    },

    clearAll(ask = true) {
        if(ask && !confirm("Clear all blocks?")) return;
        
        document.getElementById('script-container').innerHTML = `
            <div class="flex flex-col items-center justify-center mt-32 text-center opacity-30 select-none pointer-events-none">
                <div class="w-24 h-24 rounded-full bg-gray-800 flex items-center justify-center mb-4">
                    <svg class="w-10 h-10 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"></path></svg>
                </div>
                <h3 class="text-white font-bold text-lg tracking-widest">TIMELINE EMPTY</h3>
                <p class="text-gray-500 text-xs mt-2 max-w-xs font-mono">Write script on left or add manually.</p>
            </div>`;
        this.blocks = [];
        this.generatedBlobs = {};
    },

    // --- DYNAMIC DROPDOWNS ---

    populateBlockSpeakers(blockId, preSpeaker, preStyle) {
        const select = document.querySelector(`#block-${blockId} .studio-speaker-select`);
        if(!select || !window.CurrentSpeakersMap) return;

        select.innerHTML = '<option value="">Select Speaker...</option>';

        Object.keys(window.CurrentSpeakersMap).sort().forEach(spkName => {
            const opt = document.createElement('option');
            opt.value = spkName;
            opt.innerText = spkName;
            if(spkName === preSpeaker) opt.selected = true;
            select.appendChild(opt);
        });

        // Eğer bir speaker seçiliyse, stilini de güncelle
        if(preSpeaker) {
            this.updateBlockStyles(blockId, preSpeaker, preStyle);
        }
    },

    updateBlockStyles(blockId, speakerName, preStyle = null) {
        const styleSel = document.getElementById(`style-${blockId}`);
        if(!styleSel || !window.CurrentSpeakersMap) return;

        styleSel.innerHTML = '';
        const styles = window.CurrentSpeakersMap[speakerName] || ['default'];
        
        styles.forEach(style => {
            const opt = document.createElement('option');
            opt.value = style;
            // Capitalize first letter
            opt.innerText = style.charAt(0).toUpperCase() + style.slice(1);
            if(preStyle && style.toLowerCase() === preStyle.toLowerCase()) opt.selected = true;
            styleSel.appendChild(opt);
        });
        
        styleSel.disabled = styles.length <= 1 && styles[0] === 'default';
        if(styleSel.disabled) styleSel.classList.add('opacity-50');
        else styleSel.classList.remove('opacity-50');
        
        // Eğer preStyle yoksa ilkini seç ve modele kaydet
        if(!preStyle) {
            this.updateBlock(blockId, 'style', styles[0]);
        }
    },

    // --- PLAYBACK & RENDER ---

    // Bu fonksiyon HTML'deki onclick="Studio.renderAll()" tarafından çağrılır
    renderAll() {
        this.playAll(); 
    },

    async playAll() {
        // DOM sırasına göre blokları al (Sürükle bırak sonrası sıra değişmiş olabilir)
        const domBlocks = document.querySelectorAll('.studio-block');
        const orderedBlocks = [];
        domBlocks.forEach(el => {
            const id = el.id.replace('block-', '');
            const blockData = this.blocks.find(b => b.id === id);
            if(blockData) orderedBlocks.push(blockData);
        });

        if(orderedBlocks.length === 0) return UI.showToast("Timeline empty!", "error");

        const btn = document.getElementById('studio-render-btn');
        const dlBtn = document.getElementById('studio-dl-btn');
        const originalText = btn.innerHTML;
        
        btn.innerHTML = `<span class="animate-spin">↻</span> RENDERING...`;
        btn.disabled = true;
        dlBtn.disabled = true;
        this.generatedBlobs = {}; // Önceki renderları temizle

        try {
            const audioQueue = [];
            
            for(let i=0; i<orderedBlocks.length; i++) {
                const block = orderedBlocks[i];
                if(!block.text.trim() || !block.speaker) continue;

                // UI Highlight
                const el = document.getElementById(`block-${block.id}`);
                el.classList.add('border-blue-500', 'shadow-lg');

                // Prepare Params
                let finalSpeakerID = block.speaker;
                if(block.style && block.style !== 'default') {
                    finalSpeakerID = `${block.speaker}/${block.style}`;
                }

                const params = {
                    text: block.text,
                    language: document.getElementById('global-lang').value || 'en',
                    speaker_idx: finalSpeakerID,
                    temperature: 0.75,
                    speed: parseFloat(block.speed) || 1.0,
                    stream: false
                };

                const response = await API.generateTTS(params);
                if(!response.ok) throw new Error("API Error");
                
                const blob = await response.blob();
                this.generatedBlobs[block.id] = blob; // Mix için sakla
                audioQueue.push({blob: blob, elementId: `block-${block.id}`});

                el.classList.remove('border-blue-500', 'shadow-lg');
                el.classList.add('border-green-500/50');
            }

            btn.innerHTML = `▶ PLAYING SCENE...`;
            await this.playQueue(audioQueue);
            
            // Enable Download
            dlBtn.disabled = false;
            UI.showToast("Scene Rendered Successfully", "success");

        } catch(e) {
            console.error(e);
            UI.showToast("Rendering failed: " + e.message, "error");
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    },

    async playQueue(queue) {
        // Init Audio Context (User gesture gerektirir, butona basıldığı için sorun yok)
        if (window.initAudioContext) window.initAudioContext();

        for(const item of queue) {
            const el = document.getElementById(item.elementId);
            if(el) el.classList.add('playing'); // Görsel efekt

            await new Promise((resolve) => {
                const url = URL.createObjectURL(item.blob);
                const audio = new Audio(url);
                audio.onended = resolve;
                audio.play().catch(e => {
                    console.error("Playback error", e);
                    resolve(); // Hata olsa da devam et
                });
            });

            if(el) el.classList.remove('playing');
        }
    },

    async playSingle(id) {
        const block = this.blocks.find(b => b.id === id);
        if(!block || !block.text) return UI.showToast("Block empty", "error");

        // Buton ikonu değiştir
        const btn = document.querySelector(`#block-${id} button svg`).parentElement;
        const originalHTML = btn.innerHTML;
        btn.innerHTML = `<span class="animate-spin text-xs">↻</span>`;
        
        try {
             let finalSpeaker = block.speaker;
             if(block.style && block.style !== 'default') finalSpeaker += `/${block.style}`;

             const params = {
                 text: block.text,
                 language: document.getElementById('global-lang').value || 'en',
                 speaker_idx: finalSpeaker,
                 speed: parseFloat(block.speed) || 1.0,
                 stream: false 
             };

             const response = await API.generateTTS(params);
             const blob = await response.blob();
             const url = URL.createObjectURL(blob);
             const audio = new Audio(url);
             
             // Görsel efekt
             const el = document.getElementById(`block-${id}`);
             el.classList.add('playing');
             
             await audio.play();
             
             audio.onended = () => {
                 el.classList.remove('playing');
             };

        } catch(e) {
            UI.showToast("Playback failed", "error");
        } finally {
            btn.innerHTML = originalHTML;
        }
    },

    // --- MIXING ENGINE (Browser-Based) ---

    async downloadMix() {
        // DOM sırasına göre blob'ları topla
        const domBlocks = document.querySelectorAll('.studio-block');
        const blobsToMix = [];
        
        domBlocks.forEach(el => {
            const id = el.id.replace('block-', '');
            if(this.generatedBlobs[id]) {
                blobsToMix.push(this.generatedBlobs[id]);
            }
        });

        if (blobsToMix.length === 0) return UI.showToast("No audio to mix. Render first.", "error");

        UI.showToast("Mixing audio...", "info");
        
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const audioBuffers = [];

            // 1. Blob'ları decode et
            for (const blob of blobsToMix) {
                const arrayBuffer = await blob.arrayBuffer();
                const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
                audioBuffers.push(audioBuffer);
            }

            // 2. Toplam uzunluğu hesapla
            const totalLength = audioBuffers.reduce((acc, buf) => acc + buf.length, 0);
            
            // 3. Çıktı buffer'ı oluştur (Mono)
            const outputBuffer = audioContext.createBuffer(
                1, 
                totalLength,
                audioBuffers[0].sampleRate
            );
            
            // 4. Birleştir (Merge)
            const channelData = outputBuffer.getChannelData(0);
            let offset = 0;
            for (const buf of audioBuffers) {
                // Eğer buffer stereo ise sadece ilk kanalı al (mixdown), mono ise direkt al
                const inputData = buf.getChannelData(0);
                channelData.set(inputData, offset);
                offset += buf.length;
            }

            // 5. WAV olarak encode et
            const wavBytes = this.bufferToWav(outputBuffer, totalLength);
            const wavBlob = new Blob([wavBytes], { type: 'audio/wav' });

            // 6. İndir
            const url = URL.createObjectURL(wavBlob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `sentiric_director_mix_${Date.now()}.wav`;
            a.click();
            
            UI.showToast("Download started!", "success");

        } catch(e) {
            console.error(e);
            UI.showToast("Mixing failed. Browser mismatch?", "error");
        }
    },

    // WAV Encoder Helper (PCM 16-bit)
    bufferToWav(abuffer, len) {
        const numOfChan = abuffer.numberOfChannels;
        const length = len * numOfChan * 2 + 44;
        const buffer = new ArrayBuffer(length);
        const view = new DataView(buffer);
        const channels = [];
        let i;
        let sample;
        let offset = 0;
        let pos = 0;

        // Header yazma
        function setUint16(data) { view.setUint16(pos, data, true); pos += 2; }
        function setUint32(data) { view.setUint32(pos, data, true); pos += 4; }

        setUint32(0x46464952); // "RIFF"
        setUint32(length - 8); // file length - 8
        setUint32(0x45564157); // "WAVE"
        setUint32(0x20746d66); // "fmt " chunk
        setUint32(16); // length = 16
        setUint16(1); // PCM (uncompressed)
        setUint16(numOfChan);
        setUint32(abuffer.sampleRate);
        setUint32(abuffer.sampleRate * 2 * numOfChan); // avg. bytes/sec
        setUint16(numOfChan * 2); // block-align
        setUint16(16); // 16-bit
        setUint32(0x61746164); // "data" - chunk
        setUint32(length - pos - 4); // chunk length

        for(i = 0; i < abuffer.numberOfChannels; i++) channels.push(abuffer.getChannelData(i));

        while(pos < length) {
            for(i = 0; i < numOfChan; i++) {
                // Sıkıştırma/Clipping
                sample = Math.max(-1, Math.min(1, channels[i][offset])); 
                // 16-bit dönüşümü
                sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0; 
                view.setInt16(pos, sample, true); 
                pos += 2;
            }
            offset++;
        }

        return buffer;
    }
};