import pytest
from pathlib import Path


@pytest.fixture
def mock_config():
    from src.client.config import Config
    return Config()


@pytest.fixture
def tmp_config_file(tmp_path: Path):
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
