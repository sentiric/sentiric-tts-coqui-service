import subprocess
import logging
import io
import torchaudio
import torch

logger = logging.getLogger("AUDIO-PROC")

class AudioProcessor:
    """
    Görevi: Ham ses verisini (Tensor) almak, formatlamak, efekt eklemek ve byte olarak döndürmek.
    """

    @staticmethod
    def tensor_to_bytes(wav_tensor: torch.Tensor, sample_rate: int = 24000) -> bytes:
        """PyTorch Tensor'u bellekte WAV dosyasına çevirir"""
        if wav_tensor.ndim == 1:
            wav_tensor = wav_tensor.unsqueeze(0)
        
        buffer = io.BytesIO()
        torchaudio.save(buffer, wav_tensor, sample_rate, format="wav")
        buffer.seek(0)
        return buffer.read()

    @staticmethod
    def process_audio(wav_bytes: bytes, format: str, sample_rate: int, add_silence: bool = False) -> bytes:
        """FFmpeg kullanarak format dönüşümü, resampling ve loudnorm uygular"""
        try:
            cmd = ['ffmpeg', '-y', '-f', 'wav', '-i', 'pipe:0']
            
            # Filtre Zinciri
            filters = []
            
            # 1. Başlangıç Sessizliği (Tarayıcı yutmasını engellemek için - Sadece Non-Stream)
            if add_silence:
                filters.append('adelay=250|250')
            
            # 2. Ses Normalizasyonu (EBU R128 Standardı)
            filters.append('loudnorm=I=-16:TP=-1.5:LRA=11')
            
            cmd += ['-af', ','.join(filters)]
            
            # Çıktı Formatı Ayarları
            if format == "mp3":
                cmd += ['-f', 'mp3', '-acodec', 'libmp3lame', '-b:a', '192k']
            elif format == "opus":
                cmd += ['-f', 'ogg', '-acodec', 'libopus', '-b:a', '64k', '-vbr', 'on']
            elif format == "pcm":
                cmd += ['-f', 's16le', '-acodec', 'pcm_s16le']
            else:
                cmd += ['-f', 'wav', '-acodec', 'pcm_s16le']
            
            # Resampling
            cmd += ['-ar', str(sample_rate)]
            cmd += ['pipe:1']
            
            # İşlemi başlat
            process = subprocess.Popen(
                cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.DEVNULL
            )
            out, _ = process.communicate(input=wav_bytes)
            
            if process.returncode != 0:
                logger.warning("FFmpeg failed. Returning raw WAV.")
                return wav_bytes
                
            return out
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return wav_bytes

audio_processor = AudioProcessor()