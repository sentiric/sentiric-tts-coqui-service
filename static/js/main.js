let isPlaying = false;
let abortController = null;

document.addEventListener('DOMContentLoaded', () => {
    if(window.initUIEvents) window.initUIEvents();
    loadSpeakers();
    const player = document.getElementById('classicPlayer');
    if(player) {
        player.onended = () => {
            if(isPlaying && !document.getElementById('stream').checked) {
                 stopPlayback(false); 
            }
        };
    }
});

// --- NEW: Audio Core'dan gelen "Her şey bitti" sinyali ---
window.onAudioPlaybackComplete = function() {
    console.log("Stream playback finished naturally.");
    stopPlayback(false); // UI'ı resetle
};

// ... (clearAllHistory, deleteHistory, loadHistoryData, playHistory, loadSpeakers, rescanSpeakers AYNI KALACAK) ...
// (Bu fonksiyonlarda değişiklik yok, token tasarrufu için kısalttım)
window.clearAllHistory = async function() {
    if(!confirm('WARNING: This will delete ALL history...')) return;
    try {
        const res = await fetch('/api/history/all', { method: 'DELETE' });
        const data = await res.json();
        if(res.ok) { alert(`Cleanup Complete.\nDeleted Files: ${data.files_deleted}`); await loadHistoryData(); } 
        else { alert("Cleanup failed."); }
    } catch(e) { console.error(e); }
}
window.deleteHistory = async function(filename) {
    if(!confirm('Delete this entry?')) return;
    try {
        const res = await fetch(`/api/history/${filename}`, { method: 'DELETE' });
        if(res.ok) {
            const btn = document.querySelector(`button[onclick="deleteHistory('${filename}')"]`);
            if(btn) { const row = btn.closest('.group'); if(row) row.remove(); }
        } else { alert("Failed to delete."); }
    } catch(e) { console.error(e); }
}
window.loadHistoryData = async function() {
    const list = document.getElementById('historyList');
    if(!list) return;
    const header = `
    <div class="flex justify-between items-center mb-4 px-1">
        <span class="text-[10px] text-gray-500 font-bold uppercase">Recent Generations</span>
        <button onclick="clearAllHistory()" class="text-[9px] text-red-500 hover:text-red-400 bg-red-900/10 px-2 py-1 rounded border border-red-900/30 hover:bg-red-900/30 transition-all">CLEAR ALL</button>
    </div>`;
    list.innerHTML = '<div class="text-center text-[10px] text-gray-600 mt-10">Loading...</div>';
    try {
        const res = await fetch('/api/history');
        const data = await res.json();
        list.innerHTML = header;
        if(data.length === 0) { list.innerHTML += '<div class="text-center text-[10px] text-gray-600 mt-10">No history yet...</div>'; return; }
        data.forEach(item => {
            const el = document.createElement('div');
            el.className = 'bg-[#18181b] p-3 rounded-lg border border-white/5 hover:border-blue-500/30 transition-colors group flex flex-col gap-2 mb-2';
            const timeStr = item.date ? item.date.split(' ')[1] : '';
            el.innerHTML = `
                <div class="flex justify-between items-start">
                    <span class="text-[9px] font-bold text-blue-400 bg-blue-900/20 px-1.5 py-0.5 rounded uppercase">${item.mode || 'TTS'}</span>
                    <div class="flex items-center gap-2">
                         <span class="text-[9px] text-gray-600 font-mono">${timeStr}</span>
                         <button onclick="deleteHistory('${item.filename}')" class="text-gray-600 hover:text-red-500 transition-colors" title="Delete"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg></button>
                    </div>
                </div>
                <p class="text-xs text-gray-300 line-clamp-2 italic border-l-2 border-gray-700 pl-2">"${item.text}"</p>
                <div class="flex justify-between items-center pt-1 border-t border-white/5 mt-1">
                    <span class="text-[10px] text-gray-500 truncate max-w-[120px] flex items-center gap-1" title="${item.speaker}">
                        ${item.mode === 'Cloning' ? '🧬' : '🎙️'} ${item.speaker || 'Unknown'}
                    </span>
                    <div class="flex gap-2">
                        <button onclick="playHistory('${item.filename}')" class="text-gray-400 hover:text-white transition-colors p-1 rounded hover:bg-white/10" title="Play"><svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></button>
                        <a href="/api/history/audio/${item.filename}" download class="text-gray-400 hover:text-blue-400 transition-colors p-1 rounded hover:bg-white/10" title="Download"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg></a>
                    </div>
                </div>`;
            list.appendChild(el);
        });
    } catch(e) { console.error(e); list.innerHTML = '<div class="text-center text-red-500 text-xs">Error loading history</div>'; }
}
window.playHistory = function(filename) {
    if(window.resetAudioState) window.resetAudioState();
    const url = `/api/history/audio/${filename}`;
    const player = document.getElementById('classicPlayer');
    if(player) { player.src = url; player.play(); }
}
async function loadSpeakers() {
    try {
        const res = await fetch('/api/speakers');
        const data = await res.json();
        const sel = document.getElementById('speaker');
        if(!sel) return; sel.innerHTML = '';
        const groups = { 'Female': [], 'Male': [], 'Other': [] };
        data.speakers.forEach(s => { if(s.includes('F_')) groups['Female'].push(s); else if(s.includes('M_')) groups['Male'].push(s); else groups['Other'].push(s); });
        Object.keys(groups).forEach(k => { if(groups[k].length) { const g = document.createElement('optgroup'); g.label = k; groups[k].forEach(s => { const o = document.createElement('option'); o.value = s; o.innerText = s.replace('[FILE] ','').replace('F_','').replace('M_','').replace('.wav','').replace(/_/g,' '); g.appendChild(o); }); sel.appendChild(g); } });
    } catch(e){ console.error("Speaker Load Error:", e); }
}
window.rescanSpeakers = async function() {
    if(window.confirm("Scan disk for new speakers?")) {
        try { const res = await fetch('/api/speakers/refresh', { method: 'POST' }); const d = await res.json(); alert(d.message); await loadSpeakers(); } catch (e) { alert("Error: " + e.message); }
    }
}

