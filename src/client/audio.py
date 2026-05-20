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
        self._actual_sample_rate: int = sample_rate
        self._vad: Optional[SileroVAD] = None
        try:
            self._vad = SileroVAD(threshold=vad_threshold)
        except Exception as exc:
            logger.warning("vad_init_failed", error=str(exc))

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Fast linear resample using numpy interp."""
        if orig_sr == target_sr:
            return audio
        audio_float = audio.astype(np.float32)
        duration = len(audio_float) / orig_sr
        target_len = int(duration * target_sr)
        old_x = np.linspace(0, 1, len(audio_float))
        new_x = np.linspace(0, 1, target_len)
        if audio_float.ndim == 1:
            resampled = np.interp(new_x, old_x, audio_float)
        else:
            resampled = np.zeros((target_len, audio_float.shape[1]), dtype=np.float32)
            for ch in range(audio_float.shape[1]):
                resampled[:, ch] = np.interp(new_x, old_x, audio_float[:, ch])
        return resampled.astype(audio.dtype)

    def _callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            logger.warning("audio_stream_status", status=str(status))
        if not self._recording:
            return
        # Convert float32 stereo to int16 mono if needed
        audio = indata.copy()
        if audio.dtype == np.float32:
            audio = (audio * np.iinfo(np.int16).max).astype(np.int16)
        if audio.ndim > 1 and audio.shape[1] > 1:
            audio = audio.mean(axis=1, dtype=np.int16)
        self._buffer.append(audio)

    def start(self):
        if self._recording:
            return
        self._buffer = []
        self._recording = True
        self._actual_sample_rate = self.sample_rate
        if self._vad:
            self._vad.reset()
        blocksize = int(self.sample_rate * self.chunk_duration_ms / 1000)
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=blocksize,
                callback=self._callback,
            )
        except Exception as exc:
            # Fallback 1: let PortAudio choose blocksize automatically.
            logger.warning("audio_stream_blocksize_fallback", error=str(exc))
            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype=self.dtype,
                    blocksize=None,
                    callback=self._callback,
                )
            except Exception as exc2:
                # Fallback 2: use device's default samplerate.
                logger.warning("audio_stream_samplerate_fallback", error=str(exc2))
                try:
                    self._stream = sd.InputStream(
                        channels=self.channels,
                        dtype=self.dtype,
                        blocksize=None,
                        callback=self._callback,
                    )
                    self._actual_sample_rate = int(self._stream.samplerate)
                except Exception as exc3:
                    # Fallback 3: some devices require stereo or float32.
                    logger.warning("audio_stream_format_fallback", error=str(exc3))
                    try:
                        self._stream = sd.InputStream(
                            channels=2,
                            dtype="float32",
                            blocksize=None,
                            callback=self._callback,
                        )
                        self._actual_sample_rate = int(self._stream.samplerate)
                    except Exception as exc4:
                        self._recording = False
                        raise RuntimeError(
                            f"Не удалось открыть микрофон. Самая вероятная причина: "
                            f"нет прав доступа (Параметры Windows → Конфиденциальность → Микрофон). "
                            f"Также возможно: микрофон занят другим приложением, "
                            f"или устройство не поддерживает {self.sample_rate} Гц. "
                            f"Ошибки: {exc}; {exc2}; {exc3}; {exc4}"
                        ) from exc4
        self._stream.start()
        logger.info(
            "audio_capture_started",
            sample_rate=self.sample_rate,
            actual_sample_rate=self._actual_sample_rate,
        )
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
        if self._actual_sample_rate != self.sample_rate:
            logger.info(
                "audio_resampling",
                from_sr=self._actual_sample_rate,
                to_sr=self.sample_rate,
            )
            audio = self._resample(audio, self._actual_sample_rate, self.sample_rate)
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
