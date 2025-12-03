/**
 * SENTIRIC STUDIO CORE
 * Handles multi-block dialogue generation and sequencing.
 */

const Studio = {
    blocks: [],
    
    init() {
        // Initialize Sortable for Drag & Drop
        const container = document.getElementById('script-container');
        if(container) {
            new Sortable(container, {
                animation: 150,
                handle: '.drag-handle',
                ghostClass: 'bg-blue-900/20'
            });
        }
    },

    addBlock() {
        // Remove empty state placeholder
        const container = document.getElementById('script-container');
        if(container.querySelector('.text-center')) container.innerHTML = '';

        const id = Date.now().toString();
        this.blocks.push({ id: id, text: '', speaker: '', style: 'default' });

        const div = document.createElement('div');
        div.id = `block-${id}`;
        div.className = "bg-[#18181b] border border-white/5 rounded-lg p-4 group hover:border-white/10 transition-colors relative animate-slideIn";
        
        // Block HTML
        div.innerHTML = `
            <div class="flex items-start gap-4">
                <div class="mt-2 text-gray-600 cursor-move drag-handle hover:text-white"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg></div>
                <div class="flex-1 space-y-3">
                    <div class="flex gap-2">
                        <!-- Speaker Select -->
                        <div class="flex-1 max-w-[200px]">
                            <select onchange="Studio.updateBlock('${id}', 'speaker', this.value)" class="w-full bg-[#0f0f11] border border-white/10 rounded px-2 py-1.5 text-xs text-white outline-none focus:border-blue-500 studio-speaker-select">
                                <option value="">Select Speaker...</option>
                            </select>
                        </div>
                        <!-- Style Select -->
                        <div class="flex-1 max-w-[150px]">
                            <select onchange="Studio.updateBlock('${id}', 'style', this.value)" id="style-${id}" class="w-full bg-[#0f0f11] border border-white/10 rounded px-2 py-1.5 text-xs text-gray-400 outline-none focus:border-blue-500 disabled:opacity-50" disabled>
                                <option value="default">Default</option>
                            </select>
                        </div>
                    </div>
                    <!-- Text Area -->
                    <textarea oninput="Studio.updateBlock('${id}', 'text', this.value)" class="w-full bg-transparent text-sm text-gray-200 placeholder-gray-700 outline-none resize-none h-20" placeholder="Type dialogue here..."></textarea>
                </div>
                <div class="flex flex-col gap-2">
                     <button onclick="Studio.removeBlock('${id}')" class="text-gray-600 hover:text-red-500"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>
                </div>
            </div>
        `;

        container.appendChild(div);
        
        // Populate speakers for this new block
        this.populateBlockSpeakers(id);
    },

    removeBlock(id) {
        const el = document.getElementById(`block-${id}`);
        if(el) {
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 200);
        }
        this.blocks = this.blocks.filter(b => b.id !== id);
    },

    updateBlock(id, key, value) {
        const block = this.blocks.find(b => b.id === id);
        if(block) {
            block[key] = value;
            if(key === 'speaker') {
                this.updateBlockStyles(id, value);
            }
        }
    },

    clearAll() {
        if(confirm("Clear all blocks?")) {
            document.getElementById('script-container').innerHTML = `
                <div class="text-center mt-20 text-gray-600 flex flex-col items-center">
                    <p class="text-sm">Start by adding a dialogue block.</p>
                </div>
            `;
            this.blocks = [];
        }
    },

    // --- LOGIC ---

    populateBlockSpeakers(blockId) {
        const select = document.querySelector(`#block-${blockId} .studio-speaker-select`);
        if(!select || !window.CurrentSpeakersMap) return;

        Object.keys(window.CurrentSpeakersMap).forEach(spkName => {
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
        // Default select first
        this.updateBlock(blockId, 'style', styles[0]);
    },

    async playAll() {
        if(this.blocks.length === 0) return UI.showToast("No blocks to render", "error");
        
        const btn = document.getElementById('studio-play-btn');
        const originalText = btn.innerHTML;
        btn.innerHTML = `<span class="animate-spin">↻</span> RENDERING...`;
        btn.disabled = true;

        try {
            // Sequential Generation
            const audioQueue = [];
            
            for(let i=0; i<this.blocks.length; i++) {
                const block = this.blocks[i];
                if(!block.text.trim() || !block.speaker) continue;

                // Highlight current block
                const el = document.getElementById(`block-${block.id}`);
                el.classList.add('border-blue-500');

                // Prepare Params
                // "SpeakerName" or "SpeakerName/Style"
                let finalSpeakerID = block.speaker;
                if(block.style && block.style !== 'default') {
                    finalSpeakerID = `${block.speaker}/${block.style}`;
                }

                const params = {
                    text: block.text,
                    language: document.getElementById('lang').value || 'en', // Global lang setting
                    speaker_idx: finalSpeakerID,
                    temperature: 0.75, // Standard defaults for Studio
                    speed: 1.0,
                    stream: false
                };

                const response = await API.generateTTS(params);
                const blob = await response.blob();
                audioQueue.push(blob);

                el.classList.remove('border-blue-500');
                el.classList.add('border-green-500/50');
            }

            btn.innerHTML = `▶ PLAYING...`;
            await this.playQueue(audioQueue);

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
    }
};