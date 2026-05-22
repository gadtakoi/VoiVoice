import os

import httpx
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from structlog import get_logger

from ..schemas.transcribe import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])
logger = get_logger()

ASR_URL = os.getenv("ASR_URL", "http://asr:8000")
LLM_URL = os.getenv("LLM_URL", "http://llm:11434")


async def _check_service(url: str, timeout: float = 5.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            return response.status_code < 500
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    asr_ok = await _check_service(f"{ASR_URL}/health")
    llm_ok = await _check_service(f"{LLM_URL}/")

    services = {
        "asr": "ok" if asr_ok else "error",
        "llm": "ok" if llm_ok else "error",
    }

    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"

    logger.info("healthcheck", services=services, status=overall)

    if overall != "ok":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=HealthResponse(status=overall, services=services).model_dump(),
        )

    return HealthResponse(status=overall, services=services)
