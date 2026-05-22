from unittest.mock import MagicMock, patch

from src.client.tray import TrayController, TrayState


class TestTrayController:
    def test_init_defaults(self):
        tray = TrayController()
        assert tray.state == TrayState.IDLE
        assert tray.paused is False
        assert tray.language == 'Auto'
        assert tray.cleanup == 'LLM'

    def test_init_callbacks(self):
        def cb():
            pass

        tray = TrayController(on_quit=cb, on_toggle_pause=cb, on_language_change=cb, on_cleanup_change=cb)
        assert tray._on_quit is cb

    def test_set_state_changes(self):
        tray = TrayController()
        tray.set_state(TrayState.LISTENING)
        assert tray.state == TrayState.LISTENING

    def test_set_state_same_noop(self):
        tray = TrayController()
        tray.set_state(TrayState.IDLE)
        assert tray.state == TrayState.IDLE

    def test_set_state_updates_icon_when_present(self):
        tray = TrayController()
        tray._icon = MagicMock()
        tray.set_state(TrayState.PROCESSING)
        assert tray._icon.icon is not None
        assert tray._icon.title is not None

    def test_paused_property(self):
        tray = TrayController()
        assert tray.paused is False

    def test_language_property(self):
        tray = TrayController()
        assert tray.language == 'Auto'

    def test_cleanup_property(self):
        tray = TrayController()
        assert tray.cleanup == 'LLM'

    def test_set_language(self):
        tray = TrayController()
        tray._set_language('RU')
        assert tray.language == 'RU'

    def test_set_language_callback(self):
        cb = MagicMock()
        tray = TrayController(on_language_change=cb)
        tray._set_language('EN')
        cb.assert_called_once_with('EN')

    def test_set_cleanup(self):
        tray = TrayController()
        tray._set_cleanup('None')
        assert tray.cleanup == 'None'

    def test_set_cleanup_callback(self):
        cb = MagicMock()
        tray = TrayController(on_cleanup_change=cb)
        tray._set_cleanup('None')
        cb.assert_called_once_with('None')

    def test_handle_toggle_pause(self):
        tray = TrayController()
        icon = MagicMock()
        tray._handle_toggle_pause(icon, None)
        assert tray.paused is True
        icon.update_menu.assert_called_once()

    def test_handle_toggle_pause_callback(self):
        cb = MagicMock()
        tray = TrayController(on_toggle_pause=cb)
        tray._handle_toggle_pause(MagicMock(), None)
        cb.assert_called_once_with(True)

    @patch('src.client.tray.os.startfile')
    def test_handle_settings(self, mock_startfile):
        tray = TrayController()
        tray._handle_settings(MagicMock(), None)
        mock_startfile.assert_called_once_with('config.yaml')

    @patch('src.client.tray.os.path.exists')
    @patch('src.client.tray.os.startfile')
    def test_handle_logs_exists(self, mock_startfile, mock_exists):
        mock_exists.return_value = True
        tray = TrayController()
        tray._handle_logs(MagicMock(), None)
        mock_startfile.assert_called_once_with('logs')

    @patch('src.client.tray.os.path.exists')
    def test_handle_logs_not_exists(self, mock_exists):
        mock_exists.return_value = False
        tray = TrayController()
        tray._handle_logs(MagicMock(), None)

    def test_handle_quit(self):
        cb = MagicMock()
        tray = TrayController(on_quit=cb)
        icon = MagicMock()
        tray._handle_quit(icon, None)
        cb.assert_called_once()
        icon.stop.assert_called_once()

    def test_stop_no_icon(self):
        tray = TrayController()
        assert tray.stop() is None

    def test_stop_with_icon(self):
        tray = TrayController()
        tray._icon = MagicMock()
        tray.stop()
        tray._icon.stop.assert_called_once()

    def test_get_tooltip(self):
        tray = TrayController()
        assert 'Готов' in tray._get_tooltip()
        tray.set_state(TrayState.LISTENING)
        assert 'Запись' in tray._get_tooltip()

    def test_build_menu(self):
        tray = TrayController()
        menu = tray._build_menu()
        assert menu is not None

    def test_create_icon_image(self):
        tray = TrayController()
        img = tray._create_icon_image('#FF0000')
        assert img is not None
        assert img.size == (64, 64)
