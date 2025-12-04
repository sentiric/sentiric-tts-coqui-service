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
import shutil
import torchaudio
from typing import Optional, Tuple

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

class SmartMemoryManager:
    """
    6GB VRAM Optimus Prime:
    Her istekte çöp toplamak (GC) yerine, sadece gerektiğinde temizlik yapar.
    """
    def __init__(self, device: str, threshold_mb: int = 5000):
        self.device = device
        self.threshold_mb = threshold_mb
        self.request_counter = 0
        self.gc_frequency = 10 # Her 10 istekte bir zorunlu temizlik (Fragmentasyonu önlemek için)

    def check_and_clear(self):
        if self.device != "cuda":
            return

        self.request_counter += 1
        
        # 1. Periyodik Temizlik (Soft Cleanup)
        if self.request_counter % self.gc_frequency == 0:
            self._force_clean("Periodic")
            return

        # 2. Kritik Seviye Kontrolü (Hard Cleanup)
        try:
            allocated = torch.cuda.memory_allocated() / (1024 * 1024)
            reserved = torch.cuda.memory_reserved() / (1024 * 1024)
            
            # Eğer rezerve edilen alan 5GB'ı geçerse temizle (6GB kart için güvenli sınır)
            if reserved > self.threshold_mb:
                self._force_clean(f"High VRAM Usage ({int(reserved)}MB)")
        except Exception:
            pass

    def _force_clean(self, reason: str):
        logger.debug(f"🧹 Memory Cleanup Triggered: {reason}")
        gc.collect()
        torch.cuda.empty_cache()

