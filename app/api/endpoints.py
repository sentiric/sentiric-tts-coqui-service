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
import langid  # Dil algılama

from app.core.engine import tts_engine
from app.core.config import settings
from app.api.schemas import TTSRequest, OpenAISpeechRequest
from app.core.history import history_manager

logger = logging.getLogger("API")
router = APIRouter()

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"
CACHE_DIR = "/app/cache"

# XTTS v2'nin desteklediği diller (Referans için)
SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"]

# --- YARDIMCI FONKSİYONLAR ---
async def cleanup_files(file_paths: List[str]):
    """Geçici dosyaları asenkron olarak siler"""
    for path in file_paths:
        try:
            if os.path.exists(path):
                await asyncio.to_thread(os.remove, path)
                logger.debug(f"Cleaned up: {path}")
        except Exception as e:
            logger.warning(f"Cleanup failed for {path}: {e}")

# --- SYSTEM & CONFIG ENDPOINTS ---

@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")
    
@router.get("/health")
async def health_check():
    """K8s ve Docker healthcheck için durum raporu"""
    return {
        "status": "ok", 
        "device": settings.DEVICE, 
        "model_loaded": tts_engine.model is not None,
        "version": settings.APP_VERSION
    }

@router.get("/api/config")
async def get_public_config():
    """
    UI'ın (Frontend) başlangıç değerlerini ve limitlerini ayarlaması için
    backend konfigürasyonunu döner.
    """
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
            "sample_rates": [24000, 16000, 8000]
        },
        "system": {
            "streaming_enabled": settings.ENABLE_STREAMING,
            "device": settings.DEVICE
        }
    }

# --- HISTORY ENDPOINTS ---

@router.get("/api/history")
async def get_history():
    return history_manager.get_all()

