import io
import threading
import wave
from collections.abc import Callable

import numpy as np
import onnxruntime as ort
import sounddevice as sd
from loguru import logger

try:
    from scipy import signal
except Exception:
    signal = None  # type: ignore[assignment]


import os


class SileroVAD:
    """Обёртка над ONNX-моделью Silero VAD для обнаружения голосовой активности."""

    _DEFAULT_MODEL = os.path.join(os.path.dirname(__file__), "..", "..", "models", "silero_vad.onnx")

    def __init__(self, model_path: str = None, threshold: float = 0.5):
        """Инициализация VAD.

        Args:
            model_path: Путь к ONNX-модели. Если None — используется модель по умолчанию.
            threshold: Порог вероятности, выше которого считается, что речь присутствует.
        """
        if model_path is None:
            model_path = self._DEFAULT_MODEL
        self.threshold = threshold
        self.session = ort.InferenceSession(model_path)
        # Скрытые состояния LSTM-модели (hn, cn)
        self.h = np.zeros((2, 1, 64), dtype=np.float32)
        self.c = np.zeros((2, 1, 64), dtype=np.float32)
        self.sample_rates = [8000, 16000]

    def reset(self):
        """Сброс внутренних состояний LSTM (нужен при начале новой записи)."""
        self.h = np.zeros((2, 1, 64), dtype=np.float32)
        self.c = np.zeros((2, 1, 64), dtype=np.float32)

    def process(self, audio: np.ndarray, sample_rate: int = 16000) -> float:
        """Пропускает фрагмент аудио через VAD-модель.

        Args:
            audio: Одномерный массив отсчётов.
            sample_rate: Частота дискретизации (8000 или 16000 Гц).

        Returns:
            Вероятность наличия речи в диапазоне [0.0, 1.0].
        """
        if sample_rate not in self.sample_rates:
            raise ValueError(f"Unsupported sample rate: {sample_rate}")
        # Приводим к float32 в диапазоне [-1, 1]
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32) / np.iinfo(np.int16).max
        if len(audio.shape) > 1:
            audio = audio.squeeze()
        # Silero ожидает чанки по 32 мс
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
        """Удобный метод: возвращает True, если вероятность речи выше порога."""
        prob = self.process(audio, sample_rate)
        return prob > self.threshold


