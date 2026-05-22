import numpy as np

from src.client.audio import AudioCapture


def test_audio_capture_defaults():
    cap = AudioCapture()
    assert cap.sample_rate == 16000
    assert cap.channels == 1
    assert not cap.is_recording


def test_wav_encode():
    cap = AudioCapture(sample_rate=16000, channels=1, dtype="int16")
    audio = np.zeros(16000, dtype=np.int16)  # 1 second of silence
    wav = cap._encode_wav(audio)
    assert isinstance(wav, bytes)
    assert len(wav) > 0
    assert wav.startswith(b"RIFF")
