import io
import wave
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.client.audio import AudioCapture, SileroVAD


class TestSileroVAD:
    @patch('src.client.audio.ort.InferenceSession')
    def test_init(self, mock_session):
        vad = SileroVAD(model_path='fake.onnx', threshold=0.7)
        assert vad.threshold == 0.7
        mock_session.assert_called_once_with('fake.onnx')

    @patch('src.client.audio.ort.InferenceSession')
    def test_reset(self, mock_session):
        vad = SileroVAD()
        vad.h = np.ones((2, 1, 64), dtype=np.float32)
        vad.reset()
        assert np.all(vad.h == 0)
        assert np.all(vad.c == 0)

    @patch('src.client.audio.ort.InferenceSession')
    def test_process_unsupported_sample_rate(self, mock_session):
        vad = SileroVAD()
        with pytest.raises(ValueError, match='Unsupported sample rate'):
            vad.process(np.zeros(100), sample_rate=44100)

    @patch('src.client.audio.ort.InferenceSession')
    def test_process_runs_session(self, mock_session):
        instance = mock_session.return_value
        instance.run.return_value = [np.array([[0.8]], dtype=np.float32), np.zeros((2, 1, 64)), np.zeros((2, 1, 64))]
        vad = SileroVAD()
        audio = np.zeros(512, dtype=np.int16)
        result = vad.process(audio, sample_rate=16000)
        assert result == pytest.approx(0.8)

    @patch('src.client.audio.ort.InferenceSession')
    def test_is_speech_true(self, mock_session):
        instance = mock_session.return_value
        instance.run.return_value = [np.array([[0.8]], dtype=np.float32), np.zeros((2, 1, 64)), np.zeros((2, 1, 64))]
        vad = SileroVAD(threshold=0.5)
        audio = np.zeros(512, dtype=np.int16)
        assert vad.is_speech(audio, sample_rate=16000) is True

    @patch('src.client.audio.ort.InferenceSession')
    def test_is_speech_false(self, mock_session):
        instance = mock_session.return_value
        instance.run.return_value = [np.array([[0.3]], dtype=np.float32), np.zeros((2, 1, 64)), np.zeros((2, 1, 64))]
        vad = SileroVAD(threshold=0.5)
        audio = np.zeros(512, dtype=np.int16)
        assert vad.is_speech(audio, sample_rate=16000) is False


class TestAudioCapture:
    def test_init_defaults(self):
        cap = AudioCapture()
        assert cap.sample_rate == 16000
        assert cap.channels == 1
        assert cap.dtype == 'int16'
        assert not cap.is_recording

    @patch('src.client.audio.SileroVAD')
    def test_init_vad_fails_gracefully(self, mock_vad):
        mock_vad.side_effect = RuntimeError('no model')
        cap = AudioCapture()
        assert cap._vad is None

    def test_resample_same_rate(self):
        cap = AudioCapture()
        audio = np.array([1, 2, 3], dtype=np.int16)
        result = cap._resample(audio, 16000, 16000)
        assert np.array_equal(result, audio)

    def test_resample_different_rate(self):
        cap = AudioCapture()
        audio = np.array([0, 1000, 2000, 3000], dtype=np.int16)
        result = cap._resample(audio, 16000, 8000)
        assert len(result) == 2

    def test_highpass_filter_no_scipy(self):
        cap = AudioCapture()
        with patch('src.client.audio.signal', None):
            audio = np.array([100, 200, 300], dtype=np.int16)
            result = cap._highpass_filter(audio, 16000)
            assert np.array_equal(result, audio)

    def test_normalize_audio_silence(self):
        cap = AudioCapture()
        audio = np.zeros(100, dtype=np.int16)
        result = cap._normalize_audio(audio)
        assert np.array_equal(result, audio)

    def test_encode_wav(self):
        cap = AudioCapture(sample_rate=16000, channels=1, dtype='int16')
        audio = np.zeros(16000, dtype=np.int16)
        wav = cap._encode_wav(audio)
        assert isinstance(wav, bytes)
        assert wav.startswith(b'RIFF')
        # Проверим, что это валидный WAV
        buf = io.BytesIO(wav)
        with wave.open(buf, 'rb') as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16000
            assert wf.getsampwidth() == 2

    def test_callback_not_recording(self):
        cap = AudioCapture()
        cap._recording = False
        cap._callback(np.zeros((10, 1)), 10, None, None)
        assert cap._buffer == []

    def test_callback_recording(self):
        cap = AudioCapture()
        cap._recording = True
        indata = np.ones((10, 1), dtype=np.float32)
        cap._callback(indata, 10, None, None)
        assert len(cap._buffer) == 1

    @patch('src.client.audio.sd.InputStream')
    def test_start(self, mock_stream_cls):
        cap = AudioCapture()
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream
        cap.start()
        assert cap.is_recording is True
        mock_stream.start.assert_called_once()

    @patch('src.client.audio.sd.InputStream')
    def test_start_already_recording(self, mock_stream_cls):
        cap = AudioCapture()
        cap._recording = True
        cap.start()
        mock_stream_cls.assert_not_called()

    @patch('src.client.audio.sd.InputStream')
    def test_stop(self, mock_stream_cls):
        cap = AudioCapture()
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream
        cap.start()
        cap.stop()
        assert cap.is_recording is False
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()

    def test_stop_not_recording(self):
        cap = AudioCapture()
        assert cap.stop() is None

    def test_stop_empty_buffer(self):
        cap = AudioCapture()
        cap._recording = True
        cap._buffer = []
        assert cap.stop() is None

    @patch('src.client.audio.sd.InputStream')
    def test_on_max_duration_reached(self, mock_stream_cls):
        cap = AudioCapture(max_duration_ms=1000)
        cap._recording = True
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream
        cap.start()
        cb = MagicMock()
        cap.on_max_duration = cb
        cap._on_max_duration_reached()
        assert cap.is_recording is False
        cb.assert_called_once()

    def test_on_max_duration_not_recording(self):
        cap = AudioCapture()
        cap._recording = False
        cap._on_max_duration_reached()
        assert cap._recording is False
