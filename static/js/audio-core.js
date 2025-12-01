// Global Audio Context
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

// sampleRate artık parametre olarak geliyor
async function playChunk(float32Array, sampleRate) {
    initAudioContext();
    if (window.isStopRequested) return;

    const ctx = window._audioContext;
    
    // Dinamik sample rate kullanımı
    const buffer = ctx.createBuffer(1, float32Array.length, sampleRate || 24000);
    buffer.getChannelData(0).set(float32Array);
    
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser);
    analyser.connect(ctx.destination);
    
    const currentTime = ctx.currentTime;
    if (nextStartTime < currentTime) nextStartTime = currentTime;

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

// Visualizer Logic
function initVisualizer() {
    const canvas = document.getElementById('visualizer');
    if(!canvas) return;
    const ctx = canvas.getContext('2d');
    
    function resize() { canvas.width = canvas.offsetWidth; canvas.height = canvas.offsetHeight; }
    window.addEventListener('resize', resize); resize();
    
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

// Mic Handlers
async function startRecording() {
    if (!navigator.mediaDevices) return UI.showToast("Mic denied", "error");
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        window._mediaRecorder = new MediaRecorder(stream);
        let audioChunks = [];
        
        window._mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        window._mediaRecorder.onstop = () => {
            window.recordedBlob = new Blob(audioChunks, { type: 'audio/webm' });
            if(window.Controllers && window.Controllers.handleRecordingComplete) 
                window.Controllers.handleRecordingComplete();
        };
        
        window._mediaRecorder.start();
        if(UI && UI.showRecordingState) UI.showRecordingState(true);
        
    } catch(e) { UI.showToast("Mic Error: " + e.message, "error"); }
}

function stopRecording() {
    if (window._mediaRecorder && window._mediaRecorder.state !== 'inactive') {
        window._mediaRecorder.stop();
        window._mediaRecorder.stream.getTracks().forEach(track => track.stop());
        if(UI && UI.showRecordingState) UI.showRecordingState(false);
    }
}

function clearRecordingData() { window.recordedBlob = null; window._mediaRecorder = null; }