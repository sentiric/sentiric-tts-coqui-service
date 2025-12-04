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
import torch  # <--- EKLENDİ: VRAM kontrolü için gerekli

from app.core.engine import tts_engine
from app.core.config import settings
from app.api.schemas import TTSRequest, OpenAISpeechRequest
from app.core.history import history_manager

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

# --- HELPERS ---
async def cleanup_files(file_paths: List[str]):
    for path in file_paths:
        try:
            if os.path.exists(path):
                await asyncio.to_thread(os.remove, path)
        except Exception as e:
            logger.warning(f"Failed to cleanup {path}: {e}")

def calculate_vca_metrics(start_time, char_count, audio_bytes, sample_rate=24000):
    process_time = time.perf_counter() - start_time
    # Audio bytes yoksa (streaming) 0 kabul et
    len_bytes = len(audio_bytes) if audio_bytes else 0
    audio_duration_sec = len_bytes / (sample_rate * 2) 
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
    return {
        "status": "ok", 
        "device": settings.DEVICE, 
        "model_loaded": tts_engine.model is not None,
        "version": settings.APP_VERSION,
        "mode": "standalone" if settings.API_KEY else "cluster",
        # Memory Manager Stats
        "vram_allocated_mb": int(torch.cuda.memory_allocated() / (1024*1024)) if torch.cuda.is_available() else 0
    }

@router.get("/api/config")
async def get_public_config():
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

# --- SPEAKER MANAGEMENT ---

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
    try:
        params = request.model_dump()
        
        if request.stream:
            # Doğrudan Engine generator'ını kullan
            return StreamingResponse(
                tts_engine.synthesize_stream(params), 
                media_type="application/octet-stream",
                headers={"X-Stream-Start": str(start_time)}
            )
        else:
            # CPU Blocking işlemi thread'e taşıyoruz (Non-blocking server)
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
            
            # Telemetri
            metrics = calculate_vca_metrics(start_time, len(request.text), audio_bytes, request.sample_rate)
            
            logger.info("usage.recorded", extra={
                "event_type": "tts_generation",
                "char_count": len(request.text),
                "duration_ms": metrics["X-VCA-Time"],
                "rtf": metrics["X-VCA-RTF"],
                "mode": "standard"
            })

            ext = "wav"
            media_type = "audio/wav"
            if request.output_format == "mp3": ext="mp3"; media_type="audio/mpeg"
            elif request.output_format == "opus": ext="opus"; media_type="audio/ogg"
            elif request.output_format == "pcm": ext="pcm"; media_type="application/octet-stream"
            
            filename = f"tts_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            
            # Disk I/O Blocking önle
            await asyncio.to_thread(lambda: open(filepath, "wb").write(audio_bytes))
            
            history_manager.add_entry(filename, request.text, request.speaker_idx, "Standard")
            
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
            "speaker_idx": None, 
            "sample_rate": 24000
        }
        
        if stream:
            async def stream_with_cleanup():
                try:
                    for chunk in tts_engine.synthesize_stream(params, speaker_wavs=saved_files):
                        yield chunk
                finally:
                    await cleanup_files(saved_files)
            
            return StreamingResponse(
                stream_with_cleanup(), 
                media_type="application/octet-stream",
                headers={"X-Stream-Start": str(start_time)}
            )
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
            for k, v in metrics.items():
                final_response.headers[k] = v
            return final_response
            
    except Exception as e:
        await cleanup_files(saved_files)
        logger.error(f"Clone Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- OPENAI API COMPATIBILITY ---

@router.post("/v1/audio/speech")
async def openai_speech_endpoint(request: OpenAISpeechRequest):
    """
    OpenAI uyumlu endpoint. (Streaming destekler)
    """
    if not request.input or not request.input.strip():
        raise HTTPException(status_code=422, detail="Input text cannot be empty.")

    start_time = time.perf_counter()

    # Speaker Mapping
    available_speakers = tts_engine.get_speakers()
    flat_speakers = {}
    for name, styles in available_speakers.items():
        flat_speakers[name.lower()] = name
        for s in styles:
            flat_speakers[f"{name}/{s}".lower()] = f"{name}/{s}"
    
    requested_voice = request.voice.lower()
    target_speaker = settings.DEFAULT_SPEAKER

    if requested_voice in flat_speakers:
        target_speaker = flat_speakers[requested_voice]
    else:
        voice_map = {
            "alloy": "F_Narrator_Linda", "echo": "M_News_Bill",
            "shimmer": "F_Calm_Ana", "onyx": "M_Deep_Damien",
            "nova": "F_Assistant_Judy", "fable": "M_Story_Telling",
        }
        mapped_key = voice_map.get(requested_voice)
        if mapped_key and mapped_key.lower() in flat_speakers:
            target_speaker = flat_speakers[mapped_key.lower()]

    output_fmt = request.response_format
    if output_fmt == "aac": output_fmt = "mp3"
    if output_fmt == "flac": output_fmt = "wav"

    detected_lang = settings.DEFAULT_LANGUAGE
    try:
        detected_lang, _ = langid.classify(request.input)
        if detected_lang == "zh": detected_lang = "zh-cn"
        if detected_lang not in SUPPORTED_LANGUAGES:
            detected_lang = settings.DEFAULT_LANGUAGE 
    except: pass

    params = {
        "text": request.input,
        "language": detected_lang,
        "speaker_idx": target_speaker,
        "temperature": settings.DEFAULT_TEMPERATURE,
        "speed": request.speed,
        "output_format": output_fmt,
        "stream": False # Varsayılan false, aşağıda karar verilecek
    }

    try:
        # OpenAI Streaming Check (Standard dışı olsa da bazı clientlar stream=true gönderir)
        # Ancak OpenAI Speech API'sinde resmi olarak 'stream' parametresi yoktur, yanıtı stream olarak beklerler.
        # Sentiric implementasyonunda: varsayılan olarak non-stream, ancak client stream isterse destekleriz.
        # Not: OpenAI istemcileri genellikle normal bir POST atar ve chunked response bekler.
        
        # Bu endpoint'i daima streaming olarak çalıştırmak latency için iyidir, ancak 
        # format dönüşümü (MP3) streaming sırasında zordur (ffmpeg pipe gerekir).
        # Şimdilik: Eğer format PCM ise stream yap, yoksa full process.
        
        # [CRITICAL DECISION] OpenAI clientları genellikle MP3 ister. MP3 streaming için FFmpeg pipe 
        # karmaşıklığına girmek riskli. Şimdilik "Hızlı Tepki" için PCM/WAV ise stream, MP3 ise blok.
        
        should_stream = output_fmt in ["pcm", "wav"]
        
        if should_stream:
            params["stream"] = True
            params["output_format"] = "pcm" # Stream daima PCM basar
            return StreamingResponse(
                tts_engine.synthesize_stream(params),
                media_type="audio/pcm"
            )
        else:
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
            media_type = "audio/mpeg" if output_fmt == "mp3" else "audio/wav"
            return Response(content=audio_bytes, media_type=media_type)

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
    return {"object": "list", "data": models_data}