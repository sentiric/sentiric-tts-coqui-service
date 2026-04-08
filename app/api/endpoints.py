import os
import shutil
import logging
import time
import json
import hashlib
import asyncio
import queue
import threading
import tempfile
from typing import List, Optional
from collections import OrderedDict

import langid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.responses import StreamingResponse

from app.core.engine import tts_engine
from app.core.config import settings
from app.api.schemas import TTSRequest, OpenAISpeechRequest

logger = logging.getLogger("API")
router = APIRouter()

SUPPORTED_LANGUAGES = [
    "en",
    "es",
    "fr",
    "de",
    "it",
    "pt",
    "pl",
    "tr",
    "ru",
    "nl",
    "cs",
    "ar",
    "zh-cn",
    "ja",
    "hu",
    "ko",
]
LANGUAGE_NAMES = {
    "tr": "Turkish",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "pl": "Polish",
    "ru": "Russian",
    "nl": "Dutch",
    "cs": "Czech",
    "ar": "Arabic",
    "zh-cn": "Chinese",
    "ja": "Japanese",
    "hu": "Hungarian",
    "ko": "Korean",
}


class MemoryLRUCache:
    def __init__(self, capacity: int = 100):
        self.cache: OrderedDict[str, bytes] = OrderedDict()
        self.capacity = capacity

    def get(self, key: str) -> Optional[bytes]:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: bytes):
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)


RAM_CACHE = MemoryLRUCache(capacity=100)


async def cleanup_files(file_paths: List[str]):
    for path in file_paths:
        try:
            if os.path.exists(path):
                await asyncio.to_thread(os.remove, path)
        except Exception as e:
            logger.warning(
                f"Failed to cleanup {path}: {e}", extra={"event": "CLEANUP_FAIL"}
            )


def calculate_vca_metrics(
    start_time: float, char_count: int, audio_bytes: bytes, sample_rate: int = 24000
) -> dict:
    process_time = time.perf_counter() - start_time
    len_bytes = len(audio_bytes) if audio_bytes else 0
    audio_duration_sec = len_bytes / (sample_rate * 2)
    rtf = process_time / audio_duration_sec if audio_duration_sec > 0 else 0

    return {
        "X-VCA-Chars": str(char_count),
        "X-VCA-Time": f"{process_time:.3f}",
        "X-VCA-RTF": f"{rtf:.4f}",
        "X-VCA-Model": settings.MODEL_NAME,
    }


def generate_deterministic_filename(params: dict, ext: str) -> str:
    key_data = {
        "text": params.get("text"),
        "lang": params.get("language"),
        "spk": params.get("speaker_idx"),
        "temp": params.get("temperature"),
        "speed": params.get("speed"),
        "fmt": ext,
    }
    file_hash = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    return f"{file_hash}.{ext}"


async def _get_voices_list() -> list:
    speakers_map = tts_engine.get_speakers()
    voices_list = []

    openai_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    for v in openai_voices:
        voices_list.append(
            {"id": v, "name": f"OpenAI {v.capitalize()}", "object": "voice"}
        )

    if isinstance(speakers_map, dict):
        for spk_name, styles in sorted(speakers_map.items()):
            voices_list.append({"id": spk_name, "name": spk_name, "object": "voice"})
            if isinstance(styles, list):
                for style in sorted(styles):
                    if style.lower() != spk_name.lower():
                        variant_id = f"{spk_name}/{style}"
                        voices_list.append(
                            {"id": variant_id, "name": variant_id, "object": "voice"}
                        )
    return voices_list


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")


@router.get("/api/config")
async def get_public_config():
    langs = [
        {"code": code, "name": LANGUAGE_NAMES.get(code, code.upper())}
        for code in SUPPORTED_LANGUAGES
    ]
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
            "speaker": settings.DEFAULT_SPEAKER,
            "sample_rate": settings.DEFAULT_SAMPLE_RATE,
        },
        "limits": {
            "max_text_len": 5000,
            "supported_formats": ["wav", "mp3", "opus", "pcm"],
            "supported_languages": langs,
        },
        "system": {
            "streaming_enabled": settings.ENABLE_STREAMING,
            "device": settings.DEVICE,
        },
    }


