from unittest.mock import MagicMock, patch

import pytest

from src.client.injector import TextInjector


class TestTextInjector:
    def test_init_defaults(self):
        injector = TextInjector()
        assert injector.method == 'sendinput'
        assert injector.delay_ms == 10

    def test_init_custom(self):
        injector = TextInjector(method='clipboard', delay_ms=50)
        assert injector.method == 'clipboard'
        assert injector.delay_ms == 50

    def test_inject_empty_text(self):
        injector = TextInjector()
        assert injector.inject('') is True

    @patch('src.client.injector.TextInjector._send_input')
    def test_inject_sendinput_success(self, mock_send):
        injector = TextInjector(method='sendinput')
        assert injector.inject('hello') is True
        mock_send.assert_called_once_with('hello')

    @patch('src.client.injector.TextInjector._send_input')
    @patch('src.client.injector.TextInjector._clipboard_inject')
    def test_inject_sendinput_fallback(self, mock_clipboard, mock_send):
        mock_send.side_effect = RuntimeError('fail')
        injector = TextInjector(method='sendinput')
        result = injector.inject('hello')
        assert result is mock_clipboard.return_value
        mock_clipboard.assert_called_once_with('hello')

    @patch('src.client.injector.TextInjector._clipboard_inject')
    def test_inject_clipboard(self, mock_clipboard):
        injector = TextInjector(method='clipboard')
        injector.inject('hello')
        mock_clipboard.assert_called_once_with('hello')

    @patch('src.client.injector.time.sleep')
    def test_send_input(self, mock_sleep):
        injector = TextInjector(delay_ms=0)
        # 'hi' = 2 символа * 2 события (down+up) = 4 inputs
        with patch.object(injector._user32, 'SendInput', return_value=4) as mock_send:
            injector._send_input('hi')
            assert mock_send.called

    @patch('src.client.injector.time.sleep')
    def test_send_input_failure(self, mock_sleep):
        injector = TextInjector(delay_ms=0)
        with (
            patch.object(injector._user32, 'SendInput', return_value=1),
            pytest.raises(RuntimeError, match='SendInput sent'),
        ):
            injector._send_input('hi')

    @patch('src.client.injector.logger.error')
    def test_clipboard_inject_import_error(self, mock_log):
        injector = TextInjector()
        with patch.dict('sys.modules', {'win32clipboard': None}):
            result = injector._clipboard_inject('text')
        assert result is False

    @patch('src.client.injector.logger.info')
    def test_clipboard_inject_success(self, mock_log):
        injector = TextInjector()
        mock_clip = MagicMock()
        mock_con = MagicMock()
        mock_con.CF_UNICODETEXT = 13
        with patch.dict('sys.modules', {'win32clipboard': mock_clip, 'win32con': mock_con}):
            result = injector._clipboard_inject('hello')
        assert result is True
        mock_clip.OpenClipboard.assert_called_once()
        mock_clip.EmptyClipboard.assert_called_once()
        mock_clip.SetClipboardText.assert_called_once_with('hello', 13)
        mock_clip.CloseClipboard.assert_called_once()
