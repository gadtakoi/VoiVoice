from loguru import logger


class ToastNotifier:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._notifier = None
        if enabled:
            try:
                from windows_toasts import Toast, WindowsToaster
                self._toaster = WindowsToaster("VoiVoice")
                self._notifier = "windows_toasts"
            except Exception as exc:
                logger.warning("toast_init_failed", error=str(exc))
                self._notifier = None

    def show(self, title: str, message: str, duration: int = 3):
        if not self.enabled or not self._notifier:
            return
        try:
            if self._notifier == "windows_toasts":
                from windows_toasts import Toast
                toast = Toast()
                toast.text_fields = [title, message]
                self._toaster.show_toast(toast)
        except Exception as exc:
            logger.warning("toast_show_failed", error=str(exc))
