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

# --- CONFIGURATION & CONSTANTS ---
SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"]
LANGUAGE_NAMES = {
    "tr": "Turkish", "en": "English", "es": "Spanish", "fr": "French", 
    "de": "German", "it": "Italian", "pt": "Portuguese", "pl": "Polish",
    "ru": "Russian", "nl": "Dutch", "cs": "Czech", "ar": "Arabic",
    "zh-cn": "Chinese", "ja": "Japanese", "hu": "Hungarian", "ko": "Korean"
}

# --- HELPERS ---
async def cleanup_files(file_paths: List[str]):
    """Geçici dosyaları güvenli bir şekilde temizler."""
    for path in file_paths:
        try:
            if os.path.exists(path):
                await asyncio.to_thread(os.remove, path)
                logger.debug(f"Deleted temp file: {path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {path}: {e}")

def calculate_vca_metrics(start_time, char_count, audio_bytes, sample_rate=24000):
    """
    Telemetri başlıkları için metrikleri hesaplar.
    VCA: Voice Cloud Architecture standartları.
    """
    process_time = time.perf_counter() - start_time
    # 16-bit PCM = 2 bytes per sample
    audio_duration_sec = len(audio_bytes) / (sample_rate * 2) 
    rtf = process_time / audio_duration_sec if audio_duration_sec > 0 else 0
    
    return {
        "X-VCA-Chars": str(char_count),
        "X-VCA-Time": f"{process_time:.3f}",
        "X-VCA-RTF": f"{rtf:.4f}",
        "X-VCA-Model": settings.MODEL_NAME
    }

# --- SYSTEM ENDPOINTS ---

@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")
    
@router.get("/health")
async def health_check():
    """K8s/Docker Healthcheck"""
    return {
        "status": "ok", 
        "device": settings.DEVICE, 
        "model_loaded": tts_engine.model is not None,
        "version": settings.APP_VERSION,
        "mode": "standalone" if settings.API_KEY else "cluster"
    }

@router.get("/api/config")
async def get_public_config():
    """Frontend ve Gateway için yetenek haritası"""
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
            "sample_rates": [24000, 16000, 8000],
            "supported_languages": langs
        },
        "system": {
            "streaming_enabled": settings.ENABLE_STREAMING,
            "device": settings.DEVICE
        }
    }

# --- HISTORY MANAGEMENT ---

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
    history_manager.clear_all()
    deleted_count = 0
    for f in glob.glob(os.path.join(HISTORY_DIR, "*")):
        if "history.db" not in f: 
            try: 
                os.remove(f)
                deleted_count += 1
            except: pass
    return {"status": "cleared", "count": deleted_count}

@router.delete("/api/history/{filename}")
async def delete_history_entry(filename: str):
    history_manager.delete_entry(filename)
    try: 
        os.remove(os.path.join(HISTORY_DIR, filename))
    except: pass
    return {"status": "deleted"}

# --- SPEAKER MANAGEMENT ---

@router.get("/api/speakers")
async def get_speakers():
    speakers_map = tts_engine.get_speakers()
    return {"speakers": speakers_map, "count": len(speakers_map)}

@router.post("/api/speakers/refresh")
async def refresh_speakers_cache():
    # Force parametresi ile diskten taze okuma yap
    report = await asyncio.to_thread(tts_engine.refresh_speakers, force=True)
    return {"status": "ok", "data": report}

# --- CORE TTS ENDPOINTS ---

