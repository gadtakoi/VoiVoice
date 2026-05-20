"""Быстрая диагностика доступа к микрофону Windows."""
import ctypes
from ctypes import wintypes

print("=== Диагностика микрофона ===\n")

# 1. Проверка waveInOpen (Windows MME)
winmm = ctypes.windll.winmm

class WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('wFormatTag', wintypes.WORD),
        ('nChannels', wintypes.WORD),
        ('nSamplesPerSec', wintypes.DWORD),
        ('nAvgBytesPerSec', wintypes.DWORD),
        ('nBlockAlign', wintypes.WORD),
        ('wBitsPerSample', wintypes.WORD),
        ('cbSize', wintypes.WORD),
    ]

hwi = wintypes.HANDLE()
wf = WAVEFORMATEX()
wf.wFormatTag = 1  # PCM
wf.nChannels = 2
wf.nSamplesPerSec = 48000
wf.wBitsPerSample = 16
wf.nBlockAlign = 4
wf.nAvgBytesPerSec = 192000
wf.cbSize = 0

result = winmm.waveInOpen(ctypes.byref(hwi), -1, ctypes.byref(wf), 0, 0, 0)
if result == 0:
    print("[OK]  waveInOpen (MME) работает")
    winmm.waveInClose(hwi)
else:
    print(f"[FAIL] waveInOpen (MME) вернул ошибку: {result}")

# 2. Проверка WASAPI capture через pycaw/comtypes
try:
    import ctypes.util
    _orig = ctypes.util.find_library
    ctypes.util.find_library = lambda name: name + '.dll' if name in (
        'ole32', 'kernel32', 'user32', 'advapi32', 'shell32', 'winmm', 'oleaut32'
    ) else _orig(name)

    from pycaw.pycaw import AudioUtilities
    from pycaw.api.audioclient import IAudioClient
    from pycaw.api.endpointvolume import IAudioEndpointVolume
    from pycaw.constants import AudioDeviceState
    from comtypes import CLSCTX_ALL
    import warnings
    warnings.filterwarnings('ignore')

    capture_ok = False
    for dev in AudioUtilities.GetAllDevices():
        if dev.state != AudioDeviceState.Active:
            continue
        try:
            # Render устройства поддерживают IAudioEndpointVolume, capture — нет
            dev._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            continue  # Это render (динамики), пропускаем
        except Exception:
            pass  # Это capture (микрофон)

        try:
            unk = dev._dev.Activate(IAudioClient._iid_, CLSCTX_ALL, None)
            ac = unk.QueryInterface(IAudioClient)
            fmt = ac.GetMixFormat()
            hr = ac.Initialize(0, 0, 0, 0, fmt[0], None)
            if hr == 0:
                print(f"[OK]  WASAPI Initialize работает ({dev.FriendlyName})")
                capture_ok = True
            else:
                print(f"[FAIL] WASAPI Initialize вернул 0x{hr & 0xFFFFFFFF:08X} ({dev.FriendlyName})")
        except Exception as e:
            print(f"[FAIL] WASAPI ошибка для {dev.FriendlyName}: {e}")

    if not capture_ok:
        print("[FAIL] WASAPI Initialize не работает ни на одном микрофоне")
except Exception as e:
    print(f"[SKIP] WASAPI тест не удался: {e}")

print("\n=== Конец диагностики ===")
