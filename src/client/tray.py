import os
from collections.abc import Callable
from enum import Enum

import pystray
from loguru import logger
from PIL import Image, ImageDraw


class TrayState(Enum):
    """Возможные состояния иконки в системном трее."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    ERROR = "error"
    OFFLINE = "offline"


class TrayController:
    """Контроллер иконки в системном трее (pystray) с контекстным меню."""

    def __init__(
        self,
        on_quit: Callable | None = None,
        on_toggle_pause: Callable | None = None,
        on_language_change: Callable[[str], None] | None = None,
        on_cleanup_change: Callable[[str], None] | None = None,
    ):
        """Инициализация.

        Args:
            on_quit: Колбэк при выборе "Выход".
            on_toggle_pause: Колбэк при переключении паузы.
            on_language_change: Колбэк при смене языка.
            on_cleanup_change: Колбэк при смене режима cleanup.
        """
        self._state = TrayState.IDLE
        self._on_quit = on_quit
        self._on_toggle_pause = on_toggle_pause
        self._on_language_change = on_language_change
        self._on_cleanup_change = on_cleanup_change
        self._paused = False
        self._language = "Auto"
        self._cleanup = "LLM"
        self._icon: pystray.Icon | None = None

    def _create_icon_image(self, color: str) -> Image.Image:
        """Рисует круглую иконку заданного цвета 64×64 пикселя.

        Args:
            color: HEX-цвет заливки круга.

        Returns:
            Изображение PIL в формате RGBA.
        """
        width = 64
        height = 64
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        dc.ellipse([4, 4, width - 4, height - 4], fill=color)
        return image

    def _get_icon_for_state(self) -> Image.Image:
        """Возвращает иконку, соответствующую текущему состоянию."""
        colors = {
            TrayState.IDLE: "#000000",
            TrayState.LISTENING: "#FF0000",
            TrayState.PROCESSING: "#FFD700",
            TrayState.ERROR: "#FF4500",
            TrayState.OFFLINE: "#A9A9A9",
        }
        return self._create_icon_image(colors.get(self._state, "#808080"))

    def _get_tooltip(self) -> str:
        """Возвращает подсказку (tooltip) для текущего состояния."""
        tooltips = {
            TrayState.IDLE: f"VoiVoice — Готов ({self._language})",
            TrayState.LISTENING: "VoiVoice — Запись...",
            TrayState.PROCESSING: "VoiVoice — Обработка...",
            TrayState.ERROR: "VoiVoice — Ошибка",
            TrayState.OFFLINE: "VoiVoice — Сервисы недоступны",
        }
        return tooltips.get(self._state, "VoiVoice")

    def _build_menu(self) -> pystray.Menu:
        """Формирует контекстное меню иконки трея."""
        return pystray.Menu(
            pystray.MenuItem("VoiVoice v0.1.0", lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda text: "▶️ Возобновить" if self._paused else "⏸️ Пауза",
                self._handle_toggle_pause,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda text: f"🌐 Язык: {self._language}",
                pystray.Menu(
                    pystray.MenuItem("Auto", lambda icon, item: self._set_language("Auto")),
                    pystray.MenuItem("RU", lambda icon, item: self._set_language("RU")),
                    pystray.MenuItem("EN", lambda icon, item: self._set_language("EN")),
                ),
            ),
            pystray.MenuItem(
                lambda text: f"🧹 Cleanup: {self._cleanup}",
                pystray.Menu(
                    pystray.MenuItem("LLM", lambda icon, item: self._set_cleanup("LLM")),
                    pystray.MenuItem("None", lambda icon, item: self._set_cleanup("None")),
                ),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️ Настройки", self._handle_settings),
            pystray.MenuItem("📋 Открыть логи", self._handle_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Выход", self._handle_quit),
        )

    def _set_language(self, lang: str):
        """Устанавливает язык и обновляет меню."""
        self._language = lang
        if self._on_language_change:
            self._on_language_change(lang)
        if self._icon:
            self._icon.update_menu()
        logger.info("tray_language_changed", language=lang)

    def _set_cleanup(self, mode: str):
        """Устанавливает режим cleanup и обновляет меню."""
        self._cleanup = mode
        if self._on_cleanup_change:
            self._on_cleanup_change(mode)
        if self._icon:
            self._icon.update_menu()
        logger.info("tray_cleanup_changed", mode=mode)

    def _handle_toggle_pause(self, icon: pystray.Icon, item: pystray.MenuItem):
        """Обработчик переключения паузы из меню."""
        self._paused = not self._paused
        if self._on_toggle_pause:
            self._on_toggle_pause(self._paused)
        icon.update_menu()
        logger.info("tray_pause_toggled", paused=self._paused)

    def _handle_settings(self, icon: pystray.Icon, item: pystray.MenuItem):
        """Открывает config.yaml в редакторе по умолчанию."""
        os.startfile("config.yaml")

    def _handle_logs(self, icon: pystray.Icon, item: pystray.MenuItem):
        """Открывает папку с логами."""
        log_dir = "logs"
        if os.path.exists(log_dir):
            os.startfile(log_dir)
        else:
            logger.warning("logs_directory_not_found")

    def _handle_quit(self, icon: pystray.Icon, item: pystray.MenuItem):
        """Обработчик выхода из приложения."""
        logger.info("tray_quit_requested")
        if self._on_quit:
            self._on_quit()
        icon.stop()

    def start(self):
        """Запускает цикл отображения иконки в трее (блокирующий вызов)."""
        self._icon = pystray.Icon(
            "voivoice",
            icon=self._get_icon_for_state(),
            title=self._get_tooltip(),
            menu=self._build_menu(),
        )
        self._icon.run()

    def stop(self):
        """Останавливает иконку трея."""
        if self._icon:
            self._icon.stop()

    def set_state(self, state: TrayState):
        """Меняет состояние и обновляет иконку/подсказку.

        Args:
            state: Новое состояние.
        """
        if self._state == state:
            return
        self._state = state
        if self._icon:
            self._icon.icon = self._get_icon_for_state()
            self._icon.title = self._get_tooltip()
        logger.info("tray_state_changed", state=state.value)

    @property
    def state(self) -> TrayState:
        """Текущее состояние трея."""
        return self._state

    @property
    def paused(self) -> bool:
        """True, если клиент находится в режиме паузы."""
        return self._paused

    @property
    def language(self) -> str:
        """Выбранный в трее язык ("Auto", "RU", "EN")."""
        return self._language

    @property
    def cleanup(self) -> str:
        """Выбранный режим cleanup ("LLM", "None")."""
        return self._cleanup
