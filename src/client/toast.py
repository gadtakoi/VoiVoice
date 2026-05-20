from loguru import logger


class ToastNotifier:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def stop(self):
        pass

    def show(self, title: str, message: str, duration: int = 3):
        if not self.enabled:
            return
        # Fallback to tray tooltip / console logging if native toast fails
        logger.info("toast", title=title, message=message)
