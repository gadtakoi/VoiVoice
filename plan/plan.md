# План разработки VoiVoice

> **VoiVoice** — system-wide AI voice dictation платформа для Windows. Локальные модели, Docker Compose, активация
> горячей клавишей, индикация в system tray.
>
> Назначение: голосовой ввод текста в любое активное текстовое поле ОС с AI-постобработкой.

---

## 1. Обзор и цели

### 1.1 Что строим

Аналог [Wispr Flow](https://wisprflow.ai) под Windows с жёстким требованием локального инференса (privacy-first, zero
cloud).

### 1.2 Ключевые требования (из `task.md`)

| # | Требование                                    | Критичность |
|---|-----------------------------------------------|-------------|
| 1 | Запуск на Windows                             | Обязательно |
| 2 | LLM-модели локально                           | Обязательно |
| 3 | Запуск через `docker-compose`                 | Обязательно |
| 4 | Активация горячей клавишей                    | Обязательно |
| 5 | Индикация в system tray (запущено / включено) | Обязательно |
| 6 | **Работа на CPU (ноутбук без GPU)**           | Обязательно |

### 1.3 MVP Scope

В MVP реализуем полный pipeline от голоса до текста:

- Global hotkey → запись речи → VAD → ASR (Whisper) → LLM cleanup → вставка в активное окно.
- System tray с двумя состояниями.
- Конфигурация через файл.
- Fallback: если LLM-сервис недоступен — вставляем raw ASR.

> **CPU-only constraint:** Все ML-инференсы (ASR, LLM, VAD) работают на CPU. GPU не требуется. Применяются
> квантованные и ONNX/INT8 модели для минимизации latency и нагрузки на ноутбук.

### 1.4 Out of Scope (v2)

- Cross-device sync
- IDE-aware syntax formatting (camelCase/snake_case)
- Screenshot / OCR context awareness
- Cloud inference
- Snippets / voice macros
- Personal dictionary обучение

---

## 2. Архитектурная схема

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              WINDOWS HOST                                   │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────┐  │
│  │   Keyboard Hook     │    │   System Tray GUI   │    │  Audio Capture  │  │
│  │   (pynput/ctypes)   │◄──►│   (pystray)         │    │  (sounddevice)  │  │
│  └──────────┬──────────┘    └─────────────────────┘    └────────┬────────┘  │
│             │                                                   │           │
│  ┌──────────▼──────────┐                                        ▼           │
│  │   VoiVoice Client   │◄────────────────────────────  Raw Audio Chunks     │
│  │   (Python >=3.14)   │                                        │           │
│  └──────────┬──────────┘                                        │           │
│             │                                                   │           │
│             │         HTTP/WebSocket over Docker network        │           │
│             └───────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DOCKER DESKTOP (WSL2)                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      docker-compose.yml                                │ │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌────────────┐  │ │
│  │  │   ASR Svc   │   │   LLM Svc   │   │  VAD Svc    │   │  API GW    │  │ │
│  │  │  faster-    │   │   Ollama    │   │  Silero     │   │  FastAPI   │  │ │
│  │  │  whisper    │   │  (local)    │   │  VAD        │   │  (proxy)   │  │ │
│  │  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └─────┬──────┘  │ │
│  │         │                 │                 │                │         │ │
│  │         └─────────────────┴─────────────────┘                │         │ │
│  │                           │                                  │         │ │
│  │                           ▼                                  ▼         │ │
│  │                    Shared Network (bridge)                             │ │
│  │                    Volume: ./models → /models                          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Компоненты системы

### 3.1 Windows Client (`src/client/`)

Отвечает за весь UX на стороне ОС.

