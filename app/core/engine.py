import os
import time
import torch
import numpy as np
import langid
import glob
import hashlib
import json
import logging
import threading
import gc
import torchaudio

from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts
from TTS.utils.manage import ModelManager
from TTS.utils.generic_utils import get_user_data_dir

from app.core.config import settings
from app.core.normalizer import normalizer
from app.core.audio import audio_processor
from app.core.ssml_handler import ssml_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("XTTS-ENGINE")

class TTSEngine:
    _instance = None
    _thread_lock = threading.Lock()
    
    SPEAKERS_DIR = "/app/speakers"
    CACHE_DIR = "/app/cache"
    LATENTS_DIR = "/app/cache/latents"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TTSEngine, cls).__new__(cls)
            cls._instance.model = None
            cls._instance.speakers_cache = []
            cls._instance.last_cache_update = 0
            cls._instance.CACHE_TTL = 60
            
            os.makedirs(cls.SPEAKERS_DIR, exist_ok=True)
            os.makedirs(cls.CACHE_DIR, exist_ok=True)
            os.makedirs(cls.LATENTS_DIR, exist_ok=True)
        return cls._instance

    def initialize(self):
        if not self.model:
            logger.info("🚀 Initializing XTTS v2 Core Engine...")
            try:
                if torch.cuda.is_available():
                    torch.set_float32_matmul_precision("high")
                    logger.info("⚡ RTX Ampere Optimization Enabled (Float32 Matmul Precision: High)")

                self._ensure_fallback_speaker()

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
                    use_deepspeed=settings.ENABLE_DEEPSPEED,
                )
                
                target_device = settings.DEVICE
                cuda_available = torch.cuda.is_available()
                
                logger.info(f"⚙️  Config Device: '{target_device}' | CUDA Available: {cuda_available}")

                if target_device == "cuda" and cuda_available:
                    self.model.cuda()
                    
                    if settings.ENABLE_HALF_PRECISION:
                        try:
                            # RTX 30xx ve üzeri için BFLOAT16 (NaN önleyici)
                            if torch.cuda.is_bf16_supported():
                                self.model.bfloat16()
                                logger.info("✅ Model converted to BFLOAT16 (Stable & Fast for RTX 3060).")
                            else:
                                self.model.half()
                                logger.info("✅ Model converted to FLOAT16 (Standard Half Precision).")
                        except Exception as e:
                            logger.error(f"❌ Failed to convert to Half Precision: {e}")
                    
                    logger.info("✅ Model successfully moved to GPU (CUDA).")
                else:
                    if target_device == "cuda" and not cuda_available:
                        logger.error("❌ Config asked for CUDA but torch.cuda.is_available() is False!")
                    logger.warning("⚠️ Model running on CPU (Slow Performance).")
                
                self.refresh_speakers(force=True)
                
            except Exception as e:
                logger.critical(f"🔥 Model init failed: {e}")
                raise e

    def _cleanup_memory(self):
        if settings.LOW_RESOURCE_MODE:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def _ensure_fallback_speaker(self):
        if not os.path.exists(self.SPEAKERS_DIR):
            os.makedirs(self.SPEAKERS_DIR)
            
        files = glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav"))
        if not files:
            logger.warning("⚠️ No speakers found! Generating generic sine wave reference...")
            fallback_path = os.path.join(self.SPEAKERS_DIR, "system_default.wav")
            try:
                sample_rate = 24000
                duration_sec = 2.0
                t = torch.linspace(0, duration_sec, int(sample_rate * duration_sec))
                waveform = torch.sin(2 * torch.pi * 220 * t).unsqueeze(0)
                torchaudio.save(fallback_path, waveform, sample_rate)
                logger.info(f"✅ Fallback speaker created: {fallback_path}")
            except Exception as e:
                logger.error(f"❌ Failed to create fallback speaker: {e}")

    def synthesize(self, params: dict, speaker_wavs=None) -> bytes:
        text = normalizer.normalize(params.get("text", ""), params.get("language"))
        if not text: return b""
        
        is_ssml = ssml_handler.is_ssml(text)
        
        cache_key = None
        if not is_ssml and not speaker_wavs:
            cache_key = self._generate_cache_key({**params, "text": text})
            cached = self._check_cache(cache_key)
            if cached: 
                logger.info("⚡ Cache HIT")
                return cached

        logger.info(f"🐢 Synthesizing...")
        
        with self._thread_lock:
            try:
                # Inference Mode
                with torch.inference_mode():
                    gpt_cond_latent, speaker_embedding = self._get_latents(params.get("speaker_idx"), speaker_wavs)
                    
                    if is_ssml:
                        segments = ssml_handler.parse(text, params)
                        wav_chunks = []
                        for segment in segments:
                            if segment['type'] == 'text':
                                inf_params = segment['params']
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
                                wav_chunks.append(torch.zeros(int(24000 * segment['duration'])))
                        full_wav = torch.cat(wav_chunks, dim=0) if wav_chunks else torch.tensor([])
                    else:
                        out = self.model.inference(
                            text, params.get("language"), gpt_cond_latent, speaker_embedding,
                            temperature=params.get("temperature", 0.75), repetition_penalty=params.get("repetition_penalty", 2.0),
                            top_k=params.get("top_k", 50), top_p=params.get("top_p", 0.85), speed=params.get("speed", 1.0)
                        )
                        full_wav = torch.tensor(out["wav"])

                    if settings.DEVICE == "cuda": 
                        full_wav = full_wav.float().cpu() # Ses verisi için float'a geri dön
            finally:
                self._cleanup_memory()

        wav_data = audio_processor.tensor_to_bytes(full_wav)
        final_audio = audio_processor.process_audio(
            wav_data, 
            params.get("output_format", "wav"), 
            params.get("sample_rate", 24000),
            add_silence=True 
        )
        
        if not is_ssml and cache_key: 
            self._save_cache(cache_key, final_audio)
        return final_audio

    def synthesize_stream(self, params: dict, speaker_wavs=None):
        text = normalizer.normalize(params.get("text", ""), params.get("language"))
        lang = params.get("language")
        if not lang or lang == "auto": lang = langid.classify(text)[0].strip()
        if lang == "zh": lang = "zh-cn"
        
        with self._thread_lock:
            try:
                # Streaming Modu: Autocast ile FP16/BFLOAT16 desteği
                device_type = 'cuda' if settings.DEVICE == 'cuda' and torch.cuda.is_available() else 'cpu'
                
                # Hangi tipe göre autocast yapacağını belirle
                target_dtype = torch.float16
                if torch.cuda.is_bf16_supported() and settings.ENABLE_HALF_PRECISION:
                    target_dtype = torch.bfloat16
                
                use_autocast = settings.ENABLE_HALF_PRECISION and device_type == 'cuda'

                with torch.inference_mode(), torch.autocast(device_type=device_type, dtype=target_dtype, enabled=use_autocast):
                    gpt_cond_latent, speaker_embedding = self._get_latents(params.get("speaker_idx"), speaker_wavs)
                    
                    # Latentler FP32 olarak geliyor (_get_latents içinde ayarlı), autocast bunları halledecek.
                    
                    chunks = self.model.inference_stream(
                        text, lang, gpt_cond_latent, speaker_embedding,
                        temperature=params.get("temperature", 0.75), repetition_penalty=params.get("repetition_penalty", 2.0),
                        top_k=params.get("top_k", 50), top_p=params.get("top_p", 0.85), speed=params.get("speed", 1.0),
                        enable_text_splitting=True
                    )

                    for chunk in chunks:
                        if settings.DEVICE == "cuda": 
                            chunk = chunk.float().cpu()
                        
                        wav_chunk_float = chunk.numpy()
                        np.clip(wav_chunk_float, -1.0, 1.0, out=wav_chunk_float)
                        wav_int16 = (wav_chunk_float * 32767).astype(np.int16)
                        yield wav_int16.tobytes()
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield b""
            finally:
                self._cleanup_memory()

    def refresh_speakers(self, force=False):
        now = time.time()
        if not force and (now - self.last_cache_update < self.CACHE_TTL):
            return {"status": "cached", "count": len(self.speakers_cache)}

        report = {"success": [], "failed": {}, "total_scanned": 0}
        new_cache = []
        if os.path.exists(self.SPEAKERS_DIR):
            files = glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav"))
            report["total_scanned"] = len(files)
            for f in files:
                name = os.path.splitext(os.path.basename(f))[0]
                new_cache.append(name)
                report["success"].append(name)
        
        self.speakers_cache = sorted(new_cache)
        self.last_cache_update = now
        logger.info(f"🔊 Speakers refreshed. Total: {len(self.speakers_cache)}")
        return report

    def get_speakers(self):
        if not self.speakers_cache or (time.time() - self.last_cache_update > self.CACHE_TTL):
            self.refresh_speakers()
        return self.speakers_cache

    def _get_latents(self, speaker_idx, speaker_wavs):
        """Latent vektörleri FP32 (Float) olarak döndürür."""
        if speaker_wavs: 
            return self.model.get_conditioning_latents(audio_path=speaker_wavs, gpt_cond_len=30, gpt_cond_chunk_len=4, max_ref_length=60)
        
        if not speaker_idx:
            speakers = self.get_speakers()
            speaker_idx = speakers[0] if speakers else "system_default"
            if not speakers: self._ensure_fallback_speaker()
        
        latent_file = os.path.join(self.LATENTS_DIR, f"{speaker_idx}.json")
        if os.path.exists(latent_file):
            try:
                with open(latent_file, 'r') as f: data = json.load(f)
                gpt_cond_latent = torch.tensor(data["gpt_cond_latent"])
                speaker_embedding = torch.tensor(data["speaker_embedding"])
                
                # Autocast kullanacağımız için sadece CUDA'ya atıyoruz, FP32 bırakıyoruz.
                if settings.DEVICE == "cuda" and torch.cuda.is_available(): 
                    gpt_cond_latent = gpt_cond_latent.cuda()
                    speaker_embedding = speaker_embedding.cuda()
                return gpt_cond_latent, speaker_embedding
            except: pass
            
        wav_path = os.path.join(self.SPEAKERS_DIR, f"{speaker_idx}.wav")
        if not os.path.exists(wav_path): 
            files = glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav"))
            wav_path = files[0] if files else None
        if not wav_path:
            self._ensure_fallback_speaker()
            wav_path = os.path.join(self.SPEAKERS_DIR, "system_default.wav")

        gpt_cond_latent, speaker_embedding = self.model.get_conditioning_latents(audio_path=[wav_path], gpt_cond_len=30, gpt_cond_chunk_len=4, max_ref_length=60)
        try:
            with open(latent_file, 'w') as f: 
                json.dump({"gpt_cond_latent": gpt_cond_latent.float().cpu().tolist(), "speaker_embedding": speaker_embedding.float().cpu().tolist()}, f)
        except: pass
        return gpt_cond_latent, speaker_embedding

    def _generate_cache_key(self, params):
        if params.get("speaker_wavs"): return None
        key_data = {k:v for k,v in params.items() if k in ["text", "lang", "spk", "temp", "speed", "fmt", "sr"]}
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    def _check_cache(self, key):
        if not key: return None
        path = os.path.join(self.CACHE_DIR, f"{key}.bin")
        if os.path.exists(path):
            try: 
                with open(path, "rb") as f:
                    return f.read()
            except: return None
        return None

    def _save_cache(self, key, data):
        if not key: return
        try: 
            with open(os.path.join(self.CACHE_DIR, f"{key}.bin"), "wb") as f: 
                f.write(data)
        except: pass

tts_engine = TTSEngine()