from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.client.audio import AudioCapture, SileroVAD


class TestSileroVAD:
    @patch('src.client.audio.ort.InferenceSession')
    def test_init(self, mock_session):
        vad = SileroVAD(model_path='/fake/model.onnx', threshold=0.7)
        assert vad.threshold == 0.7
        mock_session.assert_called_once_with('/fake/model.onnx')

    @patch('src.client.audio.ort.InferenceSession')
    def test_reset(self, mock_session):
        vad = SileroVAD()
        vad.h = np.ones((2, 1, 64), dtype=np.float32)
        vad.reset()
        assert np.all(vad.h == 0)

    @patch('src.client.audio.ort.InferenceSession')
    def test_process_invalid_sample_rate(self, mock_session):
        vad = SileroVAD()
        with pytest.raises(ValueError, match='Unsupported sample rate'):
            vad.process(np.zeros(100, dtype=np.float32), sample_rate=44100)

    @patch('src.client.audio.ort.InferenceSession')
    def test_process_int16_input(self, mock_session):
        instance = mock_session.return_value
        instance.run.return_value = [np.array([[0.8]]), np.zeros((2, 1, 64)), np.zeros((2, 1, 64))]
        vad = SileroVAD()
        audio = np.ones(512, dtype=np.int16)
        result = vad.process(audio, sample_rate=16000)
        assert isinstance(result, float)

    @patch('src.client.audio.ort.InferenceSession')
    def test_is_speech_true(self, mock_session):
        instance = mock_session.return_value
        instance.run.return_value = [np.array([[0.8]]), np.zeros((2, 1, 64)), np.zeros((2, 1, 64))]
        vad = SileroVAD(threshold=0.5)
        audio = np.zeros(512, dtype=np.float32)
        assert vad.is_speech(audio, sample_rate=16000) is True

    @patch('src.client.audio.ort.InferenceSession')
    def test_is_speech_false(self, mock_session):
        instance = mock_session.return_value
        instance.run.return_value = [np.array([[0.3]]), np.zeros((2, 1, 64)), np.zeros((2, 1, 64))]
        vad = SileroVAD(threshold=0.5)
        audio = np.zeros(512, dtype=np.float32)
        assert vad.is_speech(audio, sample_rate=16000) is False


