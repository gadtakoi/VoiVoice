from pydantic import BaseModel, Field


class TranscribeRequest(BaseModel):
    """Схема тела запроса на транскрипцию (используется в документации)."""

    language: str | None = Field(default='auto', description='Код языка (ru, en, auto)')
    cleanup: bool = Field(default=True, description='Включить LLM-постобработку')


class TranscribeResponse(BaseModel):
    """Схема ответа эндпоинта /transcribe.

    Attributes:
        success: Флаг успешности операции.
        raw: Сырой текст от ASR.
        cleaned: Очищенный текст (или None, если cleanup не выполнялся).
        language: Определённый или запрошенный язык.
        duration_ms: Длительность аудио (опционально).
        processing_ms: Общее время обработки (мс).
        cleanup_skipped: Была ли пропущена постобработка.
        error: Сообщение об ошибке (опционально).
    """

    success: bool
    raw: str
    cleaned: str | None = None
    language: str | None = None
    duration_ms: int | None = None
    processing_ms: int | None = None
    cleanup_skipped: bool = False
    error: str | None = None


class HealthResponse(BaseModel):
    """Схема ответа эндпоинта /health.

    Attributes:
        status: Общий статус (ok / degraded).
        services: Словарь состояний отдельных сервисов.
        version: Версия API-шлюза.
    """

    status: str
    services: dict[str, str]
    version: str = '0.1.0'