@router.post("/api/tts")
async def generate_speech(request: TTSRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")
    
    start_time = time.perf_counter()
    try:
        params = request.model_dump()
        
        if request.stream:
            # Streaming modunda RTF hesaplaması stream bitince client tarafında yapılır
            # veya loglara daha sonra yazılır. Header olarak hemen dönemeyiz.
            return StreamingResponse(
                tts_engine.synthesize_stream(params), 
                media_type="application/octet-stream",
                headers={"X-Stream-Start": str(start_time)}
            )
        else:
            # CPU Blocking işlemi thread'e taşıyoruz
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
            
            # Telemetri Hesapla
            metrics = calculate_vca_metrics(start_time, len(request.text), audio_bytes, request.sample_rate)
            
            # Loglama (Structured Log)
            logger.info("usage.recorded", extra={
                "event_type": "tts_generation",
                "char_count": len(request.text),
                "duration_ms": metrics["X-VCA-Time"],
                "rtf": metrics["X-VCA-RTF"],
                "mode": "standard"
            })

            # Format Belirleme
            ext = "wav"
            media_type = "audio/wav"
            if request.output_format == "mp3": ext="mp3"; media_type="audio/mpeg"
            elif request.output_format == "opus": ext="opus"; media_type="audio/ogg"
            elif request.output_format == "pcm": ext="pcm"; media_type="application/octet-stream"
            
            # History Kaydı
            filename = f"tts_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            await asyncio.to_thread(lambda: open(filepath, "wb").write(audio_bytes))
            
            history_manager.add_entry(filename, request.text, request.speaker_idx, "Standard")
            
            # Yanıt (Headerlar ile birlikte)
            final_response = Response(content=audio_bytes, media_type=media_type)
            for k, v in metrics.items():
                final_response.headers[k] = v
                
            return final_response
            
    except Exception as e:
        logger.error(f"TTS Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/tts/clone")
async def generate_speech_clone(
    text: str = Form(...),
    language: str = Form(settings.DEFAULT_LANGUAGE),
    files: List[UploadFile] = File(...),
    # Opsiyonel Parametreler
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
        # 1. Dosyaları Kaydet
        for file in files:
            file_ext = os.path.splitext(file.filename)[1] or ".wav"
            file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{file_ext}")
            
            # Blocking IO önlemek için thread içinde kaydet
            def save_upload(src_file, dst_path):
                with open(dst_path, "wb") as buffer:
                    shutil.copyfileobj(src_file, buffer)
            
            await asyncio.to_thread(save_upload, file.file, file_path)
            saved_files.append(file_path)
            
        params = {
            "text": text, "language": language, "temperature": temperature,
            "speed": speed, "top_k": top_k, "top_p": top_p,
            "repetition_penalty": repetition_penalty, "output_format": output_format, 
            "speaker_idx": None, # Clone modunda speaker_idx yok
            "sample_rate": 24000
        }
        
        # 2. Sentezleme
        if stream:
            async def stream_with_cleanup():
                try:
                    # Generator'dan yield et
                    for chunk in tts_engine.synthesize_stream(params, speaker_wavs=saved_files):
                        yield chunk
                finally:
                    # Stream bitince veya hata alınca temizle
                    await cleanup_files(saved_files)
            
            return StreamingResponse(
                stream_with_cleanup(), 
                media_type="application/octet-stream",
                headers={"X-Stream-Start": str(start_time)}
            )
        else:
            # Full sentez
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params, speaker_wavs=saved_files)
            
            # 3. Temizlik (Cleanup)
            await cleanup_files(saved_files)
            
            # 4. Telemetri (VCA Headers - Geri Getirildi)
            metrics = calculate_vca_metrics(start_time, len(text), audio_bytes)
            
            logger.info("usage.recorded", extra={
                "event_type": "tts_clone",
                "char_count": len(text),
                "rtf": metrics["X-VCA-RTF"],
                "mode": "clone"
            })
            
            # 5. Dosya Kaydetme (History)
            ext = output_format if output_format != "pcm" else "wav"
            if ext == "opus": ext = "ogg"
            filename = f"clone_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            await asyncio.to_thread(lambda: open(filepath, "wb").write(audio_bytes))
            history_manager.add_entry(filename, text, "Cloned Voice", "Cloning")
            
            # 6. Yanıt
            media_type = "audio/wav"
            if output_format == "mp3": media_type = "audio/mpeg"
            
            final_response = Response(content=audio_bytes, media_type=media_type)
            for k, v in metrics.items():
                final_response.headers[k] = v
                
            return final_response
            
    except Exception as e:
        # Hata durumunda da temizlik yapıldığından emin ol
        await cleanup_files(saved_files)
        logger.error(f"Clone Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- OPENAI API COMPATIBILITY ---

@router.post("/v1/audio/speech")
async def openai_speech_endpoint(request: OpenAISpeechRequest):
    """
    OpenAI uyumlu endpoint. Artık tam metrik döndürüyor.
    """
    if not request.input or not request.input.strip():
        raise HTTPException(status_code=422, detail="Input text cannot be empty.")

    start_time = time.perf_counter()

    # Speaker Mapping (Gelişmiş)
    available_speakers = tts_engine.get_speakers()
    flat_speakers = {}
    for name, styles in available_speakers.items():
        flat_speakers[name.lower()] = name
        for s in styles:
            flat_speakers[f"{name}/{s}".lower()] = f"{name}/{s}"
    
    requested_voice = request.voice.lower()
    target_speaker = settings.DEFAULT_SPEAKER

    # 1. Doğrudan eşleşme veya Mapping
    if requested_voice in flat_speakers:
        target_speaker = flat_speakers[requested_voice]
    else:
        # OpenAI Map
        voice_map = {
            "alloy": "F_Narrator_Linda",
            "echo": "M_News_Bill",
            "shimmer": "F_Calm_Ana",
            "onyx": "M_Deep_Damien",
            "nova": "F_Assistant_Judy",
            "fable": "M_Story_Telling",
        }
        mapped_key = voice_map.get(requested_voice)
        if mapped_key and mapped_key.lower() in flat_speakers:
            target_speaker = flat_speakers[mapped_key.lower()]

    # Format Map
    output_fmt = request.response_format
    if output_fmt == "aac": output_fmt = "mp3"
    if output_fmt == "flac": output_fmt = "wav"

    # Dil Algılama
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
        "temperature": settings.DEFAULT_TEMPERATURE,
        "speed": request.speed,
        "output_format": output_fmt,
        "stream": False 
    }

    try:
        audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
        
        # VCA Metrics for OpenAI Endpoint too (Observability için kritik)
        metrics = calculate_vca_metrics(start_time, len(request.input), audio_bytes)
        
        media_type = "audio/mpeg" if output_fmt == "mp3" else \
                     "audio/ogg" if output_fmt == "opus" else \
                     "audio/wav"

        final_response = Response(content=audio_bytes, media_type=media_type)
        for k, v in metrics.items():
            final_response.headers[k] = v
            
        return final_response

    except Exception as e:
        logger.error(f"OpenAI API Adapter Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/v1/models")
async def list_models():
    speakers = tts_engine.get_speakers()
    
    models_data = [
        {"id": "tts-1", "object": "model", "created": 1234567890, "owned_by": "sentiric-tts"},
        {"id": "tts-1-hd", "object": "model", "created": 1234567890, "owned_by": "sentiric-tts"}
    ]
    
    for spk_name in speakers.keys():
        models_data.append({
            "id": spk_name,
            "object": "model",
            "created": 1234567890,
            "owned_by": "sentiric-local"
        })

    return {
        "object": "list",
        "data": models_data
    }