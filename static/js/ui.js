const $ = id => document.getElementById(id);

class UI {
    static initFromConfig(config) {
        if (!config) return;

        $('app-version').innerText = `v${config.version}`;
        
        const langSelect = $('global-lang');
        if (config.limits.supported_languages) {
            langSelect.innerHTML = '';
            config.limits.supported_languages.forEach(lang => {
                const opt = document.createElement('option');
                opt.value = lang.code;
                opt.innerText = lang.name.toUpperCase();
                if (lang.code === config.defaults.language) opt.selected = true;
                langSelect.appendChild(opt);
            });
        }

        const d = config.defaults;
        this._setupSlider('speed', d.speed, 0.25, 4.0, 0.1);
        this._setupSlider('temp', d.temperature, 0.01, 2.0, 0.05);
        this._setupSlider('rep_pen', d.repetition_penalty, 1.0, 10.0, 0.1);
        this._setupSlider('top_p', d.top_p, 0.01, 1.0, 0.05);
        this._setupSlider('top_k', d.top_k, 1, 100, 1);
        
        const streamCheck = $('stream');
        if(streamCheck) streamCheck.checked = config.system.streaming_enabled;
    }

    static _setupSlider(id, def, min, max, step) {
        const el = $(id);
        if (!el) return;
        el.min = min;
        el.max = max;
        el.step = step;
        el.value = def;
        
        let labelTarget = `val-${id}`;
        if(id === 'rep_pen') labelTarget = 'val-rep';
        if(id === 'top_p') labelTarget = 'val-topp';
        if(id === 'top_k') labelTarget = 'val-topk';

        const label = $(labelTarget);
        if (label) {
            label.innerText = def;
            el.addEventListener('input', (e) => label.innerText = e.target.value);
        }
    }

    static toggleAdvanced() {
        const panel = $('advanced-panel');
        const btn = $('adv-toggle-btn');
        if (panel.classList.contains('hidden')) {
            panel.classList.remove('hidden');
            panel.classList.add('animate-slideUp');
            btn.innerText = "Advanced -";
            btn.classList.add('text-blue-500');
        } else {
            panel.classList.add('hidden');
            panel.classList.remove('animate-slideUp');
            btn.innerText = "Advanced +";
            btn.classList.remove('text-blue-500');
        }
    }

    static showToast(message, type = 'info') {
        const container = $('toast-container');
        if (!container) return;
        const toast = document.createElement('div');
        
        let colorClass = "border-blue-500";
        if(type === 'error') colorClass = "border-red-500 bg-red-900/20 text-red-200";
        if(type === 'success') colorClass = "border-green-500 bg-green-900/20 text-green-200";

        toast.className = `fixed bottom-5 right-5 mb-3 p-4 rounded-lg border-l-4 ${colorClass} bg-[#18181b] shadow-2xl flex items-center justify-between min-w-[300px] animate-slideUp z-[200]`;
        toast.innerHTML = `<span class="text-xs font-bold">${message}</span>`;
        
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '×';
        closeBtn.className = "ml-4 text-lg opacity-50 hover:opacity-100";
        closeBtn.onclick = () => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); };
        toast.appendChild(closeBtn);

        document.body.appendChild(toast); // Toast container yerine body'e ekle

        setTimeout(() => {
            if (toast) {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }
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
        }
    }

    static setPlayingState(isPlaying, isHistory = false) {
        const btn = $('genBtn');
        if (!btn) return;

        if(isPlaying) {
            btn.innerHTML = `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"></path></svg> <span>STOP</span>`;
            btn.classList.add('bg-red-600', 'hover:bg-red-500');
            btn.classList.remove('bg-white', 'text-black', 'hover:bg-blue-500');
        } else {
            btn.innerHTML = `<span>GENERATE AUDIO</span>`;
            btn.classList.remove('bg-red-600', 'hover:bg-red-500');
            btn.classList.add('bg-white', 'text-black', 'hover:bg-blue-500');
        }
    }


    static populateSpeakers(data) {
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
        l.innerHTML=`<div class="flex justify-between mb-4"><span class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Recent Files</span><button onclick="Controllers.clearAllHistory()" class="text-[9px] text-red-500 hover:text-red-400 font-bold">CLEAR ALL</button></div>`;
        if(!data.length){l.innerHTML+='<div class="text-center text-xs text-gray-600 mt-10">No history yet.</div>';return;}
        data.forEach(i=>{
            const e=document.createElement('div');
            e.className='bg-[#18181b] p-3 rounded-lg border border-white/5 mb-2 hover:border-blue-500/50 transition-all group';
            e.innerHTML=`<div class="flex justify-between items-center mb-2"><span class="text-[9px] font-bold text-blue-400 bg-blue-900/10 px-2 py-0.5 rounded border border-blue-900/30">${i.mode||'TTS'}</span><button onclick="Controllers.deleteHistory('${i.filename}')" class="text-gray-600 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">×</button></div><p class="text-xs text-gray-300 font-medium truncate cursor-pointer hover:text-white" onclick="Controllers.playHistory('${i.filename}')">"${i.text}"</p><div class="flex justify-between mt-2 pt-2 border-t border-white/5"><span class="text-[9px] text-gray-500">${i.speaker}</span><span class="text-[9px] text-gray-600">${i.date.split(' ')[1]}</span></div>`;
            l.appendChild(e);
        });
    }
}