class AudioCapture:
    """Захват аудио с микрофона, предобработка и кодирование в WAV."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = "int16",
        chunk_duration_ms: int = 30,
        vad_threshold: float = 0.5,
        silence_timeout_ms: int = 500,
        max_duration_ms: int = 60000,
        on_state_change: Callable[[str], None] | None = None,
        on_max_duration: Callable[[bytes | None], None] | None = None,
    ):
        """Инициализация захвата аудио.

        Args:
            sample_rate: Желаемая частота дискретизации.
            channels: Число каналов (обычно 1 — моно).
            dtype: Тип данных отсчётов ("int16").
            chunk_duration_ms: Длительность одного блока в мс.
            vad_threshold: Порог VAD (если VAD удалось загрузить).
            silence_timeout_ms: Таймаут тишины (не используется в текущей реализации).
            max_duration_ms: Максимальная длительность записи в мс.
            on_state_change: Колбэк при смене состояния ("listening", "processing", "idle").
            on_max_duration: Колбэк при достижении максимальной длительности.
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.chunk_duration_ms = chunk_duration_ms
        self.silence_timeout_ms = silence_timeout_ms
        self.max_duration_ms = max_duration_ms
        self.on_state_change = on_state_change
        self.on_max_duration = on_max_duration
        self._buffer: list[np.ndarray] = []
        self._recording = False
        self._stream: sd.InputStream | None = None
        self._actual_sample_rate: int = sample_rate
        self._vad: SileroVAD | None = None
        self._max_duration_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        try:
            self._vad = SileroVAD(threshold=vad_threshold)
        except Exception as exc:
            logger.warning("vad_init_failed", error=str(exc))

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Передискретизация аудио с помощью scipy или линейной интерполяции.

        Args:
            audio: Исходный массив отсчётов.
            orig_sr: Исходная частота дискретизации.
            target_sr: Целевая частота дискретизации.

        Returns:
            Передискретизированный массив.
        """
        if orig_sr == target_sr:
            return audio
        audio_float = audio.astype(np.float32)
        duration = len(audio_float) / orig_sr
        target_len = int(duration * target_sr)
        if signal is not None:
            # FFT-based resample gives much better quality than linear interp
            resampled = signal.resample(audio_float, target_len)
        else:
            old_x = np.linspace(0, 1, len(audio_float))
            new_x = np.linspace(0, 1, target_len)
            if audio_float.ndim == 1:
                resampled = np.interp(new_x, old_x, audio_float)
            else:
                resampled = np.zeros((target_len, audio_float.shape[1]), dtype=np.float32)
                for ch in range(audio_float.shape[1]):
                    resampled[:, ch] = np.interp(new_x, old_x, audio_float[:, ch])
        return resampled.astype(audio.dtype)

    @staticmethod
    def _highpass_filter(audio: np.ndarray, sr: int, cutoff: float = 80.0) -> np.ndarray:
        """Применяет фильтр высоких частот Баттерворта 2-го порядка для удаления низкочастотного шума.

        Args:
            audio: Массив отсчётов.
            sr: Частота дискретизации.
            cutoff: Частота среза (Гц).

        Returns:
            Отфильтрованный массив.
        """
        if signal is None or audio.size < 10:
            return audio
        audio_float = audio.astype(np.float32)
        sos = signal.butter(2, cutoff, btype="high", fs=sr, output="sos")
        filtered = signal.sosfilt(sos, audio_float)
        return filtered.astype(audio.dtype)

    @staticmethod
    def _normalize_audio(audio: np.ndarray, target_rms: float = 0.05) -> np.ndarray:
        """Нормализация аудио до целевого уровня RMS (относительно int16 max).

        Args:
            audio: Массив отсчётов.
            target_rms: Целевое значение RMS.

        Returns:
            Нормализованный массив.
        """
        audio_float = audio.astype(np.float32)
        rms = np.sqrt(np.mean(audio_float**2))
        if rms == 0:
            return audio
        gain = target_rms * np.iinfo(np.int16).max / rms
        # Ограничиваем усиление, чтобы избежать клиппинга (макс. +20 дБ)
        gain = min(gain, 10.0)
        normalized = np.clip(audio_float * gain, np.iinfo(np.int16).min, np.iinfo(np.int16).max)
        return normalized.astype(audio.dtype)

    def _callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Колбэк sounddevice: вызывается для каждого блока входных данных."""
        if status:
            logger.warning("audio_stream_status", status=str(status))
        if not self._recording:
            return
        # Преобразуем float32 stereo в int16 mono при необходимости
        audio = indata.copy()
        if audio.dtype == np.float32:
            audio = (audio * np.iinfo(np.int16).max).astype(np.int16)
        if audio.ndim > 1 and audio.shape[1] > 1:
            audio = audio.mean(axis=1, dtype=np.int16)
        self._buffer.append(audio)

    def start(self):
        """Начинает захват аудио с микрофона.

        Пытается открыть поток с заданными параметрами; при неудаче применяет
        последовательность fallback-стратегий (авто blocksize, авто samplerate, stereo float32).
        """
        with self._lock:
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
                # Fallback 1: позволяем PortAudio выбрать blocksize автоматически
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
                    # Fallback 2: используем частоту дискретизации устройства по умолчанию
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
                        # Fallback 3: некоторые устройства требуют stereo или float32
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
            if self.max_duration_ms and self.max_duration_ms > 0:
                # Таймер принудительной остановки по достижении максимальной длительности
                self._max_duration_timer = threading.Timer(self.max_duration_ms / 1000.0, self._on_max_duration_reached)
                self._max_duration_timer.start()

    def stop(self) -> bytes | None:
        """Останавливает захват и возвращает WAV-данные.

        Returns:
            Байты WAV-файла или None, если буфер пуст.
        """
        with self._lock:
            if not self._recording:
                return None
            self._recording = False
            if self._max_duration_timer:
                self._max_duration_timer.cancel()
                self._max_duration_timer = None
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None

        if not self._buffer:
            logger.info("audio_capture_empty")
            if self.on_state_change:
                self.on_state_change("idle")
            return None

        # Склеиваем все чанки в один массив
        audio = np.concatenate(self._buffer, axis=0)
        if self._actual_sample_rate != self.sample_rate:
            # Передискретизация, если устройство работало на другой частоте
            logger.info(
                "audio_resampling",
                from_sr=self._actual_sample_rate,
                to_sr=self.sample_rate,
            )
            audio = self._resample(audio, self._actual_sample_rate, self.sample_rate)
        # Предобработка: фильтр ВЧ + нормализация
        audio = self._highpass_filter(audio, self.sample_rate, cutoff=80.0)
        audio = self._normalize_audio(audio, target_rms=0.05)
        wav_bytes = self._encode_wav(audio)
        duration_ms = int(len(audio) / self.sample_rate * 1000)
        logger.info("audio_capture_stopped", duration_ms=duration_ms, samples=len(audio))
        if self.on_state_change:
            self.on_state_change("processing")
        return wav_bytes

    def _encode_wav(self, audio: np.ndarray) -> bytes:
        """Кодирует numpy-массив в байты WAV-файла.

        Args:
            audio: Массив отсчётов int16.

        Returns:
            Байты WAV-файла.
        """
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(np.dtype(self.dtype).itemsize)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())
        return buffer.getvalue()

    def _on_max_duration_reached(self):
        """Обработчик таймера: вызывается при достижении максимальной длительности записи."""
        if self._recording:
            logger.warning("audio_max_duration_reached", max_duration_ms=self.max_duration_ms)
            wav_bytes = self.stop()
            if self.on_max_duration:
                self.on_max_duration(wav_bytes)

    @property
    def is_recording(self) -> bool:
        """True, если в данный момент идёт запись."""
        return self._recording