@router.get("/api/history/audio/{filename}")
async def get_history_audio(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(HISTORY_DIR, safe_filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Audio not found")

@router.delete("/api/history/all")
async def delete_all_history():
    try:
        history_manager.clear_all()
        async def remove_safe(path):
            try:
                await asyncio.to_thread(os.remove, path)
                return 1
            except:
                return 0
        tasks = []
        for f in glob.glob(os.path.join(HISTORY_DIR, "*")):
            if os.path.basename(f) != "history.db": tasks.append(remove_safe(f))
        # Cache temizliği opsiyonel, şimdilik history odaklı
        results = await asyncio.gather(*tasks)
        return {"status": "cleared", "files_deleted": sum(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/history/{filename}")
async def delete_history_entry(filename: str):
    try:
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(HISTORY_DIR, safe_filename)
        if os.path.exists(file_path):
            await asyncio.to_thread(os.remove, file_path)
        history_manager.delete_entry(safe_filename)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- SPEAKER MANAGEMENT ---

@router.get("/api/speakers")
async def get_speakers():
    speakers = tts_engine.get_speakers()
    return {"speakers": speakers, "count": len(speakers)}

@router.post("/api/speakers/refresh")
async def refresh_speakers_cache():
    # Force parametresi ile cache'i bypass et ve diski tara
    report = await asyncio.to_thread(tts_engine.refresh_speakers, force=True)
    return {"status": "ok", "data": report}

# --- MAIN TTS ENDPOINT ---

@router.post("/api/tts")
async def generate_speech(request: TTSRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")
    
    start_time = time.perf_counter()
    try:
        # Pydantic modeli zaten config defaultlarını içeriyor
        params = request.model_dump()
        
        if request.stream:
            return StreamingResponse(
                tts_engine.synthesize_stream(params), 
                media_type="application/octet-stream"
            )
        else:
            # Bloklayıcı işlemi thread pool'da çalıştır
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
            
            # Metrik hesaplama
            process_time = time.perf_counter() - start_time
            char_count = len(request.text)
            # 16-bit PCM = 2 bytes per sample
            audio_duration_sec = len(audio_bytes) / (request.sample_rate * 2) 
            rtf = process_time / audio_duration_sec if audio_duration_sec > 0 else 0

            logger.info("usage.recorded", extra={
                "event_type": "usage.recorded", "resource_type": "tts_character",
                "amount": char_count, "model": settings.MODEL_NAME,
                "duration_ms": round(process_time * 1000, 2), "rtf": round(rtf, 4), "mode": "standard"
            })

            # Dosya uzantısı ve MIME type belirleme
            ext = "wav"
            media_type = "audio/wav"
            
            if request.output_format == "mp3": 
                ext = "mp3"
                media_type = "audio/mpeg"
            elif request.output_format == "opus": 
                ext = "opus"
                media_type = "audio/ogg"
            elif request.output_format == "pcm":
                ext = "pcm"
                media_type = "application/octet-stream"
            
            # History'e kaydet
            filename = f"tts_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            await asyncio.to_thread(lambda: open(filepath, "wb").write(audio_bytes))
            
            history_manager.add_entry(filename, request.text, request.speaker_idx, "Standard")
            
            # Response headerları (VCA için kritik)
            final_response = Response(content=audio_bytes, media_type=media_type)
            final_response.headers["X-VCA-Chars"] = str(char_count)
            final_response.headers["X-VCA-Time"] =f"{process_time:.3f}"
            final_response.headers["X-VCA-RTF"] = f"{rtf:.4f}"
            return final_response
            
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- VOICE CLONING ENDPOINT ---

@router.post("/api/tts/clone")
async def generate_speech_clone(
    text: str = Form(...),
    language: str = Form(settings.DEFAULT_LANGUAGE),
    files: List[UploadFile] = File(...),
    # Config'den gelen varsayılan değerler
    temperature: float = Form(settings.DEFAULT_TEMPERATURE),
    speed: float = Form(settings.DEFAULT_SPEED),
    top_k: int = Form(settings.DEFAULT_TOP_K),
    top_p: float = Form(settings.DEFAULT_TOP_P),
    repetition_penalty: float = Form(settings.DEFAULT_REPETITION_PENALTY),
    stream: bool = Form(False),
    output_format: str = Form(settings.DEFAULT_OUTPUT_FORMAT)
):
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")
    
    start_time = time.perf_counter()
    saved_files = []
    try:
        # Yüklenen dosyaları geçici olarak kaydet
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
            "speaker_idx": None, # Clone modunda speaker_idx kullanılmaz, wav dosyaları kullanılır
            "sample_rate": 24000 # Varsayılan
        }
        
        if stream:
            async def stream_with_cleanup():
                try:
                    for chunk in tts_engine.synthesize_stream(params, speaker_wavs=saved_files):
                        yield chunk
                finally:
                    await cleanup_files(saved_files)
            return StreamingResponse(stream_with_cleanup(), media_type="application/octet-stream")
        else:
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params, speaker_wavs=saved_files)
            await cleanup_files(saved_files)
            
            process_time = time.perf_counter() - start_time
            char_count = len(text)
            audio_duration_sec = len(audio_bytes) / 48000
            rtf = process_time / audio_duration_sec if audio_duration_sec > 0 else 0

            logger.info("usage.recorded", extra={
                "event_type": "usage.recorded", "resource_type": "tts_character",
                "amount": char_count, "model": settings.MODEL_NAME,
                "duration_ms": round(process_time * 1000, 2), "rtf": round(rtf, 4), "mode": "clone"
            })
            
            # Format ve History
            ext = output_format if output_format != "pcm" else "wav"
            if ext == "opus": ext = "ogg"
            
            filename = f"clone_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            await asyncio.to_thread(lambda: open(filepath, "wb").write(audio_bytes))
            
            history_manager.add_entry(filename, text, "Cloned Voice", "Cloning")
            
            media_type = "audio/wav"
            if output_format == "mp3": media_type = "audio/mpeg"
            
            final_response = Response(content=audio_bytes, media_type=media_type)
            final_response.headers["X-VCA-Chars"] = str(char_count)
            final_response.headers["X-VCA-Time"] = f"{process_time:.3f}"
            final_response.headers["X-VCA-RTF"] = f"{rtf:.4f}"
            return final_response
            
    except Exception as e:
        await cleanup_files(saved_files)
        logger.error(f"Clone Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- OPENAI COMPATIBLE ENDPOINTS (Open WebUI vb. için) ---

@router.post("/v1/audio/speech")
async def openai_speech_endpoint(request: OpenAISpeechRequest):
    if not request.input or not request.input.strip():
        raise HTTPException(status_code=422, detail="Input text cannot be empty.")

    # 1. MEVCUT HOPARLÖRLERİ AL (Cached)
    available_speakers = tts_engine.get_speakers()
    available_speakers_lower = {s.lower(): s for s in available_speakers}
    
    requested_voice = request.voice.lower()
    target_speaker = ""

    # Ses Eşleştirme Mantığı
    if requested_voice in available_speakers_lower:
        target_speaker = available_speakers_lower[requested_voice]
    else:
        # OpenAI ses isimlerini eşle
        voice_map = {
            "alloy": "F_Narrator_Linda",
            "echo": "M_News_Bill",
            "shimmer": "F_Calm_Ana",
            "onyx": "M_Deep_Damien",
            "nova": "F_Assistant_Judy",
            "fable": "M_Story_Telling",
        }
        mapped_key = voice_map.get(requested_voice)
        
        if mapped_key and mapped_key.lower() in available_speakers_lower:
            target_speaker = available_speakers_lower[mapped_key.lower()]
        else:
            # Fallback: Config'den gelen varsayılan ses
            target_speaker = settings.DEFAULT_SPEAKER
            if target_speaker not in available_speakers:
                 target_speaker = available_speakers[0] if available_speakers else "system_default"

    # Format Düzeltme
    output_fmt = request.response_format
    if output_fmt == "aac": output_fmt = "mp3"
    if output_fmt == "flac": output_fmt = "wav"

    # Dil Algılama (Fallback to Config Default)
    try:
        detected_lang, _ = langid.classify(request.input)
        if detected_lang == "zh": detected_lang = "zh-cn"
        if detected_lang not in SUPPORTED_LANGUAGES:
            detected_lang = settings.DEFAULT_LANGUAGE 
    except:
        detected_lang = settings.DEFAULT_LANGUAGE

    params = {
        "text": request.input,
        "language": detected_lang,
        "speaker_idx": target_speaker,
        "temperature": settings.DEFAULT_TEMPERATURE, # Varsayılan
        "speed": request.speed,
        "output_format": output_fmt,
        "stream": False 
    }

    try:
        audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
        
        media_type = "audio/mpeg" if output_fmt == "mp3" else \
                     "audio/ogg" if output_fmt == "opus" else \
                     "audio/wav"

        return Response(content=audio_bytes, media_type=media_type)

    except Exception as e:
        logger.error(f"OpenAI API Adapter Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/v1/models")
async def list_models():
    """
    Open WebUI'ın model listesi olarak tüm hoparlörleri görmesini sağlar.
    Cache mekanizması sayesinde disk IO yapmaz.
    """
    speakers = tts_engine.get_speakers()
    
    models_data = [
        {"id": "tts-1", "object": "model", "created": 1234567890, "owned_by": "sentiric-tts"},
        {"id": "tts-1-hd", "object": "model", "created": 1234567890, "owned_by": "sentiric-tts"}
    ]
    
    for spk in speakers:
        models_data.append({
            "id": spk,
            "object": "model",
            "created": 1234567890,
            "owned_by": "sentiric-local"
        })

    return {
        "object": "list",
        "data": models_data
    }