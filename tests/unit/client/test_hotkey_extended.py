from unittest.mock import MagicMock, patch

from src.client.hotkey import HotkeyController, _match_hotkey, _normalize_key


class FakePynputKey:
    def __init__(self, name=None, char=None, vk=None):
        self._name = name
        self.char = char
        self.vk = vk

    def __str__(self):
        return f'Key.{self._name}'


class TestNormalizeKeyExtended:
    def test_vk_none_fallback(self):
        key = FakePynputKey(name='ctrl', vk=None)
        assert _normalize_key(key) == 'ctrl'

    def test_exception_in_vk(self):
        class BadKey:
            @property
            def vk(self):
                raise RuntimeError('bad')

        result = _normalize_key(BadKey())
        assert 'badkey' in result.lower() or result == ''


class TestMatchHotkeyExtended:
    def test_empty_required(self):
        assert _match_hotkey({'ctrl'}, set()) is True

    def test_empty_pressed(self):
        assert _match_hotkey(set(), {'ctrl'}) is False


class TestHotkeyControllerExtended:
    def test_stop_keyboard(self):
        hc = HotkeyController()
        hc._backend = 'keyboard'
        hc._listening = True
        with patch.dict('sys.modules', {'keyboard': MagicMock()}):
            hc.stop()
        assert hc._listening is False

    def test_stop_pynput(self):
        hc = HotkeyController()
        hc._backend = 'pynput'
        hc._pynput_listener = MagicMock()
        hc.stop()
        hc._pynput_listener.stop.assert_called_once()

    def test_stop_pynput_exception(self):
        hc = HotkeyController()
        hc._backend = 'pynput'
        listener = MagicMock()
        listener.stop.side_effect = RuntimeError('fail')
        hc._pynput_listener = listener
        hc.stop()

    def test_handle_press_not_listening(self):
        hc = HotkeyController(on_press=lambda: None)
        hc._listening = False
        hc._handle_press()
        assert hc._active is False

    def test_handle_press_already_active(self):
        hc = HotkeyController(on_press=lambda: None)
        hc._listening = True
        hc._active = True
        hc._handle_press()
        assert hc._active is True

    def test_handle_press_no_callback(self):
        hc = HotkeyController()
        hc._listening = True
        hc._handle_press()
        assert hc._active is True

    def test_run_press_handler_error(self):
        def bad():
            raise RuntimeError('fail')

        hc = HotkeyController(on_press=bad)
        hc._run_press_handler()

    def test_handle_release_not_listening(self):
        hc = HotkeyController(on_release=lambda: None)
        hc._listening = False
        hc._handle_release()
        assert hc._active is False

    def test_handle_release_no_callback(self):
        hc = HotkeyController()
        hc._listening = True
        hc._handle_release()
        assert hc._active is False

    def test_run_release_handler_error(self):
        def bad():
            raise RuntimeError('fail')

        hc = HotkeyController(on_release=bad)
        hc._run_release_handler()

    def test_start_fallback(self, monkeypatch):
        hc = HotkeyController(on_press=lambda: None, on_release=lambda: None)
        monkeypatch.setattr(hc, '_start_pynput', lambda: (_ for _ in ()).throw(RuntimeError('pynput fail')))
        monkeypatch.setattr(hc, '_start_keyboard', lambda: setattr(hc, '_listening', True))
        with patch('sys.platform', 'win32'):
            hc.start()
        # На Windows primary=pynput, fallback=keyboard. pynput упал -> keyboard
        assert hc._backend == 'keyboard'
        assert hc._listening is True

    def test_start_both_fail(self, monkeypatch):
        import pytest as pt

        hc = HotkeyController(on_press=lambda: None, on_release=lambda: None)
        monkeypatch.setattr(hc, '_start_pynput', lambda: (_ for _ in ()).throw(RuntimeError('fail')))
        monkeypatch.setattr(hc, '_start_keyboard', lambda: (_ for _ in ()).throw(RuntimeError('fail')))
        with pt.raises(RuntimeError):
            hc.start()
