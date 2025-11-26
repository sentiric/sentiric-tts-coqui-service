const $ = id => document.getElementById(id);

class UI {
    /**
     * Oynatma/Durdurma durumuna göre butonları ve metinleri günceller.
     */
    static setPlayingState(isPlaying) {
        const playIcon = $('playIcon');
        const stopIcon = $('stopIcon');
        const genBtn = $('genBtn');
        const statusText = $('statusText');
        const mobileGenBtn = $('mobileGenBtn');
        const latencyStat = $('latencyStat');

        if (isPlaying) {
            // Oynatılıyor Modu
            playIcon.classList.add('hidden');
            stopIcon.classList.remove('hidden');
            
            genBtn.classList.replace('bg-white', 'bg-red-500');
            genBtn.classList.add('text-white');
            
            statusText.innerText = "PROCESSING...";

            if (mobileGenBtn) {
                mobileGenBtn.innerHTML = '<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M6 6h12v12H6z"/></svg>';
                mobileGenBtn.classList.add('bg-red-500');
                mobileGenBtn.classList.remove('bg-blue-600');
            }
        } else {
            // Hazır Modu
            stopIcon.classList.add('hidden');
            playIcon.classList.remove('hidden');
            
            genBtn.classList.replace('bg-red-500', 'bg-white');
            genBtn.classList.remove('text-white');
            
            statusText.innerText = "READY";
            latencyStat.classList.add('hidden');

            if (mobileGenBtn) {
                mobileGenBtn.innerHTML = '<svg class="w-6 h-6 ml-1" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
                mobileGenBtn.classList.remove('bg-red-500');
                mobileGenBtn.classList.add('bg-blue-600');
            }
        }
    }

    static updateLatency(ms) {
        $('latencyVal').innerText = `${ms}ms`;
        $('latencyStat').classList.remove('hidden');
    }

    static setStatus(text) {
        $('statusText').innerText = text;
    }

    /**
     * Konuşmacı listesini Select elementine doldurur.
     */
    static populateSpeakers(data) {
        const selectElement = $('speaker');
        if (!selectElement) return;

        selectElement.innerHTML = '';
        
        // Gruplama Mantığı
        const groups = {
            'Female': [],
            'Male': [],
            'Other': []
        };

        data.speakers.forEach(speaker => {
            if (speaker.includes('F_')) groups.Female.push(speaker);
            else if (speaker.includes('M_')) groups.Male.push(speaker);
            else groups.Other.push(speaker);
        });

        // Grupları DOM'a ekle
        Object.keys(groups).forEach(key => {
            if (groups[key].length > 0) {
                const optGroup = document.createElement('optgroup');
                optGroup.label = key;
                
                groups[key].forEach(speaker => {
                    const option = document.createElement('option');
                    option.value = speaker;
                    // Dosya isimlerini temizleyerek göster
                    option.innerText = speaker
                        .replace('[FILE] ', '')
                        .replace('F_', '')
                        .replace('M_', '')
                        .replace('.wav', '')
                        .replace(/_/g, ' ');
                    optGroup.appendChild(option);
                });
                
                selectElement.appendChild(optGroup);
            }
        });
    }

    /**
     * Geçmiş listesini ekrana çizer.
     */
    static renderHistory(data) {
        const listElement = $('historyList');
        if (!listElement) return;

        // Header ve Toplu Silme Butonu
        const headerHTML = `
            <div class="flex justify-between items-center mb-4 px-1">
                <span class="text-[10px] text-gray-500 font-bold uppercase">Recent Generations</span>
                <button onclick="Controllers.clearAllHistory()" class="text-[9px] text-red-500 hover:text-red-400 bg-red-900/10 px-2 py-1 rounded border border-red-900/30 hover:bg-red-900/30 transition-all">
                    CLEAR ALL
                </button>
            </div>
        `;

        listElement.innerHTML = headerHTML;

        if (data.length === 0) {
            listElement.innerHTML += '<div class="text-center text-[10px] text-gray-600 mt-10">No history yet...</div>';
            return;
        }

        // Her bir kayıt için kart oluştur
        data.forEach(item => {
            const card = document.createElement('div');
            card.className = 'bg-[#18181b] p-3 rounded-lg border border-white/5 hover:border-blue-500/30 transition-colors group flex flex-col gap-2 mb-2';
            
            const timeStr = item.date ? item.date.split(' ')[1] : '';

            card.innerHTML = `
                <div class="flex justify-between items-start">
                    <span class="text-[9px] font-bold text-blue-400 bg-blue-900/20 px-1.5 py-0.5 rounded uppercase">${item.mode || 'TTS'}</span>
                    <div class="flex items-center gap-2">
                         <span class="text-[9px] text-gray-600 font-mono">${timeStr}</span>
                         <button onclick="Controllers.deleteHistory('${item.filename}')" class="text-gray-600 hover:text-red-500 transition-colors" title="Delete">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                         </button>
                    </div>
                </div>
                <p class="text-xs text-gray-300 line-clamp-2 italic border-l-2 border-gray-700 pl-2">"${item.text}"</p>
                <div class="flex justify-between items-center pt-1 border-t border-white/5 mt-1">
                    <span class="text-[10px] text-gray-500 truncate max-w-[120px] flex items-center gap-1" title="${item.speaker}">
                        ${item.mode === 'Cloning' ? '🧬' : '🎙️'} ${item.speaker || 'Unknown'}
                    </span>
                    <div class="flex gap-2">
                        <button onclick="Controllers.playHistory('${item.filename}')" class="text-gray-400 hover:text-white transition-colors p-1 rounded hover:bg-white/10" title="Play">
                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                        </button>
                        <a href="/api/history/audio/${item.filename}" download class="text-gray-400 hover:text-blue-400 transition-colors p-1 rounded hover:bg-white/10" title="Download">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                        </a>
                    </div>
                </div>
            `;
            listElement.appendChild(card);
        });
    }

    // --- CLONE UI ---

    static resetCloneUI() {
        $('audioPreview').classList.add('hidden');
        $('micBtn').classList.remove('hidden');
        $('fileName').innerText = "Click / Drop File";
        
        const fileInput = $('ref_audio');
        if(fileInput) fileInput.value = '';
    }

    static showRecordingState(isRecording) {
        const btn = $('micBtn');
        const txt = $('micText');
        if (isRecording) {
            btn.classList.add('recording');
            txt.innerText = "Recording...";
        } else {
            btn.classList.remove('recording');
            txt.innerText = "Hold to Record";
        }
    }

    static showRecordingSuccess() {
        $('audioPreview').classList.remove('hidden');
        $('micBtn').classList.add('hidden');
        $('fileName').innerText = "Using Microphone Audio";
    }

    static updateFileName(name) {
        $('fileName').innerText = name;
    }
}