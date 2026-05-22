import asyncio
import uuid

import httpx
from loguru import logger


class APIClient:
    """Асинхронный HTTP-клиент для взаимодействия с VoiVoice API."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        """Инициализация клиента.

        Args:
            base_url: Базовый URL сервера API.
            timeout: Таймаут по умолчанию для HTTP-запросов (в секундах).
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Ленивое создание или переиспользование httpx.AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def health(self) -> dict:
        """Проверка состояния сервера.

        Returns:
            Ответ сервера в виде словаря.
        """
        client = await self._get_client()
        # Генерируем короткий trace_id для трассировки запроса в логах
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
        model: str = "medium",
        prompt: str | None = None,
        vad_filter: bool = False,
        hotwords: str | None = None,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        multiplier: float = 2.0,
    ) -> dict:
        """Отправка аудио на сервер для транскрипции с повторными попытками при сетевых ошибках.

        Args:
            audio_bytes: Сырые байты WAV-файла.
            language: Код языка (например, "ru", "en" или "auto").
            cleanup: Флаг постобработки текста через LLM.
            model: Название модели ASR.
            prompt: Опциональный промпт для ASR.
            vad_filter: Включить фильтрацию голосовой активности.
            hotwords: Горячие слова для улучшения распознавания.
            max_attempts: Максимальное число повторных попыток.
            base_delay: Начальная задержка между попытками (в секундах).
            multiplier: Множитель экспоненциального роста задержки.

        Returns:
            Результат транскрипции от сервера.

        Raises:
            Exception: Последняя произошедшая ошибка после исчерпания попыток.
        """
        client = await self._get_client()
        trace_id = str(uuid.uuid4())[:8]
        headers = {"X-Trace-ID": trace_id}

        # Формируем multipart-данные: файл + параметры запроса
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        data = {
            "language": language,
            "cleanup": str(cleanup).lower(),
            "model": model,
            "vad_filter": str(vad_filter).lower(),
        }
        if prompt:
            data["prompt"] = prompt
        if hotwords:
            data["hotwords"] = hotwords

        last_exc: Exception | None = None
        delay = base_delay

        # Цикл повторных попыток с экспоненциальной задержкой
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
                # Сетевые ошибки — повторяем запрос
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
                # HTTP-ошибки — не повторяем, сразу прокидываем исключение
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
        """Закрытие HTTP-клиента и освобождение ресурсов."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