class TTSEngine:
    _instance = None
    _gpu_lock = threading.Lock() # Sadece GPU erişimini kilitler
    
    SPEAKERS_DIR = "/app/speakers"
    CACHE_DIR = "/app/cache"
    LATENTS_DIR = "/app/cache/latents"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TTSEngine, cls).__new__(cls)
            cls._instance.model = None
            cls._instance.speakers_map = {} 
            cls._instance.last_cache_update = 0
            cls._instance.CACHE_TTL = 60
            cls._instance.memory_manager = None
            
            os.makedirs(cls.SPEAKERS_DIR, exist_ok=True)
            os.makedirs(cls.CACHE_DIR, exist_ok=True)
            os.makedirs(cls.LATENTS_DIR, exist_ok=True)
        return cls._instance

    def initialize(self):
        if not self.model:
            logger.info(f"🚀 Initializing XTTS v2 Core Engine... (Device: {settings.DEVICE})")
            try:
                self._ensure_fallback_speaker()
                self._migrate_legacy_speakers()

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
                
                if settings.DEVICE == "cuda" and torch.cuda.is_available():
                    self.model.cuda()
                    # 6GB VRAM için Bellek Yöneticisini Başlat (Sınır: 4.8 GB)
                    self.memory_manager = SmartMemoryManager("cuda", threshold_mb=4800)
                    logger.info("✅ Model GPU'ya yüklendi. Akıllı bellek yönetimi devrede.")
                else:
                    self.memory_manager = SmartMemoryManager("cpu")
                    logger.warning("⚠️ Model CPU üzerinde çalışıyor (Yavaş).")
                
                self.refresh_speakers(force=True)
                
            except Exception as e:
                logger.critical(f"🔥 Model init failed: {e}")
                raise e

    def synthesize(self, params: dict, speaker_wavs=None) -> bytes:
        """
        Optimize Edilmiş Sentez Akışı:
        1. Pre-process (CPU)
        2. Inference (GPU - Kilitli)
        3. Post-process (CPU - Kilitsiz) -> Bu sayede GPU hemen boşa çıkar.
        """
        p_lang = params.get("language", settings.DEFAULT_LANGUAGE)
        # Diğer parametreleri al...
        p_temp = params.get("temperature", settings.DEFAULT_TEMPERATURE)
        p_speed = params.get("speed", settings.DEFAULT_SPEED)
        p_top_k = params.get("top_k", settings.DEFAULT_TOP_K)
        p_top_p = params.get("top_p", settings.DEFAULT_TOP_P)
        p_rep_pen = params.get("repetition_penalty", settings.DEFAULT_REPETITION_PENALTY)
        p_speaker_id = params.get("speaker_idx", settings.DEFAULT_SPEAKER)
        
        text = normalizer.normalize(params.get("text", ""), p_lang)
        if not text: return b""
        
        # Cache Check (CPU)
        is_ssml = ssml_handler.is_ssml(text)
        cache_key = None
        if not is_ssml and not speaker_wavs:
            cache_data = {**params, "text": text, "spk": p_speaker_id, "lang": p_lang}
            cache_key = self._generate_cache_key(cache_data)
            cached = self._check_cache(cache_key)
            if cached: return cached

        raw_wav_tensor = None

        # --- GPU CRITICAL SECTION (Sadece burası kilitlenir) ---
        with self._gpu_lock:
            try:
                logger.info(f"🐢 GPU Inference: Len={len(text)} Spk={p_speaker_id}")
                with torch.inference_mode():
                    gpt_cond_latent, speaker_embedding = self._get_latents(p_speaker_id, speaker_wavs)
                    
                    if is_ssml:
                        segments = ssml_handler.parse(text, params)
                        wav_chunks = []
                        for segment in segments:
                            if segment['type'] == 'text':
                                seg_speed = segment['params'].get("speed", p_speed)
                                out = self.model.inference(
                                    segment['content'], p_lang, gpt_cond_latent, speaker_embedding,
                                    temperature=p_temp, repetition_penalty=p_rep_pen,
                                    top_k=p_top_k, top_p=p_top_p, speed=seg_speed
                                )
                                wav_chunks.append(torch.tensor(out['wav']))
                            elif segment['type'] == 'break':
                                wav_chunks.append(torch.zeros(int(24000 * segment['duration'])))
                        raw_wav_tensor = torch.cat(wav_chunks, dim=0) if wav_chunks else torch.tensor([])
                    else:
                        out = self.model.inference(
                            text, p_lang, gpt_cond_latent, speaker_embedding,
                            temperature=p_temp, repetition_penalty=p_rep_pen,
                            top_k=p_top_k, top_p=p_top_p, speed=p_speed
                        )
                        raw_wav_tensor = torch.tensor(out["wav"])

                    # Tensörü CPU'ya taşı ve GPU belleğini hemen kontrol et
                    if settings.DEVICE == "cuda": 
                        raw_wav_tensor = raw_wav_tensor.cpu()
                    
                    # Akıllı temizlik
                    self.memory_manager.check_and_clear()

            except Exception as e:
                logger.error(f"Synthesize Error: {e}")
                return b""
        # --- END GPU LOCK ---

        # --- CPU POST-PROCESSING (Paralel çalışabilir) ---
        # GPU şu an başka bir isteği alabilir, biz CPU'da dönüştürme yapıyoruz.
        wav_data = audio_processor.tensor_to_bytes(raw_wav_tensor)
        final_audio = audio_processor.process_audio(
            wav_data, 
            params.get("output_format", settings.DEFAULT_OUTPUT_FORMAT), 
            params.get("sample_rate", settings.DEFAULT_SAMPLE_RATE),
            add_silence=True 
        )
        
        if not is_ssml and cache_key: self._save_cache(cache_key, final_audio)
        
        return final_audio

    def synthesize_stream(self, params: dict, speaker_wavs=None):
        """
        Streaming işlemi sırasında Lock tutulmak ZORUNDADIR.
        Ancak generator yield ettiği anlarda diğer threadlere (API) nefes aldırır.
        """
        p_lang = params.get("language", settings.DEFAULT_LANGUAGE)
        # Parametreleri al (synthesize ile aynı)
        p_temp = params.get("temperature", settings.DEFAULT_TEMPERATURE)
        p_speed = params.get("speed", settings.DEFAULT_SPEED)
        p_top_k = params.get("top_k", settings.DEFAULT_TOP_K)
        p_top_p = params.get("top_p", settings.DEFAULT_TOP_P)
        p_rep_pen = params.get("repetition_penalty", settings.DEFAULT_REPETITION_PENALTY)
        p_speaker_id = params.get("speaker_idx", settings.DEFAULT_SPEAKER)

        text = normalizer.normalize(params.get("text", ""), p_lang)
        if not p_lang or p_lang == "auto": 
            p_lang = langid.classify(text)[0].strip()
        if p_lang == "zh": p_lang = "zh-cn"
        
        # Streaming için Lock mecburidir, model stateful çalışır.
        with self._gpu_lock:
            try:
                with torch.inference_mode():
                    gpt_cond_latent, speaker_embedding = self._get_latents(p_speaker_id, speaker_wavs)
                    
                    chunks = self.model.inference_stream(
                        text, p_lang, gpt_cond_latent, speaker_embedding,
                        temperature=p_temp, repetition_penalty=p_rep_pen,
                        top_k=p_top_k, top_p=p_top_p, speed=p_speed,
                        enable_text_splitting=True
                    )

                    for chunk in chunks:
                        wav_chunk_float = chunk.cpu().numpy() if settings.DEVICE == "cuda" else chunk.numpy()
                        np.clip(wav_chunk_float, -1.0, 1.0, out=wav_chunk_float)
                        yield (wav_chunk_float * 32767).astype(np.int16).tobytes()
                    
                    self.memory_manager.check_and_clear()

            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield b""

    # --- Diğer yardımcı metodlar (refresh_speakers, _get_latents vb.) aynen kalır ---
    # Kodun geri kalan kısmı değişmediği için kısaltıyorum.
    # ... rest of helper methods ... (As per your Anti-Lazy policy, I will include full content if requested, 
    # but since I modified the class structure, I need to include the unmodified methods to be valid executable code?
    # NO-FLUFF POLICY dictates full content. Here are the rest.)

    def refresh_speakers(self, force=False):
        now = time.time()
        if not force and (now - self.last_cache_update < self.CACHE_TTL):
            return {"status": "cached", "count": len(self.speakers_map)}

        new_map = {}
        try:
            entries = os.listdir(self.SPEAKERS_DIR)
            for entry in entries:
                path = os.path.join(self.SPEAKERS_DIR, entry)
                if os.path.isdir(path):
                    styles = []
                    for f in glob.glob(os.path.join(path, "*.wav")):
                        style_name = os.path.splitext(os.path.basename(f))[0]
                        styles.append(style_name)
                    if styles:
                        new_map[entry] = sorted(styles)
                elif entry.endswith(".wav"):
                    speaker_name = os.path.splitext(entry)[0]
                    new_map[speaker_name] = ["default"]
        except Exception as e:
            logger.error(f"Speaker scan error: {e}")

        self.speakers_map = new_map
        self.last_cache_update = now
        logger.info(f"🔊 Speakers refreshed. Total: {len(new_map)}")
        return {"success": True, "total": len(new_map), "map": new_map}

    def get_speakers(self):
        if not self.speakers_map or (time.time() - self.last_cache_update > self.CACHE_TTL):
            self.refresh_speakers()
        return self.speakers_map

    def _ensure_fallback_speaker(self):
        if not os.path.exists(self.SPEAKERS_DIR):
            os.makedirs(self.SPEAKERS_DIR)
        
        has_files = False
        for root, dirs, files in os.walk(self.SPEAKERS_DIR):
            if any(f.endswith('.wav') for f in files):
                has_files = True
                break

        if not has_files:
            fallback_path = os.path.join(self.SPEAKERS_DIR, "system_default.wav")
            try:
                sample_rate = 24000
                duration_sec = 2.0
                t = torch.linspace(0, duration_sec, int(sample_rate * duration_sec))
                waveform = torch.sin(2 * torch.pi * 220 * t).unsqueeze(0)
                torchaudio.save(fallback_path, waveform, sample_rate)
            except Exception: pass

    def _migrate_legacy_speakers(self):
        wav_files = glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav"))
        for wav_path in wav_files:
            filename = os.path.basename(wav_path)
            if filename == "system_default.wav": continue
            speaker_name = os.path.splitext(filename)[0]
            target_folder = os.path.join(self.SPEAKERS_DIR, speaker_name)
            if not os.path.exists(target_folder):
                os.makedirs(target_folder, exist_ok=True)
                shutil.copy2(wav_path, os.path.join(target_folder, "neutral.wav"))
                try: os.remove(wav_path)
                except: pass

    def _get_latents(self, speaker_id, speaker_wavs):
        if speaker_wavs: 
            latents = self.model.get_conditioning_latents(audio_path=speaker_wavs, gpt_cond_len=30, gpt_cond_chunk_len=4, max_ref_length=60)
            return self._to_cuda(latents)
        
        if not speaker_id: speaker_id = settings.DEFAULT_SPEAKER
        
        if "/" in speaker_id:
            spk_name, spk_style = speaker_id.split("/", 1)
        else:
            spk_name, spk_style = speaker_id, "default"

        wav_path = None
        folder_path = os.path.join(self.SPEAKERS_DIR, spk_name)
        
        if os.path.isdir(folder_path):
            style_path = os.path.join(folder_path, f"{spk_style}.wav")
            if os.path.exists(style_path): wav_path = style_path
            else:
                files = glob.glob(os.path.join(folder_path, "*.wav"))
                if files: wav_path = files[0]
        
        if not wav_path:
            root_path = os.path.join(self.SPEAKERS_DIR, f"{spk_name}.wav")
            if os.path.exists(root_path): wav_path = root_path

        if not wav_path or not os.path.exists(wav_path):
            self._ensure_fallback_speaker()
            wav_path = os.path.join(self.SPEAKERS_DIR, "system_default.wav")

        cache_id = hashlib.md5(wav_path.encode()).hexdigest()
        latent_file = os.path.join(self.LATENTS_DIR, f"{cache_id}.json")
        
        if os.path.exists(latent_file):
            try:
                with open(latent_file, 'r') as f: data = json.load(f)
                gpt_cond_latent = torch.tensor(data["gpt_cond_latent"])
                speaker_embedding = torch.tensor(data["speaker_embedding"])
                return self._to_cuda((gpt_cond_latent, speaker_embedding))
            except: pass

        latents = self.model.get_conditioning_latents(audio_path=[wav_path], gpt_cond_len=30, gpt_cond_chunk_len=4, max_ref_length=60)
        
        try:
            with open(latent_file, 'w') as f: 
                json.dump({"gpt_cond_latent": latents[0].cpu().tolist(), "speaker_embedding": latents[1].cpu().tolist()}, f)
        except: pass
        
        return self._to_cuda(latents)

    def _to_cuda(self, latents):
        gpt_cond_latent, speaker_embedding = latents
        if settings.DEVICE == "cuda" and torch.cuda.is_available():
            gpt_cond_latent = gpt_cond_latent.cuda()
            speaker_embedding = speaker_embedding.cuda()
        return gpt_cond_latent, speaker_embedding
        
    def _generate_cache_key(self, params):
        if params.get("speaker_wavs"): return None
        key_data = {k:v for k,v in params.items() if k in ["text", "lang", "speaker_idx", "temperature", "speed", "output_format", "sample_rate"]}
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
        try:
            with open(os.path.join(self.CACHE_DIR, f"{key}.bin"), "wb") as f: f.write(data)
        except: pass

tts_engine = TTSEngine()