| Компонент          | Библиотека / API                                      | Назначение                                                 |
|--------------------|-------------------------------------------------------|------------------------------------------------------------|
| **Global Hotkey**  | `pynput` + `ctypes` (RegisterHotKey)                  | Перехват глобальной комбинации (например, `Ctrl+Alt+V`)    |
| **Audio Capture**  | `sounddevice` + `numpy`                               | Запись с микрофона в реальном времени, 16кГц, mono, int16  |
| **VAD (local)**    | `silero-vad` (ONNX) или `webrtcvad`                   | Обрезка тишины в начале/конце, chunk-level voice detection |
| **System Tray**    | `pystray` + `Pillow`                                  | Иконка в трее с двумя состояниями + контекстное меню       |
| **Text Injection** | `ctypes` (`SendInput`) + `pywinauto` / `uiautomation` | Эмуляция ввода текста в активное окно                      |
| **Config Manager** | `pydantic-settings` + `yaml`                          | Чтение `config.yaml`, валидация                            |
| **API Client**     | `httpx` (async)                                       | Обращение к Docker-сервисам                                |

#### System Tray состояния

| Состояние      | Иконка             | Значение                            |
|----------------|--------------------|-------------------------------------|
| `Idle` 🎤      | Серый/белый        | Приложение запущено, ожидает hotkey |
| `Listening` 🔴 | Красный/мигающий   | Идёт запись голоса                  |
| `Processing` ⏳ | Жёлтый/вращающийся | Аудио отправлено на ASR/LLM         |
| `Error` ⚠️     | Красный крест      | Ошибка сервиса или pipeline         |

### 3.2 Docker Services

#### `asr` — Speech-to-Text (CPU)

- **Базовый образ:** `fedirz/faster-whisper-server:latest-cpu` (CTranslate2 + CPU)
- **Модель по умолчанию:** `base` (рекомендуемая), fallback на `tiny` для слабых ноутбуков
- **API:** REST `/transcribe` (принимает WAV/PCM, возвращает JSON с текстом)
- **CPU Optimizations:**
  - `compute_type=int8` (INT8 квантование вместо float32)
  - `cpu_threads=4` (автоподстройка под число ядер)
  - `num_workers=1`
- **Latency на CPU:** tiny ~0.3s, base ~0.8s, small ~2s на коротких фразах (3–5 сек)
- **RAM:** tiny ~400MB, base ~600MB (включая контейнер)

#### `llm` — Post-processing & Cleanup (CPU)

- **Базовый образ:** `ollama/ollama`
- **Модель по умолчанию:** `llama3.2:3b` (рекомендуемая, Q4_K_M ~1.6GB RAM)
- **Fallback модель:** `llama3.2:1b` (для слабых ноутбуков, ~0.8GB RAM)
- **API:** Ollama Native API (`/api/generate`)
- **Prompt:** системный промпт для удаления filler words, расстановки пунктуации, грамматической нормализации
- **Quantization:** Q4_K_M
- **CPU Optimizations:**
  - `OLLAMA_NUM_THREADS=0` (auto-detect, использовать все ядра)
  - `OLLAMA_USE_MLOCK=true` (предотвращение выгрузки модели в swap)
  - `OLLAMA_FLASH_ATTENTION=1` (оптимизация памяти)
- **Latency на CPU:** 1B ~0.5s, 3B ~1.5s на коротких фразах
- **Fallback:** если cleanup вызывает задержку > 2s — вставлять raw ASR

#### `vad` — Voice Activity Detection (опционально отдельно)

- Может быть встроен в `asr` (Whisper VAD) или отдельный микросервис `silero-vad`.
- MVP: встроенный VAD в клиенте (Silero ONNX).

#### `api` — API Gateway / Orchestrator

- **Базовый образ:** `python:3.14-slim`
- **Фреймворк:** FastAPI
- **Назначение:**
    - Единая точка входа для клиента
    - Маршрутизация: `/asr` → `asr`, `/cleanup` → `llm`
    - Кэширование (Redis, опционально)
    - Healthcheck всех сервисов
    - Логирование и метрики

---

## 4. Pipeline обработки

