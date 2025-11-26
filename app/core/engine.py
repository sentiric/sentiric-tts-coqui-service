import os
import io
import time
import torch
import torchaudio
import numpy as np
import langid
import glob
import hashlib
import json
import subprocess
import logging
import threading
import gc
import torchaudio.transforms as T
import xml.etree.ElementTree as ET

from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts
from TTS.utils.manage import ModelManager
from TTS.utils.generic_utils import get_user_data_dir
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("XTTS-ENGINE")

class TTSEngine:
    _instance = None
    _thread_lock = threading.Lock()
    
    SPEAKERS_DIR = "/app/speakers"
    CACHE_DIR = "/app/cache"
    LATENTS_DIR = "/app/cache/latents"  # RAM yerine Disk Cache için

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TTSEngine, cls).__new__(cls)
            cls._instance.model = None
            os.makedirs(cls.SPEAKERS_DIR, exist_ok=True)
            os.makedirs(cls.CACHE_DIR, exist_ok=True)
            os.makedirs(cls.LATENTS_DIR, exist_ok=True)
        return cls._instance

    def initialize(self):
        if not self.model:
            logger.info("🚀 Initializing XTTS v2 Core Engine...")
            try:
                model_name = settings.MODEL_NAME
                ModelManager().download_model(model_name)
                model_path = os.path.join(get_user_data_dir("tts"), model_name.replace("/", "--"))
                config = XttsConfig()
                config.load_json(os.path.join(model_path, "config.json"))
                
                self.model = Xtts.init_from_config(config)
                self.model.load_checkpoint(
                    config,
                    checkpoint_path=os.path.join(model_path, "model.pth"),
                    vocab_path=os.path.join(model_path, "vocab.json"),
                    checkpoint_dir=model_path,
                    eval=True,
                    use_deepspeed=False,
                )
                
                if settings.DEVICE == "cuda" and torch.cuda.is_available():
                    self.model.cuda()
                    logger.info("✅ Model loaded to GPU (CUDA).")
                else:
                    logger.warning("⚠️ Model loaded to CPU. Performance will be slow.")
                
                # Speaker cache'i diskten veya dizinden tazele
                self.refresh_speakers()
                
            except Exception as e:
                logger.critical(f"🔥 Model initialization failed: {e}")
                raise e

    def _cleanup_memory(self):
        """Agresif bellek temizliği - Küçük sistemler için hayat kurtarıcı."""
        if settings.LOW_RESOURCE_MODE:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def _map_ssml_rate_to_speed(self, rate_str: str) -> float:
        mapping = {"x-slow": 0.7, "slow": 0.85, "medium": 1.0, "fast": 1.2, "x-fast": 1.4}
        if rate_str in mapping: return mapping[rate_str]
        try: return float(rate_str)
        except ValueError: return 1.0

    def _apply_emphasis(self, params: dict, level: str) -> dict:
        if level in ["strong", "moderate"]:
            params['speed'] = params.get('speed', 1.0) * 0.9
            params['repetition_penalty'] = params.get('repetition_penalty', 2.0) * 1.2
        elif level == "reduced":
            params['speed'] = params.get('speed', 1.0) * 1.1
        return params

    def _parse_ssml(self, ssml_text: str):
        try:
            # Basit ama etkili XML temizliği
            ssml_text = ssml_text.replace("&", "&amp;") 
            parser = ET.XMLParser()
            # Root wrapper ekle ki valid XML olsun
            wrapped_text = f"<root>{ssml_text}</root>"
            root = ET.fromstring(wrapped_text, parser=parser)
            segments = []
            
            def process_element(element, current_params):
                # Elementin kendi metni (örn: <p>Text</p>)
                if element.text and element.text.strip():
                    segments.append({'type': 'text', 'content': element.text.strip(), 'params': current_params.copy()})
                
                for child in element:
                    child_params = current_params.copy()
                    if child.tag == 'break':
                        duration_str = child.get('time', '0.5s').lower()
                        duration = 0.5
                        if duration_str.endswith('ms'): duration = float(duration_str[:-2]) / 1000.0
                        elif duration_str.endswith('s'): duration = float(duration_str[:-1])
                        segments.append({'type': 'break', 'duration': duration})
                    elif child.tag == 'prosody':
                        rate = child.get('rate')
                        if rate: child_params['speed'] = self._map_ssml_rate_to_speed(rate)
                    elif child.tag == 'emphasis':
                        level = child.get('level', 'moderate')
                        child_params = self._apply_emphasis(child_params, level)
                    
                    process_element(child, child_params)
                    
                    # Elementin kapanışından sonraki metin (tail)
                    if child.tail and child.tail.strip():
                        segments.append({'type': 'text', 'content': child.tail.strip(), 'params': current_params.copy()})

            # SSML içeriğini işle
            process_element(root, {})
            
            # Eğer sadece root wrapper varsa ve içerik boşsa veya parse edilemediyse
            if not segments:
                 # Fallback: Tagleri temizle düz metin döndür
                 text_content = "".join(root.itertext())
                 return [{'type': 'text', 'content': text_content, 'params': {}}]
                 
            return segments
        except ET.ParseError as e:
            logger.error(f"SSML Parse Error: {e}. Falling back to plain text.")
            # Hata durumunda tagleri regex ile temizle (basit fallback)
            import re
            clean_text = re.sub(r'<[^>]+>', '', ssml_text)
            return [{'type': 'text', 'content': clean_text, 'params': {}}]

    def synthesize(self, params: dict, speaker_wavs=None) -> bytes:
        text = params.get("text", "").strip()
        if not text: return b""

        # SSML kontrolü
        is_ssml = ("<speak>" in text) or ("<break" in text) or ("<prosody" in text)
        
        # Cache Kontrolü (SSML değilse ve speaker_wavs yoksa)
        cache_key = None
        if not is_ssml and not speaker_wavs:
            cache_key = self._generate_cache_key(params)
            cached_audio = self._check_cache(cache_key)
            if cached_audio:
                logger.info("⚡ Cache HIT! Serving from disk.")
                return cached_audio

        logger.info(f"🐢 Synthesizing ({params.get('language')}, SSML: {is_ssml})...")
        
        # --- GLOBAL LOCK (Küçük sistemler için kritik) ---
        with self._thread_lock:
            try:
                # 1. Latent Hesaplama (En Maliyetli İşlem)
                gpt_cond_latent, speaker_embedding = self._get_latents(params.get("speaker_idx"), speaker_wavs)
                
                # 2. Inference
                if is_ssml:
                    segments = self._parse_ssml(text)
                    wav_chunks = []
                    for segment in segments:
                        if segment['type'] == 'text':
                            inf_params = params.copy()
                            inf_params.update(segment['params'])
                            
                            out = self.model.inference(
                                segment['content'], 
                                inf_params.get("language"), 
                                gpt_cond_latent, 
                                speaker_embedding,
                                temperature=inf_params.get("temperature", 0.75),
                                repetition_penalty=inf_params.get("repetition_penalty", 2.0),
                                top_k=inf_params.get("top_k", 50),
                                top_p=inf_params.get("top_p", 0.85),
                                speed=inf_params.get("speed", 1.0)
                            )
                            wav_chunks.append(torch.tensor(out['wav']))
                        elif segment['type'] == 'break':
                            # Sessizlik oluştur
                            samples = int(24000 * segment['duration'])
                            wav_chunks.append(torch.zeros(samples))
                            
                    full_wav = torch.cat(wav_chunks, dim=0) if wav_chunks else torch.tensor([])
                else:
                    out = self.model.inference(
                        text, 
                        params.get("language"), 
                        gpt_cond_latent, 
                        speaker_embedding,
                        temperature=params.get("temperature", 0.75),
                        repetition_penalty=params.get("repetition_penalty", 2.0),
                        top_k=params.get("top_k", 50),
                        top_p=params.get("top_p", 0.85),
                        speed=params.get("speed", 1.0)
                    )
                    full_wav = torch.tensor(out["wav"])

                # GPU'dan CPU'ya al
                if settings.DEVICE == "cuda":
                    full_wav = full_wav.cpu()

            finally:
                # Bellek Temizliği (Her sentezden sonra)
                self._cleanup_memory()

        # 3. Post-Processing (Lock dışında yapılabilir)
        wav_tensor = full_wav.unsqueeze(0)
        sr = 24000
        target_sr = params.get("sample_rate", 24000)
        
        if target_sr != 24000:
            resampler = T.Resample(24000, target_sr)
            wav_tensor = resampler(wav_tensor)
            sr = target_sr
            
        buffer = io.BytesIO()
        torchaudio.save(buffer, wav_tensor, sr, format="wav")
        buffer.seek(0)
        wav_data = buffer.read()
        
        final_audio = self._process_audio(wav_data, params.get("output_format", "wav"), sr)
        
        if not is_ssml and cache_key: 
            self._save_cache(cache_key, final_audio)
            
        return final_audio

    def synthesize_stream(self, params: dict, speaker_wavs=None):
        text = params.get("text", "")
        # Stream için SSML desteği zordur, düz metin varsayıyoruz.
        
        lang = params.get("language")
        if not lang or lang == "auto": 
            lang = langid.classify(text)[0].strip()
        if lang == "zh": lang = "zh-cn"
        
        with self._thread_lock:
            try:
                gpt_cond_latent, speaker_embedding = self._get_latents(params.get("speaker_idx"), speaker_wavs)
                
                chunks = self.model.inference_stream(
                    text, lang, gpt_cond_latent, speaker_embedding,
                    temperature=params.get("temperature", 0.75), 
                    repetition_penalty=params.get("repetition_penalty", 2.0),
                    top_k=params.get("top_k", 50), 
                    top_p=params.get("top_p", 0.85), 
                    speed=params.get("speed", 1.0),
                    enable_text_splitting=True
                )

                resampler = None
                if params.get("sample_rate") and params.get("sample_rate") != 24000:
                    resampler = T.Resample(24000, params.get("sample_rate"))

                for chunk in chunks:
                    if settings.DEVICE == "cuda":
                        chunk = chunk.cpu()
                        
                    if resampler: 
                        chunk = resampler(chunk)
                    
                    # Float32 -> Int16 Conversion with Audio Gain
                    wav_chunk_float = chunk.numpy()
                    wav_chunk_float = wav_chunk_float * 1.5 # Gain
                    np.clip(wav_chunk_float, -1.0, 1.0, out=wav_chunk_float)
                    wav_int16 = (wav_chunk_float * 32767).astype(np.int16)

                    yield wav_int16.tobytes()
                    
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield b"" # Boş byte gönder bağlantı kopmasın
            finally:
                self._cleanup_memory()

    def refresh_speakers(self):
        """Hoparlörleri tarar ancak latents'leri hemen RAM'e yüklemez (Lazy Loading)."""
        report = {"success": [], "failed": {}, "total_scanned": 0}
        if os.path.exists(self.SPEAKERS_DIR):
            files = glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav"))
            report["total_scanned"] = len(files)
            
            # Eski, geçersiz latent dosyalarını temizle
            # (Bu logic karmaşıklığı artırır, şimdilik atlıyoruz - basit tutalım)
            
            for f in files:
                name = os.path.splitext(os.path.basename(f))[0]
                report["success"].append(name)
                
        return report

    def get_speakers(self):
        # Klasördeki dosyaları listele
        if os.path.exists(self.SPEAKERS_DIR):
             return [os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav"))]
        return []

    def _get_latents(self, speaker_idx, speaker_wavs):
        """
        Latents hesaplar ve diske cacheler. 
        RAM kullanımını minimumda tutar.
        """
        # 1. Eğer özel ses klonlama ise (cachelenemez)
        if speaker_wavs:
            return self.model.get_conditioning_latents(
                audio_path=speaker_wavs, 
                gpt_cond_len=30, 
                gpt_cond_chunk_len=4, 
                max_ref_length=60
            )

        # 2. Eğer standart speaker ise, önce Disk Cache'e bak
        if not speaker_idx: raise ValueError("Speaker ID required")
        
        latent_file = os.path.join(self.LATENTS_DIR, f"{speaker_idx}.json")
        
        if os.path.exists(latent_file):
            try:
                # Diskten yükle
                with open(latent_file, 'r') as f:
                    data = json.load(f)
                    
                # JSON list -> Tensor
                gpt_cond_latent = torch.tensor(data["gpt_cond_latent"])
                speaker_embedding = torch.tensor(data["speaker_embedding"])
                
                if settings.DEVICE == "cuda":
                    gpt_cond_latent = gpt_cond_latent.cuda()
                    speaker_embedding = speaker_embedding.cuda()
                    
                return gpt_cond_latent, speaker_embedding
            except Exception as e:
                logger.warning(f"Corrupt latent cache for {speaker_idx}, recomputing... Error: {e}")

        # 3. Cache yoksa hesapla ve kaydet
        wav_path = os.path.join(self.SPEAKERS_DIR, f"{speaker_idx}.wav")
        if not os.path.exists(wav_path):
            # Fallback: İlk bulduğun wav dosyasını kullan
            files = glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav"))
            if not files: raise ValueError("No speakers found on disk.")
            wav_path = files[0]
            logger.warning(f"Speaker '{speaker_idx}' not found. Using fallback: {wav_path}")

        gpt_cond_latent, speaker_embedding = self.model.get_conditioning_latents(
            audio_path=[wav_path], 
            gpt_cond_len=30, 
            gpt_cond_chunk_len=4, 
            max_ref_length=60
        )
        
        # Diske kaydet (Tensor -> List -> JSON)
        try:
            data = {
                "gpt_cond_latent": gpt_cond_latent.cpu().tolist(),
                "speaker_embedding": speaker_embedding.cpu().tolist()
            }
            with open(latent_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save latent cache: {e}")

        return gpt_cond_latent, speaker_embedding

    def _generate_cache_key(self, params):
        if params.get("speaker_wavs"): return None
        # Parametrelerin kararlı bir hash'ini oluştur
        key_data = {
            "text": params["text"], 
            "lang": params["language"], 
            "spk": params["speaker_idx"], 
            "temp": params["temperature"], 
            "speed": params["speed"], 
            "fmt": params.get("output_format", "wav"), 
            "sr": params.get("sample_rate", 24000)
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    def _check_cache(self, key):
        if not key: return None
        path = os.path.join(self.CACHE_DIR, f"{key}.bin")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f: return f.read()
            except: return None
        return None

    def _save_cache(self, key, data):
        if not key: return
        path = os.path.join(self.CACHE_DIR, f"{key}.bin")
        try:
            with open(path, "wb") as f: f.write(data)
        except Exception as e: logger.error(f"Cache write failed: {e}")

    def _process_audio(self, wav_bytes: bytes, format: str, sample_rate: int) -> bytes:
        try:
            # Loudness Normalization için EBU R128 standardı
            # Small System: Eğer CPU çok yoğunsa bu adımı atlayabilirsin, ama kalite için gerekli.
            cmd = ['ffmpeg', '-y', '-i', 'pipe:0', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11']
            
            if format == "mp3": cmd += ['-f', 'mp3', '-b:a', '192k']
            elif format == "opus": cmd += ['-f', 'opus', '-b:a', '64k']
            elif format == "pcm": cmd += ['-f', 's16le', '-acodec', 'pcm_s16le']
            else: cmd += ['-f', 'wav']
            
            cmd += ['-ar', str(sample_rate), 'pipe:1']
            
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = process.communicate(input=wav_bytes)
            
            if process.returncode != 0: 
                logger.warning(f"FFmpeg failed. Returning raw WAV.")
                return wav_bytes
                
            return out
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return wav_bytes

tts_engine = TTSEngine()