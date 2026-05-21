import os
import time
import httpx
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from structlog import get_logger

from ..schemas.transcribe import TranscribeResponse

router = APIRouter(prefix="/api/v1", tags=["transcribe"])
logger = get_logger()

ASR_URL = os.getenv("ASR_URL", "http://asr:8000")
LLM_URL = os.getenv("LLM_URL", "http://llm:11434")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "llama3.2:3b")

# Prompt template for cleanup
CLEANUP_PROMPT = """You are an AI dictation assistant. Clean up the following raw speech transcript.
Rules:
- Remove filler words (uh, um, like, you know, ну типа, эм)
- Add proper punctuation
- Fix grammar and capitalization
- Preserve the original language
- Output ONLY the cleaned text, no explanations

Raw: {text}
Cleaned:"""


async def _call_asr(audio: bytes, language: str) -> dict:
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        files = {"file": ("audio.wav", audio, "audio/wav")}
        data = {"model": "base", "language": language if language != "auto" else None}
        data = {k: v for k, v in data.items() if v is not None}

        response = await client.post(f"{ASR_URL}/v1/audio/transcriptions", files=files, data=data)
        response.raise_for_status()
        return response.json()


async def _call_llm_cleanup(text: str, model: str) -> str:
    prompt = CLEANUP_PROMPT.format(text=text)
    timeout = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 256,
            },
        }
        response = await client.post(f"{LLM_URL}/api/generate", json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("response", text).strip()


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Form("auto"),
    cleanup: bool = Form(True),
) -> TranscribeResponse:
    start_time = time.perf_counter()
    trace_id = os.urandom(8).hex()

    logger.info("transcribe_request", trace_id=trace_id, language=language, cleanup=cleanup)

    try:
        audio = await file.read()
    except Exception as exc:
        logger.error("audio_read_failed", trace_id=trace_id, error=str(exc))
        raise HTTPException(status_code=400, detail="Failed to read audio file") from exc

    # ASR
    asr_start = time.perf_counter()
    try:
        asr_result = await _call_asr(audio, language)
    except httpx.HTTPStatusError as exc:
        logger.error("asr_http_error", trace_id=trace_id, status=exc.response.status_code)
        raise HTTPException(status_code=502, detail="ASR service error") from exc
    except httpx.RequestError as exc:
        logger.error("asr_request_error", trace_id=trace_id, error=str(exc))
        raise HTTPException(status_code=503, detail="ASR service unavailable") from exc

    raw_text = asr_result.get("text", "").strip()
    asr_elapsed = int((time.perf_counter() - asr_start) * 1000)
    logger.info("asr_complete", trace_id=trace_id, duration_ms=asr_elapsed, text_len=len(raw_text))

    if not raw_text:
        return TranscribeResponse(success=True, raw="", cleaned="", language=language, processing_ms=0)

    # LLM Cleanup
    cleaned_text = None
    cleanup_skipped = False
    llm_elapsed = 0

    if cleanup:
        llm_start = time.perf_counter()
        try:
            cleaned_text = await _call_llm_cleanup(raw_text, DEFAULT_LLM_MODEL)
            llm_elapsed = int((time.perf_counter() - llm_start) * 1000)
            logger.info("llm_cleanup_complete", trace_id=trace_id, duration_ms=llm_elapsed)
        except Exception as exc:
            llm_elapsed = int((time.perf_counter() - llm_start) * 1000)
            logger.warning("llm_cleanup_failed", trace_id=trace_id, error=str(exc), fallback="raw")
            cleanup_skipped = True
    else:
        cleanup_skipped = True

    total_elapsed = int((time.perf_counter() - start_time) * 1000)

    return TranscribeResponse(
        success=True,
        raw=raw_text,
        cleaned=cleaned_text if cleaned_text else raw_text,
        language=language,
        processing_ms=total_elapsed,
        cleanup_skipped=cleanup_skipped,
    )
