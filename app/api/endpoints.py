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

from app.core.engine import tts_engine
from app.core.config import settings
from app.api.schemas import TTSRequest, OpenAISpeechRequest
from app.core.history import history_manager

logger = logging.getLogger("API")
router = APIRouter()

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"
CACHE_DIR = "/app/cache"

# Tüm diller burada tanımlı
SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"]
LANGUAGE_NAMES = {
    "tr": "Turkish", "en": "English", "es": "Spanish", "fr": "French", 
    "de": "German", "it": "Italian", "pt": "Portuguese", "pl": "Polish",
    "ru": "Russian", "nl": "Dutch", "cs": "Czech", "ar": "Arabic",
    "zh-cn": "Chinese", "ja": "Japanese", "hu": "Hungarian", "ko": "Korean"
}

# ... (Helper functions same as before) ...
async def cleanup_files(file_paths: List[str]):
    for path in file_paths:
        try:
            if os.path.exists(path):
                await asyncio.to_thread(os.remove, path)
        except: pass

@router.get("/favicon.ico", include_in_schema=False)
async def favicon(): return Response(content=b"", media_type="image/x-icon")
    
@router.get("/health")
async def health_check():
    return {"status": "ok", "device": settings.DEVICE, "model_loaded": tts_engine.model is not None, "version": settings.APP_VERSION}

@router.get("/api/config")
async def get_public_config():
    # Frontend için zenginleştirilmiş dil listesi
    langs = [{"code": code, "name": LANGUAGE_NAMES.get(code, code.upper())} for code in SUPPORTED_LANGUAGES]
    
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "defaults": {
            "temperature": settings.DEFAULT_TEMPERATURE,
            "speed": settings.DEFAULT_SPEED,
            "top_k": settings.DEFAULT_TOP_K,
            "top_p": settings.DEFAULT_TOP_P,
            "repetition_penalty": settings.DEFAULT_REPETITION_PENALTY,
            "language": settings.DEFAULT_LANGUAGE,
            "speaker": settings.DEFAULT_SPEAKER
        },
        "limits": {
            "max_text_len": 5000,
            "supported_formats": ["wav", "mp3", "opus", "pcm"],
            "supported_languages": langs # ARTIK BU LISTEYI DONUYORUZ
        },
        "system": {
            "streaming_enabled": settings.ENABLE_STREAMING,
            "device": settings.DEVICE
        }
    }

# ... (History Endpoints - Aynı)
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
    # Dosya silme mantığı basitleştirildi
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

# ... (Speaker Endpoints - Aynı)
@router.get("/api/speakers")
async def get_speakers():
    speakers_map = tts_engine.get_speakers()
    return {"speakers": speakers_map, "count": len(speakers_map)}

@router.post("/api/speakers/refresh")
async def refresh_speakers_cache():
    report = await asyncio.to_thread(tts_engine.refresh_speakers, force=True)
    return {"status": "ok", "data": report}

# ... (Main TTS Endpoint - Aynı)
@router.post("/api/tts")
async def generate_speech(request: TTSRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")
    
    start_time = time.perf_counter()
    try:
        params = request.model_dump()
        
        if request.stream:
            return StreamingResponse(tts_engine.synthesize_stream(params), media_type="application/octet-stream")
        else:
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
            
            process_time = time.perf_counter() - start_time
            char_count = len(request.text)
            audio_duration_sec = len(audio_bytes) / (request.sample_rate * 2) 
            rtf = process_time / audio_duration_sec if audio_duration_sec > 0 else 0

            # Log ve Headerlar
            ext = "wav"
            media_type = "audio/wav"
            if request.output_format == "mp3": ext="mp3"; media_type="audio/mpeg"
            elif request.output_format == "opus": ext="opus"; media_type="audio/ogg"
            elif request.output_format == "pcm": ext="pcm"; media_type="application/octet-stream"
            
            filename = f"tts_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            # Async IO için thread'e atıyoruz
            await asyncio.to_thread(lambda: open(filepath, "wb").write(audio_bytes))
            
            history_manager.add_entry(filename, request.text, request.speaker_idx, "Standard")
            
            final_response = Response(content=audio_bytes, media_type=media_type)
            final_response.headers["X-VCA-Chars"] = str(char_count)
            final_response.headers["X-VCA-Time"] =f"{process_time:.3f}"
            final_response.headers["X-VCA-RTF"] = f"{rtf:.4f}"
            return final_response
            
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ... (Clone Endpoint - Aynı)
@router.post("/api/tts/clone")
async def generate_speech_clone(
    text: str = Form(...),
    language: str = Form(settings.DEFAULT_LANGUAGE),
    files: List[UploadFile] = File(...),
    temperature: float = Form(settings.DEFAULT_TEMPERATURE),
    speed: float = Form(settings.DEFAULT_SPEED),
    top_k: int = Form(settings.DEFAULT_TOP_K),
    top_p: float = Form(settings.DEFAULT_TOP_P),
    repetition_penalty: float = Form(settings.DEFAULT_REPETITION_PENALTY),
    stream: bool = Form(False),
    output_format: str = Form(settings.DEFAULT_OUTPUT_FORMAT)
):
    start_time = time.perf_counter()
    saved_files = []
    try:
        for file in files:
            file_ext = os.path.splitext(file.filename)[1] or ".wav"
            file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{file_ext}")
            def save_upload(src_file, dst_path):
                with open(dst_path, "wb") as buffer:
                    shutil.copyfileobj(src_file, buffer)
            await asyncio.to_thread(save_upload, file.file, file_path)
            saved_files.append(file_path)
            
        params = {
            "text": text, "language": language, "temperature": temperature,
            "speed": speed, "top_k": top_k, "top_p": top_p,
            "repetition_penalty": repetition_penalty, "output_format": output_format, 
            "speaker_idx": None, "sample_rate": 24000
        }
        
        # Clone işleminde stream logic'i basitleştirildi
        audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params, speaker_wavs=saved_files)
        await cleanup_files(saved_files)
        
        process_time = time.perf_counter() - start_time
        
        # Kayıt ve Yanıt
        filename = f"clone_{uuid.uuid4()}.wav"
        filepath = os.path.join(HISTORY_DIR, filename)
        await asyncio.to_thread(lambda: open(filepath, "wb").write(audio_bytes))
        history_manager.add_entry(filename, text, "Cloned Voice", "Cloning")

        final_response = Response(content=audio_bytes, media_type="audio/wav")
        return final_response
            
    except Exception as e:
        await cleanup_files(saved_files)
        logger.error(f"Clone Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ... (OpenAI Endpoints - Aynı, özet geçildi)
@router.post("/v1/audio/speech")
async def openai_speech_endpoint(request: OpenAISpeechRequest):
    # Basit implementasyon
    try:
        params = { "text": request.input, "language": "en", "speaker_idx": settings.DEFAULT_SPEAKER }
        audio = await asyncio.to_thread(tts_engine.synthesize, params)
        return Response(content=audio, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))