```text
[User holds Hotkey]
         │
         ▼
┌─────────────────┐
│  System Tray    │──► Icon = Listening 🔴
│  (pystray)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Audio Capture  │──► sounddevice stream → numpy buffer
│  (16kHz, mono)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  VAD (Silero)   │──► detect speech start/end
└────────┬────────┘
         │
[User releases Hotkey]
         │
         ▼
┌─────────────────┐
│  Encode to WAV  │
│  (in-memory)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      HTTP POST
│  API Gateway    │──────────────────────────► Docker (api)
│  (httpx async)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                         DOCKER SIDE                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │  API GW     │───►│   ASR Svc   │───►  Raw Transcript  │  │
│  │  FastAPI    │    │  Whisper    │    │  "uh send report"│  │
│  └──────┬──────┘    └─────────────┘    └─────────────────┘  │
│         │                                                    │
│         │ (если LLM enabled)                                 │
│         ▼                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │  LLM Svc    │───►  Cleanup    │───►  Final Text      │  │
│  │  Ollama     │    │  Prompt     │    │  "Send report?"  │  │
│  └─────────────┘    └─────────────┘    └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Text Injection │──► SendInput / clipboard → active window
│  (ctypes)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  System Tray    │──► Icon = Idle 🎤
└─────────────────┘
```

### 4.1 LLM Cleanup Prompt (пример)

```
You are an AI dictation assistant. Clean up the following raw speech transcript.
Rules:
- Remove filler words (uh, um, like, you know)
- Add proper punctuation
- Fix grammar and capitalization
- Preserve the original language
- Output ONLY the cleaned text, no explanations

Raw: {raw_transcript}
Cleaned:
```

### 4.2 Fallback Behavior

| Условие               | Действие                                 |
|-----------------------|------------------------------------------|
| LLM сервис недоступен | Вставить raw ASR transcript              |
| ASR сервис недоступен | Показать tray error, не вставлять ничего |
| Hotkey зажат < 300 мс | Игнорировать (антидребезг)               |
| VAD не обнаружил речь | Не отправлять на ASR, вернуть idle       |

---

## 5. Технологический стек

### 5.1 Python зависимости (клиент)

```toml
dependencies = [
    "sounddevice>=0.5",
    "numpy>=2.0",
    "pystray>=0.19",
    "pillow>=10.0",
    "pynput>=1.7",
    "httpx[http2]>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
    "onnxruntime>=1.18", # Silero VAD
]
```

### 5.2 Docker Images

| Сервис | Образ                                               | Порты   |
|--------|-----------------------------------------------------|---------|
| ASR    | `fedirz/faster-whisper-server:latest-cpu`           | `8000`  |
| LLM    | `ollama/ollama`                                     | `11434` |
| API GW | кастомный `Dockerfile` (FastAPI)                    | `8080`  |

### 5.3 Инфраструктура хоста

- **Docker Desktop** с WSL2 backend
- **Python 3.14+** (клиент запускается natively на Windows, не в Docker)
- **RAM:** минимум 4GB (для tiny + 1B моделей), рекомендуется 8GB+ (для base + 3B)
- **CPU:** любой современный x64 процессор (Intel 6th gen+ / AMD Ryzen)
- **GPU:** не требуется

### 5.4 CPU-оптимизации

| Оптимизация | Применение | Эффект |
|-------------|------------|--------|
| **INT8 квантование** (ASR) | `faster-whisper` с `compute_type=int8` | Снижение RAM на 50%, ускорение на CPU до 2x |
| **Q4_K_M квантование** (LLM) | Ollama с `q4_0` / `q4_k_m` | Модель 3B занимает ~1.6GB вместо 6GB |
| **ONNX Runtime** (VAD) | Silero VAD через `onnxruntime` | CPU inference, ~10MB RAM |
| **Thread limiting** | `WHISPER_CPU_THREADS=4`, `OLLAMA_NUM_THREADS=0` | Предотвращение блокировки системы |
| **Memory limits** | Docker `deploy.resources.limits.memory` | Предотвращение OOM на ноутбуках |
| **Flash Attention** | `OLLAMA_FLASH_ATTENTION=1` | Ускорение inference на CPU, снижение RAM |
| **Model tiering** | `tiny`/`1b` для слабых, `base`/`3b` для средних | Адаптация под железо пользователя |

