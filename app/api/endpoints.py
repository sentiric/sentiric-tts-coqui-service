from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from typing import List
import asyncio
import os
import shutil
import glob
import uuid
import logging
import time
import langid
import torch
import hashlib
import json

from app.core.engine import tts_engine
from app.core.config import settings
from app.api.schemas import TTSRequest, OpenAISpeechRequest
from app.core.history import history_manager
from app.core.audio import audio_processor

logger = logging.getLogger("API")
router = APIRouter()

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"
CACHE_DIR = "/app/cache"

SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"]
LANGUAGE_NAMES = {
    "tr": "Turkish", "en": "English", "es": "Spanish", "fr": "French", 
    "de": "German", "it": "Italian", "pt": "Portuguese", "pl": "Polish",
    "ru": "Russian", "nl": "Dutch", "cs": "Czech", "ar": "Arabic",
    "zh-cn": "Chinese", "ja": "Japanese", "hu": "Hungarian", "ko": "Korean"
}

async def cleanup_files(file_paths: List[str]):
    for path in file_paths:
        try:
            if os.path.exists(path):
                await asyncio.to_thread(os.remove, path)
        except Exception as e:
            logger.warning(f"Failed to cleanup {path}: {e}")

def calculate_vca_metrics(start_time, char_count, audio_bytes, sample_rate=24000):
    process_time = time.perf_counter() - start_time
    len_bytes = len(audio_bytes) if audio_bytes else 0
    audio_duration_sec = len_bytes / (sample_rate * 2) 
    rtf = process_time / audio_duration_sec if audio_duration_sec > 0 else 0
    
    return {
        "X-VCA-Chars": str(char_count),
        "X-VCA-Time": f"{process_time:.3f}",
        "X-VCA-RTF": f"{rtf:.4f}",
        "X-VCA-Model": settings.MODEL_NAME
    }

def generate_deterministic_filename(params: dict, ext: str) -> str:
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

# --- SYSTEM ENDPOINTS ---
@router.get("/favicon.ico", include_in_schema=False)
async def favicon(): return Response(content=b"", media_type="image/x-icon")
    
@router.get("/health")
async def health_check():
    return {
        "status": "ok", "device": settings.DEVICE, "model_loaded": tts_engine.model is not None,
        "version": settings.APP_VERSION, "mode": "standalone" if settings.API_KEY else "cluster",
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
            "language": settings.DEFAULT_LANGUAGE, "speaker": settings.DEFAULT_SPEAKER
        },
        "limits": {
            "max_text_len": 5000, "supported_formats": ["wav", "mp3", "opus", "pcm"],
            "sample_rates": [24000, 16000, 8000], "supported_languages": langs
        },
        "system": {"streaming_enabled": settings.ENABLE_STREAMING, "device": settings.DEVICE}
    }

# --- HISTORY MANAGEMENT ---
@router.get("/api/history")
async def get_history(): return history_manager.get_all()

