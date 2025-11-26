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
    speaker_latents_cache = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TTSEngine, cls).__new__(cls)
            cls._instance.model = None
            os.makedirs(cls.SPEAKERS_DIR, exist_ok=True)
            os.makedirs(cls.CACHE_DIR, exist_ok=True)
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
                self.model.cuda()
                logger.info("✅ Model loaded directly to GPU.")
                self.refresh_speakers()
            except Exception as e:
                logger.critical(f"🔥 Model initialization failed: {e}")
                raise e

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
            parser = ET.XMLParser()
            ssml_text = f"<root>{ssml_text}</root>"
            root = ET.fromstring(ssml_text, parser=parser)
            segments = []
            
            def process_element(element, current_params):
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
                    if child.tail and child.tail.strip():
                        segments.append({'type': 'text', 'content': child.tail.strip(), 'params': current_params.copy()})

            for speak_tag in root.findall('speak'):
                initial_params = {}
                process_element(speak_tag, initial_params)
            
            if not segments:
                return [{'type': 'text', 'content': ET.fromstring(ssml_text, parser=parser).text, 'params': {}}]
            return segments
        except ET.ParseError as e:
            logger.error(f"SSML Parse Error: {e}")
            raise ValueError(f"Invalid SSML format: {e}")

    def synthesize(self, params: dict, speaker_wavs=None) -> bytes:
        text = params.get("text", "").strip()
        is_ssml = text.startswith('<speak>') and text.endswith('</speak>')
        if not is_ssml:
            params["speaker_wavs"] = speaker_wavs
            cache_key = self._generate_cache_key(params)
            cached_audio = self._check_cache(cache_key)
            if cached_audio:
                logger.info("⚡ Cache HIT! Serving from disk.")
                return cached_audio
        logger.info(f"🐢 Synthesizing ({params.get('language')}, SSML: {is_ssml})...")
        with self._thread_lock:
            gpt_cond_latent, speaker_embedding = self._get_latents(params.get("speaker_idx"), speaker_wavs)
            if is_ssml:
                segments = self._parse_ssml(text)
                wav_chunks = []
                for segment in segments:
                    if segment['type'] == 'text':
                        inference_params = params.copy()
                        inference_params.update(segment['params'])
                        chunk = self.model.inference(
                            segment['content'], inference_params.get("language"), gpt_cond_latent, speaker_embedding,
                            temperature=inference_params.get("temperature", 0.75),
                            repetition_penalty=inference_params.get("repetition_penalty", 2.0),
                            top_k=inference_params.get("top_k", 50),
                            top_p=inference_params.get("top_p", 0.85),
                            speed=inference_params.get("speed", 1.0)
                        )['wav']
                        wav_chunks.append(torch.tensor(chunk))
                    elif segment['type'] == 'break':
                        sample_rate = 24000
                        silence_duration = int(sample_rate * segment['duration'])
                        silence = torch.zeros(silence_duration)
                        wav_chunks.append(silence)
                full_wav = torch.cat(wav_chunks, dim=0) if wav_chunks else torch.tensor([])
            else:
                 out = self.model.inference(
                    text, params.get("language"), gpt_cond_latent, speaker_embedding,
                    temperature=params.get("temperature", 0.75),
                    repetition_penalty=params.get("repetition_penalty", 2.0),
                    top_k=params.get("top_k", 50),
                    top_p=params.get("top_p", 0.85),
                    speed=params.get("speed", 1.0)
                )
                 full_wav = torch.tensor(out["wav"])
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
        if not is_ssml: self._save_cache(cache_key, final_audio)
        return final_audio

    def synthesize_stream(self, params: dict, speaker_wavs=None):
        text = params.get("text", "")
        is_ssml = text.strip().startswith('<speak>')
        if is_ssml:
            logger.warning("SSML is not supported for streaming. The request will be processed as plain text, which may cause tags to be read aloud.")
        
        lang = params.get("language")
        if not lang or lang == "auto": lang = langid.classify(text)[0].strip()
        if lang == "zh": lang = "zh-cn"
        with self._thread_lock:
            try:
                gpt_cond_latent, speaker_embedding = self._get_latents(params.get("speaker_idx"), speaker_wavs)
                resampler = None
                if params.get("sample_rate") == 8000: resampler = T.Resample(24000, 8000)
                chunks = self.model.inference_stream(
                    text, lang, gpt_cond_latent, speaker_embedding,
                    temperature=params.get("temperature", 0.75), repetition_penalty=params.get("repetition_penalty", 2.0),
                    top_k=params.get("top_k", 50), top_p=params.get("top_p", 0.85), speed=params.get("speed", 1.0),
                    enable_text_splitting=True
                )

                # --- YENİ BÖLÜM: GERÇEK ZAMANLI SES YÜKSELTME ---
                # loudnorm'a yakın bir seviye için ~1.5x kazanç (deneyerek bulunur)
                gain_factor = 1.5
                
                for i, chunk in enumerate(chunks):
                    if resampler: chunk = resampler(chunk)
                    
                    # float32'ye dönüştür, kazancı uygula, sonra int16'ya çevir
                    wav_chunk_float = chunk.cpu().numpy()
                    
                    # Kazancı uygula
                    amplified_chunk_float = wav_chunk_float * gain_factor
                    
                    # Kırpılmayı (clipping) önle. Değerleri [-1.0, 1.0] aralığında tut.
                    np.clip(amplified_chunk_float, -1.0, 1.0, out=amplified_chunk_float)

                    # int16'ya dönüştür
                    wav_int16 = (amplified_chunk_float * 32767).astype(np.int16)

                    yield wav_int16.tobytes()
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"Error: {str(e)}".encode()
    
    # ... (Diğer tüm metodlar aynı kalır) ...
    def refresh_speakers(self):
        report = {"success": [], "failed": {}, "total_scanned": 0}
        if os.path.exists(self.SPEAKERS_DIR):
            files = glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav"))
            report["total_scanned"] = len(files)
            logger.info(f"Scanning {len(files)} speaker files...")
            for f in files:
                name = os.path.splitext(os.path.basename(f))[0]
                if name not in self.speaker_latents_cache:
                    try:
                        gpt_cond_latent, speaker_embedding = self.model.get_conditioning_latents(audio_path=[f], gpt_cond_len=30, gpt_cond_chunk_len=4, max_ref_length=60)
                        self.speaker_latents_cache[name] = { "gpt_cond_latent": gpt_cond_latent, "speaker_embedding": speaker_embedding }
                        report["success"].append(name)
                    except Exception as e:
                        error_message = str(e)
                        logger.warning(f"Could not load speaker '{name}': {error_message}")
                        report["failed"][name] = error_message
        return report
    def get_speakers(self): return list(self.speaker_latents_cache.keys())
    def _get_latents(self, speaker_idx, speaker_wavs):
        if speaker_wavs: return self.model.get_conditioning_latents(audio_path=speaker_wavs, gpt_cond_len=30, gpt_cond_chunk_len=4, max_ref_length=60)
        if speaker_idx in self.speaker_latents_cache: c = self.speaker_latents_cache[speaker_idx]; return c["gpt_cond_latent"], c["speaker_embedding"]
        files = glob.glob(os.path.join(self.SPEAKERS_DIR, "*.wav"))
        if files: logger.warning(f"Speaker '{speaker_idx}' not found. Using fallback: {files[0]}"); return self.model.get_conditioning_latents(audio_path=[files[0]])
        raise ValueError("No speakers found available for synthesis.")
    def _generate_cache_key(self, params):
        if params.get("speaker_wavs"): return None
        key_data = {"text": params["text"], "lang": params["language"], "spk": params["speaker_idx"], "temp": params["temperature"], "speed": params["speed"], "fmt": params.get("output_format", "wav"), "sr": params.get("sample_rate", 24000)}
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    def _check_cache(self, key):
        if not key: return None
        path = os.path.join(self.CACHE_DIR, f"{key}.bin");
        if os.path.exists(path):
            with open(path, "rb") as f: return f.read()
        return None
    def _save_cache(self, key, data):
        if not key: return
        path = os.path.join(self.CACHE_DIR, f"{key}.bin")
        try:
            with open(path, "wb") as f: f.write(data)
        except Exception as e: logger.error(f"Cache write failed: {e}")
    def _process_audio(self, wav_bytes: bytes, format: str, sample_rate: int) -> bytes:
        try:
            cmd = ['ffmpeg', '-i', 'pipe:0', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11']
            if format == "mp3": cmd += ['-f', 'mp3', '-b:a', '192k']
            elif format == "opus": cmd += ['-f', 'opus', '-b:a', '64k']
            elif format == "pcm": cmd += ['-f', 's16le', '-acodec', 'pcm_s16le']
            else: cmd += ['-f', 'wav']
            cmd += ['-ar', str(sample_rate), 'pipe:1']
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = process.communicate(input=wav_bytes)
            if process.returncode != 0: logger.warning(f"FFmpeg returned error code {process.returncode}")
            return out
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return wav_bytes

tts_engine = TTSEngine()