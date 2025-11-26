import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from typing import List
import os
import asyncio
import shutil
import glob
import uuid
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.engine import tts_engine
from app.core.config import settings
from app.api.schemas import TTSRequest
from app.core.history import history_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("XTTS-API")

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"
CACHE_DIR = "/app/cache"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Engine...")
    tts_engine.initialize()
    yield
    logger.info("Shutting down...")
    if os.path.exists(UPLOAD_DIR): shutil.rmtree(UPLOAD_DIR)

app = FastAPI(title="Sentiric XTTS Ultimate", lifespan=lifespan)

Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "device": settings.DEVICE, "model_loaded": tts_engine.model is not None}

@app.get("/api/history")
async def get_history(): return history_manager.get_all()

@app.get("/api/history/audio/{filename}")
async def get_history_audio(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(HISTORY_DIR, safe_filename)
    if os.path.exists(file_path): return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Audio not found")
    
@app.get("/api/speakers")
async def get_speakers():
    speakers = tts_engine.get_speakers()
    return {"speakers": speakers, "count": len(speakers)}
    
@app.post("/api/speakers/refresh")
async def refresh_speakers_cache():
    report = await asyncio.to_thread(tts_engine.refresh_speakers)
    return {"status": "ok", "message": "Refreshed", "data": report}

@app.delete("/api/history/all")
async def delete_all_history():
    """NUCLEAR OPTION: Her şeyi siler (History, Cache, Latents)"""
    try:
        history_manager.clear_all()
        files = glob.glob(os.path.join(HISTORY_DIR, "*"))
        deleted_count = 0
        for f in files:
            if os.path.basename(f) != "history.db":
                try: os.remove(f); deleted_count += 1
                except: pass
        cache_files = glob.glob(os.path.join(CACHE_DIR, "*.bin"))
        for f in cache_files:
            try: os.remove(f)
            except: pass
        latent_files = glob.glob(os.path.join(CACHE_DIR, "latents", "*.json"))
        for f in latent_files:
            try: os.remove(f)
            except: pass
        return {"status": "cleared", "files_deleted": deleted_count, "cache_cleared": True}
    except Exception as e:
        logger.error(f"Clear all error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/history/{filename}")
async def delete_history_entry(filename: str):
    try:
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(HISTORY_DIR, safe_filename)
        if os.path.exists(file_path): os.remove(file_path)
        history_manager.delete_entry(safe_filename)
        return {"status": "deleted", "filename": safe_filename}
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tts")
async def generate_speech(request: TTSRequest):
    # --- FIX: Boş Metin Kontrolü ---
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty or whitespace only.")

    try:
        params = request.model_dump()
        if request.stream:
            generator = tts_engine.synthesize_stream(params)
            return StreamingResponse(generator, media_type="application/octet-stream")
        else:
            audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
            ext = "wav"
            if request.output_format == "mp3": ext = "mp3"
            elif request.output_format == "opus": ext = "opus"
            elif request.output_format == "pcm": ext = "pcm"
            filename = f"tts_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(HISTORY_DIR, filename)
            with open(filepath, "wb") as f: f.write(audio_bytes)
            history_manager.add_entry(filename, request.text, request.speaker_idx, "Standard")
            media_type = "audio/wav"
            if ext == "mp3": media_type = "audio/mpeg"
            elif ext == "opus": media_type = "audio/ogg"
            elif ext == "pcm": media_type = "application/octet-stream"
            return Response(content=audio_bytes, media_type=media_type)
    except Exception as e:
        logger.error(f"TTS Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tts/clone")
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
    # --- FIX: Boş Metin Kontrolü ---
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty or whitespace only.")

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
            "repetition_penalty": repetition_penalty, "split_sentences": True,
            "output_format": output_format, "speaker_idx": None
        }
        if stream:
            generator = tts_engine.synthesize_stream(params, speaker_wavs=saved_files)
            return StreamingResponse(generator, media_type="application/octet-stream")
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
        logger.error(f"Clone Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for f in saved_files:
            if os.path.exists(f): os.unlink(f)

app.mount("/", StaticFiles(directory="static", html=True), name="static")