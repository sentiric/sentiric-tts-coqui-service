import os
import torch
import numpy as np
import langid
import glob
import hashlib
import json
import logging
import threading
import gc
import xml.etree.ElementTree as ET

from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts
from TTS.utils.manage import ModelManager
from TTS.utils.generic_utils import get_user_data_dir

from app.core.config import settings
from app.core.normalizer import normalizer
from app.core.audio import audio_processor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("XTTS-ENGINE")

class TTSEngine:
    """
    Görevi: Model Yükleme, VRAM Yönetimi ve Inference (Sentezleme).
    """
    _instance = None
    _thread_lock = threading.Lock()
    
    SPEAKERS_DIR = "/app/speakers"
    CACHE_DIR = "/app/cache"
    LATENTS_DIR = "/app/cache/latents"

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
                    logger.warning("⚠️ Model loaded to CPU.")
                
                self.refresh_speakers()
            except Exception as e:
                logger.critical(f"🔥 Model init failed: {e}")
                raise e

    def _cleanup_memory(self):
        if settings.LOW_RESOURCE_MODE:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def _parse_ssml(self, ssml_text: str):
        # Basit SSML Parser
        try:
            ssml_text = ssml_text.replace("&", "&amp;") 
            parser = ET.XMLParser()
            root = ET.fromstring(f"<root>{ssml_text}</root>", parser=parser)
            segments = []
            
            def process_element(element, current_params):
                if element.text and element.text.strip():
                    segments.append({'type': 'text', 'content': element.text.strip(), 'params': current_params.copy()})
                for child in element:
                    child_params = current_params.copy()
                    if child.tag == 'break':
                        duration = 0.5
                        try: duration = float(child.get('time', '0.5s').replace('s',''))
                        except: pass
                        segments.append({'type': 'break', 'duration': duration})
                    elif child.tag == 'prosody':
                        rate = child.get('rate')
                        if rate == "slow": child_params['speed'] = 0.85
                        elif rate == "fast": child_params['speed'] = 1.2
                    process_element(child, child_params)
                    if child.tail and child.tail.strip():
                        segments.append({'type': 'text', 'content': child.tail.strip(), 'params': current_params.copy()})

            process_element(root, {})
            if not segments: return [{'type': 'text', 'content': "".join(root.itertext()), 'params': {}}]
            return segments
        except:
            import re
            return [{'type': 'text', 'content': re.sub(r'<[^>]+>', '', ssml_text), 'params': {}}]

    def synthesize(self, params: dict, speaker_wavs=None) -> bytes:
        # 1. Normalizasyon
        text = normalizer.normalize(params.get("text", ""), params.get("language"))
        if not text: return b""
        
        is_ssml = "<speak>" in text
        
        # 2. Cache Kontrolü
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
                gpt_cond_latent, speaker_embedding = self._get_latents(params.get("speaker_idx"), speaker_wavs)
                
                if is_ssml:
                    segments = self._parse_ssml(text)
                    wav_chunks = []
                    for segment in segments:
                        if segment['type'] == 'text':
                            inf_params = params.copy()
                            inf_params.update(segment['params'])
                            out = self.model.inference(
                                segment['content'], inf_params.get("language"), gpt_cond_latent, speaker_embedding,
                                temperature=inf_params.get("temperature", 0.75),
                                repetition_penalty=inf_params.get("repetition_penalty", 2.0),
                                top_k=inf_params.get("top_k", 50), top_p=inf_params.get("top_p", 0.85),
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

                if settings.DEVICE == "cuda": full_wav = full_wav.cpu()
            finally:
                self._cleanup_memory()

        # 3. Audio Processing (External Delegate)
        wav_data = audio_processor.tensor_to_bytes(full_wav)
        final_audio = audio_processor.process_audio(
            wav_data, 
            params.get("output_format", "wav"), 
            params.get("sample_rate", 24000),
            add_silence=True 
        )
        
        if not is_ssml and cache_key: self._save_cache(cache_key, final_audio)
        return final_audio

    def synthesize_stream(self, params: dict, speaker_wavs=None):
        text = normalizer.normalize(params.get("text", ""), params.get("language"))
        lang = params.get("language")
        if not lang or lang == "auto": lang = langid.classify(text)[0].strip()
        if lang == "zh": lang = "zh-cn"
        
        with self._thread_lock:
            try:
                gpt_cond_latent, speaker_embedding = self._get_latents(params.get("speaker_idx"), speaker_wavs)
                chunks = self.model.inference_stream(
                    text, lang, gpt_cond_latent, speaker_embedding,
                    temperature=params.get("temperature", 0.75), repetition_penalty=params.get("repetition_penalty", 2.0),
                    top_k=params.get("top_k", 50), top_p=params.get("top_p", 0.85), speed=params.get("speed", 1.0),
                    enable_text_splitting=True
                )

                for chunk in chunks:
                    if settings.DEVICE == "cuda": chunk = chunk.cpu()
                    wav_chunk_float = chunk.numpy()
                    np.clip(wav_chunk_float, -1.0, 1.0, out=wav_chunk_float)
                    wav_int16 = (wav_chunk_float * 32767).astype(np.int16)
                    yield wav_int16.tobytes()
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield b""
            finally:
                self._cleanup_memory()

    def refresh_speakers(self):
        report = {"success": [], "failed": {}, "total_scanned": 0}
        if os.path.exists(self.SPEAKERS_DIR):
            files = glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav"))
            report["total_scanned"] = len(files)
            for f in files:
                name = os.path.splitext(os.path.basename(f))[0]
                report["success"].append(name)
        return report

    def get_speakers(self):
        if os.path.exists(self.SPEAKERS_DIR): return [os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav"))]
        return []

    def _get_latents(self, speaker_idx, speaker_wavs):
        if speaker_wavs: return self.model.get_conditioning_latents(audio_path=speaker_wavs, gpt_cond_len=30, gpt_cond_chunk_len=4, max_ref_length=60)
        if not speaker_idx: raise ValueError("Speaker ID required")
        
        latent_file = os.path.join(self.LATENTS_DIR, f"{speaker_idx}.json")
        if os.path.exists(latent_file):
            try:
                with open(latent_file, 'r') as f: data = json.load(f)
                gpt_cond_latent = torch.tensor(data["gpt_cond_latent"])
                speaker_embedding = torch.tensor(data["speaker_embedding"])
                if settings.DEVICE == "cuda": gpt_cond_latent = gpt_cond_latent.cuda(); speaker_embedding = speaker_embedding.cuda()
                return gpt_cond_latent, speaker_embedding
            except: pass
            
        wav_path = os.path.join(self.SPEAKERS_DIR, f"{speaker_idx}.wav")
        if not os.path.exists(wav_path): files = glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav")); wav_path = files[0] if files else None
        if not wav_path: raise ValueError("No speakers found.")
        
        gpt_cond_latent, speaker_embedding = self.model.get_conditioning_latents(audio_path=[wav_path], gpt_cond_len=30, gpt_cond_chunk_len=4, max_ref_length=60)
        try:
            with open(latent_file, 'w') as f: json.dump({"gpt_cond_latent": gpt_cond_latent.cpu().tolist(), "speaker_embedding": speaker_embedding.cpu().tolist()}, f)
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
                with open(path, "rb") as f: return f.read()
            except: return None
        return None

    def _save_cache(self, key, data):
        if not key: return
        try:
            with open(os.path.join(self.CACHE_DIR, f"{key}.bin"), "wb") as f: f.write(data)
        except: pass

tts_engine = TTSEngine()