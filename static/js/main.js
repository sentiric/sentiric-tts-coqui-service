let isPlaying = false;
let abortController = null;

document.addEventListener('DOMContentLoaded', () => {
    if(window.initUIEvents) window.initUIEvents();
    loadSpeakers();
    
    const player = document.getElementById('classicPlayer');
    if(player) {
        player.onended = () => {
            if(isPlaying && !document.getElementById('stream').checked) {
                 stopPlayback(false); // Doğal bitiş
            }
        };
    }
});

// Stream bittiğinde çağrılır
window.onAudioPlaybackComplete = function() {
    console.log("Stream playback finished naturally.");
    stopPlayback(false); // Doğal bitiş
};

// ... (History, Speaker, Delete fonksiyonları AYNI - Değişiklik yok) ...
// Kod kalabalığı olmasın diye burayı kısalttım, önceki commit'teki haliyle kalacak.
window.clearAllHistory = async function() { if(!confirm('Delete ALL?')) return; try { await fetch('/api/history/all', { method: 'DELETE' }); await loadHistoryData(); alert("Cleared"); } catch(e) {} }
window.deleteHistory = async function(filename) { if(!confirm('Delete?')) return; try { const res = await fetch(`/api/history/${filename}`, { method: 'DELETE' }); if(res.ok) { const btn = document.querySelector(`button[onclick="deleteHistory('${filename}')"]`); if(btn) btn.closest('.group').remove(); } } catch(e) {} }
window.loadHistoryData = async function() { const l = document.getElementById('historyList'); if(!l) return; l.innerHTML = 'Loading...'; try { const r = await fetch('/api/history'); const d = await r.json(); let h = `<div class="flex justify-between mb-2 px-1"><span class="text-[10px] font-bold text-gray-500">RECENT</span><button onclick="clearAllHistory()" class="text-[9px] text-red-500 border border-red-900/30 px-2 py-1 rounded">CLEAR ALL</button></div>`; if(!d.length) { l.innerHTML = h + '<div class="text-center text-xs text-gray-600">Empty</div>'; return; } d.forEach(i => { h += `<div class="bg-[#18181b] p-2 rounded border border-white/5 mb-2 group"><div class="flex justify-between"><span class="text-[9px] font-bold text-blue-400 bg-blue-900/20 px-1 rounded">${i.mode||'TTS'}</span><button onclick="deleteHistory('${i.filename}')" class="text-gray-600 hover:text-red-500"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button></div><p class="text-xs text-gray-300 italic truncate mt-1">"${i.text}"</p><div class="flex justify-between mt-1 pt-1 border-t border-white/5"><span class="text-[9px] text-gray-500">${i.speaker}</span><button onclick="playHistory('${i.filename}')" class="text-gray-400 hover:text-white"><svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></button></div></div>`; }); l.innerHTML = h; } catch(e) { l.innerHTML = 'Error'; } }
window.playHistory = function(f) { if(window.resetAudioState) window.resetAudioState(); const p = document.getElementById('classicPlayer'); if(p) { p.src = `/api/history/audio/${f}`; p.play(); } }
async function loadSpeakers() { try { const r = await fetch('/api/speakers'); const d = await r.json(); const s = document.getElementById('speaker'); if(!s) return; s.innerHTML = ''; const g = {'Female':[],'Male':[],'Other':[]}; d.speakers.forEach(i=>{if(i.includes('F_'))g.Female.push(i);else if(i.includes('M_'))g.Male.push(i);else g.Other.push(i)}); Object.keys(g).forEach(k=>{if(g[k].length){const o = document.createElement('optgroup');o.label=k;g[k].forEach(i=>{const el=document.createElement('option');el.value=i;el.innerText=i.replace('[FILE] ','').replace('F_','').replace('M_','').replace('.wav','').replace(/_/g,' ');o.appendChild(el)});s.appendChild(o)}}); } catch(e){} }
window.rescanSpeakers = async function() { if(confirm("Rescan?")) { try { await fetch('/api/speakers/refresh', {method:'POST'}); await loadSpeakers(); alert("Done"); } catch(e){} } }

async function handleGenerate() {
    // --- FIX 1: STOP STATE CHECK ---
    // isPlaying değişkeni artık doğru çalışacak
    if (isPlaying) { 
        stopPlayback(true); // Kullanıcı durdurdu
        return; 
    }

    const textInput = document.getElementById('textInput');
    const text = textInput ? textInput.value.trim() : "";
    if (!text) return alert("Please enter text.");
    
    let isStream = document.getElementById('stream').checked;
    if (text.startsWith('<speak>') && isStream) { alert("SSML no stream."); isStream = false; }

    setPlayingState(true);
    // --- FIX 2: STATE SENKRONİZASYONU ---
    // UI kırmızıya döner dönmez mantıksal olarak da "Çalıyor" demeliyiz.
    isPlaying = true; 

    const startTime = performance.now();
    let firstChunk = false;

    if(window.initAudioContext) window.initAudioContext();
    // Yeni başladığı için motoru sıfırla
    if(window.resetAudioState) window.resetAudioState();

    try {
        abortController = new AbortController();
        
        // Form data hazırlığı
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
                const f = document.getElementById('ref_audio').files[0];
                if (!f) throw new Error("No file.");
                fd.append('files', f);
            }
            Object.entries(params).forEach(([k,v]) => fd.append(k,v));
            body = fd;
        }

        if (mode === 'clone') setStatusText("ANALYZING...");

        const response = await fetch(url, { method: 'POST', headers, body, signal: abortController.signal });
        
        if (!response.ok) { throw new Error(await response.text()); }

        if (params.stream) {
            const reader = response.body.getReader();
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
            if(window.notifyDownloadFinished) window.notifyDownloadFinished();
            
        } else {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const player = document.getElementById('classicPlayer');
            if(player) { player.src = url; player.play(); }
            updateLatency(Math.round(performance.now() - startTime));
            setStatusText("PLAYING");
            await loadHistoryData(); 
        }

    } catch (err) {
        if (err.name !== 'AbortError') { 
            alert("Error: " + err.message); 
            stopPlayback(false); 
        }
    }
}

function stopPlayback(isUserInitiated = true) {
    if (isUserInitiated) {
        // --- FIX 3: AGRESİF DURDURMA ---
        // Sadece kullanıcı durdurduysa bağlantıyı ve sesi kes.
        console.log("User stopped playback.");
        if (abortController) { abortController.abort(); abortController = null; }
        if(window.resetAudioState) window.resetAudioState();
        const player = document.getElementById('classicPlayer');
        if(player) { player.pause(); player.currentTime = 0; }
    } else {
        // Doğal bitiş: Hiçbir şeyi öldürme, sadece UI'ı güncelle.
        // Böylece son kelime ("ağzı bozuk") kesilmeden biter.
        console.log("Playback finished naturally.");
    }

    setPlayingState(false);
    // --- FIX 4: STATE SIFIRLAMA ---
    isPlaying = false;
    
    const stat = document.getElementById('latencyStat');
    if(stat) stat.classList.add('hidden');
    setStatusText("READY");
}