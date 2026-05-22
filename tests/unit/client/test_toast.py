from unittest.mock import patch

from src.client.toast import ToastNotifier


class TestToastNotifier:
    def test_init_enabled(self):
        toast = ToastNotifier(enabled=True)
        assert toast.enabled is True

    def test_init_disabled(self):
        toast = ToastNotifier(enabled=False)
        assert toast.enabled is False

    def test_stop_does_nothing(self):
        toast = ToastNotifier()
        assert toast.stop() is None

    @patch('src.client.toast.logger.info')
    def test_show_when_enabled(self, mock_log):
        toast = ToastNotifier(enabled=True)
        toast.show('Test Title', 'Test Message', duration=5)
        mock_log.assert_called_once_with('toast', title='Test Title', message='Test Message')

    @patch('src.client.toast.logger.info')
    def test_show_when_disabled(self, mock_log):
        toast = ToastNotifier(enabled=False)
        toast.show('Test Title', 'Test Message')
        assert not mock_log.called
