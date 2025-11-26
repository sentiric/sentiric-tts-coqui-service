const SAMPLE_RATE = 24000;
let audioContext = null;
let analyser = null;
let nextStartTime = 0; // Sesin ne zaman çalacağını takip eden zamanlayıcı
let mediaRecorder = null;
let audioChunks = [];
let sourceNodes = []; 

// İlk başlangıç gecikmesi (Tarayıcının uyanması için)
const INITIAL_BUFFER_DELAY = 0.5; 

function initAudioContext(sampleRate = 24000) {
    if (!audioContext || audioContext.sampleRate !== sampleRate) {
        if(audioContext) audioContext.close();
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: sampleRate });
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8;
        initVisualizer();
    }
    if (audioContext.state === 'suspended') {
        audioContext.resume();
    }
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

    // --- STREAM FIX ZAMANLAMA MANTIĞI ---
    
    // Durum 1: İlk Paket (Yepyeni bir akış başlıyor)
    if (nextStartTime === 0) {
        // Tarayıcıyı uyandırmak için güvenli bir boşluk bırak
        nextStartTime = currentTime + INITIAL_BUFFER_DELAY;
    } 
    // Durum 2: Buffer Underrun (İnternet yavaşladı, ses yetişmedi, zaman geride kaldı)
    else if (nextStartTime < currentTime) {
        // Geriye dönük çalamayız, o yüzden "şu an"a atla ve minik bir boşluk bırak
        nextStartTime = currentTime + 0.1;
    }
    // Durum 3: Normal Akış (nextStartTime gelecekte bir yer, sorun yok, ucuna ekle)
    
    source.start(nextStartTime);
    sourceNodes.push(source);
    
    source.onended = () => {
        const index = sourceNodes.indexOf(source);
        if (index > -1) sourceNodes.splice(index, 1);
    };

    // Bir sonraki parçanın başlama zamanını güncelle
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
    
    // Çalan her şeyi durdur
    sourceNodes.forEach(node => {
        try { node.stop(); node.disconnect(); } catch(e) {}
    });
    sourceNodes = [];
    
    // Zamanlayıcıyı kesinlikle sıfırla
    nextStartTime = 0;
    
    // Stop flag'ini kısa süre sonra kaldır
    setTimeout(() => { window.isStopRequested = false; }, 200);
}

// ... (initVisualizer, startRecording, stopRecording, clearRecordingData AYNI KALACAK) ...
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
function clearRecordingData() { 
    window.recordedBlob = null; 
    audioChunks = []; 
}