class TestAudioCapture:
    def test_init_defaults(self):
        cap = AudioCapture()
        assert cap.sample_rate == 16000
        assert cap.channels == 1
        assert cap.dtype == 'int16'
        assert cap.is_recording is False

    def test_init_custom(self):
        cap = AudioCapture(sample_rate=44100, channels=2, max_duration_ms=10000)
        assert cap.sample_rate == 44100
        assert cap.channels == 2
        assert cap.max_duration_ms == 10000

    def test_init_vad_fail(self):
        # VAD не должен падать при ошибке инициализации
        with patch('src.client.audio.SileroVAD', side_effect=RuntimeError('no model')):
            cap = AudioCapture()
        assert cap._vad is None

    def test_encode_wav(self):
        cap = AudioCapture(sample_rate=16000, channels=1, dtype='int16')
        audio = np.zeros(16000, dtype=np.int16)
        wav = cap._encode_wav(audio)
        assert isinstance(wav, bytes)
        assert wav.startswith(b'RIFF')

    def test_resample_same_rate(self):
        cap = AudioCapture()
        audio = np.array([1, 2, 3], dtype=np.int16)
        result = cap._resample(audio, 16000, 16000)
        np.testing.assert_array_equal(result, audio)

    def test_resample_different_rate(self):
        cap = AudioCapture()
        audio = np.array([0, 1000, 2000, 3000], dtype=np.int16)
        result = cap._resample(audio, 16000, 8000)
        assert len(result) == 2

    def test_highpass_filter_no_signal(self):
        cap = AudioCapture()
        audio = np.array([1, 2, 3], dtype=np.int16)
        with patch.object(__import__('src.client.audio', fromlist=['signal']), 'signal', None):
            result = cap._highpass_filter(audio, 16000)
        np.testing.assert_array_equal(result, audio)

    def test_highpass_filter_too_short(self):
        cap = AudioCapture()
        audio = np.array([1], dtype=np.int16)
        result = cap._highpass_filter(audio, 16000)
        np.testing.assert_array_equal(result, audio)

    def test_normalize_audio_zero_rms(self):
        cap = AudioCapture()
        audio = np.zeros(100, dtype=np.int16)
        result = cap._normalize_audio(audio)
        np.testing.assert_array_equal(result, audio)

    def test_normalize_audio_nonzero(self):
        cap = AudioCapture()
        audio = np.full(100, 1000, dtype=np.int16)
        result = cap._normalize_audio(audio)
        assert result.dtype == np.int16

    def test_callback_not_recording(self):
        cap = AudioCapture()
        cap._recording = False
        cap._callback(np.zeros(10), 10, None, None)
        assert cap._buffer == []

    def test_callback_recording(self):
        cap = AudioCapture()
        cap._recording = True
        indata = np.ones((10, 1), dtype=np.int16)
        cap._callback(indata, 10, None, None)
        assert len(cap._buffer) == 1

    def test_callback_with_status(self):
        cap = AudioCapture()
        cap._recording = True
        with patch('src.client.audio.logger.warning') as mock_log:
            cap._callback(np.zeros((10, 1), dtype=np.int16), 10, None, 'overrun')
            mock_log.assert_called_once()

    def test_start_when_already_recording(self):
        cap = AudioCapture()
        cap._recording = True
        cap.start()
        assert cap._recording is True

    @patch('src.client.audio.sd.InputStream')
    def test_start_success(self, mock_stream_class):
        mock_stream = MagicMock()
        mock_stream_class.return_value = mock_stream
        cap = AudioCapture(max_duration_ms=0)
        cap.start()
        assert cap._recording is True
        mock_stream.start.assert_called_once()

    @patch('src.client.audio.sd.InputStream')
    def test_start_with_state_callback(self, mock_stream_class):
        mock_stream = MagicMock()
        mock_stream_class.return_value = mock_stream
        cb = MagicMock()
        cap = AudioCapture(on_state_change=cb, max_duration_ms=0)
        cap.start()
        cb.assert_called_once_with('listening')

    @patch('src.client.audio.sd.InputStream')
    def test_stop_not_recording(self, mock_stream_class):
        cap = AudioCapture()
        result = cap.stop()
        assert result is None

    @patch('src.client.audio.sd.InputStream')
    def test_stop_empty_buffer(self, mock_stream_class):
        mock_stream = MagicMock()
        mock_stream_class.return_value = mock_stream
        cap = AudioCapture(max_duration_ms=0)
        cap.start()
        result = cap.stop()
        assert result is None
        assert cap.is_recording is False

    @patch('src.client.audio.sd.InputStream')
    def test_stop_with_data(self, mock_stream_class):
        mock_stream = MagicMock()
        mock_stream_class.return_value = mock_stream
        cap = AudioCapture(sample_rate=16000, max_duration_ms=0)
        cap.start()
        cap._buffer = [np.zeros(16000, dtype=np.int16)]
        result = cap.stop()
        assert isinstance(result, bytes)
        assert result.startswith(b'RIFF')

    @patch('src.client.audio.sd.InputStream')
    def test_stop_resample(self, mock_stream_class):
        mock_stream = MagicMock()
        mock_stream_class.return_value = mock_stream
        mock_stream.samplerate = 44100
        cap = AudioCapture(sample_rate=16000, max_duration_ms=0)
        cap.start()
        cap._actual_sample_rate = 44100
        cap._buffer = [np.zeros(44100, dtype=np.int16)]
        result = cap.stop()
        assert isinstance(result, bytes)

    def test_on_max_duration_not_recording(self):
        cap = AudioCapture()
        cap._recording = False
        cap._on_max_duration_reached()

    @patch('src.client.audio.sd.InputStream')
    def test_on_max_duration_recording(self, mock_stream_class):
        mock_stream = MagicMock()
        mock_stream_class.return_value = mock_stream
        cb = MagicMock()
        cap = AudioCapture(on_max_duration=cb, max_duration_ms=0)
        cap.start()
        cap._buffer = [np.zeros(16000, dtype=np.int16)]
        cap._on_max_duration_reached()
        assert cap.is_recording is False
