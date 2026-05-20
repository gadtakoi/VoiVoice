import io
import wave
from typing import Optional, Callable
import numpy as np
import sounddevice as sd
import onnxruntime as ort
from loguru import logger


import os

class SileroVAD:
    """Simple ONNX Silero VAD wrapper."""

    _DEFAULT_MODEL = os.path.join(os.path.dirname(__file__), "..", "..", "models", "silero_vad.onnx")

    def __init__(self, model_path: str = None, threshold: float = 0.5):
        if model_path is None:
            model_path = self._DEFAULT_MODEL
        self.threshold = threshold
        self.session = ort.InferenceSession(model_path)
        self.h = np.zeros((2, 1, 64), dtype=np.float32)
        self.c = np.zeros((2, 1, 64), dtype=np.float32)
        self.sample_rates = [8000, 16000]

    def reset(self):
        self.h = np.zeros((2, 1, 64), dtype=np.float32)
        self.c = np.zeros((2, 1, 64), dtype=np.float32)

    def process(self, audio: np.ndarray, sample_rate: int = 16000) -> float:
        if sample_rate not in self.sample_rates:
            raise ValueError(f"Unsupported sample rate: {sample_rate}")
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32) / np.iinfo(np.int16).max
        if len(audio.shape) > 1:
            audio = audio.squeeze()
        input_len = int(sample_rate * 0.032)  # 32ms chunks for 16kHz = 512 samples
        if len(audio) < input_len:
            audio = np.pad(audio, (0, input_len - len(audio)))
        audio = audio[:input_len]
        inputs = {
            "input": audio.reshape(1, -1),
            "h": self.h,
            "c": self.c,
            "sr": np.array(sample_rate, dtype=np.int64),
        }
        out, h, c = self.session.run(["output", "hn", "cn"], inputs)
        self.h = h
        self.c = c
        return float(out[0][0])

    def is_speech(self, audio: np.ndarray, sample_rate: int = 16000) -> bool:
        prob = self.process(audio, sample_rate)
        return prob > self.threshold


class AudioCapture:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = "int16",
        chunk_duration_ms: int = 30,
        vad_threshold: float = 0.5,
        silence_timeout_ms: int = 500,
        max_duration_ms: int = 60000,
        on_state_change: Optional[Callable[[str], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.chunk_duration_ms = chunk_duration_ms
        self.silence_timeout_ms = silence_timeout_ms
        self.max_duration_ms = max_duration_ms
        self.on_state_change = on_state_change
        self._buffer: list[np.ndarray] = []
        self._recording = False
        self._stream: Optional[sd.InputStream] = None
        self._vad: Optional[SileroVAD] = None
        try:
            self._vad = SileroVAD(threshold=vad_threshold)
        except Exception as exc:
            logger.warning("vad_init_failed", error=str(exc))

    def _callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            logger.warning("audio_stream_status", status=str(status))
        if self._recording:
            self._buffer.append(indata.copy())

    def start(self):
        if self._recording:
            return
        self._buffer = []
        self._recording = True
        if self._vad:
            self._vad.reset()
        blocksize = int(self.sample_rate * self.chunk_duration_ms / 1000)
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            blocksize=blocksize,
            callback=self._callback,
        )
        self._stream.start()
        logger.info("audio_capture_started", sample_rate=self.sample_rate)
        if self.on_state_change:
            self.on_state_change("listening")

    def stop(self) -> Optional[bytes]:
        if not self._recording:
            return None
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._buffer:
            logger.info("audio_capture_empty")
            if self.on_state_change:
                self.on_state_change("idle")
            return None

        audio = np.concatenate(self._buffer, axis=0)
        wav_bytes = self._encode_wav(audio)
        duration_ms = int(len(audio) / self.sample_rate * 1000)
        logger.info("audio_capture_stopped", duration_ms=duration_ms, samples=len(audio))
        if self.on_state_change:
            self.on_state_change("processing")
        return wav_bytes

    def _encode_wav(self, audio: np.ndarray) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(np.dtype(self.dtype).itemsize)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())
        return buffer.getvalue()

    @property
    def is_recording(self) -> bool:
        return self._recording
