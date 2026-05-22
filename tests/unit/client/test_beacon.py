from unittest.mock import patch

from src.client.beacon import AudioBeacon


class TestAudioBeacon:
    def test_init_defaults(self):
        beacon = AudioBeacon()
        assert beacon.enabled is True
        assert beacon.volume == 0.3
        assert beacon.success is False
        assert beacon._sample_rate == 48000

    def test_init_custom(self):
        beacon = AudioBeacon(enabled=False, volume=0.8, success=True)
        assert beacon.enabled is False
        assert beacon.volume == 0.8
        assert beacon.success is True

    def test_volume_clamped(self):
        beacon = AudioBeacon(volume=2.0)
        assert beacon.volume == 1.0
        beacon2 = AudioBeacon(volume=-1.0)
        assert beacon2.volume == 0.0

    @patch('src.client.beacon.sd.play')
    def test_beep_when_enabled(self, mock_play):
        beacon = AudioBeacon(enabled=True)
        beacon._beep(800, 40)
        assert mock_play.called

    @patch('src.client.beacon.sd.play')
    def test_beep_when_disabled(self, mock_play):
        beacon = AudioBeacon(enabled=False)
        beacon._beep(800, 40)
        assert not mock_play.called

    @patch('src.client.beacon.sd.play')
    def test_start(self, mock_play):
        beacon = AudioBeacon()
        beacon.start()
        assert mock_play.call_count == 2

    @patch('src.client.beacon.sd.play')
    def test_stop(self, mock_play):
        beacon = AudioBeacon()
        beacon.stop()
        assert mock_play.call_count == 2

    @patch('src.client.beacon.sd.play')
    def test_success_beep_when_enabled(self, mock_play):
        beacon = AudioBeacon(success=True)
        beacon.success_beep()
        assert mock_play.called

    @patch('src.client.beacon.sd.play')
    def test_success_beep_when_disabled(self, mock_play):
        beacon = AudioBeacon(success=False)
        beacon.success_beep()
        assert not mock_play.called

    @patch('src.client.beacon.sd.play')
    @patch('src.client.beacon.sd.sleep')
    def test_error(self, mock_sleep, mock_play):
        beacon = AudioBeacon()
        beacon.error()
        assert mock_play.call_count == 2
        assert mock_sleep.called
