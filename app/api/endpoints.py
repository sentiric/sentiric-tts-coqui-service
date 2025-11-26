from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import StreamingResponse, FileResponse
import asyncio
import os
import shutil
import glob
import uuid
import logging

from app.core.engine import tts_engine
from app.core.config import settings
from app.api.schemas import TTSRequest
from app.core.history import history_manager

logger = logging.getLogger("API")
router = APIRouter()

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"
CACHE_DIR = "/app/cache"

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
    if os.path.exists(file_path): return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Audio not found")

@router.delete("/api/history/all")
async def delete_all_history():
    try:
        history_manager.clear_all()
        files_deleted = 0
        for f in glob.glob(os.path.join(HISTORY_DIR, "*")):
            if os.path.basename(f) != "history.db":
                try: os.remove(f); files_deleted += 1; except: pass
        for f in glob.glob(os.path.join(CACHE_DIR, "*.bin")):
            try: os.remove(f); except: pass
        for f in glob.glob(os.path.join(CACHE_DIR, "latents", "*.json")):
            try: os.remove(f); except: pass
        return {"status": "cleared", "files_deleted": files_deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/history/{filename}")
async def delete_history_entry(filename: str):
    try:
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(HISTORY_DIR, safe_filename)
        if os.path.exists(file_path): os.remove(file_path)
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
    try:
        params = request.model_dump()
        if request.stream:
            return StreamingResponse(tts_engine.synthesize_stream(params), media_type="application/octet-stream")
        else:
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
            ext = "wav"
            if request.output_format == "mp3": ext = "mp3"
            elif request.output_format == "opus": ext = "opus"
            
            filename = f"tts_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            with open(filepath, "wb") as f: f.write(audio_bytes)
            
            history_manager.add_entry(filename, request.text, request.speaker_idx, "Standard")
            
            media_type = "audio/wav"
            if ext == "mp3": media_type = "audio/mpeg"
            elif ext == "opus": media_type = "audio/ogg"
            return Response(content=audio_bytes, media_type=media_type)
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
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")
        
    saved_files = []
    try:
        for file in files:
            file_ext = os.path.splitext(file.filename)[1] or ".wav"
            file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{file_ext}")
            with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
            saved_files.append(file_path)
            
        params = {
            "text": text, "language": language, "temperature": temperature,
            "speed": speed, "top_k": top_k, "top_p": top_p,
            "repetition_penalty": repetition_penalty, "output_format": output_format, "speaker_idx": None
        }
        
        if stream:
            return StreamingResponse(tts_engine.synthesize_stream(params, speaker_wavs=saved_files), media_type="application/octet-stream")
        else:
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params, speaker_wavs=saved_files)
            ext = output_format if output_format != "opus" else "opus"
            filename = f"clone_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            with open(filepath, "wb") as f: f.write(audio_bytes)
            history_manager.add_entry(filename, text, "Cloned Voice", "Cloning")
            
            media_type = "audio/wav"
            if ext == "mp3": media_type = "audio/mpeg"
            return Response(content=audio_bytes, media_type=media_type)
            
    except Exception as e:
        logger.error(f"Clone Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for f in saved_files:
            if os.path.exists(f): os.unlink(f)