async function handleGenerate() {
    if (isPlaying) { stopPlayback(true); return; }

    const textInput = document.getElementById('textInput');
    const text = textInput ? textInput.value.trim() : "";
    if (!text) return alert("Please enter text.");
    
    let isStream = document.getElementById('stream').checked;
    if (text.startsWith('<speak>') && isStream) { alert("SSML does not support streaming."); isStream = false; }

    setPlayingState(true);
    const startTime = performance.now();
    let firstChunk = false;

    if(window.initAudioContext) window.initAudioContext();

    try {
        abortController = new AbortController();
        const modePanel = document.getElementById('panel-std');
        const mode = (modePanel && !modePanel.classList.contains('hidden')) ? 'standard' : 'clone';
        
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

        let body, headers = {};
        const url = mode === 'standard' ? '/api/tts' : '/api/tts/clone';

        if (mode === 'standard') {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify({ ...params, speaker_idx: document.getElementById('speaker').value });
        } else {
            const fd = new FormData();
            if (window.recordedBlob) { fd.append('files', window.recordedBlob, 'recording.webm'); } 
            else {
                const fileInput = document.getElementById('ref_audio');
                const file = fileInput ? fileInput.files[0] : null;
                if (!file) throw new Error("Please upload a file or record audio for cloning.");
                fd.append('files', file);
            }
            Object.entries(params).forEach(([k,v]) => fd.append(k,v));
            body = fd;
        }

        if (mode === 'clone') setStatusText("ANALYZING VOICE...");

        const response = await fetch(url, { method: 'POST', headers, body, signal: abortController.signal });
        
        if (!response.ok) {
            const errText = await response.text();
            throw new Error(errText || "Server Error");
        }

        if (params.stream) {
            const reader = response.body.getReader();
            if(window.resetAudioState) window.resetAudioState();
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                if (!firstChunk) {
                    firstChunk = true;
                    updateLatency(Math.round(performance.now() - startTime));
                    setStatusText("STREAMING");
                }
                const float32 = convertInt16ToFloat32(new Int16Array(value.buffer, value.byteOffset, value.byteLength / 2));
                await playChunk(float32, 24000);
            }
            
            // --- FIX: STOP PLAYBACK ÇAĞIRMIYORUZ ---
            // Sadece indirme bitti diye haber veriyoruz.
            // UI resetleme işini audio-core.js'deki callback yapacak.
            if(window.notifyDownloadFinished) window.notifyDownloadFinished();
            
        } else {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const player = document.getElementById('classicPlayer');
            if(player) { player.src = url; player.play(); }
            updateLatency(Math.round(performance.now() - startTime));
            setStatusText("PLAYING (NON-STREAM)");
            await loadHistoryData(); 
        }

    } catch (err) {
        if (err.name !== 'AbortError') { alert("Error: " + err.message); console.error(err); stopPlayback(false); }
    }
}

function stopPlayback(isUserInitiated = true) {
    if (abortController) { abortController.abort(); abortController = null; }
    if(window.resetAudioState) window.resetAudioState();
    const player = document.getElementById('classicPlayer');
    if(player) { player.pause(); if(isUserInitiated) player.currentTime = 0; }
    setPlayingState(false);
    const stat = document.getElementById('latencyStat');
    if(stat) stat.classList.add('hidden');
    setStatusText("READY");
    isPlaying = false;
}