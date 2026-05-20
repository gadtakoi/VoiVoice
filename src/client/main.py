"""
VoiVoice Windows Client — entry point.

Phases 1-4: voice capture → ASR → LLM cleanup → text injection + polish.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path for both `python -m src.client.main`
# and `python src/client/main.py` launch modes.
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import time
import asyncio
import threading

from loguru import logger

from src.client.config import Config
from src.client.api_client import APIClient
from src.client.tray import TrayController, TrayState
from src.client.audio import AudioCapture
from src.client.hotkey import HotkeyController
from src.client.injector import TextInjector
from src.client.beacon import AudioBeacon
from src.client.timing import TimingLogger
from src.client.toast import ToastNotifier


class VoiVoiceClient:
    def __init__(self):
        self.config = Config.from_yaml(Path("config.yaml"))
        self.tray = TrayController(
            on_quit=self._on_quit,
            on_toggle_pause=self._on_toggle_pause,
            on_language_change=self._on_language_change,
            on_cleanup_change=self._on_cleanup_change,
        )
        self.api = APIClient(self.config.services.api_url)
        self.audio = AudioCapture(
            sample_rate=self.config.audio.sample_rate,
            channels=self.config.audio.channels,
            dtype=self.config.audio.dtype,
            chunk_duration_ms=self.config.audio.chunk_duration_ms,
            vad_threshold=self.config.audio.vad_threshold,
            silence_timeout_ms=self.config.audio.silence_timeout_ms,
            on_state_change=self._on_audio_state_change,
        )
        self.hotkey = HotkeyController(
            combination=self.config.hotkey.combination,
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )
        self.injector = TextInjector(
            method=self.config.injection.method,
            delay_ms=self.config.injection.delay_between_chars_ms,
        )
        self.beacon = AudioBeacon(
            enabled=True,
            volume=0.3,
            success=False,
        )
        self.timing = TimingLogger(
            directory=self.config.logging.directory,
            enabled=True,
        )
        self.toast = ToastNotifier(enabled=self.config.tray.show_notifications)
        self._running = True
        self._health_ok = False
        self._processing = False

    def _setup_logging(self):
        log_dir = Path(self.config.logging.directory)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "client_{time:YYYY-MM-DD}.log"
        logger.remove()
        if self.config.logging.format == "json":
            logger.add(
                str(log_file),
                rotation=f"{self.config.logging.rotation_mb} MB",
                retention=f"{self.config.logging.retention_days} days",
                serialize=True,
                level=self.config.logging.level,
            )
        else:
            logger.add(
                str(log_file),
                rotation=f"{self.config.logging.rotation_mb} MB",
                retention=f"{self.config.logging.retention_days} days",
                level=self.config.logging.level,
            )
        logger.add(sys.stdout, level=self.config.logging.level)

    def _on_quit(self):
        self._running = False
        asyncio.run_coroutine_threadsafe(self.api.close(), asyncio.get_event_loop())
        logger.info("client_quit")

    def _on_toggle_pause(self, paused: bool):
        if paused:
            self.tray.set_state(TrayState.IDLE)
            self.toast.show("VoiVoice", "⏸️ Приложение приостановлено")
        else:
            self.toast.show("VoiVoice", "▶️ Приложение возобновлено")
        logger.info("client_pause_toggled", paused=paused)

    def _on_language_change(self, lang: str):
        logger.info("language_changed", language=lang)

    def _on_cleanup_change(self, mode: str):
        self.config.services.cleanup_enabled = (mode != "None")
        logger.info("cleanup_mode_changed", mode=mode)

    def _on_audio_state_change(self, state: str):
        if state == "listening":
            self.tray.set_state(TrayState.LISTENING)
        elif state == "processing":
            self.tray.set_state(TrayState.PROCESSING)
        elif state == "idle":
            self.tray.set_state(TrayState.IDLE)

    def _on_hotkey_press(self):
        if self.tray.paused or self._processing:
            return
        try:
            self.timing.start(f"trace-{int(time.time() * 1000)}")
            self.timing.mark("hotkey_press")
            self.beacon.start()
            self.audio.start()
            self.timing.mark("capture_start")
        except Exception as exc:
            logger.error("audio_start_failed", error=str(exc))
            self.beacon.error()
            self.tray.set_state(TrayState.ERROR)

    def _on_hotkey_release(self):
        if not self.audio.is_recording:
            return
        try:
            self.beacon.stop()
            self.timing.mark("capture_duration")
            wav_bytes = self.audio.stop()
            if wav_bytes:
                self._processing = True
                asyncio.create_task(self._process_audio(wav_bytes))
            else:
                self.timing.finish()
                self.tray.set_state(TrayState.IDLE)
        except Exception as exc:
            logger.error("audio_stop_failed", error=str(exc))
            self.beacon.error()
            self.tray.set_state(TrayState.ERROR)
            self._processing = False
            self.timing.finish()

    async def _process_audio(self, wav_bytes: bytes):
        start_time = time.perf_counter()
        trace_id = self.timing._current_trace or "unknown"
        try:
            self.timing.mark("vad_process")
            self.timing.mark("encode_wav")

            language_map = {"Auto": "auto", "RU": "ru", "EN": "en"}
            language = language_map.get(self.tray.language, "auto")
            cleanup = self.config.services.cleanup_enabled

            self.timing.mark("network_upload")
            result = await self.api.transcribe(
                audio_bytes=wav_bytes,
                language=language,
                cleanup=cleanup,
                max_attempts=self.config.retry.asr.max_attempts,
                base_delay=self.config.retry.asr.base_delay,
                multiplier=self.config.retry.asr.multiplier,
            )
            self.timing.mark("network_download")

            raw = result.get("raw", "")
            cleaned = result.get("cleaned", raw)
            processing_ms = result.get("processing_ms", 0)
            total_ms = int((time.perf_counter() - start_time) * 1000)

            logger.info(
                "transcription_complete",
                trace_id=trace_id,
                raw=raw,
                cleaned=cleaned,
                processing_ms=processing_ms,
                total_ms=total_ms,
            )

            self.timing.mark("text_inject")
            success = self.injector.inject(cleaned)
            self.timing.finish(text_length=len(cleaned), language=language)

            if success:
                self.beacon.success_beep()
                self.toast.show("VoiVoice", "✅ Транскрипция готова")
            else:
                self.beacon.error()
                self.toast.show("VoiVoice", "⚠️ Ошибка вставки текста")
                self.tray.set_state(TrayState.ERROR)
                return

            self.tray.set_state(TrayState.IDLE)
        except Exception as exc:
            logger.error("transcription_failed", trace_id=trace_id, error=str(exc))
            self.beacon.error()
            self.toast.show("VoiVoice", f"⚠️ Ошибка: {type(exc).__name__}")
            self.tray.set_state(TrayState.ERROR)
            self.timing.finish()
        finally:
            self._processing = False

    async def _health_loop(self):
        while self._running:
            if self.tray.paused:
                await asyncio.sleep(5)
                continue
            try:
                result = await self.api.health()
                ok = result.get("status") == "ok"
                if ok and not self._health_ok:
                    if not self.audio.is_recording and not self._processing:
                        self.tray.set_state(TrayState.IDLE)
                    self._health_ok = True
                elif not ok and self._health_ok:
                    if not self.audio.is_recording and not self._processing:
                        self.tray.set_state(TrayState.OFFLINE)
                    self._health_ok = False
                logger.debug("healthcheck", status=result.get("status"), services=result.get("services"))
            except Exception as exc:
                if self._health_ok:
                    if not self.audio.is_recording and not self._processing:
                        self.tray.set_state(TrayState.OFFLINE)
                    self._health_ok = False
                logger.warning("healthcheck_failed", error=type(exc).__name__)
            await asyncio.sleep(10)

    async def run(self):
        self._setup_logging()
        logger.info("client_starting", version=self.config.app_version)

        tray_thread = threading.Thread(target=self.tray.start, daemon=True)
        tray_thread.start()
        await asyncio.sleep(1)

        try:
            self.hotkey.start()
        except Exception as exc:
            logger.error("hotkey_init_failed", error=str(exc))
            self.tray.set_state(TrayState.ERROR)

        self.toast.show("VoiVoice", "🎤 Готов к работе. Нажмите Ctrl+Alt+V")

        try:
            await self._health_loop()
        except asyncio.CancelledError:
            pass
        finally:
            self.hotkey.stop()
            self.tray.stop()
            self.timing.close()
            await self.api.close()
            logger.info("client_stopped")


def main():
    client = VoiVoiceClient()
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        logger.info("client_interrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