@router.get("/v1/models")
async def list_models():
    voices = await _get_voices_list()
    models_data = [
        {"id": v["id"], "object": "model", "name": v.get("name", v["id"])}
        for v in voices
    ]
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
            logger.info(
                f"Detected Lang: {detected_lang} (Conf: {confidence})",
                extra={"event": "LANG_DETECTED"},
            )
    except Exception:
        pass

    openai_map = {
        "alloy": "F_TR_Kurumsal_Ece",
        "echo": "M_TR_Heyecanli_Can",
        "fable": "M_TR_Enerjik_Mert",
        "onyx": "M_TR_Tok_Kadir",
        "nova": "F_TR_Parlak_Zeynep",
        "shimmer": "F_TR_Genc_Selin",
    }
    final_speaker = openai_map.get(request.voice.lower(), request.voice)

    available_speakers = tts_engine.get_speakers()
    base_speaker = final_speaker.split("/")[0]
    if base_speaker not in available_speakers:
        fallback = (
            list(available_speakers.keys())[0]
            if available_speakers
            else "system_default"
        )
        logger.warning(
            f"Speaker '{final_speaker}' not found. Falling back to '{fallback}'",
            extra={"event": "SPEAKER_FALLBACK"},
        )
        final_speaker = fallback

    output_fmt = "mp3"
    logger.info(
        f"OpenAI TTS: '{request.input[:15]}...' -> {final_speaker} ({detected_lang}) -> {output_fmt}",
        extra={"event": "OPENAI_SPEECH_REQ"},
    )

    internal_req = TTSRequest(
        text=request.input,
        language=detected_lang,
        speaker_idx=final_speaker,
        stream=False,
        speed=request.speed if request.speed else settings.DEFAULT_SPEED,
        output_format=output_fmt,
    )

    try:
        params = internal_req.model_dump()
        audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        logger.error(
            f"TTS Generation Failed: {e}",
            exc_info=True,
            extra={"event": "TTS_GEN_FAIL"},
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/speakers")
async def get_speakers():
    return {"speakers": tts_engine.get_speakers()}


@router.post("/api/speakers/refresh")
async def refresh_speakers_cache():
    return await asyncio.to_thread(tts_engine.refresh_speakers, force=True)


@router.post("/api/tts")
async def generate_speech(request: TTSRequest, http_req: Request):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=422)

    params = request.model_dump()
    start_time = time.perf_counter()

    if request.stream:
        logger.info(
            "Stream request: Bypassing cache.", extra={"event": "STREAM_REQUEST_INIT"}
        )

        async def stream_no_save():
            q: queue.Queue = queue.Queue(maxsize=5)
            abort_event = threading.Event()

            def producer():
                try:
                    for chunk in tts_engine.synthesize_stream(
                        params, is_aborted_cb=abort_event.is_set
                    ):
                        while not abort_event.is_set():
                            try:
                                q.put(("chunk", chunk), timeout=0.1)
                                break
                            except queue.Full:
                                continue
                    if not abort_event.is_set():
                        q.put(("done", None))
                except Exception as ex:
                    q.put(("error", ex))

            threading.Thread(target=producer, daemon=True).start()

            try:
                while True:
                    if await http_req.is_disconnected():
                        logger.warning(
                            "HTTP Client disconnected during stream.",
                            extra={"event": "HTTP_CLIENT_DISCONNECT"},
                        )
                        abort_event.set()
                        break
                    try:
                        msg_type, payload = await asyncio.to_thread(q.get, True, 0.1)
                    except queue.Empty:
                        continue

                    if msg_type == "error":
                        logger.error(
                            f"Stream error in thread: {payload}",
                            extra={"event": "STREAM_THREAD_ERROR"},
                        )
                        raise payload
                    elif msg_type == "done":
                        break
                    else:
                        yield payload
            except asyncio.CancelledError:
                abort_event.set()
                raise

        return StreamingResponse(
            stream_no_save(), media_type="application/octet-stream"
        )
    else:
        ext = request.output_format
        media_type = {
            "mp3": "audio/mpeg",
            "opus": "audio/ogg",
            "pcm": "application/octet-stream",
        }.get(ext, "audio/wav")
        safe_hash = generate_deterministic_filename(params, ext)

        cached_audio = RAM_CACHE.get(safe_hash)
        if cached_audio:
            logger.info(f"RAM Cache Hit: {safe_hash}", extra={"event": "CACHE_HIT"})
            return Response(
                content=cached_audio, media_type=media_type, headers={"X-Cache": "HIT"}
            )

        audio_bytes = await asyncio.to_thread(tts_engine.synthesize, params)
        metrics = calculate_vca_metrics(
            start_time, len(request.text), audio_bytes, request.sample_rate
        )

        RAM_CACHE.put(safe_hash, audio_bytes)

        return Response(content=audio_bytes, media_type=media_type, headers=metrics)


@router.post("/api/tts/clone")
async def generate_speech_clone(
    http_req: Request,
    text: str = Form(...),
    language: str = Form(settings.DEFAULT_LANGUAGE),
    files: List[UploadFile] = File(...),
    stream: bool = Form(False),
    output_format: str = Form(settings.DEFAULT_OUTPUT_FORMAT),
):
    saved_files = []
    try:
        for file in files:
            fd, path = tempfile.mkstemp(suffix=".wav")
            with os.fdopen(fd, "wb") as f:
                shutil.copyfileobj(file.file, f)
            saved_files.append(path)

        params = {"text": text, "language": language, "output_format": output_format}

        if stream:

            async def stream_with_cleanup():
                q: queue.Queue = queue.Queue(maxsize=5)
                abort_event = threading.Event()

                def producer():
                    try:
                        for chunk in tts_engine.synthesize_stream(
                            params,
                            speaker_wavs=saved_files,
                            is_aborted_cb=abort_event.is_set,
                        ):
                            while not abort_event.is_set():
                                try:
                                    q.put(("chunk", chunk), timeout=0.1)
                                    break
                                except queue.Full:
                                    continue
                        if not abort_event.is_set():
                            q.put(("done", None))
                    except Exception as ex:
                        q.put(("error", ex))

                threading.Thread(target=producer, daemon=True).start()

                try:
                    while True:
                        if await http_req.is_disconnected():
                            abort_event.set()
                            break
                        try:
                            msg_type, payload = await asyncio.to_thread(
                                q.get, True, 0.1
                            )
                        except queue.Empty:
                            continue

                        if msg_type == "error":
                            break
                        elif msg_type == "done":
                            break
                        else:
                            yield payload
                except asyncio.CancelledError:
                    abort_event.set()
                    raise
                finally:
                    await cleanup_files(saved_files)

            return StreamingResponse(
                stream_with_cleanup(), media_type="application/octet-stream"
            )
        else:
            audio_bytes = await asyncio.to_thread(
                tts_engine.synthesize, params, speaker_wavs=saved_files
            )
            await cleanup_files(saved_files)
            return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        await cleanup_files(saved_files)
        logger.error(f"Clone generation failed: {e}", extra={"event": "CLONE_GEN_FAIL"})
        raise HTTPException(500, str(e))
