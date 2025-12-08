// Global Audio Context
window._audioContext = null;
window._mediaRecorder = null;
let analyser = null;

// --- JITTER BUFFER & GAPLESS PLAYBACK STATE ---
let nextStartTime = 0; 
let isDownloadFinished = false;
let activeSourceNodes = []; 
let isStopRequested = false;

// --- BAŞLATMA TAMPONU (PRIMING BUFFER) ---
let primingBuffer = [];
let isPlaybackStarted = false;
// *** OPTİMUM DEĞER: . ***
var PRIMING_BUFFER_DURATION_MS = 1000;


function initAudioContext() {
    if (!window._audioContext || window._audioContext.state === 'closed') {
        try {
            window._audioContext = new (window.AudioContext || window.webkitAudioContext)();
            analyser = window._audioContext.createAnalyser();
            analyser.fftSize = 256;
            analyser.smoothingTimeConstant = 0.8;
            analyser.connect(window._audioContext.destination);
            initVisualizer();
            console.log("AudioContext Initialized. State:", window._audioContext.state);
        } catch (e) {
            console.error("Failed to initialize AudioContext:", e);
            return;
        }
    }
    
    if (window._audioContext.state === 'suspended') { 
        window._audioContext.resume().catch(e => console.warn("AudioContext resume failed:", e)); 
    }
}

function notifyDownloadFinished() {
    isDownloadFinished = true;
    checkIfPlaybackFinished();
}

function checkIfPlaybackFinished() {
    if (!isPlaybackStarted && isDownloadFinished && primingBuffer.length > 0) {
        console.log("Priming Buffer: Flushing remaining audio at stream end.");
        _startPlaybackFromPrimingBuffer(24000);
    }

    if (isDownloadFinished && activeSourceNodes.length === 0) {
        console.log("Jitter Buffer: Playback queue finished.");
        if (window.onAudioPlaybackComplete) {
            window.onAudioPlaybackComplete();
        }
    }
}

function _schedulePlayback(float32Array, sampleRate) {
    const ctx = window._audioContext;
    if (!ctx || ctx.state === 'closed') return;

    const buffer = ctx.createBuffer(1, float32Array.length, sampleRate);
    buffer.getChannelData(0).set(float32Array);
    
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser); 
    
    source.start(nextStartTime);
    nextStartTime += buffer.duration;
    
    activeSourceNodes.push(source);
    
    source.onended = () => {
        const index = activeSourceNodes.indexOf(source);
        if (index > -1) activeSourceNodes.splice(index, 1);
        source.disconnect();
        checkIfPlaybackFinished();
    };
}

function _startPlaybackFromPrimingBuffer(sampleRate) {
    const ctx = window._audioContext;
    if (primingBuffer.length === 0 || !ctx) return;
    
    const currentTime = ctx.currentTime;
    const WAKE_UP_DELAY = 0.1; // 100ms
    nextStartTime = currentTime + WAKE_UP_DELAY;

    const totalLength = primingBuffer.reduce((sum, arr) => sum + arr.length, 0);
    const concatenatedBuffer = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of primingBuffer) {
        concatenatedBuffer.set(chunk, offset);
        offset += chunk.length;
    }
    
    console.log(`Priming Buffer: Full. Scheduling playback in ${WAKE_UP_DELAY * 1000}ms.`);
    _schedulePlayback(concatenatedBuffer, sampleRate);

    primingBuffer = [];
}

async function playChunk(float32Array, sampleRate) {
    initAudioContext();
    if (isStopRequested) return;

    if (!isPlaybackStarted) {
        primingBuffer.push(float32Array);
        const currentBufferedDuration = primingBuffer.reduce((sum, arr) => sum + arr.length, 0) / sampleRate * 1000;

        if (currentBufferedDuration >= PRIMING_BUFFER_DURATION_MS) {
            isPlaybackStarted = true;
            _startPlaybackFromPrimingBuffer(sampleRate);
        }
    } else {
        _schedulePlayback(float32Array, sampleRate);
    }
}

function resetAudioState() {
    isStopRequested = true;
    isDownloadFinished = false;
    
    activeSourceNodes.forEach(node => { 
        try { node.stop(0); node.disconnect(); } catch(e) {} 
    });
    activeSourceNodes = [];
    nextStartTime = 0;
    
    primingBuffer = [];
    isPlaybackStarted = false;
    
    console.log("Jitter & Priming Buffer: State Reset.");
    
    setTimeout(() => { isStopRequested = false; }, 100);
}

// Visualizer (Değişiklik yok)
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

// Mic Recording functions (değişiklik yok)
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