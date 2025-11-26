const $ = id => document.getElementById(id);

function insertSSMLTag(type) {
    const textarea = $('textInput');
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = textarea.value.substring(start, end);
    let newText = '';

    if (type === 'pause') {
        newText = ' <break time="1s"/> ';
        textarea.setRangeText(newText, start, end, 'end');
    } else if (selectedText) {
        if (type === 'emphasize') {
            newText = `<emphasis level="strong">${selectedText}</emphasis>`;
        } else if (type === 'slow') {
            newText = `<prosody rate="slow">${selectedText}</prosody>`;
        }
        textarea.setRangeText(newText, start, end, 'end');
    } else {
        alert("Please select the text you want to wrap with the tag.");
        textarea.focus();
        return;
    }

    const fullText = textarea.value.trim();
    if (fullText && (!fullText.startsWith('<speak>') || !fullText.endsWith('</speak>'))) {
        textarea.value = `<speak>${fullText}</speak>`;
    }

    textarea.focus();
}

function setMode(m) {
    const active = 'flex-1 py-2 text-[10px] font-bold uppercase tracking-wider rounded-md bg-blue-600 text-white shadow-lg transition-all';
    const inactive = 'flex-1 py-2 text-[10px] font-bold uppercase tracking-wider rounded-md text-gray-500 hover:text-white transition-all';
    
    if(m === 'standard') {
        $('btn-std').className = active; $('btn-cln').className = inactive;
        $('panel-std').classList.remove('hidden'); $('panel-cln').classList.add('hidden');
    } else {
        $('btn-cln').className = active; $('btn-std').className = inactive;
        $('panel-cln').classList.remove('hidden'); $('panel-std').classList.add('hidden');
    }
}

function toggleAdvanced() {
    const panel = $('advanced-panel');
    const icon = $('adv-icon');
    if (panel.classList.contains('accordion-open')) {
        panel.classList.remove('accordion-open');
        icon.style.transform = 'rotate(0deg)';
    } else {
        panel.classList.add('accordion-open');
        icon.style.transform = 'rotate(180deg)';
    }
}

function toggleHistory() {
    const d = $('historyDrawer');
    const o = $('historyOverlay');
    const isOpen = !d.classList.contains('translate-x-full');
    
    if(isOpen) {
        d.classList.add('translate-x-full');
        o.classList.remove('opacity-100');
        setTimeout(() => o.classList.add('hidden'), 300);
    } else {
        d.classList.remove('translate-x-full');
        o.classList.remove('hidden');
        void o.offsetWidth;
        o.classList.add('opacity-100');
        if(window.loadHistoryData) window.loadHistoryData();
    }
}

function toggleMicUI(isRecording) {
    if(isRecording) {
        $('micBtn').classList.add('recording');
        $('micText').innerText = "Recording...";
    } else {
        $('micBtn').classList.remove('recording');
        $('micText').innerText = "Hold to Record";
    }
}

function onRecordingComplete() {
    $('audioPreview').classList.remove('hidden');
    $('micBtn').classList.add('hidden');
    $('fileName').innerText = "Using Microphone Audio";
}

function clearRecordingUI() {
    if(window.clearRecordingData) window.clearRecordingData();
    $('audioPreview').classList.add('hidden');
    $('micBtn').classList.remove('hidden');
    $('fileName').innerText = "Click / Drop File";
}

function updVal(id) { $(`val-${id}`).innerText = $(id).value; }

function setPlayingState(playing) {
    if(playing) {
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
    }
}

function updateLatency(ms) {
    $('latencyVal').innerText = `${ms}ms`;
    $('latencyStat').classList.remove('hidden');
}

function setStatusText(text) {
    $('statusText').innerText = text;
}

function initUIEvents() {
    ['temp', 'speed', 'topk', 'topp', 'rep'].forEach(id => $(id).addEventListener('input', () => updVal(id)));
    $('ref_audio').addEventListener('change', (e) => { 
        $('fileName').innerText = e.target.files[0] ? e.target.files[0].name : 'Drop .WAV here';
        clearRecordingUI(); 
    });
}