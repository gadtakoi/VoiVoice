from loguru import logger


class ToastNotifier:
    """Упрощённый показатель уведомлений (fallback на лог, если native toast недоступен)."""

    def __init__(self, enabled: bool = True):
        """Инициализация.

        Args:
            enabled: Включить ли уведомления.
        """
        self.enabled = enabled

    def stop(self):
        """Освобождение ресурсов (заглушка для совместимости)."""
        pass

    def show(self, title: str, message: str, duration: int = 3):
        """Показывает уведомление или записывает его в лог.

        Args:
            title: Заголовок уведомления.
            message: Текст сообщения.
            duration: Длительность показа (сек), не используется в fallback-режиме.
        """
        if not self.enabled:
            return
        # Если нативные toast недоступны, логируем в консоль
        logger.info('toast', title=title, message=message)
