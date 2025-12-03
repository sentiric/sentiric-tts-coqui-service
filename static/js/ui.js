const $ = id => document.getElementById(id);

class UI {
    static initFromConfig(config) {
        if (!config) return;

        $('app-version').innerText = `v${config.version}`;
        
        // Setup Sliders
        const d = config.defaults;
        this._setupSlider('speed', d.speed, 0.25, 4.0, 0.1);
        this._setupSlider('temp', d.temperature, 0.01, 2.0, 0.05);
    }

    static _setupSlider(id, def, min, max, step) {
        const el = $(id);
        if (!el) return;
        el.min = min;
        el.max = max;
        el.step = step;
        el.value = def;
        
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
        
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '×';
        closeBtn.className = "ml-4 text-lg opacity-50 hover:opacity-100";
        closeBtn.onclick = () => toast.remove();
        toast.appendChild(closeBtn);

        container.appendChild(toast);

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
            $('genBtn').innerText = "PROCESSING...";
            $('genBtn').classList.add('animate-pulse');
            $('genBtn').disabled = true;
        } else {
            $('genBtn').innerText = "GENERATE SPEECH";
            $('genBtn').classList.remove('animate-pulse');
            $('genBtn').disabled = false;
        }
    }

    static setStatus(text) { /* legacy support */ }
    static updateLatency(ms) { /* legacy support */ }

    static populateSpeakers(data) {
        // Data format: { "speakers": { "Name": ["style1", "style2"] } }
        const map = data.speakers;
        window.CurrentSpeakersMap = map; 
        
        const sel = $('speaker'); 
        if(!sel) return;
        sel.innerHTML = '';
        
        Object.keys(map).sort().forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.innerText = name;
            sel.appendChild(opt);
        });

        if(sel.value) UI.onSpeakerChange(sel.value);
    }

    static onSpeakerChange(speakerName) {
        const styleContainer = $('style-container');
        const styleSelect = $('style-select');
        
        if(!window.CurrentSpeakersMap || !window.CurrentSpeakersMap[speakerName]) {
            styleContainer.classList.add('hidden');
            return;
        }

        const styles = window.CurrentSpeakersMap[speakerName];
        
        if (styles.length === 1 && styles[0] === 'default') {
            styleContainer.classList.add('hidden');
        } else {
            styleContainer.classList.remove('hidden');
            styleSelect.innerHTML = '';
            styles.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s;
                opt.innerText = s.charAt(0).toUpperCase() + s.slice(1);
                styleSelect.appendChild(opt);
            });
        }
    }

    static renderHistory(data) {
        const l=$('historyList'); if(!l)return;
        l.innerHTML=`<div class="flex justify-between mb-2 px-1"><span class="text-[10px] font-bold text-gray-500">RECENT</span><button onclick="Controllers.clearAllHistory()" class="text-[9px] text-red-500 hover:text-red-400">CLEAR ALL</button></div>`;
        if(!data.length){l.innerHTML+='<div class="text-center text-xs text-gray-600 mt-5">Empty</div>';return;}
        data.forEach(i=>{
            const e=document.createElement('div');
            e.className='bg-[#18181b] p-2 rounded border border-white/5 mb-2 hover:border-blue-500/30 transition-colors';
            e.innerHTML=`<div class="flex justify-between"><span class="text-[9px] font-bold text-blue-400 bg-blue-900/20 px-1 rounded">${i.mode||'TTS'}</span><button onclick="Controllers.deleteHistory('${i.filename}')" class="text-gray-600 hover:text-red-500">×</button></div><p class="text-xs text-gray-300 italic truncate mt-1 cursor-pointer" onclick="Controllers.playHistory('${i.filename}')">"${i.text}"</p>`;
            l.appendChild(e);
        });
    }

    static resetCloneUI(clearInput = true) {
        $('fileName').innerText = "Upload Reference Audio";
        if (clearInput) { const fileInput = $('ref_audio'); if(fileInput) fileInput.value = ''; }
    }
    static showRecordingSuccess() { $('fileName').innerText = "Mic Audio Ready"; }
    static updateFileName(name) { $('fileName').innerText = name; }
}