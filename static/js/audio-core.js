const SOURCE_SAMPLE_RATE = 24000;

let audioContext = null;
let analyser = null;
let nextStartTime = 0; 
let isDownloadFinished = false;
let sourceNodes = []; 

function initAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8;
        initVisualizer();
    }
    if (audioContext.state === 'suspended') { audioContext.resume(); }
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

    const buffer = audioContext.createBuffer(1, float32Array.length, serverSampleRate);
    buffer.getChannelData(0).set(float32Array);
    
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser);
    analyser.connect(audioContext.destination);
    
    // --- ANTI-GLITCH LOGIC ---
    const currentTime = audioContext.currentTime;
    
    // 1. Eğer bu ilk paketse veya buffer boşaldıysa (Underrun)
    if (nextStartTime < currentTime) {
        // "Şimdi"ye eşitle ama çok küçük bir güvenlik payı bırak (0.02s)
        // Bu, tarayıcının sesi işlemesi için gereken mini süredir.
        nextStartTime = currentTime + 0.02;
    }

    source.start(nextStartTime);
    sourceNodes.push(source);
    
    source.onended = () => {
        const index = sourceNodes.indexOf(source);
        if (index > -1) sourceNodes.splice(index, 1);
        checkIfPlaybackFinished();
    };

    // Bir sonraki parçanın başlama zamanı = Bu parçanın bitiş zamanı
    nextStartTime += buffer.duration;
}

// ... (resetAudioState, convertInt16ToFloat32 ve diğerleri AYNI) ...
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
    for (let i = 0; i < int16Data.length; i++) { float32[i] = int16Data[i] >= 0 ? int16Data[i] / 32767 : int16Data[i] / 32768; }
    return float32;
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
async function startRecording() {
    if (!navigator.mediaDevices) return alert("Mic denied");
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.onstop = () => {
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
function clearRecordingData() { window.recordedBlob = null; audioChunks = []; }