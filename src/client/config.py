from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class HotkeyConfig(BaseSettings):
    """Настройки горячей клавиши для активации записи."""

    combination: str = "ctrl+alt+v"
    hold_to_record: bool = True


class AudioConfig(BaseSettings):
    """Настройки аудиозахвата с микрофона."""

    sample_rate: int = 16000
    channels: int = 1
    dtype: str = "int16"
    chunk_duration_ms: int = 30
    vad_threshold: float = 0.5
    silence_timeout_ms: int = 500
    max_duration_ms: int = 60000


class ServicesConfig(BaseSettings):
    """Настройки подключения к внешним сервисам (ASR, LLM)."""

    api_url: str = "http://localhost:8080"
    asr_model: str = "medium"
    asr_language: str = "ru"
    asr_prompt: str = "Это диктовка на русском языке. Соблюдай орфографию и пунктуацию."
    asr_vad_filter: bool = True
    asr_hotwords: str = ""
    llm_model: str = "llama3.2:3b"
    cleanup_enabled: bool = True
    fallback_to_raw: bool = True


class TrayConfig(BaseSettings):
    """Настройки системного трея и уведомлений."""

    show_notifications: bool = True
    startup_minimized: bool = False


class InjectionConfig(BaseSettings):
    """Настройки вставки текста в активное окно."""

    method: str = "sendinput"
    delay_between_chars_ms: int = 10


class LoggingConfig(BaseSettings):
    """Настройки логирования."""

    level: str = "INFO"
    format: str = "json"
    directory: str = "./logs"
    rotation_mb: int = 10
    retention_days: int = 7


class RetryConfig(BaseSettings):
    """Параметры повторных попыток для HTTP-запросов."""

    max_attempts: int = 3
    base_delay: float = 0.5
    multiplier: float = 2.0


class RetrySection(BaseSettings):
    """Группировка настроек повторных попыток по сервисам."""

    asr: RetryConfig = RetryConfig()
    llm: RetryConfig = RetryConfig(max_attempts=2, base_delay=1.0, multiplier=2.0)


class Config(BaseSettings):
    """Корневой класс конфигурации приложения.

    Загружает параметры из переменных окружения (префикс VOIVOICE_)
    и YAML-файла config.yaml.
    """

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
    def from_yaml(cls, path: Path | None = None) -> "Config":
        """Загружает конфигурацию из YAML-файла.

        Args:
            path: Путь к YAML-файлу. Если None — ищет config.yaml в текущей директории.

        Returns:
            Экземпляр Config с параметрами из файла (или значениями по умолчанию).
        """
        if path is None:
            path = Path("config.yaml")
        if not path.exists():
            return cls()
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
