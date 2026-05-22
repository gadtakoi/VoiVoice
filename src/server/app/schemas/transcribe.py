from pydantic import BaseModel, Field


class TranscribeRequest(BaseModel):
    language: str | None = Field(default="auto", description="Language code (ru, en, auto)")
    cleanup: bool = Field(default=True, description="Enable LLM cleanup")


class TranscribeResponse(BaseModel):
    success: bool
    raw: str
    cleaned: str | None = None
    language: str | None = None
    duration_ms: int | None = None
    processing_ms: int | None = None
    cleanup_skipped: bool = False
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    services: dict[str, str]
    version: str = "0.1.0"
