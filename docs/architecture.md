# Architecture

## Overview

VoiVoice consists of two main parts:

1. **Windows Client** (native Python) — captures audio, handles hotkeys, shows tray icon, injects text.
2. **Docker Services** (WSL2) — runs ML models for ASR and text cleanup.

## Pipeline

```
[Hotkey Press]
    ↓
Audio Capture (sounddevice) → 16kHz mono PCM
    ↓
Silero VAD (ONNX) — optional speech detection
    ↓
[Hotkey Release]
    ↓
WAV encoding (in-memory)
    ↓
HTTP POST → API Gateway (FastAPI)
    ↓
ASR Service (faster-whisper, CPU INT8)
    ↓
LLM Service (Ollama, optional cleanup)
    ↓
API Gateway response
    ↓
Text Injection (SendInput / clipboard)
    ↓
System Tray update
```

## Components

### Client (`src/client/`)

| Module        | Purpose                          |
|---------------|----------------------------------|
| `main.py`     | Event loop, orchestration        |
| `config.py`   | Configuration management         |
| `audio.py`    | Microphone capture + VAD         |
| `hotkey.py`   | Global keyboard hook             |
| `tray.py`     | System tray icon and menu        |
| `injector.py` | Text input simulation            |
| `api_client`  | HTTP client with retry logic     |
| `beacon.py`   | Audio feedback tones             |
| `timing.py`   | Performance timing logs          |
| `toast.py`    | Windows notifications            |

### Server (`src/server/`)

| Module             | Purpose                     |
|--------------------|-----------------------------|
| `main.py`          | FastAPI application         |
| `routers/health.py`| Healthcheck aggregation     |
| `routers/transcribe.py` | ASR + LLM orchestration |
| `schemas/`         | Pydantic request/response     |

## Data Flow

All audio and text processing stays local. No data leaves the machine.
