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
from typing import Optional, Tuple, Dict, Any

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
    def __init__(self, device: str, threshold_mb: int = 4500): # Eşiği biraz düşürdük
        self.device = device
        self.threshold_mb = threshold_mb
        self.request_counter = 0
        self.gc_frequency = 10 

    def check_and_clear(self):
        if self.device != "cuda": return
        self.request_counter += 1
        
        # *** DÜZELTME: Bellek kontrolünü daha proaktif hale getir. ***
        # 'torch.cuda.memory_reserved()' yerine 'torch.cuda.memory_allocated()' kullan.
        # Bu, modelin aktif olarak kullandığı belleği yansıtır ve daha hızlı tepki verir.
        try:
            allocated = torch.cuda.memory_allocated() / (1024 * 1024)
            if allocated > self.threshold_mb or (self.request_counter % self.gc_frequency == 0):
                reason = f"High VRAM ({int(allocated)}MB)" if allocated > self.threshold_mb else "Periodic"
                self._force_clean(reason)
        except Exception: pass

    def _force_clean(self, reason: str):
        logger.info(f"🧹 Memory Cleanup Triggered: {reason}. Cleaning cache...")
        gc.collect()
        torch.cuda.empty_cache()
        # Senkronizasyon, belleğin gerçekten boşaltıldığından emin olmaya yardımcı olur.
        torch.cuda.synchronize()


