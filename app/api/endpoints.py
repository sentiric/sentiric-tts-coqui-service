import os
import shutil
import glob
import uuid
import logging
import time
import json
import hashlib
import asyncio
from typing import List, Optional

import torch
import langid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse

from app.core.engine import tts_engine
from app.core.config import settings
from app.api.schemas import TTSRequest, OpenAISpeechRequest
from app.core.history import history_manager
from app.core.audio import audio_processor

# Loglama yapılandırması
logger = logging.getLogger("API")
router = APIRouter()

# Dizin tanımları
UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"
CACHE_DIR = "/app/cache"

# Dizinlerin varlığından emin ol
for d in [UPLOAD_DIR, HISTORY_DIR, CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

# Dil İsimleri Haritası (UI için)
SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"]
LANGUAGE_NAMES = {
    "tr": "Turkish", "en": "English", "es": "Spanish", "fr": "French", 
    "de": "German", "it": "Italian", "pt": "Portuguese", "pl": "Polish",
    "ru": "Russian", "nl": "Dutch", "cs": "Czech", "ar": "Arabic",
    "zh-cn": "Chinese", "ja": "Japanese", "hu": "Hungarian", "ko": "Korean"
}

# --- YARDIMCI FONKSİYONLAR ---

async def cleanup_files(file_paths: List[str]):
    """Geçici dosyaları temizler."""
    for path in file_paths:
        try:
            if os.path.exists(path):
                await asyncio.to_thread(os.remove, path)
        except Exception as e:
            logger.warning(f"Failed to cleanup {path}: {e}")

def calculate_vca_metrics(start_time, char_count, audio_bytes, sample_rate=24000):
    """Value and Cost Analytics (VCA) metriklerini hesaplar."""
    process_time = time.perf_counter() - start_time
    len_bytes = len(audio_bytes) if audio_bytes else 0
    # 16-bit mono varsayımıyla süre hesaplama
    audio_duration_sec = len_bytes / (sample_rate * 2) 
    rtf = process_time / audio_duration_sec if audio_duration_sec > 0 else 0
    
    return {
        "X-VCA-Chars": str(char_count),
        "X-VCA-Time": f"{process_time:.3f}",
        "X-VCA-RTF": f"{rtf:.4f}",
        "X-VCA-Model": settings.MODEL_NAME
    }

def generate_deterministic_filename(params: dict, ext: str) -> str:
    """Parametrelere dayalı benzersiz bir dosya adı (hash) üretir (Caching için)."""
    key_data = {
        "text": params.get("text"),
        "lang": params.get("language"),
        "spk": params.get("speaker_idx"),
        "temp": params.get("temperature"),
        "speed": params.get("speed"),
        "fmt": ext
    }
    file_hash = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    return f"{file_hash}.{ext}"

async def _get_voices_list():
    """
    OpenAI ve Open WebUI uyumlu ses listesi oluşturucu.
    Tüm stilleri (neutral dahil) açıkça listeler.
    """
    speakers_map = tts_engine.get_speakers()
    voices_list = []
    
    openai_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    for v in openai_voices:
        voices_list.append({"id": v, "name": f"OpenAI {v.capitalize()}", "object": "voice"})

    if isinstance(speakers_map, dict):
        for spk_name, styles in sorted(speakers_map.items()):
            # Ana konuşmacıyı (genellikle neutral/default) ekle
            voices_list.append({"id": spk_name, "name": spk_name, "object": "voice"})
            
            # *** DÜZELTME: 'neutral' filtresini kaldır. Tüm stilleri listele. ***
            if isinstance(styles, list):
                for style in sorted(styles):
                    # Ana isimle aynı olan stili (örn: F_TR_Genc_Selin/F_TR_Genc_Selin) ekleme
                    if style.lower() != spk_name.lower():
                        variant_id = f"{spk_name}/{style}"
                        voices_list.append({"id": variant_id, "name": variant_id, "object": "voice"})
    return voices_list

# --- SYSTEM ENDPOINTS ---

@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")
    
@router.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "device": settings.DEVICE, 
        "model_loaded": tts_engine.model is not None,
        "version": settings.APP_VERSION, 
        "mode": "standalone" if settings.API_KEY else "cluster",
        "vram_allocated_mb": int(torch.cuda.memory_allocated() / (1024*1024)) if torch.cuda.is_available() else 0
    }

