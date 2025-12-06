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
    Hem saf konuşmacı adlarını hem de stil varyasyonlarını (Speaker/Style) döndürür.
    """
    speakers_map = tts_engine.get_speakers()
    voices_list = []
    
    # 1. Standart OpenAI seslerini taklit et (Uyumluluk için)
    openai_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    for v in openai_voices:
        voices_list.append({
            "id": v,
            "name": f"OpenAI {v.capitalize()}",
            "object": "voice", 
            "created": 1677610602,
            "owned_by": "openai"
        })

    # 2. Sentiric Yerel Sesleri
    if isinstance(speakers_map, dict):
        for spk_name, styles in speakers_map.items():
            # A. Saf İsim (Default stil)
            voices_list.append({
                "id": spk_name,
                "name": spk_name,
                "object": "voice",
                "created": 1677610602,
                "owned_by": "sentiric-local"
            })
            
            # B. Stil Varyasyonları (Örn: Ece/happy)
            if isinstance(styles, list):
                for style in styles:
                    if style != "default" and style != "neutral":
                        variant_id = f"{spk_name}/{style}"
                        voices_list.append({
                            "id": variant_id,
                            "name": variant_id,
                            "object": "voice",
                            "created": 1677610602,
                            "owned_by": "sentiric-style"
                        })
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
            "language": settings.DEFAULT_LANGUAGE, "speaker": settings.DEFAULT_SPEAKER
        },
        "limits": {
            "max_text_len": 5000, "supported_formats": ["wav", "mp3", "opus", "pcm"],
            "sample_rates": [24000, 16000, 8000], "supported_languages": langs
        },
        "system": {"streaming_enabled": settings.ENABLE_STREAMING, "device": settings.DEVICE}
    }

# --- OPENAI COMPATIBLE ENDPOINTS (CRITICAL FIX FOR OPEN WEBUI) ---

@router.get("/v1/models")
async def list_models():
    """
    Standart OpenAI Models Endpoint.
    Open WebUI bu endpoint'i çağırarak dropdown listesini doldurur.
    """
    voices = await _get_voices_list()
    # OpenAI 'data' anahtarı içinde 'model' objeleri bekler
    models_data = []
    for v in voices:
        v_copy = v.copy()
        v_copy["object"] = "model" # Tipi değiştir, bazı clientlar 'model' bekler
        models_data.append(v_copy)
    return {"object": "list", "data": models_data}

@router.get("/v1/audio/voices")
async def list_voices_custom():
    """
    Open WebUI Custom Endpoint.
    Bazı versiyonlar /v1/audio/voices endpoint'ini ve { "voices": [...] } formatını bekler.
    """
    voices = await _get_voices_list()
    return {"voices": voices}

@router.post("/v1/audio/speech")
async def openai_speech_endpoint(request: OpenAISpeechRequest):
    """
    OpenAI TTS Endpoint (Open WebUI için Optimize Edildi).
    Özellikler:
    1. Streaming KAPALI (Tam dosya döner, tarayıcı hatasını önler).
    2. MP3 ZORUNLU (Tarayıcı uyumluluğu için).
    3. Otomatik Dil Tespiti.
    4. Speaker/Style Mapping.
    """
    if not request.input or not request.input.strip(): 
        raise HTTPException(status_code=422, detail="Input text cannot be empty.")
    
    # 1. Dil Tespiti (Language Detection)
    # Open WebUI dil göndermezse metinden anla
    detected_lang = settings.DEFAULT_LANGUAGE
    try:
        lang_code, confidence = langid.classify(request.input)
        if lang_code in SUPPORTED_LANGUAGES:
            detected_lang = lang_code
            logger.info(f"Detected Lang: {detected_lang} (Conf: {confidence})")
    except: pass

    # 2. Speaker Mapping (OpenAI -> Sentiric)
    openai_map = {
        "alloy": "F_TR_Kurumsal_Ece",
        "echo": "M_TR_Heyecanli_Can",
        "fable": "M_TR_Enerjik_Mert",
        "onyx": "M_TR_Tok_Kadir",
        "nova": "F_TR_Parlak_Zeynep",
        "shimmer": "F_TR_Genc_Selin"
    }
    
    final_speaker = request.voice
    if request.voice.lower() in openai_map:
        final_speaker = openai_map[request.voice.lower()]
    
    # Fallback: Eğer speaker sistemde yoksa var olan ilk speaker'ı al
    available_speakers = tts_engine.get_speakers()
    # Speaker adını '/' ile ayırıp ana isme bak (stil varsa)
    base_speaker = final_speaker.split('/')[0]
    if base_speaker not in available_speakers:
        if available_speakers:
            fallback = list(available_speakers.keys())[0]
            logger.warning(f"Speaker '{final_speaker}' not found. Falling back to '{fallback}'")
            final_speaker = fallback
        else:
             final_speaker = "system_default" # Engine fallback'i

    # 3. Format Zorlaması (MP3 & No-Stream)
    # Tarayıcılar en iyi MP3 sever. WebUI bazen formatı boş gönderir.
    output_fmt = "mp3"
    
    logger.info(f"OpenAI TTS: '{request.input[:15]}...' -> {final_speaker} ({detected_lang}) -> {output_fmt} (Buffered)")

    # İç İsteği Oluştur
    internal_req = TTSRequest(
        text=request.input,
        language=detected_lang,
        speaker_idx=final_speaker,
        stream=False, # <--- KRİTİK: Streaming'i kapatıyoruz. Tam dosya oluşturulacak.
        speed=request.speed if request.speed else settings.DEFAULT_SPEED,
        output_format=output_fmt
    )
    
    # Sesi Üret (Buffer'da)
    start_time = time.perf_counter()
    try:
        # Engine parametrelerini hazırla
        params = internal_req.model_dump()
        
        # Sentezle (Bloklayıcı işlem ama güvenli thread)
        audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
        
        process_time = time.perf_counter() - start_time
        logger.info(f"TTS Generated in {process_time:.2f}s | Size: {len(audio_bytes)} bytes")

        # MP3 Header'ları ile tam yanıt
        return Response(
            content=audio_bytes, 
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=speech.mp3",
                "X-VCA-Time": f"{process_time:.3f}"
            }
        )
        
    except Exception as e:
        logger.error(f"TTS Generation Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- INTERNAL API ENDPOINTS (STUDIO & MICROSERVICES) ---

@router.get("/api/speakers")
async def get_speakers():
    speakers_map = tts_engine.get_speakers()
    return {"speakers": speakers_map, "count": len(speakers_map)}

@router.post("/api/speakers/refresh")
async def refresh_speakers_cache():
    report = await asyncio.to_thread(tts_engine.refresh_speakers, force=True)
    return {"status": "ok", "data": report}

@router.get("/api/history")
async def get_history(): 
    return history_manager.get_all()

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

@router.post("/api/tts")
async def generate_speech(request: TTSRequest):
    """
    Standart Sentiric API (Streaming destekler).
    Internal servisler ve Studio burayı kullanır.
    """
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")
    
    start_time = time.perf_counter()
    params = request.model_dump()
    
    # Format belirle
    ext = "wav"
    media_type = "audio/wav"
    if request.output_format == "mp3": ext="mp3"; media_type="audio/mpeg"
    elif request.output_format == "opus": ext="opus"; media_type="audio/ogg"
    elif request.output_format == "pcm": ext="pcm"; media_type="application/octet-stream"

    safe_filename = generate_deterministic_filename(params, ext)
    filepath = os.path.join(HISTORY_DIR, safe_filename)

    # 1. CACHE CHECK
    if os.path.exists(filepath):
        if os.path.getsize(filepath) < 44: # Bozuk dosya kontrolü
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

    # 2. GENERATION
    try:
        if request.stream:
            # Streaming Logic (Gateway'ler için önemli)
            async def stream_and_save():
                accumulated_bytes = bytearray()
                try:
                    for chunk in tts_engine.synthesize_stream(params):
                        accumulated_bytes.extend(chunk)
                        yield chunk
                finally:
                    # Stream bitince diske WAV olarak kaydet
                    if accumulated_bytes:
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
            # Non-Streaming Logic
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
        # Dosyaları kaydet
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