@router.get("/api/history/audio/{filename}")
async def get_history_audio(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(HISTORY_DIR, safe_filename)
    if os.path.exists(file_path): return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Audio not found")

@router.delete("/api/history/all")
async def delete_all_history():
    history_manager.clear_all()
    for f in glob.glob(os.path.join(HISTORY_DIR, "*")):
        if "history.db" not in f: 
            try: os.remove(f)
            except: pass
    return {"status": "cleared"}

@router.delete("/api/history/{filename}")
async def delete_history_entry(filename: str):
    history_manager.delete_entry(filename)
    try: os.remove(os.path.join(HISTORY_DIR, filename))
    except: pass
    return {"status": "deleted"}

@router.get("/api/speakers")
async def get_speakers():
    speakers_map = tts_engine.get_speakers()
    return {"speakers": speakers_map, "count": len(speakers_map)}

@router.post("/api/speakers/refresh")
async def refresh_speakers_cache():
    report = await asyncio.to_thread(tts_engine.refresh_speakers, force=True)
    return {"status": "ok", "data": report}

# --- CORE TTS ENDPOINTS ---
@router.post("/api/tts")
async def generate_speech(request: TTSRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")
    
    start_time = time.perf_counter()
    params = request.model_dump()
    
    ext = "wav"
    media_type = "audio/wav"
    if request.output_format == "mp3": ext="mp3"; media_type="audio/mpeg"
    elif request.output_format == "opus": ext="opus"; media_type="audio/ogg"
    elif request.output_format == "pcm": ext="pcm"; media_type="application/octet-stream"

    safe_filename = generate_deterministic_filename(params, ext)
    filepath = os.path.join(HISTORY_DIR, safe_filename)

    # CACHE CHECK
    if os.path.exists(filepath):
        # Dosya boyutu kontrolü (Header yoksa 44 byte altı olabilir, bozuktur)
        if os.path.getsize(filepath) < 44:
            logger.warning(f"🗑️ Corrupted cache file found ({safe_filename}), deleting...")
            try: os.remove(filepath)
            except: pass
        else:
            history_manager.add_entry(safe_filename, request.text, request.speaker_idx, "Cached")
            logger.info(f"⚡ Cache Hit: {safe_filename}")
            audio_bytes = await asyncio.to_thread(lambda: open(filepath, "rb").read())
            final_response = Response(content=audio_bytes, media_type=media_type)
            final_response.headers["X-Cache"] = "HIT"
            final_response.headers["X-VCA-Time"] = "0.001"
            return final_response

    try:
        if request.stream:
            async def stream_and_save():
                accumulated_bytes = bytearray()
                try:
                    for chunk in tts_engine.synthesize_stream(params):
                        accumulated_bytes.extend(chunk)
                        yield chunk
                finally:
                    if accumulated_bytes:
                        # FIX: Ham PCM verisini WAV formatına çevirip kaydet
                        # Bu fonksiyon sadece header ekler, encode etmez (Hızlıdır)
                        wav_ready_bytes = audio_processor.raw_pcm_to_wav(
                            bytes(accumulated_bytes), 
                            request.sample_rate
                        )
                        await asyncio.to_thread(lambda: open(filepath, "wb").write(wav_ready_bytes))
                        history_manager.add_entry(safe_filename, request.text, request.speaker_idx, "Stream")

            return StreamingResponse(
                stream_and_save(), 
                media_type="application/octet-stream",
                headers={"X-Stream-Start": str(start_time)}
            )
        else:
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
            metrics = calculate_vca_metrics(start_time, len(request.text), audio_bytes, request.sample_rate)
            await asyncio.to_thread(lambda: open(filepath, "wb").write(audio_bytes))
            history_manager.add_entry(safe_filename, request.text, request.speaker_idx, "Standard")
            final_response = Response(content=audio_bytes, media_type=media_type)
            for k, v in metrics.items(): final_response.headers[k] = v
            return final_response
            
    except Exception as e:
        logger.error(f"TTS Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/tts/clone")
async def generate_speech_clone(
    text: str = Form(...), language: str = Form(settings.DEFAULT_LANGUAGE),
    files: List[UploadFile] = File(...), temperature: float = Form(settings.DEFAULT_TEMPERATURE),
    speed: float = Form(settings.DEFAULT_SPEED), top_k: int = Form(settings.DEFAULT_TOP_K),
    top_p: float = Form(settings.DEFAULT_TOP_P), repetition_penalty: float = Form(settings.DEFAULT_REPETITION_PENALTY),
    stream: bool = Form(False), output_format: str = Form(settings.DEFAULT_OUTPUT_FORMAT)
):
    if not text or not text.strip(): raise HTTPException(status_code=422, detail="Text cannot be empty.")
    
    start_time = time.perf_counter()
    saved_files = []
    
    try:
        for file in files:
            file_ext = os.path.splitext(file.filename)[1] or ".wav"
            file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{file_ext}")
            def save_upload(src_file, dst_path):
                with open(dst_path, "wb") as buffer: shutil.copyfileobj(src_file, buffer)
            await asyncio.to_thread(save_upload, file.file, file_path)
            saved_files.append(file_path)
            
        params = {
            "text": text, "language": language, "temperature": temperature,
            "speed": speed, "top_k": top_k, "top_p": top_p,
            "repetition_penalty": repetition_penalty, "output_format": output_format, 
            "speaker_idx": None, "sample_rate": 24000
        }
        
        if stream:
            async def stream_with_cleanup():
                try:
                    for chunk in tts_engine.synthesize_stream(params, speaker_wavs=saved_files): yield chunk
                finally: await cleanup_files(saved_files)
            return StreamingResponse(stream_with_cleanup(), media_type="application/octet-stream", headers={"X-Stream-Start": str(start_time)})
        else:
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params, speaker_wavs=saved_files)
            await cleanup_files(saved_files)
            metrics = calculate_vca_metrics(start_time, len(text), audio_bytes)
            
            ext = output_format if output_format != "pcm" else "wav"
            if ext == "opus": ext = "ogg"
            filename = f"clone_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            await asyncio.to_thread(lambda: open(filepath, "wb").write(audio_bytes))
            history_manager.add_entry(filename, text, "Cloned Voice", "Cloning")
            
            media_type = "audio/wav"
            if output_format == "mp3": media_type = "audio/mpeg"
            
            final_response = Response(content=audio_bytes, media_type=media_type)
            for k, v in metrics.items(): final_response.headers[k] = v
            return final_response
            
    except Exception as e:
        await cleanup_files(saved_files)
        logger.error(f"Clone Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/v1/audio/speech")
async def openai_speech_endpoint(request: OpenAISpeechRequest):
    if not request.input or not request.input.strip(): raise HTTPException(status_code=422, detail="Input text cannot be empty.")
    return await generate_speech(TTSRequest(
        text=request.input,
        language="en", 
        speaker_idx="Ana Florence", 
        stream=True,
        output_format=request.response_format if request.response_format in ["wav", "pcm"] else "mp3"
    ))

@router.get("/v1/models")
async def list_models():
    speakers = tts_engine.get_speakers()
    models_data = [{"id": "tts-1", "object": "model", "created": 1234567890, "owned_by": "sentiric-tts"}]
    for spk_name in speakers.keys(): models_data.append({"id": spk_name, "object": "model", "created": 1234567890, "owned_by": "sentiric-local"})
    return {"object": "list", "data": models_data}