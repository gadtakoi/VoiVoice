# FAQ

## Why not Google Speech API or Whisper API?

VoiVoice is privacy-first. All audio and text processing happens locally. No data ever leaves your machine.

## Can I run without Docker?

No. The ASR and LLM services require Docker for isolation and dependency management.

## Does it work on Windows 7?

No. Python 3.14+ and modern Windows APIs require Windows 10 or 11.

## Will it work on macOS or Linux?

The client is Windows-specific (SendInput, global hotkeys, system tray). The server (Docker) could run anywhere, but the client would need a complete rewrite.

## How much RAM do I need?

- Minimum: 4GB (tiny + 1B models)
- Recommended: 8GB (base + 3B models)

## Can I use a GPU?

The application is optimized for CPU-only laptops. GPU support is not implemented but could be added in the future.

## What languages are supported?

Russian and English are the primary targets. Whisper supports 99+ languages, but the cleanup prompt and UI are optimized for RU/EN.
