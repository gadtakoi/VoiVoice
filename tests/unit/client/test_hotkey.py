import sys
from unittest.mock import MagicMock

from src.client.hotkey import HotkeyController, _match_hotkey, _normalize_key


class FakePynputKey:
    """Вспомогательный класс для создания фейковых ключей pynput в тестах."""

    def __init__(self, name=None, char=None, vk=None):
        self._name = name
        self.char = char
        self.vk = vk

    def __str__(self):
        return f'Key.{self._name}'


class TestNormalizeKey:
    """Тесты нормализации клавиш (раскладко-независимость)."""

    def test_vk_latin_lowercase(self):
        """VK-код латинской 'v' должен определяться даже при русской раскладке."""
        key = FakePynputKey(char='м', vk=0x56)
        assert _normalize_key(key) == 'v'

    def test_vk_digit(self):
        """VK-код цифры '7' должен определяться независимо от символа."""
        key = FakePynputKey(char='&', vk=0x37)  # VK для '7'
        assert _normalize_key(key) == '7'

    def test_char_fallback(self):
        """Fallback на символ клавиши при отсутствии VK."""
        key = FakePynputKey(char='B', vk=None)
        assert _normalize_key(key) == 'b'

    def test_modifier_fallback(self):
        """Fallback для имени модификатора при отсутствии VK."""
        key = FakePynputKey(name='ctrl_l', vk=None)
        assert _normalize_key(key) == 'ctrl_l'


class TestMatchHotkey:
    """Тесты проверки совпадения комбинаций клавиш."""

    def test_simple_match(self):
        """Простое совпадение комбинации ctrl+alt+v."""
        assert _match_hotkey({'ctrl_l', 'alt_l', 'v'}, {'ctrl', 'alt', 'v'})

    def test_missing_key(self):
        """Несовпадение при отсутствующей клавише."""
        assert not _match_hotkey({'ctrl_l', 'alt_l'}, {'ctrl', 'alt', 'v'})

    def test_alias_match(self):
        """Правые модификаторы тоже должны распознаваться."""
        assert _match_hotkey({'ctrl_r', 'alt_r', 'v'}, {'ctrl', 'alt', 'v'})

    def test_alt_gr_alias(self):
        """AltGr должен считаться эквивалентом Alt."""
        assert _match_hotkey({'ctrl_l', 'alt_gr', 'v'}, {'ctrl', 'alt', 'v'})


class TestHotkeyController:
    """Тесты контроллера горячих клавиш."""

    def test_init_defaults(self):
        """Проверка дефолтных значений при инициализации."""
        hc = HotkeyController()
        assert hc.combination == 'ctrl+alt+v'
        assert not hc._listening

    def test_start_uses_pynput_on_windows(self, monkeypatch):
        """На Windows должен предпочитаться pynput, на Linux — keyboard."""
        hc = HotkeyController(on_press=lambda: None, on_release=lambda: None)

        fake_listener = MagicMock()
        fake_listener.start = MagicMock()

        def fake_start_pynput():
            hc._pynput_listener = fake_listener
            hc._listening = True

        monkeypatch.setattr(hc, '_start_pynput', fake_start_pynput)
        # Гарантируем, что keyboard не вызовется на Windows
        monkeypatch.setattr(hc, '_start_keyboard', lambda: (_ for _ in ()).throw(RuntimeError('should not be called')))

        hc.start()
        if sys.platform == 'win32':
            assert hc._backend == 'pynput'
        else:
            assert hc._backend == 'keyboard'
        assert hc._listening

    def test_pynput_release_only_when_combination_breaks(self, monkeypatch):
        """Отпускание посторонней клавиши (например, пробела) при зажатой
        комбинации НЕ должно триггерить on_release.
        """
        press_calls = []
        release_calls = []

        hc = HotkeyController(
            combination='ctrl+alt+v',
            on_press=lambda: press_calls.append(1),
            on_release=lambda: release_calls.append(1),
        )
        hc._listening = True

        # Эмулируем нажатие ctrl, alt, v
        hc._pynput_pressed = {'ctrl_l', 'alt_l', 'v'}
        hc._handle_press()
        # Даём daemon-потоку время отработать
        import time

        time.sleep(0.05)
        assert len(press_calls) == 1

        # Отпускаем постороннюю клавишу (пробел), комбинация всё ещё активна
        hc._pynput_pressed.add('space')
        was_active = _match_hotkey(hc._pynput_pressed, {'ctrl', 'alt', 'v'})
        hc._pynput_pressed.discard('space')
        still_active = _match_hotkey(hc._pynput_pressed, {'ctrl', 'alt', 'v'})
        if was_active and not still_active:
            hc._handle_release()
        time.sleep(0.05)
        assert len(release_calls) == 0

        # Теперь отпускаем v — комбинация реально разрывается
        hc._pynput_pressed = {'ctrl_l', 'alt_l', 'v'}  # восстанавливаем
        was_active = _match_hotkey(hc._pynput_pressed, {'ctrl', 'alt', 'v'})
        hc._pynput_pressed.discard('v')
        still_active = _match_hotkey(hc._pynput_pressed, {'ctrl', 'alt', 'v'})
        if was_active and not still_active:
            hc._handle_release()
        time.sleep(0.05)
        assert len(release_calls) == 1
