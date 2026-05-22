import ctypes
import time

from loguru import logger


class TextInjector:
    """Инжектор текста в активное окно через SendInput или буфер обмена."""

    def __init__(self, method: str = 'sendinput', delay_ms: int = 10):
        """Инициализация инжектора.

        Args:
            method: Способ вставки — "sendinput" или "clipboard".
            delay_ms: Задержка между символами (мс), только для sendinput.
        """
        self.method = method
        self.delay_ms = delay_ms
        self._user32 = ctypes.windll.user32

    def inject(self, text: str) -> bool:
        """Вставляет текст в активное окно выбранным способом.

        Args:
            text: Текст для вставки.

        Returns:
            True при успехе, False при ошибке.
        """
        if not text:
            return True
        if self.method == 'sendinput':
            try:
                self._send_input(text)
                logger.info('text_injected', method='sendinput', length=len(text))
                return True
            except Exception as exc:
                logger.warning('sendinput_failed', error=str(exc), fallback='clipboard')
                return self._clipboard_inject(text)
        else:
            return self._clipboard_inject(text)

    def _send_input(self, text: str):
        """Низкоуровневая вставка через Win32 SendInput с Unicode-символами.

        Args:
            text: Текст для посимвольной отправки.
        """
        INPUT_KEYBOARD = 1
        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ('wVk', ctypes.c_ushort),
                ('wScan', ctypes.c_ushort),
                ('dwFlags', ctypes.c_ulong),
                ('time', ctypes.c_ulong),
                ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong)),
            ]

        class INPUT_I(ctypes.Union):
            _fields_ = [('ki', KEYBDINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [('type', ctypes.c_ulong), ('ii', INPUT_I)]

        inputs = []
        for char in text:
            # Нажатие клавиши
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.ii.ki.wVk = 0
            inp.ii.ki.wScan = ord(char)
            inp.ii.ki.dwFlags = KEYEVENTF_UNICODE
            inp.ii.ki.time = 0
            inp.ii.ki.dwExtraInfo = None
            inputs.append(inp)

            # Отпускание клавиши
            inp_up = INPUT()
            inp_up.type = INPUT_KEYBOARD
            inp_up.ii.ki.wVk = 0
            inp_up.ii.ki.wScan = ord(char)
            inp_up.ii.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            inp_up.ii.ki.time = 0
            inp_up.ii.ki.dwExtraInfo = None
            inputs.append(inp_up)

        nInputs = len(inputs)
        LPINPUT = INPUT * nInputs
        pInputs = LPINPUT(*inputs)
        cbSize = ctypes.sizeof(INPUT)
        sent = self._user32.SendInput(nInputs, pInputs, cbSize)
        if sent != nInputs:
            raise RuntimeError(f'SendInput sent {sent}/{nInputs} events')
        if self.delay_ms > 0:
            # Имитируем естественный ввод с задержкой
            time.sleep(self.delay_ms / 1000.0 * len(text))

    def _clipboard_inject(self, text: str) -> bool:
        """Резервный способ вставки через системный буфер обмена.

        Args:
            text: Текст для копирования.

        Returns:
            True при успехе, False при ошибке.
        """
        try:
            import win32clipboard
            import win32con

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            logger.info('text_injected', method='clipboard', length=len(text))
            return True
        except Exception as exc:
            logger.error('clipboard_inject_failed', error=str(exc))
            return False