### 5.5 Билингвальность (русский + английский)

Whisper из коробки поддерживает 99+ языков с автоопределением, но для русского/английского сочетания есть нюансы:

| Аспект | Рекомендация | Почему |
|--------|-------------|--------|
| **ASR модель** | `small` вместо `base` если RAM ≥ 8GB | На русском `base` иногда путает окончания и ударения; `small` заметно точнее |
| **Язык (explicit)** | Параметр `language` в API (ru/en) | Ускоряет inference на ~20% vs `auto`, убирает ошибки определения на коротких фразах |
| **Язык (auto)** | `language=auto` по умолчанию | Удобно, но +100-300ms на определение; fallback если mixed speech |
| **LLM cleanup** | Prompt: *"Preserve the original language of the transcript"* | Предотвращает перевод русского текста на английский при cleanup |
| **Code-switching** | Ожидайте худшей точности | Переключение языка внутри фразы ("давай сделаем deploy") — слабое место всех ASR |
| **Кэширование** | Кэшировать системный промпт LLM по языку | Снижает время подготовки prompt на повторных запросах |

**Рекомендуемая стратегия для двуязычного пользователя:**
1. В `config.yaml` — `language: auto` по умолчанию.
2. В tray меню — быстрое переключение "RU / EN / Auto".
3. Если пользователь знает язык — явно передавать в Whisper (`language=ru`), это ускорит и улучшит точность.
4. Для преимущественно русского использования — `small` модель, если позволяет железо.
5. Для английского — `base` достаточно, можно не менять модель.

---

## 6. Файловая структура проекта

```
VoiVoice/
├── plan/
│   ├── wispr_flow.md      # эталонная архитектура
│   ├── task.md            # требования
│   └── plan.md            # этот документ
├── src/
│   ├── client/            # Windows native client
│   │   ├── __init__.py
│   │   ├── main.py        # entry point
│   │   ├── config.py      # pydantic-settings
│   │   ├── audio.py       # capture + VAD
│   │   ├── hotkey.py      # global hotkey hook
│   │   ├── tray.py        # system tray indicator
│   │   ├── injector.py    # text injection
│   │   └── api_client.py  # HTTP client to docker services
│   └── server/            # API Gateway (Docker)
│       ├── Dockerfile
│       ├── main.py
│       └── requirements.txt
├── docker-compose.yml
├── config.yaml            # пользовательская конфигурация
├── pyproject.toml
└── README.md
```

---

## 7. Roadmap по фазам

### Phase 0: Инфраструктура и скелет

**Цель:** Работающий Docker Compose + запускаемый клиент.

- [ ] Создать `docker-compose.yml` с `asr`, `llm`, `api`
- [ ] Создать FastAPI Gateway (`/health`, `/asr`, `/cleanup`)
- [ ] Создать базовый `src/client/main.py` с циклом событий
- [ ] System Tray: иконка + меню (Quit, Settings)
- [ ] Проверка связи клиент ↔ Docker

**Deliverable:** `docker-compose up` поднимает сервисы, клиент показывает tray иконку.

### Phase 1: Голосовой захват + ASR

**Цель:** Hold hotkey → говоришь → получаешь raw transcript на CPU.

- [ ] Реализация `audio.py` (sounddevice stream)
- [ ] VAD интеграция (Silero ONNX — CPU inference)
- [ ] Отправка WAV на ASR сервис (CPU, int8)
- [ ] Тест на `tiny` модели (быстро, но менее точно) и `base` (баланс)
- [ ] Замер latency: целевой < 1s на фразу до 5 секунд
- [ ] Вывод raw transcript в консоль / тестовое окно
- [ ] Tray state: Listening → Processing → Idle

