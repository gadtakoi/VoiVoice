import sys
import threading
from collections.abc import Callable

from loguru import logger

# Сопоставление модификаторов с возможными псевдонимами клавиш
_KEY_ALIASES = {
    'ctrl': {'ctrl_l', 'ctrl_r'},
    'alt': {'alt_l', 'alt_r', 'alt_gr'},
    'shift': {'shift_l', 'shift_r'},
    'win': {'cmd', 'cmd_l', 'cmd_r'},
}


def _normalize_key(key) -> str:
    """Приводит объект клавиши pynput к нормализованной строке.

    Использует виртуальные коды клавиш (VK) для независимости от раскладки
    при работе с латинскими буквами и цифрами.

    Args:
        key: Объект клавиши от pynput.

    Returns:
        Нормализованное строковое представление клавиши.
    """
    # Сначала пробуем виртуальный код клавиши (независимо от раскладки)
    try:
        vk = None
        if hasattr(key, 'vk') and key.vk is not None:
            vk = key.vk
        elif hasattr(key, 'value') and hasattr(key.value, 'vk'):
            vk = key.value.vk

        if vk is not None:
            # VK-коды для A-Z
            if 0x41 <= vk <= 0x5A:
                return chr(vk).lower()
            # VK-коды для 0-9
            if 0x30 <= vk <= 0x39:
                return chr(vk)
    except Exception:
        pass

    # Fallback на символ клавиши
    try:
        if hasattr(key, 'char') and key.char:
            return key.char.lower()
    except Exception:
        pass
    return str(key).replace('Key.', '').lower()


def _match_hotkey(pressed: set[str], required: set[str]) -> bool:
    """Проверяет, что нажатые клавиши соответствуют требуемой комбинации (с учётом псевдонимов).

    Args:
        pressed: Множество нажатых клавиш.
        required: Множество клавиш требуемой комбинации.

    Returns:
        True, если комбинация полностью совпадает.
    """
    for req in required:
        aliases = _KEY_ALIASES.get(req, {req})
        if not any(alias in pressed for alias in aliases):
            return False
    return True


class HotkeyController:
    """Контроллер глобальных горячих клавиш с поддержкой pynput и keyboard."""

    def __init__(
        self,
        combination: str = 'ctrl+alt+v',
        on_press: Callable | None = None,
        on_release: Callable | None = None,
    ):
        """Инициализация контроллера.

        Args:
            combination: Комбинация клавиш в формате "ctrl+alt+v".
            on_press: Колбэк при нажатии комбинации.
            on_release: Колбэк при отпускании комбинации.
        """
        self.combination = combination.lower()
        self.on_press = on_press
        self.on_release = on_release
        self._listening = False
        self._backend = 'keyboard'
        self._pynput_listener = None
        self._pynput_pressed: set[str] = set()
        self._keyboard_active = False
        self._active = False

    def start(self):
        """Запускает прослушивание горячей клавиши.

        На Windows предпочитает pynput (не требует прав администратора),
        на Linux — keyboard. При неудаче пробует fallback-бэкенд.
        """
        if sys.platform == 'win32':
            primary, fallback = self._start_pynput, self._start_keyboard
            primary_name, fallback_name = 'pynput', 'keyboard'
        else:
            primary, fallback = self._start_keyboard, self._start_pynput
            primary_name, fallback_name = 'keyboard', 'pynput'

        try:
            primary()
            self._backend = primary_name
            logger.info('hotkey_started', combination=self.combination, backend=primary_name)
        except Exception as exc:
            logger.warning(f'{primary_name}_backend_failed', error=str(exc), fallback=fallback_name)
            try:
                fallback()
                self._backend = fallback_name
                logger.info('hotkey_started', combination=self.combination, backend=fallback_name)
            except Exception as exc2:
                logger.error(
                    'hotkey_start_failed', **{f'{primary_name}_error': str(exc), f'{fallback_name}_error': str(exc2)}
                )
                raise

    def stop(self):
        """Останавливает прослушивание и освобождает хуки."""
        self._listening = False
        self._active = False
        if self._backend == 'keyboard':
            try:
                import keyboard

                keyboard.unhook_all()
            except Exception as exc:
                logger.warning('hotkey_stop_failed', error=str(exc))
        elif self._backend == 'pynput' and self._pynput_listener:
            try:
                self._pynput_listener.stop()
            except Exception as exc:
                logger.warning('pynput_stop_failed', error=str(exc))

    def _start_keyboard(self):
        """Запуск через библиотеку keyboard (хуки на уровне ОС)."""
        import keyboard

        # on_press_key ожидает одну клавишу, а не комбинацию.
        # Хукаем 'v' и вручную проверяем модификаторы.
        def on_v_press(_event=None):
            try:
                if keyboard.is_pressed('ctrl') and keyboard.is_pressed('alt'):
                    self._keyboard_active = True
                    self._handle_press()
            except Exception:
                logger.exception('keyboard_press_callback_error')

        def on_v_release(_event=None):
            try:
                if self._keyboard_active:
                    self._keyboard_active = False
                    self._handle_release()
            except Exception:
                logger.exception('keyboard_release_callback_error')

        keyboard.on_press_key('v', on_v_press)
        keyboard.on_release_key('v', on_v_release)
        self._listening = True

    def _start_pynput(self):
        """Запуск через библиотеку pynput (cross-platform)."""
        from pynput import keyboard as pynput_keyboard

        required = set(self.combination.split('+'))
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
            still_active = _match_hotkey(self._pynput_pressed, required)
            # Отпускаем только если комбинация реально разорвалась
            if was_active and not still_active:
                self._handle_release()

        self._pynput_listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
        self._pynput_listener.start()
        self._listening = True

    def _handle_press(self):
        """Внутренний обработчик нажатия (с защитой от дребезга)."""
        if not self._listening or self._active:
            return
        self._active = True
        logger.debug('hotkey_pressed')
        if self.on_press:
            # Запускаем обработчик в отдельном потоке, чтобы
            # хук pynput на Windows вернул управление немедленно.
            threading.Thread(target=self._run_press_handler, daemon=True).start()

    def _run_press_handler(self):
        """Безопасный вызов пользовательского on_press с логированием ошибок."""
        try:
            self.on_press()
        except Exception as exc:
            logger.error('hotkey_press_handler_error', error=str(exc))

    def _handle_release(self):
        """Внутренний обработчик отпускания клавиш."""
        if not self._listening:
            return
        self._active = False
        logger.debug('hotkey_released')
        if self.on_release:
            threading.Thread(target=self._run_release_handler, daemon=True).start()

    def _run_release_handler(self):
        """Безопасный вызов пользовательского on_release с логированием ошибок."""
        try:
            self.on_release()
        except Exception as exc:
            logger.error('hotkey_release_handler_error', error=str(exc))
