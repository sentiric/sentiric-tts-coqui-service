from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import StreamingResponse, FileResponse
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

# XTTS v2'nin desteklediği diller
SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"]

# --- YARDIMCI FONKSİYONLAR ---
async def cleanup_files(file_paths: List[str]):
    """Geçici dosyaları asenkron olarak siler"""
    for path in file_paths:
        try:
            if os.path.exists(path):
                await asyncio.to_thread(os.remove, path)
                logger.info(f"Cleaned up: {path}")
        except Exception as e:
            logger.warning(f"Cleanup failed for {path}: {e}")

# --- STANDART ENDPOINTLER ---

@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")
    
@router.get("/health")
async def health_check():
    return {"status": "ok", "device": settings.DEVICE, "model_loaded": tts_engine.model is not None}

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
        # ... (Temizlik kodları aynı) ...
        async def remove_safe(path):
            try:
                await asyncio.to_thread(os.remove, path)
                return 1
            except:
                return 0
        tasks = []
        for f in glob.glob(os.path.join(HISTORY_DIR, "*")):
            if os.path.basename(f) != "history.db": tasks.append(remove_safe(f))
        for f in glob.glob(os.path.join(CACHE_DIR, "*.bin")): tasks.append(remove_safe(f))
        for f in glob.glob(os.path.join(CACHE_DIR, "latents", "*.json")): tasks.append(remove_safe(f))
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

@router.get("/api/speakers")
async def get_speakers():
    speakers = tts_engine.get_speakers()
    return {"speakers": speakers, "count": len(speakers)}

