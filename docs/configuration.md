# Configuration Guide

VoiVoice uses `config.yaml` in the project root for all settings.

## Sections

### `app`

| Key       | Default      | Description         |
|-----------|--------------|---------------------|
| `name`    | `"VoiVoice"` | Application name    |
| `version` | `"0.1.0"`    | Application version |

### `hotkey`

| Key             | Default          | Description                        |
|-----------------|------------------|------------------------------------|
| `combination`   | `"ctrl+alt+v"`   | Global hotkey combination          |
| `hold_to_record`| `true`           | Hold to record vs toggle mode      |

### `audio`

| Key                  | Default | Description                          |
|----------------------|---------|--------------------------------------|
| `sample_rate`        | `16000` | Microphone sample rate (Hz)          |
| `channels`           | `1`     | Mono recording                       |
| `chunk_duration_ms`  | `30`    | Audio chunk size for VAD             |
| `vad_threshold`      | `0.5`   | Silero VAD speech threshold          |
| `silence_timeout_ms` | `500`   | Stop after N ms of silence           |

### `services`

| Key               | Default           | Description                          |
|-------------------|-------------------|--------------------------------------|
| `api_url`         | `"localhost:8080"`| API Gateway URL                      |
| `asr_model`       | `"base"`          | Whisper model: tiny/base/small       |
| `llm_model`       | `"llama3.2:3b"`   | Ollama model for cleanup             |
| `cleanup_enabled` | `true`            | Enable LLM post-processing           |
| `fallback_to_raw` | `true`            | Use raw ASR if cleanup fails         |

### `tray`

| Key                  | Default | Description                          |
|----------------------|---------|--------------------------------------|
| `show_notifications` | `true`  | Windows toast notifications          |
| `startup_minimized`  | `false` | Start minimized to tray              |

### `injection`

| Key                      | Default       | Description                      |
|--------------------------|---------------|----------------------------------|
| `method`                 | `"sendinput"` | Text injection method            |
| `delay_between_chars_ms` | `10`          | Typing delay for SendInput       |

## Example Profiles

### Weak Laptop (4GB RAM)

```yaml
services:
  asr_model: "tiny"
  llm_model: "llama3.2:1b"
  cleanup_enabled: false
```

### Maximum Quality (8GB+ RAM)

```yaml
services:
  asr_model: "small"
  llm_model: "llama3.2:3b"
  cleanup_enabled: true
```
