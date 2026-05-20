# API Reference

## Client → Gateway

### POST /api/v1/transcribe

Transcribe audio and optionally clean up the text.

**Request:**
```http
Content-Type: multipart/form-data

file: <audio.wav>
language: auto|ru|en
cleanup: true|false
```

**Response:**
```json
{
  "success": true,
  "raw": "raw transcript",
  "cleaned": "cleaned text",
  "language": "ru",
  "processing_ms": 450,
  "cleanup_skipped": false
}
```

### GET /api/v1/health

Check service health.

**Response:**
```json
{
  "status": "ok",
  "services": {
    "asr": "ok",
    "llm": "ok"
  },
  "version": "0.1.0"
}
```

## Internal (Gateway → Services)

### ASR

```
POST /v1/audio/transcriptions
Content-Type: multipart/form-data
file: <audio>
model: base
language: ru
```

### LLM (Ollama)

```
POST /api/generate
{
  "model": "llama3.2:3b",
  "prompt": "...",
  "stream": false
}
```
