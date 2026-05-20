# Models

## ASR (Speech-to-Text)

| Model  | Size  | RAM    | Latency (5s audio) | Accuracy | Recommended For |
|--------|-------|--------|--------------------|----------|-----------------|
| `tiny` | ~75MB | ~400MB | ~0.3s              | Basic    | Weak laptops    |
| `base` | ~150MB| ~600MB | ~0.8s              | Good     | General use     |
| `small`| ~500MB| ~1.2GB | ~2s                | Better   | Russian speech  |

## LLM (Cleanup)

| Model          | Size   | RAM    | Latency | Quality | Recommended For |
|----------------|--------|--------|---------|---------|-----------------|
| `llama3.2:1b`  | ~1.3GB | ~0.8GB | ~0.5s   | Good    | Weak laptops    |
| `llama3.2:3b`  | ~2.0GB | ~1.6GB | ~1.5s   | Better  | General use     |

## Quantization

- ASR: `int8` (faster-whisper)
- LLM: `Q4_K_M` (Ollama)

Both significantly reduce RAM usage and improve CPU inference speed.
