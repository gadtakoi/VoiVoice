import sys
from unittest.mock import MagicMock

import pytest

from src.client.hotkey import _normalize_key, _match_hotkey, HotkeyController


class FakePynputKey:
    """Helper to build fake pynput keys."""

    def __init__(self, name=None, char=None, vk=None):
        self._name = name
        self.char = char
        self.vk = vk

    def __str__(self):
        return f"Key.{self._name}"


class TestNormalizeKey:
    def test_vk_latin_lowercase(self):
        # VK 0x56 = 'v', even with Russian layout char='м'
        key = FakePynputKey(char="м", vk=0x56)
        assert _normalize_key(key) == "v"

    def test_vk_digit(self):
        key = FakePynputKey(char="&", vk=0x37)  # VK for '7'
        assert _normalize_key(key) == "7"

    def test_char_fallback(self):
        key = FakePynputKey(char="B", vk=None)
        assert _normalize_key(key) == "b"

    def test_modifier_fallback(self):
        key = FakePynputKey(name="ctrl_l", vk=None)
        assert _normalize_key(key) == "ctrl_l"


class TestMatchHotkey:
    def test_simple_match(self):
        assert _match_hotkey({"ctrl_l", "alt_l", "v"}, {"ctrl", "alt", "v"})

    def test_missing_key(self):
        assert not _match_hotkey({"ctrl_l", "alt_l"}, {"ctrl", "alt", "v"})

    def test_alias_match(self):
        assert _match_hotkey({"ctrl_r", "alt_r", "v"}, {"ctrl", "alt", "v"})


class TestHotkeyController:
    def test_init_defaults(self):
        hc = HotkeyController()
        assert hc.combination == "ctrl+alt+v"
        assert not hc._listening

    def test_start_uses_pynput_on_windows(self, monkeypatch):
        hc = HotkeyController(on_press=lambda: None, on_release=lambda: None)

        fake_listener = MagicMock()
        fake_listener.start = MagicMock()

        def fake_start_pynput():
            hc._pynput_listener = fake_listener
            hc._listening = True

        monkeypatch.setattr(hc, "_start_pynput", fake_start_pynput)
        # Ensure keyboard is never called on Windows
        monkeypatch.setattr(hc, "_start_keyboard", lambda: (_ for _ in ()).throw(RuntimeError("should not be called")))

        hc.start()
        if sys.platform == "win32":
            assert hc._backend == "pynput"
        else:
            assert hc._backend == "keyboard"
        assert hc._listening