@router.get("/api/config")
async def get_public_config():
    langs = [{"code": code, "name": LANGUAGE_NAMES.get(code, code.upper())} for code in SUPPORTED_LANGUAGES]
    return {
        "app_name": settings.APP_NAME, "version": settings.APP_VERSION,
        "defaults": {
            "temperature": settings.DEFAULT_TEMPERATURE, "speed": settings.DEFAULT_SPEED,
            "top_k": settings.DEFAULT_TOP_K, "top_p": settings.DEFAULT_TOP_P,
            "repetition_penalty": settings.DEFAULT_REPETITION_PENALTY,
            "language": settings.DEFAULT_LANGUAGE, "speaker": settings.DEFAULT_SPEAKER,
            "sample_rate": settings.DEFAULT_SAMPLE_RATE
        },
        "limits": {
            "max_text_len": 5000, "supported_formats": ["wav", "mp3", "opus", "pcm"],
            "supported_languages": langs
        },
        "system": {"streaming_enabled": settings.ENABLE_STREAMING, "device": settings.DEVICE}
    }

# --- OPENAI COMPATIBLE ENDPOINTS (CRITICAL FIX FOR OPEN WEBUI) ---

@router.get("/v1/models")
async def list_models():
    voices = await _get_voices_list()
    models_data = [{"id": v["id"], "object": "model", "name": v.get("name", v["id"])} for v in voices]
    return {"object": "list", "data": models_data}

@router.get("/v1/audio/voices")
async def list_voices_custom():
    voices = await _get_voices_list()
    return {"voices": voices}

@router.post("/v1/audio/speech")
async def openai_speech_endpoint(request: OpenAISpeechRequest):
    if not request.input or not request.input.strip(): 
        raise HTTPException(status_code=422, detail="Input text cannot be empty.")
    
    detected_lang = settings.DEFAULT_LANGUAGE
    try:
        lang_code, confidence = langid.classify(request.input)
        if lang_code in SUPPORTED_LANGUAGES:
            detected_lang = lang_code
            logger.info(f"Detected Lang: {detected_lang} (Conf: {confidence})")
    except: pass

    openai_map = {
        "alloy": "F_TR_Kurumsal_Ece", "echo": "M_TR_Heyecanli_Can",
        "fable": "M_TR_Enerjik_Mert", "onyx": "M_TR_Tok_Kadir",
        "nova": "F_TR_Parlak_Zeynep", "shimmer": "F_TR_Genc_Selin"
    }
    final_speaker = openai_map.get(request.voice.lower(), request.voice)
    
    # *** DÜZELTME: Stil belirtilmemişse, 'neutral' veya 'default' varsay. ***
    if "/" not in final_speaker:
        logger.info(f"No style specified for '{final_speaker}', defaulting to neutral/default.")
        # Engine'in kendi varsayılanını kullanmasına izin ver, bu daha esnek.
        # final_speaker = f"{final_speaker}/neutral" satırını kaldırdık.
        # _get_latents fonksiyonu bu durumu zaten yönetiyor.
        pass

    available_speakers = tts_engine.get_speakers()
    base_speaker = final_speaker.split('/')[0]
    if base_speaker not in available_speakers:
        fallback = list(available_speakers.keys())[0] if available_speakers else "system_default"
        logger.warning(f"Speaker '{final_speaker}' not found. Falling back to '{fallback}'")
        final_speaker = fallback

    output_fmt = "mp3"
    logger.info(f"OpenAI TTS: '{request.input[:15]}...' -> {final_speaker} ({detected_lang}) -> {output_fmt}")

    internal_req = TTSRequest(
        text=request.input, language=detected_lang, speaker_idx=final_speaker,
        stream=False, speed=request.speed if request.speed else settings.DEFAULT_SPEED,
        output_format=output_fmt
    )
    
    start_time = time.perf_counter()
    try:
        params = internal_req.model_dump()
        audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"TTS Generation Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- INTERNAL API ENDPOINTS (STUDIO & MICROSERVICES) ---

