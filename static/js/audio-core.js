const SAMPLE_RATE = 24000;
let audioContext = null;
let analyser = null;
let nextStartTime = 0;
let mediaRecorder = null;
let audioChunks = [];
// recordedBlob'u buradan kaldırıyoruz veya sadece lokal referans tutuyoruz
// Esas veri window.recordedBlob olacak

let sourceNodes = []; 
const INITIAL_BUFFER_DELAY = 0.8; 

// ... (initAudioContext, playChunk, convertInt16ToFloat32, resetAudioState, initVisualizer AYNI KALACAK) ...

function initAudioContext(sampleRate = 24000) {
    if (!audioContext || audioContext.sampleRate !== sampleRate) {
        if(audioContext) audioContext.close();
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: sampleRate });
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8;
        initVisualizer();
    }
    if (audioContext.state === 'suspended') { audioContext.resume(); }
}

async function playChunk(float32Array, sampleRate = 24000) {
    initAudioContext(sampleRate);
    if (window.isStopRequested) return;
    const buffer = audioContext.createBuffer(1, float32Array.length, sampleRate);
    buffer.getChannelData(0).set(float32Array);
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser);
    analyser.connect(audioContext.destination);
    const currentTime = audioContext.currentTime;
    if (nextStartTime < currentTime) { nextStartTime = currentTime + 0.1; }
    if (sourceNodes.length === 0) { nextStartTime = currentTime + INITIAL_BUFFER_DELAY; }
    source.start(nextStartTime);
    sourceNodes.push(source);
    source.onended = () => {
        const index = sourceNodes.indexOf(source);
        if (index > -1) sourceNodes.splice(index, 1);
    };
    nextStartTime += buffer.duration;
}

function convertInt16ToFloat32(int16Data) {
    const float32 = new Float32Array(int16Data.length);
    for (let i = 0; i < int16Data.length; i++) {
        float32[i] = int16Data[i] >= 0 ? int16Data[i] / 32767 : int16Data[i] / 32768;
    }
    return float32;
}

function resetAudioState() {
    window.isStopRequested = true;
    sourceNodes.forEach(node => { try { node.stop(); node.disconnect(); } catch(e) {} });
    sourceNodes = [];
    nextStartTime = 0;
    setTimeout(() => { window.isStopRequested = false; }, 500);
}

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
        const cy = canvas.height / 2;
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

// --- FIX BURADA BAŞLIYOR ---
async function startRecording() {
    if (!navigator.mediaDevices) return alert("Mic denied");
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.onstop = () => {
            // FIX: Window nesnesine ata ki main.js görebilsin
            window.recordedBlob = new Blob(audioChunks, { type: 'audio/webm' });
            if(window.onRecordingComplete) window.onRecordingComplete();
        };
        mediaRecorder.start();
        if(window.toggleMicUI) window.toggleMicUI(true);
    } catch(e) { alert(e.message); }
}
function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        if(window.toggleMicUI) window.toggleMicUI(false);
    }
}
function clearRecordingData() { 
    window.recordedBlob = null; // Global'i sıfırla
    audioChunks = []; 
}