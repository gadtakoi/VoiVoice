from typing import Callable, Optional, Set
from loguru import logger


_KEY_ALIASES = {
    "ctrl": {"ctrl_l", "ctrl_r"},
    "alt": {"alt_l", "alt_r"},
    "shift": {"shift_l", "shift_r"},
    "win": {"cmd", "cmd_l", "cmd_r"},
}


def _normalize_key(key) -> str:
    """Convert pynput key to normalized string."""
    try:
        if hasattr(key, "char") and key.char:
            return key.char.lower()
    except Exception:
        pass
    return str(key).replace("Key.", "").lower()


def _match_hotkey(pressed: Set[str], required: Set[str]) -> bool:
    """Check if pressed keys match required combination (with aliases)."""
    for req in required:
        aliases = _KEY_ALIASES.get(req, {req})
        if not any(alias in pressed for alias in aliases):
            return False
    return True


class HotkeyController:
    def __init__(
        self,
        combination: str = "ctrl+alt+v",
        on_press: Optional[Callable] = None,
        on_release: Optional[Callable] = None,
    ):
        self.combination = combination.lower()
        self.on_press = on_press
        self.on_release = on_release
        self._listening = False
        self._backend = "keyboard"
        self._pynput_listener = None
        self._pynput_pressed: Set[str] = set()

    def start(self):
        try:
            self._start_keyboard()
            self._backend = "keyboard"
            logger.info("hotkey_started", combination=self.combination, backend="keyboard")
        except Exception as exc:
            logger.warning("keyboard_backend_failed", error=str(exc), fallback="pynput")
            try:
                self._start_pynput()
                self._backend = "pynput"
                logger.info("hotkey_started", combination=self.combination, backend="pynput")
            except Exception as exc2:
                logger.error("hotkey_start_failed", keyboard_error=str(exc), pynput_error=str(exc2))
                raise

    def stop(self):
        self._listening = False
        if self._backend == "keyboard":
            try:
                import keyboard
                keyboard.unhook_all()
            except Exception as exc:
                logger.warning("hotkey_stop_failed", error=str(exc))
        elif self._backend == "pynput" and self._pynput_listener:
            try:
                self._pynput_listener.stop()
            except Exception as exc:
                logger.warning("pynput_stop_failed", error=str(exc))

    def _start_keyboard(self):
        import keyboard
        keyboard.on_press_key(self.combination, lambda _: self._handle_press())
        keyboard.on_release_key(self.combination, lambda _: self._handle_release())
        self._listening = True

    def _start_pynput(self):
        from pynput import keyboard as pynput_keyboard

        required = set(self.combination.split("+"))
        self._pynput_pressed = set()

        def on_press(key):
            k = _normalize_key(key)
            self._pynput_pressed.add(k)
            if _match_hotkey(self._pynput_pressed, required):
                self._handle_press()

        def on_release(key):
            k = _normalize_key(key)
            was_active = _match_hotkey(self._pynput_pressed, required)
            self._pynput_pressed.discard(k)
            if was_active:
                self._handle_release()

        self._pynput_listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
        self._pynput_listener.start()
        self._listening = True

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
