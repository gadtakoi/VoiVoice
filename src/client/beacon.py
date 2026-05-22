import numpy as np
import sounddevice as sd


class AudioBeacon:
    """Генератор коротких звуковых сигналов (бипов) для аудио-обратной связи."""

    def __init__(
        self,
        enabled: bool = True,
        volume: float = 0.3,
        success: bool = False,
    ):
        """Инициализация бипера.

        Args:
            enabled: Включить ли звуковые сигналы.
            volume: Громкость от 0.0 до 1.0.
            success: Включить ли звук успешного завершения.
        """
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))
        self.success = success
        self._sample_rate = 48000

    def _beep(self, freq: int, duration_ms: int):
        """Воспроизводит синусоидальный тон заданной частоты и длительности.

        Args:
            freq: Частота тона (Гц).
            duration_ms: Длительность (мс).
        """
        if not self.enabled:
            return
        # Генерируем временную шкалу
        t = np.linspace(0, duration_ms / 1000, int(self._sample_rate * duration_ms / 1000))
        # Синусоида с затуханием амплитуды к концу
        wave = np.sin(2 * np.pi * freq * t) * self.volume
        wave *= np.linspace(0.3, 0, len(wave))  # fade out
        sd.play(wave, self._sample_rate)

    def start(self):
        """Воспроизводит восходящий тон: 800 Гц → 1200 Гц (сигнал начала записи)."""
        self._beep(800, 40)
        self._beep(1200, 40)

    def stop(self):
        """Воспроизводит нисходящий тон: 1200 Гц → 800 Гц (сигнал окончания записи)."""
        self._beep(1200, 40)
        self._beep(800, 40)

    def success_beep(self):
        """Высокий короткий звук — успешное завершение операции."""
        if self.success:
            self._beep(1500, 50)

    def error(self):
        """Двойной низкий тон — ошибка."""
        self._beep(300, 150)
        sd.sleep(100)
        self._beep(300, 150)