@router.post("/api/speakers/refresh")
async def refresh_speakers_cache():
    report = await asyncio.to_thread(tts_engine.refresh_speakers)
    return {"status": "ok", "data": report}

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
            audio_duration_sec = len(audio_bytes) / 48000 # 24k * 2 bytes
            rtf = process_time / audio_duration_sec if audio_duration_sec > 0 else 0

            logger.info("usage.recorded", extra={
                "event_type": "usage.recorded", "resource_type": "tts_character",
                "amount": char_count, "model": settings.MODEL_NAME,
                "duration_ms": round(process_time * 1000, 2), "rtf": round(rtf, 4), "mode": "standard"
            })

            ext = "wav"
            if request.output_format == "mp3": ext = "mp3"
            elif request.output_format == "opus": ext = "opus"
            
            filename = f"tts_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            await asyncio.to_thread(lambda: open(filepath, "wb").write(audio_bytes))
            
            history_manager.add_entry(filename, request.text, request.speaker_idx, "Standard")
            
            media_type = "audio/wav"
            if ext == "mp3": media_type = "audio/mpeg"
            elif ext == "opus": media_type = "audio/ogg"
            
            final_response = Response(content=audio_bytes, media_type=media_type)
            final_response.headers["X-VCA-Chars"] = str(char_count)
            final_response.headers["X-VCA-Time"] =f"{process_time:.3f}"
            final_response.headers["X-VCA-RTF"] = f"{rtf:.4f}"
            return final_response
            
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/tts/clone")
async def generate_speech_clone(
    text: str = Form(...),
    language: str = Form("en"),
    files: List[UploadFile] = File(...),
    temperature: float = Form(0.75),
    speed: float = Form(1.0),
    top_k: int = Form(50),
    top_p: float = Form(0.85),
    repetition_penalty: float = Form(2.0),
    stream: bool = Form(False),
    output_format: str = Form("wav")
):
    # ... (Clone fonksiyonu içeriği aynı kalacak, sadece sonu Response header eklemesi) ...
    # Kısalık için burayı tekrarlamıyorum, önceki kodunuzdaki clone mantığı geçerlidir.
    # Tek fark return kısmında X-VCA headerlarını eklemektir.
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
            "repetition_penalty": repetition_penalty, "output_format": output_format, "speaker_idx": None
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
            
            ext = output_format if output_format != "opus" else "opus"
            filename = f"clone_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            await asyncio.to_thread(lambda: open(filepath, "wb").write(audio_bytes))
            
            history_manager.add_entry(filename, text, "Cloned Voice", "Cloning")
            
            media_type = "audio/wav"
            if ext == "mp3": media_type = "audio/mpeg"
            
            final_response = Response(content=audio_bytes, media_type=media_type)
            final_response.headers["X-VCA-Chars"] = str(char_count)
            final_response.headers["X-VCA-Time"] = f"{process_time:.3f}"
            final_response.headers["X-VCA-RTF"] = f"{rtf:.4f}"
            return final_response
            
    except Exception as e:
        await cleanup_files(saved_files)
        logger.error(f"Clone Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- OPENAI UYUMLU AKILLI ENDPOINTLER ---

@router.post("/v1/audio/speech")
async def openai_speech_endpoint(request: OpenAISpeechRequest):
    if not request.input or not request.input.strip():
        raise HTTPException(status_code=422, detail="Input text cannot be empty.")

    # 1. MEVCUT HOPARLÖRLERİ AL (Dinamik)
    # Bu liste /app/speakers klasöründeki dosyaları anlık olarak tarar.
    # Yani yeni bir dosya atıldığında restart gerekmeden burada görünür.
    available_speakers = tts_engine.get_speakers()
    
    requested_voice = request.voice
    target_speaker = ""

    # MANTIK 1: Eğer kullanıcı Open WebUI'da direkt dosya adını yazdıysa (örn: "M_Deep_Damien")
    # ve bu isim bizde varsa, direkt onu kullan.
    if requested_voice in available_speakers:
        target_speaker = requested_voice
        logger.info(f"OpenAI TTS: Direct match found for '{requested_voice}'")
    
    # MANTIK 2: Eğer isim bizde yoksa (örn: "alloy"), haritalamaya bak.
    else:
        voice_map = {
            "alloy": "F_Narrator_Linda",
            "echo": "M_News_Bill",
            # "echo": "M_default",         # My Voice  
            "shimmer": "F_Calm_Ana",
            "onyx": "M_Deep_Damien",
            "nova": "F_Assistant_Judy",
            "fable": "M_Story_Telling",
            
        }
        
        # Haritada varsa onu al, yoksa listedeki İLK sesi al (Default Fallback)
        mapped = voice_map.get(requested_voice)
        
        if mapped and mapped in available_speakers:
            target_speaker = mapped
            logger.info(f"OpenAI TTS: Mapped '{requested_voice}' -> '{target_speaker}'")
        else:
            # Fallback: Haritada yoksa veya haritadaki dosya silinmişse
            target_speaker = available_speakers[0] if available_speakers else "default"
            logger.warning(f"OpenAI TTS: Voice '{requested_voice}' not found. Using fallback '{target_speaker}'")

    # 2. FORMAT DÜZELTME
    output_fmt = request.response_format
    if output_fmt == "aac": output_fmt = "mp3"
    if output_fmt == "flac": output_fmt = "wav"

    # 3. OTOMATİK DİL ALGILAMA (LangID)
    try:
        detected_lang, _ = langid.classify(request.input)
        if detected_lang == "zh": detected_lang = "zh-cn"
        if detected_lang not in SUPPORTED_LANGUAGES:
            detected_lang = "en" # Desteklenmiyorsa İngilizce varsay
    except:
        detected_lang = "tr" # Hata olursa Türkçe varsay

    params = {
        "text": request.input,
        "language": detected_lang,
        "speaker_idx": target_speaker,
        "temperature": 0.75,
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
    Böylece 'Model' dropdown'ında 'tts-1' yerine 'M_News_Bill' seçilebilir hale gelir.
    """
    speakers = tts_engine.get_speakers()
    
    # Standart OpenAI modelleri
    models_data = [
        {"id": "tts-1", "object": "model", "created": 1234567890, "owned_by": "sentiric-tts"},
        {"id": "tts-1-hd", "object": "model", "created": 1234567890, "owned_by": "sentiric-tts"}
    ]
    
    # Bizim hoparlörleri de model gibi ekle
    # (Bazı UI'lar sesleri model listesinden seçtirir)
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