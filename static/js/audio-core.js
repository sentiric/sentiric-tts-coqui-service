const SAMPLE_RATE = 24000;
let audioContext = null;
let analyser = null;
let nextStartTime = 0;
let mediaRecorder = null;
let audioChunks = [];
let recordedBlob = null;

// --- TUNING PARAMETERS ---
// Kötü ağlar için tampon süresini artırdık (0.1 -> 0.5s)
// Bu, sesi 0.5sn geç başlatır ama kesilmeyi önler.
const INITIAL_BUFFER_DELAY = 0.5; 

function initAudioContext(sampleRate = 24000) {
    if (!audioContext || audioContext.sampleRate !== sampleRate) {
        if(audioContext) audioContext.close();
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: sampleRate });
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8; // Görselleştiriciyi yumuşat
        initVisualizer();
    }
    if (audioContext.state === 'suspended') audioContext.resume();
}

async function playChunk(float32Array, sampleRate = 24000) {
    initAudioContext(sampleRate);
    
    const buffer = audioContext.createBuffer(1, float32Array.length, sampleRate);
    buffer.getChannelData(0).set(float32Array);
    
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser);
    analyser.connect(audioContext.destination);
    
    const currentTime = audioContext.currentTime;

    // --- AKILLI SENKRONİZASYON ---
    if (nextStartTime < currentTime) {
        // Eğer tampon boşaldıysa (internet yavaşladıysa),
        // hemen çalma, biraz bekle ki yeni paketler biriksin.
        nextStartTime = currentTime + 0.1; 
    }
    
    // İlk başlangıçta güvenli bir boşluk bırak
    if (nextStartTime === 0) {
        nextStartTime = currentTime + INITIAL_BUFFER_DELAY;
    }
    
    source.start(nextStartTime);
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
    // AudioContext'i kapatmıyoruz, sadece zamanlayıcıyı sıfırlıyoruz
    // Kapatıp açmak tarayıcıda "patlama" sesine neden olabilir.
    nextStartTime = 0; 
}

// ... (Diğer visualizer ve mic kodları aynı kalacak) ...
// (Tam dosya içeriğini bozmamak için sadece değişen kritik yerleri vurguladım)
// Aşağısı görselleştirici ve kayıt kodlarının aynısıdır:

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