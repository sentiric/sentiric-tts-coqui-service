import subprocess
import logging
import io
import torchaudio
import torch
import wave

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
    def raw_pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
        """
        Ham PCM (Int16) verisine RIFF WAV Header ekler.
        Bu işlem tarayıcıların dosyayı 'audio/wav' olarak tanıması için zorunludur.
        """
        try:
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)      # Mono
                wav_file.setsampwidth(2)      # 16-bit (2 bytes)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm_bytes)
            
            return buffer.getvalue()
        except Exception as e:
            logger.error(f"PCM to WAV conversion failed: {e}")
            return pcm_bytes # Fallback (Yine de kaydetmeyi dene)

    @staticmethod
    def process_audio(wav_bytes: bytes, format: str, sample_rate: int, add_silence: bool = False) -> bytes:
        try:
            cmd = ['ffmpeg', '-y', '-f', 'wav', '-i', 'pipe:0']
            
            filters = []
            
            if add_silence:
                filters.append('adelay=50|50') 
            
            # --- SES MASTERING ZİNCİRİ ---
            filters.append('bass=g=2:f=100:w=0.5')
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