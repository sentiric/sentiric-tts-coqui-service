const $ = id => document.getElementById(id);

class UI {
    static initFromConfig(config) {
        if (!config) return;

        // 1. App Info
        $('app-version').innerText = `v${config.version}`;
        
        // 2. Defaults & Limits (Sliders)
        const d = config.defaults;
        this._setupSlider('speed', d.speed, 0.25, 4.0, 0.1);
        this._setupSlider('temp', d.temperature, 0.01, 2.0, 0.05);
        this._setupSlider('topk', d.top_k, 1, 100, 1);
        this._setupSlider('topp', d.top_p, 0.01, 1.0, 0.05);
        this._setupSlider('rep', d.repetition_penalty, 1.0, 10.0, 0.1);

        // 3. System Settings
        $('stream').checked = config.system.streaming_enabled;
        
        // 4. Formats
        const fmtSelect = $('format');
        fmtSelect.innerHTML = '';
        config.limits.supported_formats.forEach(fmt => {
            const opt = document.createElement('option');
            opt.value = fmt;
            opt.innerText = fmt.toUpperCase();
            if (fmt === 'wav') opt.selected = true;
            fmtSelect.appendChild(opt);
        });
    }

    static _setupSlider(id, def, min, max, step) {
        const el = $(id);
        if (!el) return;
        el.min = min;
        el.max = max;
        el.step = step;
        el.value = def;
        
        // Label update listener
        const label = $(`val-${id}`);
        if (label) {
            label.innerText = def;
            el.addEventListener('input', (e) => label.innerText = e.target.value);
        }
    }

    static showToast(message, type = 'info') {
        const container = $('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `<span>${message}</span>`;
        
        // Close button
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '×';
        closeBtn.className = "ml-4 text-lg opacity-50 hover:opacity-100";
        closeBtn.onclick = () => toast.remove();
        toast.appendChild(closeBtn);

        container.appendChild(toast);

        // Auto remove
        setTimeout(() => {
            toast.style.animation = 'fadeOut 0.5s forwards';
            setTimeout(() => toast.remove(), 500);
        }, 5000);
    }

    static setBootState(isLoading, statusText = "") {
        const overlay = $('boot-overlay');
        const statusEl = $('boot-status');
        
        if (statusText) statusEl.innerText = statusText;

        if (!isLoading) {
            overlay.style.opacity = '0';
            setTimeout(() => overlay.classList.add('hidden'), 500);
            $('genBtn').disabled = false;
            this.setStatus("READY");
        }
    }

    static setPlayingState(isPlaying) {
        if(isPlaying) {
            $('playIcon').classList.add('hidden');
            $('stopIcon').classList.remove('hidden');
            $('genBtn').classList.replace('bg-white','bg-red-500');
            $('genBtn').classList.add('text-white');
            $('statusText').innerText = "PROCESSING...";
            $('textInput').disabled = true;
        } else {
            $('stopIcon').classList.add('hidden');
            $('playIcon').classList.remove('hidden');
            $('genBtn').classList.replace('bg-red-500','bg-white');
            $('genBtn').classList.remove('text-white');
            $('statusText').innerText = "READY";
            $('textInput').disabled = false;
            $('textInput').focus();
        }
    }

    static setStatus(text) { $('statusText').innerText = text; }
    static updateLatency(ms) { $('latencyVal').innerText = `${ms}ms`; $('latencyStat').classList.remove('hidden'); }

    static populateSpeakers(data) {
        const sel=$('speaker'); if(!sel)return; 
        sel.innerHTML='';
        if (!data.speakers || data.speakers.length === 0) {
            sel.innerHTML = '<option>No speakers found</option>';
            return;
        }
        
        // Grouping logic... (same as before)
        const groups={'Female':[],'Male':[],'Other':[]};
        data.speakers.forEach(s=>{if(s.includes('F_'))groups.Female.push(s);else if(s.includes('M_'))groups.Male.push(s);else groups.Other.push(s)});
        
        Object.keys(groups).forEach(k=>{
            if(groups[k].length){
                const g=document.createElement('optgroup');g.label=k;
                groups[k].forEach(s=>{
                    const o=document.createElement('option');o.value=s;
                    o.innerText=s.replace('[FILE] ','').replace('F_','').replace('M_','').replace('.wav','').replace(/_/g,' ');
                    g.appendChild(o)
                });
                sel.appendChild(g)
            }
        });
    }

    static renderHistory(data) {
        const l=$('historyList'); if(!l)return;
        l.innerHTML=`<div class="flex justify-between mb-2 px-1"><span class="text-[10px] font-bold text-gray-500">RECENT</span><button onclick="Controllers.clearAllHistory()" class="text-[9px] text-red-500 border border-red-900/30 px-2 py-1 rounded hover:bg-red-900/20">CLEAR ALL</button></div>`;
        if(!data.length){l.innerHTML+='<div class="text-center text-xs text-gray-600 mt-5">Empty</div>';return;}
        data.forEach(i=>{
            const e=document.createElement('div');
            e.className='bg-[#18181b] p-2 rounded border border-white/5 mb-2 group hover:border-blue-500/30 transition-colors';
            e.innerHTML=`<div class="flex justify-between"><span class="text-[9px] font-bold text-blue-400 bg-blue-900/20 px-1 rounded">${i.mode||'TTS'}</span><button onclick="Controllers.deleteHistory('${i.filename}')" class="text-gray-600 hover:text-red-500"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button></div><p class="text-xs text-gray-300 italic truncate mt-1 cursor-pointer" onclick="Controllers.playHistory('${i.filename}')">"${i.text}"</p><div class="flex justify-between mt-1 pt-1 border-t border-white/5"><span class="text-[9px] text-gray-500">${i.speaker}</span><button onclick="Controllers.playHistory('${i.filename}')" class="text-gray-400 hover:text-white"><svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></button></div>`;
            l.appendChild(e);
        });
    }

    // ... (Clone UI helpers remain same) ...
    static resetCloneUI(clearInput = true) {
        $('audioPreview').classList.add('hidden');
        $('micBtn').classList.remove('hidden');
        $('fileName').innerText = "Tap to Upload Reference";
        if (clearInput) { const fileInput = $('ref_audio'); if(fileInput) fileInput.value = ''; }
    }
    static showRecordingState(isRec) {
        const b=$('micBtn'); const t=$('micText');
        if(isRec){b.classList.add('recording');t.innerText="Recording...";}
        else{b.classList.remove('recording');t.innerText="Hold to Record";}
    }
    static showRecordingSuccess() { $('audioPreview').classList.remove('hidden'); $('micBtn').classList.add('hidden'); $('fileName').innerText = "Mic Audio Ready"; }
    static updateFileName(name) { $('fileName').innerText = name; }
}