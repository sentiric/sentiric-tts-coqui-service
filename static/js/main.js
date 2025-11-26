let isPlaying = false;
let abortController = null;

document.addEventListener('DOMContentLoaded', () => {
    if(window.initUIEvents) window.initUIEvents();
    loadSpeakers();
});

window.loadHistoryData = async function() {
    const list = document.getElementById('historyList');
    if(!list) return;
    
    list.innerHTML = '<div class="text-center text-[10px] text-gray-600 mt-10">Loading...</div>';
    
    try {
        const res = await fetch('/api/history');
        const data = await res.json();
        
        list.innerHTML = '';
        if(data.length === 0) {
            list.innerHTML = '<div class="text-center text-[10px] text-gray-600 mt-10">No history yet...</div>';
            return;
        }

        data.forEach(item => {
            const el = document.createElement('div');
            el.className = 'bg-[#18181b] p-3 rounded-lg border border-white/5 hover:border-blue-500/30 transition-colors group flex flex-col gap-2';
            
            const timeStr = item.date ? item.date.split(' ')[1] : '';
            
            el.innerHTML = `
                <div class="flex justify-between items-start">
                    <span class="text-[9px] font-bold text-blue-400 bg-blue-900/20 px-1.5 py-0.5 rounded uppercase">${item.mode || 'TTS'}</span>
                    <span class="text-[9px] text-gray-600 font-mono">${timeStr}</span>
                </div>
                <p class="text-xs text-gray-300 line-clamp-2 italic border-l-2 border-gray-700 pl-2">"${item.text}"</p>
                <div class="flex justify-between items-center pt-1 border-t border-white/5 mt-1">
                    <span class="text-[10px] text-gray-500 truncate max-w-[120px] flex items-center gap-1" title="${item.speaker}">
                        ${item.mode === 'Cloning' ? '🧬' : '🎙️'} ${item.speaker || 'Unknown'}
                    </span>
                    <div class="flex gap-2">
                        <button onclick="playHistory('${item.filename}')" class="text-gray-400 hover:text-white transition-colors p-1 rounded hover:bg-white/10" title="Play">
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

    } catch(e) { 
        console.error(e); 
        list.innerHTML = '<div class="text-center text-red-500 text-xs">Error loading history</div>'; 
    }
}

window.playHistory = function(filename) {
    const url = `/api/history/audio/${filename}`;
    const player = document.getElementById('classicPlayer');
    if(player) {
        player.src = url;
        player.play();
    }
}

async function loadSpeakers() {
    try {
        const res = await fetch('/api/speakers');
        const data = await res.json();
        const sel = document.getElementById('speaker');
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
    } catch(e){ console.error("Speaker Load Error:", e); }
}

window.rescanSpeakers = async function() {
    if(window.confirm("This will scan the disk for new speaker files on the server. Continue?")) {
        try {
            const res = await fetch('/api/speakers/refresh', { method: 'POST' });
            const report = await res.json();

            let alertMessage = `${report.message}\n\n`;
            alertMessage += `Total Scanned: ${report.total_files_scanned}\n`;
            alertMessage += `Newly Loaded: ${report.newly_loaded.length}\n`;
            alertMessage += `Failed to Load: ${Object.keys(report.failed_to_load).length}\n\n`;

            if(Object.keys(report.failed_to_load).length > 0) {
                alertMessage += "Failed Files:\n";
                for(const [file, error] of Object.entries(report.failed_to_load)) {
                    alertMessage += `- ${file}: ${error}\n`;
                }
            }
            
            alert(alertMessage);
            await loadSpeakers();

        } catch (e) {
            alert("An error occurred while rescanning: " + e.message);
        }
    }
}

async function handleGenerate() {
    const textInput = document.getElementById('textInput');
    const text = textInput ? textInput.value.trim() : "";
    
    if (!text) return alert("Please enter text to synthesize.");
    if (isPlaying) { stopPlayback(); return; }
    
    let isStream = document.getElementById('stream').checked;
    const isSSML = text.startsWith('<speak>');

    if (isSSML && isStream) {
        alert("SSML (advanced tags) is not supported in Streaming mode.\n\nYour request will be sent in Normal (high quality) mode to ensure correctness.");
        isStream = false;
    }

    setPlayingState(true);
    const startTime = performance.now();
    let firstChunk = false;

    try {
        abortController = new AbortController();
        const modePanel = document.getElementById('panel-std');
        const mode = (modePanel && !modePanel.classList.contains('hidden')) ? 'standard' : 'clone';
        
        const formatInput = document.getElementById('format');
        const sampleRateInput = document.getElementById('sampleRate');
        
        const params = {
            text: text, 
            language: document.getElementById('lang').value, 
            temperature: document.getElementById('temp').value,
            speed: document.getElementById('speed').value, 
            top_k: document.getElementById('topk').value, 
            top_p: document.getElementById('topp').value,
            repetition_penalty: document.getElementById('rep').value, 
            stream: isStream,
            output_format: formatInput ? formatInput.value : 'wav',
            sample_rate: sampleRateInput ? parseInt(sampleRateInput.value) : 24000
        };

        let body, headers = {};
        const url = mode === 'standard' ? '/api/tts' : '/api/tts/clone';

        if (mode === 'standard') {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify({ ...params, speaker_idx: document.getElementById('speaker').value });
        } else {
            const fd = new FormData();
            if (window.recordedBlob) {
                fd.append('files', window.recordedBlob, 'recording.webm');
            } else {
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
                await playChunk(float32, params.sample_rate);
            }
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
        if (err.name !== 'AbortError') { alert("Error: " + err.message); console.error(err); }
    } finally {
        const finalDelay = document.getElementById('stream').checked && !isSSML ? 1500 : 100;
        setTimeout(() => setPlayingState(false), finalDelay);
    }
}

function stopPlayback() {
    if (abortController) abortController.abort();
    if(window.resetAudioState) window.resetAudioState();
    setPlayingState(false);
    const stat = document.getElementById('latencyStat');
    if(stat) stat.classList.add('hidden');
}