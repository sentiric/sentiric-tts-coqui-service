const State = { isPlaying: false, abortController: null };

const Controllers = {
    // ... (Diğer metodlar AYNI) ...
    async loadSpeakers() { try{UI.populateSpeakers(await API.getSpeakers());}catch(e){console.error(e);} },
    async loadHistory() { try{UI.renderHistory(await API.getHistory());}catch(e){console.error(e);} },
    async rescanSpeakers() { if(confirm("Rescan?")) try{await API.refreshSpeakers();this.loadSpeakers();}catch(e){alert(e);} },
    async clearAllHistory() { if(confirm("Delete All?")) try{await API.deleteAllHistory();this.loadHistory();}catch(e){console.error(e);} },
    async deleteHistory(f) { if(confirm("Delete?")) try{if(await API.deleteHistory(f)) document.querySelector(`button[onclick*='${f}']`).closest('.group').remove();}catch(e){console.error(e);} },
    playHistory(f) { if(window.resetAudioState) window.resetAudioState(); const p = document.getElementById('classicPlayer'); if(p){p.src=`/api/history/audio/${f}`; p.play();} },
    stopPlayback(isUserInitiated=true) { if(isUserInitiated) { if(State.abortController){State.abortController.abort();State.abortController=null;} if(window.resetAudioState)window.resetAudioState(); const p=document.getElementById('classicPlayer');if(p){p.pause();p.currentTime=0;} } UI.setPlayingState(false); State.isPlaying=false; UI.setStatus("READY"); },

    // --- CLONE LOGIC ---
    handleFileSelect(e) {
        const f = e.target.files[0];
        if(f) { 
            if(window.clearRecordingData) window.clearRecordingData(); 
            // FIX: false parametresi ile inputu silme diyoruz
            UI.resetCloneUI(false); 
            UI.updateFileName(f.name); 
        }
    },
    handleRecordingComplete() { 
        // Mikrofon kaydı bittiğinde inputu silebiliriz (true)
        UI.resetCloneUI(true); 
        UI.showRecordingSuccess(); 
    },
    clearCloneData() { 
        if(window.clearRecordingData) window.clearRecordingData(); 
        UI.resetCloneUI(true); // X butonuna basınca her şeyi sil
    },

    // ... (handleGenerate AYNI) ...
    async handleGenerate() {
        if(State.isPlaying) { this.stopPlayback(true); return; }
        const text = document.getElementById('textInput').value.trim();
        if(!text) return alert("Text required.");
        const isStream = document.getElementById('stream').checked;
        if(text.startsWith('<speak>') && isStream) { alert("SSML no stream."); return; }

        UI.setPlayingState(true); State.isPlaying=true;
        const startTime = performance.now();
        let firstChunk=false;

        if(window.initAudioContext) window.initAudioContext();
        if(window.resetAudioState) window.resetAudioState();

        try {
            State.abortController = new AbortController();
            const mode = document.getElementById('panel-std').classList.contains('hidden') ? 'clone' : 'standard';
            
            const params = {
                text, language: document.getElementById('lang').value,
                temperature: document.getElementById('temp').value,
                speed: document.getElementById('speed').value,
                top_k: document.getElementById('topk').value, top_p: document.getElementById('topp').value,
                repetition_penalty: document.getElementById('rep').value,
                stream: isStream, output_format: document.getElementById('format').value,
                sample_rate: parseInt(document.getElementById('sampleRate').value)
            };

            let res;
            if(mode==='standard') {
                params.speaker_idx = document.getElementById('speaker').value;
                res = await API.generateTTS(params, State.abortController.signal);
            } else {
                const fd = new FormData();
                if(window.recordedBlob) fd.append('files', window.recordedBlob, 'recording.webm');
                else {
                    const f = document.getElementById('ref_audio').files[0];
                    if(!f) throw new Error("No file.");
                    fd.append('files', f);
                }
                Object.entries(params).forEach(([k,v])=>fd.append(k,v));
                UI.setStatus("ANALYZING...");
                res = await API.generateClone(fd, State.abortController.signal);
            }

            if(isStream) {
                const reader = res.body.getReader();
                while(true) {
                    const {done, value} = await reader.read();
                    if(done) break;
                    if(!firstChunk) { firstChunk=true; UI.updateLatency(Math.round(performance.now()-startTime)); UI.setStatus("STREAMING"); }
                    const f32 = new Float32Array(value.buffer.byteLength/2);
                    const i16 = new Int16Array(value.buffer);
                    for(let i=0; i<i16.length; i++) f32[i] = i16[i] >= 0 ? i16[i]/32767 : i16[i]/32768;
                    await playChunk(f32, 24000);
                }
                if(window.notifyDownloadFinished) window.notifyDownloadFinished();
            } else {
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const p = document.getElementById('classicPlayer');
                if(p){p.src=url; p.play();}
                UI.updateLatency(Math.round(performance.now()-startTime));
                UI.setStatus("PLAYING");
                await this.loadHistory();
            }
        } catch(e) {
            if(e.name !== 'AbortError') { alert("Error: "+e.message); this.stopPlayback(false); }
        }
    }
};

// Bridges
window.Controllers = Controllers;
window.handleGenerate = () => Controllers.handleGenerate();
window.toggleHistory = () => { const d=document.getElementById('historyDrawer');const o=document.getElementById('historyOverlay');if(!d.classList.contains('translate-x-full')){d.classList.add('translate-x-full');o.classList.remove('opacity-100');setTimeout(()=>o.classList.add('hidden'),300);}else{d.classList.remove('translate-x-full');o.classList.remove('hidden');void o.offsetWidth;o.classList.add('opacity-100');Controllers.loadHistory();}};
window.setMode = (m) => { const bS=document.getElementById('btn-std');const bC=document.getElementById('btn-cln');const pS=document.getElementById('panel-std');const pC=document.getElementById('panel-cln');if(m==='standard'){bS.className='flex-1 py-2 text-[10px] font-bold uppercase tracking-wider rounded-md bg-blue-600 text-white shadow-lg transition-all';bC.className='flex-1 py-2 text-[10px] font-bold uppercase tracking-wider rounded-md text-gray-500 hover:text-white transition-all';pS.classList.remove('hidden');pC.classList.add('hidden');}else{bC.className=bS.className;bS.className='flex-1 py-2 text-[10px] font-bold uppercase tracking-wider rounded-md text-gray-500 hover:text-white transition-all';pC.classList.remove('hidden');pS.classList.add('hidden');}};
window.toggleAdvanced = () => { const p=document.getElementById('advanced-panel');const i=document.getElementById('adv-icon');if(p.classList.contains('accordion-open')){p.classList.remove('accordion-open');i.style.transform='rotate(0deg)';}else{p.classList.add('accordion-open');i.style.transform='rotate(180deg)';}};
window.toggleMicUI = (v) => UI.showRecordingState(v);
window.onRecordingComplete = () => Controllers.handleRecordingComplete();
window.clearRecordingUI = () => Controllers.clearCloneData();
window.onAudioPlaybackComplete = () => Controllers.stopPlayback(false);

document.addEventListener('DOMContentLoaded', () => {
    if(window.initUIEvents) window.initUIEvents();
    Controllers.loadSpeakers();
    const fi = document.getElementById('ref_audio'); if(fi) fi.addEventListener('change', (e)=>Controllers.handleFileSelect(e));
    const p = document.getElementById('classicPlayer'); if(p) p.onended = () => { if(State.isPlaying && !document.getElementById('stream').checked) Controllers.stopPlayback(false); };
});