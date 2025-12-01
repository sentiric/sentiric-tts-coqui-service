const $ = id => document.getElementById(id);

class UI {

    static setPlayingState(isPlaying) {
        if(isPlaying) {
            $('playIcon').classList.add('hidden');
            $('stopIcon').classList.remove('hidden');
            $('genBtn').classList.replace('bg-white','bg-red-500');
            $('genBtn').classList.add('text-white');
            $('statusText').innerText = "PROCESSING...";
            // Kullanıcı tekrar basamasın diye butonu disable etmiyoruz (stop için lazım)
            // Ama inputları disable edebiliriz.
        } else {
            $('stopIcon').classList.add('hidden');
            $('playIcon').classList.remove('hidden');
            $('genBtn').classList.replace('bg-red-500','bg-white');
            $('genBtn').classList.remove('text-white');
            $('statusText').innerText = "READY";
            $('latencyStat').classList.add('hidden');
        }
    }

    // YENİ: Global Hata Gösterimi
    static showError(message) {
        const statusEl = $('statusText');
        statusEl.innerText = "ERROR!";
        statusEl.classList.add('text-red-500');
        
        // Basit bir toast veya alert
        alert(`⚠️ Operation Failed:\n${message}`);
        
        setTimeout(() => {
            statusEl.innerText = "READY";
            statusEl.classList.remove('text-red-500');
        }, 3000);
        
        this.setPlayingState(false);
    }

    static updateLatency(ms) { $('latencyVal').innerText = `${ms}ms`; $('latencyStat').classList.remove('hidden'); }
    static setStatus(text) { $('statusText').innerText = text; }
    static populateSpeakers(data) {
        const sel=$('speaker'); if(!sel)return; sel.innerHTML='';
        const groups={'Female':[],'Male':[],'Other':[]};
        data.speakers.forEach(s=>{if(s.includes('F_'))groups.Female.push(s);else if(s.includes('M_'))groups.Male.push(s);else groups.Other.push(s)});
        Object.keys(groups).forEach(k=>{if(groups[k].length){const g=document.createElement('optgroup');g.label=k;groups[k].forEach(s=>{const o=document.createElement('option');o.value=s;o.innerText=s.replace('[FILE] ','').replace('F_','').replace('M_','').replace('.wav','').replace(/_/g,' ');g.appendChild(o)});sel.appendChild(g)}});
    }
    static renderHistory(data) {
        const l=$('historyList'); if(!l)return;
        l.innerHTML=`<div class="flex justify-between mb-2 px-1"><span class="text-[10px] font-bold text-gray-500">RECENT</span><button onclick="Controllers.clearAllHistory()" class="text-[9px] text-red-500 border border-red-900/30 px-2 py-1 rounded">CLEAR ALL</button></div>`;
        if(!data.length){l.innerHTML+='<div class="text-center text-xs text-gray-600 mt-5">Empty</div>';return;}
        data.forEach(i=>{const e=document.createElement('div');e.className='bg-[#18181b] p-2 rounded border border-white/5 mb-2 group';e.innerHTML=`<div class="flex justify-between"><span class="text-[9px] font-bold text-blue-400 bg-blue-900/20 px-1 rounded">${i.mode||'TTS'}</span><button onclick="Controllers.deleteHistory('${i.filename}')" class="text-gray-600 hover:text-red-500"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button></div><p class="text-xs text-gray-300 italic truncate mt-1">"${i.text}"</p><div class="flex justify-between mt-1 pt-1 border-t border-white/5"><span class="text-[9px] text-gray-500">${i.speaker}</span><button onclick="Controllers.playHistory('${i.filename}')" class="text-gray-400 hover:text-white"><svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></button></div>`;l.appendChild(e);});
    }
    static resetCloneUI(clearInput = true) {
        $('audioPreview').classList.add('hidden');
        $('micBtn').classList.remove('hidden');
        $('fileName').innerText = "Click / Drop File";
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

// --- YENİ EKLENTİ: VCA EVENT LISTENER ---
document.addEventListener('vca-update', (e) => {
    const m = e.detail;
    const panel = document.getElementById('vca-panel');
    
    if(m.time) {
        panel.classList.remove('hidden');
        document.getElementById('vca-time').innerText = `${m.time}s`;
        document.getElementById('vca-chars').innerText = m.chars;
        
        const rtfEl = document.getElementById('vca-rtf');
        rtfEl.innerText = m.rtf;
        
        // RTF'e göre renk değiştir (Düşük RTF = İyi Performans)
        const rtfVal = parseFloat(m.rtf);
        if (rtfVal < 0.1) rtfEl.className = "font-bold text-green-400";
        else if (rtfVal < 0.5) rtfEl.className = "font-bold text-yellow-400";
        else rtfEl.className = "font-bold text-red-400";
        
        panel.classList.add('animate-pulse');
        setTimeout(() => panel.classList.remove('animate-pulse'), 500);
    }
});