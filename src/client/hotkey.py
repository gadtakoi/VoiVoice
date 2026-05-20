import threading
from typing import Callable, Optional
from loguru import logger


class HotkeyController:
    def __init__(
        self,
        combination: str = "ctrl+alt+v",
        on_press: Optional[Callable] = None,
        on_release: Optional[Callable] = None,
    ):
        self.combination = combination
        self.on_press = on_press
        self.on_release = on_release
        self._listening = False
        self._hook_handle = None

    def start(self):
        try:
            import keyboard
            keyboard.on_press_key(self.combination, lambda _: self._handle_press())
            keyboard.on_release_key(self.combination, lambda _: self._handle_release())
            self._listening = True
            logger.info("hotkey_started", combination=self.combination)
        except Exception as exc:
            logger.error("hotkey_start_failed", error=str(exc))
            raise

    def stop(self):
        try:
            import keyboard
            keyboard.unhook_all()
            self._listening = False
            logger.info("hotkey_stopped")
        except Exception as exc:
            logger.warning("hotkey_stop_failed", error=str(exc))

    def _handle_press(self):
        if not self._listening:
            return
        logger.debug("hotkey_pressed")
        if self.on_press:
            try:
                self.on_press()
            except Exception as exc:
                logger.error("hotkey_press_handler_error", error=str(exc))

    def _handle_release(self):
        if not self._listening:
            return
        logger.debug("hotkey_released")
        if self.on_release:
            try:
                self.on_release()
            except Exception as exc:
                logger.error("hotkey_release_handler_error", error=str(exc))
