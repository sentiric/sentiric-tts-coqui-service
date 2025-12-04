import subprocess
import logging
import io
import torchaudio
import torch

logger = logging.getLogger("AUDIO-PROC")

class AudioProcessor:
    @staticmethod
    def tensor_to_bytes(wav_tensor: torch.Tensor, sample_rate: int = 24000) -> bytes:
        if wav_tensor.ndim == 1:
            wav_tensor = wav_tensor.unsqueeze(0)
        
        buffer = io.BytesIO()
        torchaudio.save(buffer, wav_tensor, sample_rate, format="wav")
        buffer.seek(0)
        return buffer.read()

    @staticmethod
    def process_audio(wav_bytes: bytes, format: str, sample_rate: int, add_silence: bool = False) -> bytes:
        try:
            cmd = ['ffmpeg', '-y', '-f', 'wav', '-i', 'pipe:0']
            
            filters = []
            
            if add_silence:
                filters.append('adelay=50|50') # Gecikmeyi minimize ettim (50ms)
            
            # --- SES MASTERING ZİNCİRİ ---
            
            # 1. EQ: Sese tokluk kat (Bass Boost: 100Hz frekansını +2dB artır)
            # Hızlı konuşmada (1.25x) ses inceldiği için bu dengeyi sağlar.
            filters.append('bass=g=2:f=100:w=0.5')
            
            # 2. Normalizasyon: EBU R128 standardı (Yayın kalitesi)
            # Target Loudness: -18 LUFS (Podcasting standardına yakın)
            filters.append('loudnorm=I=-18:TP=-1.5:LRA=11')
            
            cmd += ['-af', ','.join(filters)]
            
            if format == "mp3":
                cmd += ['-f', 'mp3', '-acodec', 'libmp3lame', '-b:a', '192k']
            elif format == "opus":
                cmd += ['-f', 'ogg', '-acodec', 'libopus', '-b:a', '64k', '-vbr', 'on']
            elif format == "pcm":
                cmd += ['-f', 's16le', '-acodec', 'pcm_s16le']
            else:
                cmd += ['-f', 'wav', '-acodec', 'pcm_s16le']
            
            cmd += ['-ar', str(sample_rate)]
            cmd += ['pipe:1']
            
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = process.communicate(input=wav_bytes)
            
            if process.returncode != 0: return wav_bytes
            return out
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return wav_bytes

audio_processor = AudioProcessor()