class TTSEngine:
    _instance = None
    _gpu_lock = threading.Lock()
    
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
        return cls._instance

    def initialize(self):
        if not self.model:
            os.makedirs(self.SPEAKERS_DIR, exist_ok=True)
            os.makedirs(self.CACHE_DIR, exist_ok=True)
            os.makedirs(self.LATENTS_DIR, exist_ok=True)

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
                    self.memory_manager = SmartMemoryManager("cuda", threshold_mb=4500)
                    logger.info("✅ Model GPU'ya yüklendi. Akıllı bellek yönetimi devrede.")
                else:
                    self.memory_manager = SmartMemoryManager("cpu")
                    logger.warning("⚠️ Model CPU üzerinde çalışıyor (Yavaş).")
                
                self.refresh_speakers(force=True)
            except Exception as e:
                logger.critical(f"🔥 Model init failed: {e}")
                raise e

    def _prepare_inference(self, params: dict, speaker_wavs=None) -> Dict[str, Any]:
        p_lang = params.get("language", settings.DEFAULT_LANGUAGE)
        text = normalizer.normalize(params.get("text", ""), p_lang)
        if not p_lang or p_lang == "auto":
            try: p_lang = langid.classify(text)[0].strip()
            except: p_lang = settings.DEFAULT_LANGUAGE
        if p_lang == "zh": p_lang = "zh-cn"

        p_speaker_id = params.get("speaker_idx", settings.DEFAULT_SPEAKER)
        gpt_cond_latent, speaker_embedding = self._get_latents(p_speaker_id, speaker_wavs)

        return {
            "text": text,
            "language": p_lang,
            "gpt_cond_latent": gpt_cond_latent,
            "speaker_embedding": speaker_embedding,
            "temperature": params.get("temperature", settings.DEFAULT_TEMPERATURE),
            "speed": params.get("speed", settings.DEFAULT_SPEED),
            "top_k": params.get("top_k", settings.DEFAULT_TOP_K),
            "top_p": params.get("top_p", settings.DEFAULT_TOP_P),
            "repetition_penalty": params.get("repetition_penalty", settings.DEFAULT_REPETITION_PENALTY),
            "split_sentences": params.get("split_sentences", True),
        }

    def _clean_and_trim_tensor(self, wav_tensor: torch.Tensor, threshold: float = 0.025, fade_len: int = 2400) -> torch.Tensor:
        if wav_tensor.numel() == 0: return wav_tensor
        if wav_tensor.device.type == "cuda": wav_tensor = wav_tensor.cpu()

        wav_np = wav_tensor.numpy()
        abs_wav = np.abs(wav_np)
        
        mask = abs_wav > threshold
        if not np.any(mask): return wav_tensor 
            
        last_index = len(mask) - 1 - np.argmax(mask[::-1])
        cut_index = min(last_index + fade_len, len(wav_np))
        trimmed_wav = wav_np[:cut_index]
        
        if len(trimmed_wav) > fade_len:
            fade_curve = np.linspace(1.0, 0.0, fade_len)
            trimmed_wav[-fade_len:] *= fade_curve

        return torch.from_numpy(trimmed_wav)

    def synthesize(self, params: dict, speaker_wavs=None) -> bytes:
        conf = self._prepare_inference(params, speaker_wavs)
        try:
            with self._gpu_lock:
                raw_wav_tensor = self._run_inference(conf)
        except RuntimeError as e:
            if "CUDA out of memory" in str(e):
                logger.warning("⚠️ CUDA OOM detected. Forcing sentence splitting and retrying...")
                self.memory_manager._force_clean("OOM Recovery")
                conf["split_sentences"] = True
                try:
                    with self._gpu_lock:
                         raw_wav_tensor = self._run_inference(conf)
                except Exception as final_e:
                    logger.error(f"❌ OOM recovery failed: {final_e}")
                    raise final_e
            else:
                raise e
        
        cleaned_tensor = self._clean_and_trim_tensor(raw_wav_tensor)
        
        wav_data = audio_processor.tensor_to_bytes(cleaned_tensor)
        final_audio = audio_processor.process_audio(
            wav_data, 
            params.get("output_format", settings.DEFAULT_OUTPUT_FORMAT), 
            params.get("sample_rate", settings.DEFAULT_SAMPLE_RATE)
        )
        return final_audio

    def _run_inference(self, conf: dict) -> torch.Tensor:
        with torch.inference_mode():
            if ssml_handler.is_ssml(conf['text']):
                segments = ssml_handler.parse(conf['text'], conf)
                wav_chunks = []
                for segment in segments:
                    if segment['type'] == 'text':
                        seg_speed = segment['params'].get("speed", conf['speed'])
                        out = self.model.inference(
                            segment['content'], conf['language'], conf['gpt_cond_latent'], conf['speaker_embedding'],
                            temperature=conf['temperature'], repetition_penalty=conf['repetition_penalty'],
                            top_k=conf['top_k'], top_p=conf['top_p'], speed=seg_speed
                        )
                        wav_chunks.append(torch.tensor(out['wav']))
                    elif segment['type'] == 'break':
                        wav_chunks.append(torch.zeros(int(24000 * segment['duration'])))
                raw_wav_tensor = torch.cat(wav_chunks, dim=0) if wav_chunks else torch.tensor([])
            else:
                out = self.model.inference(
                    conf['text'], conf['language'], conf['gpt_cond_latent'], conf['speaker_embedding'],
                    temperature=conf['temperature'], repetition_penalty=conf['repetition_penalty'],
                    top_k=conf['top_k'], top_p=conf['top_p'], speed=conf['speed']
                )
                raw_wav_tensor = torch.tensor(out["wav"])

            if settings.DEVICE == "cuda": raw_wav_tensor = raw_wav_tensor.cpu()
            self.memory_manager.check_and_clear()
            return raw_wav_tensor

    def synthesize_stream(self, params: dict, speaker_wavs=None):
        conf = self._prepare_inference(params, speaker_wavs)
        
        with self._gpu_lock:
            try:
                with torch.inference_mode():
                    chunks = self.model.inference_stream(
                        conf['text'], conf['language'], conf['gpt_cond_latent'], conf['speaker_embedding'],
                        temperature=conf['temperature'], repetition_penalty=conf['repetition_penalty'],
                        top_k=conf['top_k'], top_p=conf['top_p'], speed=conf['speed'],
                        enable_text_splitting=conf['split_sentences']
                    )

                    last_chunk_np = None
                    for chunk in chunks:
                        wav_chunk_float = chunk.cpu().numpy() if settings.DEVICE == "cuda" else chunk.numpy()
                        if np.max(np.abs(wav_chunk_float)) < 0.005: continue
                        if last_chunk_np is not None:
                            np.clip(last_chunk_np, -1.0, 1.0, out=last_chunk_np)
                            yield (last_chunk_np * 32767).astype(np.int16).tobytes()
                        last_chunk_np = wav_chunk_float
                    
                    if last_chunk_np is not None:
                        logger.debug("🔪 Cleaning last stream chunk (Fade-Out)...")
                        last_tensor = torch.from_numpy(last_chunk_np)
                        cleaned_tensor = self._clean_and_trim_tensor(last_tensor, threshold=0.025, fade_len=2400)
                        cleaned_np = cleaned_tensor.numpy()
                        np.clip(cleaned_np, -1.0, 1.0, out=cleaned_np)
                        yield (cleaned_np * 32767).astype(np.int16).tobytes()
                    
                    self.memory_manager.check_and_clear()
            except Exception:
                logger.error(f"Stream error", exc_info=True)
                yield b""

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
                    if styles: new_map[entry] = sorted(styles)
                elif entry.endswith(".wav"):
                    speaker_name = os.path.splitext(entry)[0]
                    new_map[speaker_name] = ["default"]
        except Exception: pass
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
                os.makedirs(self.SPEAKERS_DIR, exist_ok=True)
            default_path = os.path.join(self.SPEAKERS_DIR, "system_default.wav")
            if not os.path.exists(default_path) or os.path.getsize(default_path) < 100:
                logger.info("⚠️ System default speaker missing. Generating fallback tone...")
                try:
                    sr = 24000
                    silent_waveform = torch.zeros(1, sr)
                    torchaudio.save(default_path, silent_waveform, sr)
                    logger.info(f"✅ Fallback speaker created at {default_path}")
                except Exception as e:
                    logger.error(f"❌ Failed to create fallback speaker: {e}")
                    
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
        if "/" in speaker_id: spk_name, spk_style = speaker_id.split("/", 1)
        else: spk_name, spk_style = speaker_id, "default"
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
                return self._to_cuda((torch.tensor(data["gpt_cond_latent"]), torch.tensor(data["speaker_embedding"])))
            except: pass
        latents = self.model.get_conditioning_latents(audio_path=[wav_path], gpt_cond_len=30, gpt_cond_chunk_len=4, max_ref_length=60)
        try:
            with open(latent_file, 'w') as f: 
                json.dump({"gpt_cond_latent": latents[0].cpu().tolist(), "speaker_embedding": latents[1].cpu().tolist()}, f)
        except: pass
        return self._to_cuda(latents)

    def _to_cuda(self, latents):
        g, s = latents
        if settings.DEVICE == "cuda" and torch.cuda.is_available():
            g, s = g.cuda(), s.cuda()
        return g, s

tts_engine = TTSEngine()