**Deliverable:** Голосовой ввод работает на CPU, вставляется raw ASR текст.

### Phase 2: LLM Post-processing

**Цель:** Очистка и форматирование текста через локальную CPU-модель.

- [ ] Интеграция Ollama API (`/api/generate`)
- [ ] Pull `llama3.2:1b` и `llama3.2:3b`, сравнение latency на CPU
- [ ] Prompt engineering для cleanup
- [ ] Настройка `OLLAMA_NUM_THREADS` и memory limits
- [ ] Сравнение raw vs cleaned (latency/quality)
- [ ] Fallback на raw при недоступности LLM или при latency > 2s
- [ ] Опция `cleanup_enabled: false` для очень слабых ноутбуков

**Deliverable:** Текст проходит cleanup перед вставкой, работает на CPU.

### Phase 3: Windows Integration (Hotkey + Injection)

**Цель:** Полная интеграция с ОС.

- [ ] Global hotkey (`Ctrl+Alt+V` по умолчанию, настраивается)
- [ ] `SendInput` / `clipboard` для вставки в активное окно
- [ ] Обработка разных типов окон (Electron, native, IDE)
- [ ] Tray индикация: запущено (idle) / включено (listening/processing)
- [ ] Автозапуск с Windows (опционально)

**Deliverable:** Полный MVP: hotkey → голос → текст в любом окне.

### Phase 4: Polish & Stability

**Цель:** Production-ready UX.

- [ ] Конфигурация через `config.yaml` (hotkey, модели, пороги VAD)
- [ ] Логирование (`loguru` или `structlog`)
- [ ] Обработка ошибок и retry logic
- [ ] Иконки для всех tray состояний
- [ ] Установщик / `.bat` для запуска
- [ ] README с инструкцией по установке

### Phase 5: Advanced Features (v2)

- [ ] Сниппеты / voice macros
- [ ] Personal dictionary (phrase biasing для ASR)
- [ ] IDE context detection (форматирование camelCase и т.д.)
- [ ] Screenshot + OCR для context awareness
- [ ] Мультиязычность (auto-detect языка)

---

## 8. API Specification (draft)

### 8.1 Client → API Gateway

#### `POST /api/v1/transcribe`

**Request:**

```http
Content-Type: multipart/form-data

file: <audio.wav>
language: ru          # optional, default auto
cleanup: true        # optional, default true
```

**Response:**

```json
{
  "success": true,
  "raw": "ну типа отправь отчет завтра",
  "cleaned": "Отправь отчёт завтра.",
  "language": "ru",
  "duration_ms": 2340,
  "processing_ms": 450
}
```

#### `GET /api/v1/health`

**Response:**

```json
{
  "status": "ok",
  "services": {
    "asr": "ok",
    "llm": "ok"
  }
}
```

### 8.2 Internal (API Gateway → Services)

#### ASR Service

```
POST /v1/audio/transcriptions
Content-Type: multipart/form-data
file: <audio>
model: base
language: ru
```

#### LLM Service (Ollama)

```
POST /api/generate
{
  "model": "llama3.2:3b",
  "prompt": "...",
  "stream": false,
  "options": {
    "temperature": 0.1,
    "num_predict": 256
  }
}
```

---

## 9. Конфигурация (`config.yaml`)

