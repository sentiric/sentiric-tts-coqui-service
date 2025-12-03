/**
 * SENTIRIC STUDIO CORE v2.0
 * Features: Drag & Drop, Block-level settings, Audio Mixing
 */

const Studio = {
    blocks: [],
    generatedBlobs: {}, // Store generated audio for mixing
    
    init() {
        const container = document.getElementById('script-container');
        if(container && !this.sortable) {
            this.sortable = new Sortable(container, {
                animation: 150,
                handle: '.drag-handle',
                ghostClass: 'bg-blue-900/10'
            });
        }
    },

    addBlock() {
        const container = document.getElementById('script-container');
        // Clear empty state
        const emptyState = container.querySelector('.text-center');
        if(emptyState) emptyState.remove();

        const id = Date.now().toString();
        this.blocks.push({ id: id, text: '', speaker: '', style: 'default' });

        const div = document.createElement('div');
        div.id = `block-${id}`;
        div.className = "bg-[#131315] border border-white/5 rounded-xl p-4 group hover:border-blue-500/30 transition-all relative animate-slideIn mb-4 shadow-lg";
        
        div.innerHTML = `
            <div class="flex items-start gap-4">
                <div class="mt-3 text-gray-700 cursor-move drag-handle hover:text-blue-500 transition-colors"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8h16M4 16h16"></path></svg></div>
                
                <div class="flex-1 space-y-3">
                    <div class="flex flex-wrap gap-2">
                        <div class="flex-1 min-w-[150px]">
                            <select onchange="Studio.updateBlock('${id}', 'speaker', this.value)" class="w-full bg-[#18181b] border border-white/10 rounded-lg px-3 py-2 text-xs font-bold text-gray-200 outline-none focus:border-blue-500 studio-speaker-select transition-colors cursor-pointer">
                                <option value="">Select Speaker...</option>
                            </select>
                        </div>
                        <div class="w-[120px]">
                            <select onchange="Studio.updateBlock('${id}', 'style', this.value)" id="style-${id}" class="w-full bg-[#18181b] border border-white/10 rounded-lg px-3 py-2 text-xs font-bold text-gray-400 outline-none focus:border-blue-500 disabled:opacity-30 cursor-pointer" disabled>
                                <option value="default">Default</option>
                            </select>
                        </div>
                    </div>
                    
                    <textarea oninput="Studio.updateBlock('${id}', 'text', this.value)" class="w-full bg-black/20 rounded-lg p-3 text-sm text-gray-200 placeholder-gray-700 outline-none resize-none h-24 border border-transparent focus:border-white/10 transition-all" placeholder="Write dialogue here..."></textarea>
                </div>

                <div class="flex flex-col gap-2 pt-1">
                     <button onclick="Studio.removeBlock('${id}')" class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-red-900/20 text-gray-600 hover:text-red-500 transition-colors"><span class="text-xl leading-none">×</span></button>
                </div>
            </div>
        `;

        container.appendChild(div);
        this.populateBlockSpeakers(id);
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
            if(key === 'speaker') this.updateBlockStyles(id, value);
        }
    },

    clearAll() {
        if(confirm("Clear all blocks?")) {
            document.getElementById('script-container').innerHTML = `
                <div class="flex flex-col items-center justify-center mt-32 text-center opacity-40">
                    <div class="w-20 h-20 border-2 border-dashed border-gray-600 rounded-xl flex items-center justify-center mb-4"><span class="text-2xl text-gray-600">+</span></div>
                    <h3 class="text-white font-bold text-lg">Your canvas is empty</h3>
                </div>`;
            this.blocks = [];
            this.generatedBlobs = {};
        }
    },

    populateBlockSpeakers(blockId) {
        const select = document.querySelector(`#block-${blockId} .studio-speaker-select`);
        if(!select || !window.CurrentSpeakersMap) return;

        Object.keys(window.CurrentSpeakersMap).sort().forEach(spkName => {
            const opt = document.createElement('option');
            opt.value = spkName;
            opt.innerText = spkName;
            select.appendChild(opt);
        });
    },

    updateBlockStyles(blockId, speakerName) {
        const styleSel = document.getElementById(`style-${blockId}`);
        if(!styleSel || !window.CurrentSpeakersMap) return;

        styleSel.innerHTML = '';
        const styles = window.CurrentSpeakersMap[speakerName] || ['default'];
        
        styles.forEach(style => {
            const opt = document.createElement('option');
            opt.value = style;
            opt.innerText = style.charAt(0).toUpperCase() + style.slice(1);
            styleSel.appendChild(opt);
        });
        
        styleSel.disabled = styles.length <= 1 && styles[0] === 'default';
        if(styleSel.disabled) styleSel.classList.add('opacity-50');
        else styleSel.classList.remove('opacity-50');
        
        this.updateBlock(blockId, 'style', styles[0]);
    },

    async playAll() {
        if(this.blocks.length === 0) return UI.showToast("No blocks to render", "error");
        
        const btn = document.getElementById('studio-play-btn');
        const dlBtn = document.getElementById('studio-dl-btn');
        const originalText = btn.innerHTML;
        
        btn.innerHTML = `<span class="animate-spin">↻</span> PROCESSING...`;
        btn.disabled = true;
        dlBtn.disabled = true;
        this.generatedBlobs = {}; // Reset for new render

        try {
            const audioQueue = [];
            
            for(let i=0; i<this.blocks.length; i++) {
                const block = this.blocks[i];
                if(!block.text.trim() || !block.speaker) continue;

                const el = document.getElementById(`block-${block.id}`);
                el.className = "bg-[#131315] border border-blue-500 rounded-xl p-4 transition-all relative shadow-[0_0_20px_rgba(59,130,246,0.2)]";

                let finalSpeakerID = block.speaker;
                if(block.style && block.style !== 'default') {
                    finalSpeakerID = `${block.speaker}/${block.style}`;
                }

                const params = {
                    text: block.text,
                    language: document.getElementById('global-lang').value || 'en',
                    speaker_idx: finalSpeakerID,
                    temperature: 0.75,
                    speed: 1.0,
                    stream: false
                };

                const response = await API.generateTTS(params);
                const blob = await response.blob();
                
                this.generatedBlobs[block.id] = blob; // Store for mixing
                audioQueue.push(blob);

                el.className = "bg-[#131315] border border-green-500/50 rounded-xl p-4 transition-all relative";
            }

            btn.innerHTML = `▶ PLAYING...`;
            await this.playQueue(audioQueue);
            
            // Enable Download
            dlBtn.disabled = false;

        } catch(e) {
            UI.showToast("Rendering failed: " + e.message, "error");
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    },

    async playQueue(blobs) {
        for(const blob of blobs) {
            await new Promise((resolve) => {
                const url = URL.createObjectURL(blob);
                const audio = new Audio(url);
                audio.onended = resolve;
                audio.play();
            });
        }
    },

    // --- AUDIO MIXING ENGINE ---
    async downloadMix() {
        const blobs = Object.values(this.generatedBlobs);
        if (blobs.length === 0) return UI.showToast("No audio to mix. Render first.", "error");

        UI.showToast("Mixing audio...", "info");
        
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const audioBuffers = [];

            // 1. Decode all blobs
            for (const blob of blobs) {
                const arrayBuffer = await blob.arrayBuffer();
                const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
                audioBuffers.push(audioBuffer);
            }

            // 2. Calculate total duration
            const totalLength = audioBuffers.reduce((acc, buf) => acc + buf.length, 0);
            
            // 3. Create output buffer
            const outputBuffer = audioContext.createBuffer(
                1, // Mono (TTS usually mono)
                totalLength,
                audioBuffers[0].sampleRate
            );
            
            // 4. Merge
            const channelData = outputBuffer.getChannelData(0);
            let offset = 0;
            for (const buf of audioBuffers) {
                channelData.set(buf.getChannelData(0), offset);
                offset += buf.length;
            }

            // 5. Encode to WAV (Simple Helper)
            const wavBytes = this.bufferToWav(outputBuffer, totalLength);
            const wavBlob = new Blob([wavBytes], { type: 'audio/wav' });

            // 6. Download
            const url = URL.createObjectURL(wavBlob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `sentiric_mix_${Date.now()}.wav`;
            a.click();
            
            UI.showToast("Download started!", "success");

        } catch(e) {
            console.error(e);
            UI.showToast("Mixing failed. Browser mismatch?", "error");
        }
    },

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

        // Write WAV HEADER
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
        setUint16(16); // 16-bit (hardcoded in this helper)
        setUint32(0x61746164); // "data" - chunk
        setUint32(length - pos - 4); // chunk length

        for(i = 0; i < abuffer.numberOfChannels; i++) channels.push(abuffer.getChannelData(i));

        while(pos < len) {
            for(i = 0; i < numOfChan; i++) {
                sample = Math.max(-1, Math.min(1, channels[i][pos])); // clamp
                sample = (0.5 + sample < 0 ? sample * 32768 : sample * 32767) | 0; // scale to 16-bit
                view.setInt16(44 + offset, sample, true); 
                offset += 2;
            }
            pos++;
        }

        return buffer;

        function setUint16(data) { view.setUint16(pos, data, true); pos += 2; }
        function setUint32(data) { view.setUint32(pos, data, true); pos += 4; }
    }
};