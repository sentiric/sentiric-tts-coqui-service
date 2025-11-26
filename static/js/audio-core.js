const SOURCE_SAMPLE_RATE = 24000;

// Global değişkenleri window altına alarak scope hatalarını engelliyoruz
window._audioContext = null;
window._mediaRecorder = null;
let analyser = null;
let nextStartTime = 0; 
let isDownloadFinished = false;
let sourceNodes = []; 

function initAudioContext() {
    if (!window._audioContext) {
        window._audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = window._audioContext.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8;
        initVisualizer();
    }
    if (window._audioContext.state === 'suspended') { window._audioContext.resume(); }
}

function notifyDownloadFinished() {
    isDownloadFinished = true;
    checkIfPlaybackFinished();
}

function checkIfPlaybackFinished() {
    if (isDownloadFinished && sourceNodes.length === 0) {
        if (window.onAudioPlaybackComplete) window.onAudioPlaybackComplete();
    }
}

async function playChunk(float32Array, serverSampleRate = 24000) {
    initAudioContext();
    if (window.isStopRequested) return;

    const ctx = window._audioContext;
    const buffer = ctx.createBuffer(1, float32Array.length, serverSampleRate);
    buffer.getChannelData(0).set(float32Array);
    
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser);
    analyser.connect(ctx.destination);
    
    const currentTime = ctx.currentTime;

    if (nextStartTime < currentTime) {
        nextStartTime = currentTime;
    }

    source.start(nextStartTime);
    sourceNodes.push(source);
    
    source.onended = () => {
        const index = sourceNodes.indexOf(source);
        if (index > -1) sourceNodes.splice(index, 1);
        checkIfPlaybackFinished();
    };

    nextStartTime += buffer.duration;
}

function resetAudioState() {
    window.isStopRequested = true;
    isDownloadFinished = false;
    sourceNodes.forEach(node => { try { node.stop(); node.disconnect(); } catch(e) {} });
    sourceNodes = [];
    nextStartTime = 0;
    setTimeout(() => { window.isStopRequested = false; }, 200);
}

function convertInt16ToFloat32(int16Data) {
    const float32 = new Float32Array(int16Data.length);
    for (let i = 0; i < int16Data.length; i++) {
        float32[i] = int16Data[i] >= 0 ? int16Data[i] / 32767 : int16Data[i] / 32768;
    }
    return float32;
}

function initVisualizer() {
    const canvas = document.getElementById('visualizer');
    if(!canvas) return;
    const ctx = canvas.getContext('2d');
    
    function resize() { 
        canvas.width = canvas.offsetWidth; 
        canvas.height = canvas.offsetHeight; 
    }
    window.addEventListener('resize', resize); 
    resize();
    
    function draw() {
        requestAnimationFrame(draw);
        if(!analyser) return;
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        analyser.getByteFrequencyData(dataArray);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        const barWidth = (canvas.width / bufferLength) * 2.5;
        let x = 0;
        for(let i = 0; i < bufferLength; i++) {
            const v = dataArray[i] / 255.0;
            const h = v * canvas.height;
            ctx.fillStyle = `rgba(60, 130, 246, ${v + 0.2})`;
            ctx.fillRect(x, canvas.height - h, barWidth, h);
            x += barWidth + 1;
        }
    }
    draw();
}

// --- MİKROFON İŞLEMLERİ (Hata Düzeltmesi) ---

async function startRecording() {
    if (!navigator.mediaDevices) return alert("Mic denied");
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        window._mediaRecorder = new MediaRecorder(stream);
        
        let audioChunks = [];
        
        window._mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        window._mediaRecorder.onstop = () => {
            window.recordedBlob = new Blob(audioChunks, { type: 'audio/webm' });
            if(window.onRecordingComplete) window.onRecordingComplete();
        };
        
        window._mediaRecorder.start();
        if(window.toggleMicUI) window.toggleMicUI(true);
        
    } catch(e) { 
        alert("Mic Error: " + e.message); 
    }
}

function stopRecording() {
    // DEFANSİF KOD: Değişken tanımlı mı kontrol et
    if (typeof window._mediaRecorder !== 'undefined' && 
        window._mediaRecorder && 
        window._mediaRecorder.state !== 'inactive') {
        
        window._mediaRecorder.stop();
        
        // Stream'i de kapat (Mic ışığı sönsün)
        window._mediaRecorder.stream.getTracks().forEach(track => track.stop());
        
        if(window.toggleMicUI) window.toggleMicUI(false);
    }
}

function clearRecordingData() { 
    window.recordedBlob = null; 
    window._mediaRecorder = null;
}