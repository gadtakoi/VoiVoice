import numpy as np
import sounddevice as sd


class AudioBeacon:
    def __init__(
        self,
        enabled: bool = True,
        volume: float = 0.3,
        success: bool = False,
    ):
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))
        self.success = success
        self._sample_rate = 48000

    def _beep(self, freq: int, duration_ms: int):
        if not self.enabled:
            return
        t = np.linspace(0, duration_ms / 1000, int(self._sample_rate * duration_ms / 1000))
        wave = np.sin(2 * np.pi * freq * t) * self.volume
        wave *= np.linspace(0.3, 0, len(wave))  # fade out
        sd.play(wave, self._sample_rate)

    def start(self):
        """Ascending tone: 800Hz -> 1200Hz."""
        self._beep(800, 40)
        self._beep(1200, 40)

    def stop(self):
        """Descending tone: 1200Hz -> 800Hz."""
        self._beep(1200, 40)
        self._beep(800, 40)

    def success_beep(self):
        """High pitch ding."""
        if self.success:
            self._beep(1500, 50)

    def error(self):
        """Double low tone."""
        self._beep(300, 150)
        sd.sleep(100)
        self._beep(300, 150)
