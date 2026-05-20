# VoiVoice

System-wide AI voice dictation for Windows. Local-only inference via Docker Compose. Press and hold `Ctrl+Alt+V`, speak, release — clean text appears in any active text field.

## Features

- 🎙️ **Voice-to-text** in any Windows application
- 🔒 **100% local** — no cloud, no data leaks
- 🧠 **AI cleanup** via local LLM (Ollama)
- 🌐 **Bilingual** — Russian + English (auto-detect)
- 💻 **CPU-only** — works on laptops without GPU
- 🔧 **Configurable** — models, hotkeys, cleanup modes

## Requirements

- Windows 10/11
- Python 3.14+
- Docker Desktop with WSL2 backend
- 4GB+ RAM (8GB recommended)

## Quick Start

1. **Clone and enter the directory:**
   ```bash
   git clone <repo-url>
   cd VoiVoice
   ```

2. **Start Docker services:**
   ```bash
   docker-compose up -d
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -e .
   ```

4. **Run the client:**
   ```bash
   python -m src.client.main
   ```

   Or double-click `start.bat`.

5. **Use it:**
   - Hold `Ctrl+Alt+V`
   - Speak
   - Release — text appears in the active window

## Architecture

```
Windows Host
  ├── VoiVoice Client (Python)
  │     ├── Global Hotkey (keyboard)
  │     ├── Audio Capture (sounddevice)
  │     ├── System Tray (pystray)
  │     └── Text Injection (SendInput / clipboard)
  │
  └── Docker Desktop (WSL2)
        ├── ASR: faster-whisper-server (CPU, INT8)
        ├── LLM: Ollama (llama3.2:3b, Q4_K_M)
        ├── LanguageTool (optional grammar check)
        └── API Gateway (FastAPI)
```

## Configuration

Edit `config.yaml` to customize:

```yaml
hotkey:
  combination: "ctrl+alt+v"

audio:
  sample_rate: 16000
  vad_threshold: 0.5

services:
  asr_model: "base"          # tiny / base / small
  llm_model: "llama3.2:3b"   # llama3.2:1b / llama3.2:3b
  cleanup_enabled: true

tray:
  show_notifications: true
```

## Documentation

- [Configuration](docs/configuration.md)
- [Architecture](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
- [API Reference](docs/api.md)
- [Models](docs/models.md)
- [FAQ](docs/faq.md)

## License

MIT
