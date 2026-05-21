import uuid
import asyncio
from typing import Optional
import httpx
from loguru import logger


class APIClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def health(self) -> dict:
        client = await self._get_client()
        trace_id = str(uuid.uuid4())[:8]
        headers = {"X-Trace-ID": trace_id}
        resp = await client.get(f"{self.base_url}/api/v1/health", headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "auto",
        cleanup: bool = True,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        multiplier: float = 2.0,
    ) -> dict:
        client = await self._get_client()
        trace_id = str(uuid.uuid4())[:8]
        headers = {"X-Trace-ID": trace_id}

        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        data = {"language": language, "cleanup": str(cleanup).lower()}

        last_exc: Optional[Exception] = None
        delay = base_delay

        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug(
                    "transcribe_attempt",
                    trace_id=trace_id,
                    attempt=attempt,
                    max_attempts=max_attempts,
                )
                resp = await client.post(
                    f"{self.base_url}/api/v1/transcribe",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
                )
                resp.raise_for_status()
                result = resp.json()
                logger.info(
                    "transcribe_success",
                    trace_id=trace_id,
                    attempt=attempt,
                    raw_len=len(result.get("raw", "")),
                )
                return result
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                logger.warning(
                    "transcribe_retry",
                    trace_id=trace_id,
                    attempt=attempt,
                    error=type(exc).__name__,
                    next_delay=delay if attempt < max_attempts else None,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(delay)
                    delay *= multiplier
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "transcribe_http_error",
                    trace_id=trace_id,
                    status=exc.response.status_code,
                )
                raise

        logger.error(
            "transcribe_failed",
            trace_id=trace_id,
            attempts=max_attempts,
            error=type(last_exc).__name__ if last_exc else "unknown",
        )
        raise last_exc or RuntimeError("Transcribe failed after all retries")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
