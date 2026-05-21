import yaml
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class HotkeyConfig(BaseSettings):
    combination: str = "ctrl+alt+v"
    hold_to_record: bool = True


class AudioConfig(BaseSettings):
    sample_rate: int = 16000
    channels: int = 1
    dtype: str = "int16"
    chunk_duration_ms: int = 30
    vad_threshold: float = 0.5
    silence_timeout_ms: int = 500
    max_duration_ms: int = 60000


class ServicesConfig(BaseSettings):
    api_url: str = "http://localhost:8080"
    asr_model: str = "base"
    llm_model: str = "llama3.2:3b"
    cleanup_enabled: bool = True
    fallback_to_raw: bool = True


class TrayConfig(BaseSettings):
    show_notifications: bool = True
    startup_minimized: bool = False


class InjectionConfig(BaseSettings):
    method: str = "sendinput"
    delay_between_chars_ms: int = 10


class LoggingConfig(BaseSettings):
    level: str = "INFO"
    format: str = "json"
    directory: str = "./logs"
    rotation_mb: int = 10
    retention_days: int = 7


class RetryConfig(BaseSettings):
    max_attempts: int = 3
    base_delay: float = 0.5
    multiplier: float = 2.0


class RetrySection(BaseSettings):
    asr: RetryConfig = RetryConfig()
    llm: RetryConfig = RetryConfig(max_attempts=2, base_delay=1.0, multiplier=2.0)


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VOIVOICE_", extra="ignore")

    app_name: str = "VoiVoice"
    app_version: str = "0.1.0"
    hotkey: HotkeyConfig = HotkeyConfig()
    audio: AudioConfig = AudioConfig()
    services: ServicesConfig = ServicesConfig()
    tray: TrayConfig = TrayConfig()
    injection: InjectionConfig = InjectionConfig()
    logging: LoggingConfig = LoggingConfig()
    retry: RetrySection = RetrySection()

    @classmethod
    def from_yaml(cls, path: Optional[Path] = None) -> "Config":
        if path is None:
            path = Path("config.yaml")
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