```yaml
app:
  name: "VoiVoice"
  version: "0.1.0"

hotkey:
  combination: "ctrl+alt+v"   # глобальная комбинация
  hold_to_record: true        # true = зажал, говоришь, отпустил
  # false = toggle mode (нажал — записываем, нажал — стоп)

audio:
  sample_rate: 16000
  channels: 1
  dtype: "int16"
  chunk_duration_ms: 30       # размер чанка для VAD
  vad_threshold: 0.5          # порог уверенности Silero
  silence_timeout_ms: 500     # остановка через N мс тишины

services:
  api_url: "http://localhost:8080"
  asr_model: "base"           # tiny (слабый CPU), base (рекомендуемо), small (если RAM ≥ 8GB)
  llm_model: "llama3.2:3b"    # llama3.2:1b (слабый CPU), llama3.2:3b (рекомендуемо)
  cleanup_enabled: true
  fallback_to_raw: true

tray:
  show_notifications: true
  startup_minimized: false

injection:
  method: "sendinput"         # sendinput | clipboard
  delay_between_chars_ms: 10  # для SendInput (антидетект ботов)
```

---

## 10. Docker Compose (`docker-compose.yml`)

```yaml
version: "3.8"

services:
  asr:
    image: fedirz/faster-whisper-server:latest-cpu
    ports:
      - "8000:8000"
    volumes:
      - ./models/whisper:/models:ro
    environment:
      - WHISPER_MODEL=base
      - WHISPER_LANGUAGE=auto
      - WHISPER_COMPUTE_TYPE=int8
      - WHISPER_CPU_THREADS=4
    deploy:
      resources:
        limits:
          memory: 2G

  llm:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ./models/ollama:/root/.ollama
    environment:
      - OLLAMA_NUM_THREADS=0
      - OLLAMA_USE_MLOCK=true
      - OLLAMA_FLASH_ATTENTION=1
    deploy:
      resources:
        limits:
          memory: 3G

  api:
    build: ./src/server
    ports:
      - "8080:8080"
    environment:
      - ASR_URL=http://asr:8000
      - LLM_URL=http://llm:11434
    depends_on:
      - asr
      - llm
```

---

## 11. Риски и ограничения

| Риск                  | Влияние | Митигация                                                                  |
|-----------------------|---------|----------------------------------------------------------------------------|
| **Латентность LLM**   | Высокое | Использовать 3B модели, Q4_K_M квантование, кэширование промптов           |
| **Text Injection**    | Среднее | Два метода: SendInput (безопасный) и clipboard (для проблемных приложений) |
| **Docker on Windows** | Среднее | Требовать WSL2 backend, тестировать на чистой Windows 10/11                |
| **Размер моделей**    | Среднее | Whisper base (~150MB) + Llama 3B (~2GB) — приемлемо для современных ПК     |
| **GPU зависимость**   | Низкое  | **CPU-only — GPU не требуется**                                            |
| **CPU нагрузка**      | Среднее | ASR + LLM могут загружать CPU; ограничение потоков в конфиге               |
| **RAM на ноутбуке**   | Среднее | Минимум 4GB (tiny + 1B), рекомендуется 8GB (base + 3B)                     |
| **Безопасность**      | Среднее | Все данные остаются локально, no cloud calls                               |
| **Конфликт hotkey**   | Низкое  | Настраиваемая комбинация в config.yaml                                     |

---

## 12. Критерии приёмки MVP

1. [ ] `docker-compose up` поднимает все сервисы без ошибок на CPU.
2. [ ] Клиент запускается на Windows, показывает иконку в tray.
3. [ ] Зажатие `Ctrl+Alt+V` → иконка меняется на Listening.
4. [ ] Голос записывается, отправляется, возвращается cleaned текст.
5. [ ] Текст вставляется в активное текстовое поле (Notepad, браузер, VS Code).
6. [ ] Отпускание hotkey → иконка возвращается в Idle.
7. [ ] При недоступности LLM вставляется raw ASR текст.
8. [ ] Конфигурация меняет hotkey, модель, язык.
9. [ ] **Работает на ноутбуке без GPU:** Intel i5 8th gen / 8GB RAM / без дискретной видеокарты.
10. [ ] **Latency фразы 3-5 секунд < 2 секунд** (end-to-end на CPU).

---

## 13. Следующий шаг

Перейти к **Phase 0** — создать `docker-compose.yml`, FastAPI Gateway, базовый скелет клиента и проверить end-to-end
связность.
