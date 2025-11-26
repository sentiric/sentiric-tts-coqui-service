const $ = id => document.getElementById(id);

class UI {
    static toggleSpinner(show) {
        // İlerde spinner eklersek burayı doldururuz
    }

    static setPlayingState(isPlaying) {
        if(isPlaying) {
            $('playIcon').classList.add('hidden');
            $('stopIcon').classList.remove('hidden');
            $('genBtn').classList.replace('bg-white','bg-red-500');
            $('genBtn').classList.add('text-white');
            $('statusText').innerText = "INITIALIZING...";
            
            const mobBtn = $('mobileGenBtn');
            if(mobBtn) {
                mobBtn.innerHTML = '<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M6 6h12v12H6z"/></svg>';
                mobBtn.classList.add('bg-red-500'); mobBtn.classList.remove('bg-blue-600');
            }
        } else {
            $('stopIcon').classList.add('hidden');
            $('playIcon').classList.remove('hidden');
            $('genBtn').classList.replace('bg-red-500','bg-white');
            $('genBtn').classList.remove('text-white');
            $('statusText').innerText = "READY";
            
            const mobBtn = $('mobileGenBtn');
            if(mobBtn) {
                mobBtn.innerHTML = '<svg class="w-6 h-6 ml-1" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
                mobBtn.classList.remove('bg-red-500'); mobBtn.classList.add('bg-blue-600');
            }
            $('latencyStat').classList.add('hidden');
        }
    }

    static updateLatency(ms) {
        $('latencyVal').innerText = `${ms}ms`;
        $('latencyStat').classList.remove('hidden');
    }

    static setStatus(text) {
        $('statusText').innerText = text;
    }

    static populateSpeakers(data) {
        const sel = $('speaker');
        if(!sel) return;
        sel.innerHTML = '';
        const groups = { 'Female': [], 'Male': [], 'Other': [] };
        
        data.speakers.forEach(s => {
            if(s.includes('F_')) groups['Female'].push(s);
            else if(s.includes('M_')) groups['Male'].push(s);
            else groups['Other'].push(s);
        });

        Object.keys(groups).forEach(k => {
            if(groups[k].length) {
                const g = document.createElement('optgroup'); 
                g.label = k;
                groups[k].forEach(s => {
                    const o = document.createElement('option'); 
                    o.value = s;
                    o.innerText = s.replace('[FILE] ','').replace('F_','').replace('M_','').replace('.wav','').replace(/_/g,' ');
                    g.appendChild(o);
                });
                sel.appendChild(g);
            }
        });
    }

    static renderHistory(data) {
        const list = $('historyList');
        if(!list) return;
        
        const header = `
        <div class="flex justify-between items-center mb-4 px-1">
            <span class="text-[10px] text-gray-500 font-bold uppercase">Recent Generations</span>
            <button onclick="Controllers.clearAllHistory()" class="text-[9px] text-red-500 hover:text-red-400 bg-red-900/10 px-2 py-1 rounded border border-red-900/30 hover:bg-red-900/30 transition-all">CLEAR ALL</button>
        </div>`;
        
        list.innerHTML = header;
        
        if(data.length === 0) {
            list.innerHTML += '<div class="text-center text-[10px] text-gray-600 mt-10">No history yet...</div>';
            return;
        }

        data.forEach(item => {
            const el = document.createElement('div');
            el.className = 'bg-[#18181b] p-3 rounded-lg border border-white/5 hover:border-blue-500/30 transition-colors group flex flex-col gap-2 mb-2';
            const timeStr = item.date ? item.date.split(' ')[1] : '';
            
            el.innerHTML = `
                <div class="flex justify-between items-start">
                    <span class="text-[9px] font-bold text-blue-400 bg-blue-900/20 px-1.5 py-0.5 rounded uppercase">${item.mode || 'TTS'}</span>
                    <div class="flex items-center gap-2">
                         <span class="text-[9px] text-gray-600 font-mono">${timeStr}</span>
                         <button onclick="Controllers.deleteHistory('${item.filename}')" class="text-gray-600 hover:text-red-500 transition-colors" title="Delete">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                         </button>
                    </div>
                </div>
                <p class="text-xs text-gray-300 line-clamp-2 italic border-l-2 border-gray-700 pl-2">"${item.text}"</p>
                <div class="flex justify-between items-center pt-1 border-t border-white/5 mt-1">
                    <span class="text-[10px] text-gray-500 truncate max-w-[120px] flex items-center gap-1" title="${item.speaker}">
                        ${item.mode === 'Cloning' ? '🧬' : '🎙️'} ${item.speaker || 'Unknown'}
                    </span>
                    <div class="flex gap-2">
                        <button onclick="Controllers.playHistory('${item.filename}')" class="text-gray-400 hover:text-white transition-colors p-1 rounded hover:bg-white/10" title="Play">
                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                        </button>
                        <a href="/api/history/audio/${item.filename}" download class="text-gray-400 hover:text-blue-400 transition-colors p-1 rounded hover:bg-white/10" title="Download">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                        </a>
                    </div>
                </div>
            `;
            list.appendChild(el);
        });
    }

    static initCloneEvents() {
        const fileInput = $('ref_audio');
        if(fileInput) {
            fileInput.addEventListener('change', (e) => { 
                $('fileName').innerText = e.target.files[0] ? e.target.files[0].name : 'Drop .WAV here';
                UI.clearRecordingUI(); 
            });
        }
    }

    static toggleMicUI(isRecording) {
        const btn = $('micBtn');
        const txt = $('micText');
        if(isRecording) {
            btn.classList.add('recording'); // CSS'de tanımlı pulse animasyonu
            txt.innerText = "Recording...";
        } else {
            btn.classList.remove('recording');
            txt.innerText = "Hold to Record";
        }
    }

    static onRecordingComplete() {
        $('audioPreview').classList.remove('hidden');
        $('micBtn').classList.add('hidden');
        $('fileName').innerText = "Using Microphone Audio";
    }

    static clearRecordingUI() {
        // Global audio core fonksiyonunu çağır (Veriyi temizle)
        if(window.clearRecordingData) window.clearRecordingData();
        
        $('audioPreview').classList.add('hidden');
        $('micBtn').classList.remove('hidden');
        $('fileName').innerText = "Click / Drop File";
        
        // Dosya inputunu da sıfırla
        const fileInput = $('ref_audio');
        if(fileInput) fileInput.value = '';
    }    
}