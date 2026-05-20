from pydantic import BaseModel, Field
from typing import Optional


class TranscribeRequest(BaseModel):
    language: Optional[str] = Field(default="auto", description="Language code (ru, en, auto)")
    cleanup: bool = Field(default=True, description="Enable LLM cleanup")


class TranscribeResponse(BaseModel):
    success: bool
    raw: str
    cleaned: Optional[str] = None
    language: Optional[str] = None
    duration_ms: Optional[int] = None
    processing_ms: Optional[int] = None
    cleanup_skipped: bool = False
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    services: dict[str, str]
    version: str = "0.1.0"
