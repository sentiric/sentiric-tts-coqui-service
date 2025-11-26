const SAMPLE_RATE = 24000;
let audioContext = null;
let analyser = null;
let nextStartTime = 0;
let mediaRecorder = null;
let audioChunks = [];
let recordedBlob = null;
let sourceNodes = []; 

// CUTOFF FIX: Bu değeri 0.5'ten 0.8'e çektik. 
// İlk parça gelince tarayıcıya "Şu an çalma, 0.8 saniye sonra çal" diyoruz.
// Bu sırada tarayıcı uyanıyor ve veri birikiyor.
const INITIAL_BUFFER_DELAY = 0.8; 

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
    
    // STOP FIX: Eğer kullanıcı stop'a bastıysa yeni gelen paketleri reddet
    if (window.isStopRequested) return;

    // Buffer oluştur
    const buffer = audioContext.createBuffer(1, float32Array.length, sampleRate);
    buffer.getChannelData(0).set(float32Array);
    
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser);
    analyser.connect(audioContext.destination);
    
    const currentTime = audioContext.currentTime;

    // Zamanlama Mantığı (Scheduling)
    if (nextStartTime < currentTime) {
        // Eğer geri kaldıysak, hemen sıfırla ve buffer ekle
        nextStartTime = currentTime + 0.1;
    }
    
    // İLK BAŞLANGIÇ KRİTİK NOKTA
    // nextStartTime eğer çok yakınsa (0 ise), ileriye at.
    // sourceNodes.length === 0 kontrolü, bunun "yeni" bir akış olduğunu garanti eder.
    if (sourceNodes.length === 0) {
        // İlk paket için eksta güvenli boşluk
        nextStartTime = currentTime + INITIAL_BUFFER_DELAY;
    }
    
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
    // STOP FIX: Agresif Durdurma
    window.isStopRequested = true; // Flag set et
    
    // 1. Web Audio API düğümlerini durdur
    sourceNodes.forEach(node => {
        try { node.stop(); node.disconnect(); } catch(e) {}
    });
    sourceNodes = [];
    nextStartTime = 0;
    
    // AudioContext'i askıya al (CPU tasarrufu ve reset için iyi)
    if (audioContext && audioContext.state === 'running') {
        // Hemen suspend etmek yerine biraz bekle, yoksa "pop" sesi çıkabilir
        // Ama acil durdurma için suspend iyidir.
        // audioContext.suspend(); 
    }
    
    setTimeout(() => { window.isStopRequested = false; }, 500);
}

// ... Visualizer ve Recorder kodları aynı ...
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
            recordedBlob = new Blob(audioChunks, { type: 'audio/webm' });
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
function clearRecordingData() { recordedBlob = null; audioChunks = []; }