@router.get("/api/speakers")
async def get_speakers():
    return {"speakers": tts_engine.get_speakers()}

@router.post("/api/speakers/refresh")
async def refresh_speakers_cache():
    return await asyncio.to_thread(tts_engine.refresh_speakers, force=True)

@router.get("/api/history")
async def get_history(): 
    return history_manager.get_all()

@router.get("/api/history/audio/{filename}")
async def get_history_audio(filename: str):
    file_path = os.path.join(HISTORY_DIR, os.path.basename(filename))
    if os.path.exists(file_path): return FileResponse(file_path)
    raise HTTPException(status_code=404)

@router.delete("/api/history/all")
async def delete_all_history():
    history_manager.clear_all()
    for f in glob.glob(os.path.join(HISTORY_DIR, "*")):
        if "history.db" not in f: os.remove(f)
    return {"status": "cleared"}

@router.delete("/api/history/{filename}")
async def delete_history_entry(filename: str):
    history_manager.delete_entry(filename)
    try: os.remove(os.path.join(HISTORY_DIR, filename))
    except: pass
    return {"status": "deleted"}

@router.post("/api/tts")
async def generate_speech(request: TTSRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=422)
    
    params = request.model_dump()
    start_time = time.perf_counter()
    
    if request.stream:
        logger.info("Stream request: Bypassing cache.")
        async def stream_and_save():
            accumulated_bytes = bytearray()
            safe_filename = generate_deterministic_filename(params, "wav")
            filepath = os.path.join(HISTORY_DIR, safe_filename)
            try:
                for chunk in tts_engine.synthesize_stream(params):
                    accumulated_bytes.extend(chunk)
                    yield chunk
            finally:
                if accumulated_bytes:
                    wav_bytes = audio_processor.raw_pcm_to_wav(bytes(accumulated_bytes), request.sample_rate)
                    await asyncio.to_thread(open(filepath, "wb").write, wav_bytes)
                    history_manager.add_entry(safe_filename, request.text, request.speaker_idx, "Stream")
        return StreamingResponse(stream_and_save(), media_type="application/octet-stream")
    else:
        ext = request.output_format
        media_type = {"mp3": "audio/mpeg", "opus": "audio/ogg", "pcm": "application/octet-stream"}.get(ext, "audio/wav")
        safe_filename = generate_deterministic_filename(params, ext)
        filepath = os.path.join(HISTORY_DIR, safe_filename)
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 44:
            logger.info(f"Cache Hit: {safe_filename}")
            audio_bytes = await asyncio.to_thread(open(filepath, "rb").read)
            return Response(content=audio_bytes, media_type=media_type, headers={"X-Cache": "HIT"})
            
        audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
        metrics = calculate_vca_metrics(start_time, len(request.text), audio_bytes, request.sample_rate)
        await asyncio.to_thread(open(filepath, "wb").write, audio_bytes)
        history_manager.add_entry(safe_filename, request.text, request.speaker_idx, "Standard")
        return Response(content=audio_bytes, media_type=media_type, headers=metrics)

@router.post("/api/tts/clone")
async def generate_speech_clone(
    text: str = Form(...), language: str = Form(settings.DEFAULT_LANGUAGE), files: List[UploadFile] = File(...),
    stream: bool = Form(False), output_format: str = Form(settings.DEFAULT_OUTPUT_FORMAT)
):
    saved_files = []
    try:
        for file in files:
            file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.wav")
            with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
            saved_files.append(file_path)
        params = {"text": text, "language": language, "output_format": output_format}
        if stream:
            async def stream_with_cleanup():
                try:
                    for chunk in tts_engine.synthesize_stream(params, speaker_wavs=saved_files): yield chunk
                finally: await cleanup_files(saved_files)
            return StreamingResponse(stream_with_cleanup(), media_type="application/octet-stream")
        else:
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params, speaker_wavs=saved_files)
            await cleanup_files(saved_files)
            return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        await cleanup_files(saved_files)
        raise HTTPException(500, str(e))