from src.client.config import Config


def test_default_config():
    cfg = Config()
    assert cfg.app_name == "VoiVoice"
    assert cfg.hotkey.combination == "ctrl+alt+v"
    assert cfg.audio.sample_rate == 16000
    assert cfg.audio.max_duration_ms == 60000
    assert cfg.services.api_url == "http://localhost:8080"


def test_config_from_yaml(tmp_config_file):
    cfg = Config.from_yaml(tmp_config_file)
    assert cfg.app_name == "VoiVoice"
    assert cfg.audio.sample_rate == 16000


def test_missing_yaml_returns_defaults(tmp_path):
    missing = tmp_path / "nonexistent.yaml"
    cfg = Config.from_yaml(missing)
    assert cfg.app_name == "VoiVoice"
