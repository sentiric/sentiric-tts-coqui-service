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
        """PyTorch tensörünü WAV formatında byte dizisine dönüştürür."""
        if wav_tensor.ndim == 1:
            wav_tensor = wav_tensor.unsqueeze(0)
        
        buffer = io.BytesIO()
        torchaudio.save(buffer, wav_tensor, sample_rate, format="wav")
        buffer.seek(0)
        return buffer.read()

    @staticmethod
    def raw_pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
        """Ham PCM (Int16) verisine RIFF WAV Header ekler."""
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
            return pcm_bytes

    @staticmethod
    def process_audio(wav_bytes: bytes, format: str, sample_rate: int, add_silence: bool = False) -> bytes:
        if format == "wav" and sample_rate == 24000:
            return wav_bytes

        try:
            input_buffer = io.BytesIO(wav_bytes)
            waveform, original_sr = torchaudio.load(input_buffer)

            if original_sr != sample_rate:
                resampler = torchaudio.transforms.Resample(orig_freq=original_sr, new_freq=sample_rate)
                waveform = resampler(waveform)

            output_buffer = io.BytesIO()
            if format == "mp3":
                # *** KRİTİK DÜZELTME: Hatalı 'compression' parametresi kaldırıldı. ***
                # torchaudio'nun varsayılan yüksek kaliteli VBR ayarlarını kullanmasına izin ver.
                torchaudio.save(output_buffer, waveform, sample_rate, format="mp3")
            elif format == "opus":
                torchaudio.save(output_buffer, waveform, sample_rate, format="opus")
            elif format == "pcm":
                waveform = (waveform * 32767).to(torch.int16)
                output_buffer.write(waveform.squeeze().numpy().tobytes())
            else: # wav
                torchaudio.save(output_buffer, waveform, sample_rate, format="wav")
            
            output_buffer.seek(0)
            return output_buffer.read()
            
        except Exception as e:
            logger.error(f"Audio processing error with torchaudio: {e}", exc_info=True)
            return wav_bytes

audio_processor = AudioProcessor()