from pathlib import Path

import pytest


@pytest.fixture
def mock_config():
    """Фикстура: возвращает дефолтный объект Config для тестов клиента."""
    from src.client.config import Config

    return Config()


@pytest.fixture
def tmp_config_file(tmp_path: Path):
    """Фикстура: создаёт временный YAML-файл конфигурации.

    Args:
        tmp_path: Встроенная фикстура pytest для временной директории.

    Returns:
        Path к созданному файлу config.yaml.
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
app:
  name: "VoiVoice"
  version: "0.1.0"
hotkey:
  combination: "ctrl+alt+v"
audio:
  sample_rate: 16000
services:
  api_url: "http://localhost:8080"
""",
        encoding="utf-8",
    )
    return config_path
