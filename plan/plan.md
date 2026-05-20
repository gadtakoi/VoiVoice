# План разработки VoiVoice

> **VoiVoice** — system-wide AI voice dictation платформа для Windows. Локальные модели, Docker Compose, активация
> горячей клавишей, индикация в system tray.
>
> Назначение: голосовой ввод текста в любое активное текстовое поле ОС с AI-постобработкой.

---

## 0. Описание задачи

**Что нужно создать**

Необходимо разработать приложение **VoiVoice** — систему голосового ввода текста (voice dictation) для Windows,
функционально аналогичную Wispr Flow. Пользователь зажимает глобальную горячую клавишу, произносит текст, отпускает
клавишу — и отредактированный текст появляется в активном текстовом поле любой программы (Notepad, браузер, VS Code,
мессенджеры и т.д.).

**Ключевое ограничение — полная локальность.** В отличие от облачных решений, все этапы обработки (распознавание речи,
постобработка текста, проверка грамматики) выполняются на машине пользователя. Ни аудио, ни текст, ни метаданные не
покидают компьютер. Это достигается за счёт развёртывания ML-моделей в Docker-контейнерах на той же машине.

**Платформа и окружение**

Приложение ориентировано исключительно на Windows 10/11. Целевое железо — ноутбуки без дискретной видеокарты, то есть
весь инференс (ASR, LLM, шумоподавление) должен работать на CPU. Docker Desktop с WSL2 backend используется как среда
выполнения для ML-сервисов. Windows-клиент запускается нативно (Python 3.14+) и взаимодействует с Docker-сервисами по
HTTP.

**Основной сценарий использования**

1. Пользователь нажимает и удерживает заданную комбинацию клавиш (например, `Ctrl+Alt+V`).
2. В system tray появляется индикация «Слушаю…», возможно — звуковой бейкон и OSD-оверлей.
3. Пользователь произносит фразу (на русском или английском).
4. При отпускании клавиши аудио проходит pipeline:
    - Шумоподавление (RNNoise) — очистка записи от посторонних шумов;
    - VAD (Silero) — определение границ речи;
    - ASR (Whisper) — распознавание речи в текст;
    - LLM cleanup (Ollama) — удаление слов-паразитов, расстановка пунктуации, грамматическая правка;
    - Вставка текста — эмуляция нажатий клавиш (`SendInput`) или буфер обмена.
5. В system tray отображается подтверждение («Транскрипция готова»), приложение возвращается в режим ожидания.
6. Если какой-либо сервис недоступен (Docker не запущен, сеть между клиентом и контейнерами упала) — приложение
   показывает понятную ошибку в tray, не зависает и продолжает слушать hotkey.

**Индикация и обратная связь**

System tray — основной интерфейс приложения. Он должен чётко показывать текущее состояние: ожидание, запись, обработка,
ошибка, пауза, отсутствие микрофона, скачивание модели и другие. Дополнительно используются: всплывающие
toast-уведомления Windows, звуковые бейконы (короткие тона на старт/стоп/ошибку) и опциональный OSD-оверлей поверх
экрана.

**Билингвальность**

Приложение должно поддерживать распознавание на русском и английском языках (в том числе смешанную речь). Язык можно
задать явно (RU/EN) или оставить автоопределение. Постобработка текста должна сохранять исходный язык транскрипции, не
переводя его.

**Архитектура в двух словах**

- **Windows-клиент** (Python) — захват аудио, глобальный hotkey, system tray, вставка текста, взаимодействие с
  сервисами.
- **Docker Compose** — оркестрация локальных ML-сервисов:
    - ASR: Whisper (faster-whisper, CPU, INT8);
    - LLM: Ollama (llama3.2:1b/3b, Q4_K_M);
    - LanguageTool: опциональная грамматическая проверка;
    - API Gateway: единая точка входа для клиента.

**Требования к устойчивости и отладке**

- Подробное структурированное логирование каждого шага с `trace_id` (structlog/loguru).
- Отдельный timing-лог: замер времени на каждом этапе pipeline от микрофона до вставки.
- Retry-механизм при временной недоступности Docker-сервисов (1–2 повторные попытки).
- Graceful degradation: при отказе LLM — вставка raw ASR; при отказе ASR — error toast без краша.
- Обработка edge-case'ов: сеть упала, микрофон отключён, пользователь забыл отпустить hotkey (таймаут 60s).

**Документация**

Проект должен содержать корневой README.md с быстрым стартом и подробную документацию в `docs/`: руководство по
настройке, описание архитектуры, API reference, troubleshooting, FAQ, сравнение моделей и CHANGELOG.

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
| **Global Hotkey**  | `keyboard` (boppreh) + `pynput` fallback              | Перехват глобальной комбинации (например, `Ctrl+Alt+V`)    |
| **Audio Capture**  | `sounddevice` + `numpy`                               | Запись с микрофона в реальном времени, 16кГц, mono, int16  |
| **VAD (local)**    | `silero-vad` (ONNX) или `webrtcvad`                   | Обрезка тишины в начале/конце, chunk-level voice detection |
| **System Tray**    | `pystray` + `Pillow`                                  | Иконка в трее с расширенной индикацией (10 состояний)      |
| **Text Injection** | `ctypes` (`SendInput`) + `pywinauto` / `uiautomation` | Эмуляция ввода текста в активное окно                      |
| **Config Manager** | `pydantic-settings` + `yaml`                          | Чтение `config.yaml`, валидация                            |
| **API Client**     | `httpx` (async)                                       | Обращение к Docker-сервисам                                |

#### System Tray состояния (расширенные)

| Состояние        | Иконка                         | Значение              | Когда срабатывает                        |
|------------------|--------------------------------|-----------------------|------------------------------------------|
| `Idle` 🎤        | Серый/белый                    | Готов к работе        | Приложение запущено, все сервисы OK      |
| `Listening` 🔴   | Красный/мигающий               | Запись голоса         | Зажат hotkey, идёт запись                |
| `Processing` ⏳   | Жёлтый/вращающийся             | Обработка             | Аудио отправлено на ASR/LLM              |
| `Cooldown` 🟡    | Жёлтый статичный               | Перезарядка           | Небольшая пауза между запросами (~1s)    |
| `Disabled` ⏸️    | Полупрозрачный/серый           | Приложение выключено  | Пользователь нажал "Pause" в tray меню   |
| `Offline` 🚫     | Серый крест / отключённая сеть | Нет связи с сервисами | Docker не запущен или сервисы недоступны |
| `No Mic` 🔇      | Микрофон перечёркнут           | Микрофон недоступен   | PyAudio не видит микрофон                |
| `Downloading` ⬇️ | Синий/вращающийся              | Скачивание модели     | Ollama pull / Whisper model download     |
| `Low Volume` 📉  | Тихий/бледный                  | Слишком тихо          | VAD обнаружил сигнал ниже порога         |
| `Error` ❌        | Красный крест                  | Ошибка pipeline       | Исключение в любом компоненте            |

#### Дополнительные UI/UX элементы

**OSD (On-Screen Display) — оверлей:**

- Маленькое полупрозрачное окно рядом с курсором или в центре экрана
- Показывает: `🔴 Listening...` во время записи
- Показывает partial transcript в real-time (если ASR поддерживает streaming)
- Авто-скрытие через 2 секунды после вставки текста
- Реализация: `tkinter` (встроен в Python) или `PyQt` / `PySide` — поверх всех окон (`-topmost` /
  `Qt.WindowStaysOnTopHint`)

**Звуковой бейкон (Audio Beacon):**
Короткий звуковой сигнал даёт тактильную уверенность, что система отреагировала — особенно важно при голосовом вводе,
когда пользователь не смотрит на экран.

| Событие            | Звук                                        | Описание      | Когда                                          |
|--------------------|---------------------------------------------|---------------|------------------------------------------------|
| **Start Beacon**   | Короткий ascending tone (800→1200Hz, 80ms)  | «Пик»         | При зажатии hotkey, начало записи              |
| **Stop Beacon**    | Короткий descending tone (1200→800Hz, 80ms) | «Пук»         | При отпускании hotkey, конец записи            |
| **Success Beacon** | Мягкий high-pitch «динь» (1500Hz, 50ms)     | Подтверждение | При успешной вставке текста (опционально)      |
| **Error Beacon**   | Двойной низкий tone (300Hz ×2, 150ms)       | «Бип-бип»     | При ошибке pipeline или недоступности сервисов |
| **Mute Beacon**    | Короткий mid tone (600Hz, 40ms)             | «Щелчок»      | При нажатии «Пауза» в tray меню                |

**Технические варианты реализации:**

| Вариант                                 | Плюсы                                                    | Минусы                                                       |
|-----------------------------------------|----------------------------------------------------------|--------------------------------------------------------------|
| `winsound.Beep(freq, dur)`              | Встроен в Python, нет зависимостей, не требует файлов    | Простые square wave, не очень приятные на слух; Windows only |
| **Генерация sine wave + `sounddevice`** | Приятные sin tones, любая частота/длительность           | Требует `sounddevice` (уже есть в проекте)                   |
| **Встроенные `.wav` файлы**             | Полный контроль над звуком, можно записать custom sounds | +N KB к дистрибутиву, нужно хранить ассеты                   |

**Рекомендация:** Генерация sine wave через `sounddevice` или `winsound` — не нужно таскать WAV-файлы, звук чистый и
предсказуемый.

**Пример генерации (Python):**

```python
import numpy as np
import sounddevice as sd


def beep(freq: int, duration_ms: int, fade: bool = True):
    t = np.linspace(0, duration_ms / 1000, int(48000 * duration_ms / 1000))
    wave = np.sin(2 * np.pi * freq * t)
    if fade:
        wave *= np.linspace(0.3, 0, len(wave))  # fade out
    sd.play(wave, 48000)


# Start beacon: ascending
beep(800, 40);
beep(1200, 40)
# Stop beacon: descending
beep(1200, 40);
beep(800, 40)
```

**Правила использования:**

- Start/Stop бейконы — всегда показываются (если `audio_feedback: true`).
- Success бейкон — отключён по умолчанию (может раздражать при частом использовании), включается через
  `audio_feedback_success: true`.
- Error бейкон — всегда, независимо от настроек (критическая обратная связь).
- Громкость бейконов относительно системной: `audio_feedback_volume: 0.3` (30%).

**Конфигурация:**

```yaml
audio_feedback:
  enabled: true
  volume: 0.3                 # 0.0 - 1.0
  success: false              # бейкон после успешной вставки
  start_freq: [ 800, 1200 ]     # Hz, ascending
  stop_freq: [ 1200, 800 ]      # Hz, descending
  error_freq: [ 300, 300 ]      # Hz, double
```

**Tray Tooltip:**

- Динамический tooltip с текущим статусом:
    - `VoiVoice — Готов (Ctrl+Alt+V)`
    - `VoiVoice — Запись: 3.2s`
    - `VoiVoice — Ошибка: LLM недоступен`

**Toast-уведомления (Windows native):**
Библиотека: `windows-toasts` (рекомендуется, WinRT-based, Windows 10/11) или `win10toast`.

| Состояние / Событие  | Toast-сообщение                                     | Приоритет | Когда показывать                                      |
|----------------------|-----------------------------------------------------|-----------|-------------------------------------------------------|
| `Idle` (после init)  | 🎤 VoiVoice готов. Нажмите **Ctrl+Alt+V** для ввода | Normal    | После успешного старта клиента и healthcheck сервисов |
| `Listening` (начало) | 🔴 Слушаю…                                          | Low       | При зажатии hotkey (опционально, может мешать)        |
| `Processing`         | ⏳ Распознаю речь…                                   | Low       | При отправке на ASR (если занимает > 1s)              |
| `Cooldown`           | ✅ Транскрипция готова                               | Normal    | После успешной вставки текста                         |
| `Disabled`           | ⏸️ VoiVoice приостановлен                           | Normal    | При нажатии "Пауза" в tray меню                       |
| `Offline`            | ❌ Сервисы недоступны. Запустите Docker              | High      | При падении healthcheck                               |
| `No Mic`             | 🚫 Микрофон не найден                               | High      | Если PyAudio не видит устройств                       |
| `Downloading`        | ⬇️ Скачивается модель «llama3.2:3b»…                | Normal    | При `ollama pull` / скачивании Whisper                |
| `Downloaded`         | ✅ Модель «llama3.2:3b» готова                       | Normal    | По завершении скачивания                              |
| `Low Volume`         | 📉 Говорите громче                                  | Low       | Если VAD обнаружил слишком тихий сигнал               |
| `Error`              | ⚠️ Ошибка: {краткое описание}                       | High      | При любом исключении в pipeline                       |
| `Language Switch`    | 🌐 Язык изменён на: Русский                         | Low       | При ручном переключении в tray меню                   |

**Правила показа (anti-spam):**

- `Cooldown`, `Offline`, `No Mic`, `Error` — показывать всегда.
- `Listening`, `Processing` — не показывать по умолчанию (могут мешать при частом использовании), включаются через
  `config.yaml: toasts.verbose: true`.
- Между toast'ами одного типа — минимальный интервал 5 секунд (debounce).
- Уведомления о транскрипции (`Cooldown`) показываются только если вставка успешна и текст непустой.
- Все toast'ы кликабельны: клик по `Offline` открывает логи, клик по `Cooldown` — ничего не делает (или показывает
  последний распознанный текст).

**Конфигурация:**

```yaml
toasts:
  enabled: true              # глобальный выключатель
  verbose: false             # показывать Listening / Processing
  on_success: true           # «Транскрипция готова»
  on_error: true             # ошибки всегда
  duration_seconds: 3        # время показа (Windows ограничивает ~5-7s)
```

**Tray меню (контекстное):**

```
🎤 VoiVoice v0.1.0
———————————————————
⏸️ Пауза / ▶️ Возобновить
🌐 Язык: [Auto ▼]  →  RU | EN | Auto
🧹 Cleanup: [LLM ▼] → LLM | LanguageTool | Both | None
🎙️ Шумоподавление: [RNNoise ▼] → RNNoise | None
———————————————————
📊 Статус сервисов  →  [подменю]
⚙️ Настройки        →  открыть config.yaml
📋 Открыть логи    →  открыть logs/
🔄 Перезапустить сервисы
———————————————————
❌ Выход
```

**Подменю «Статус сервисов» (live health):**

```
📊 Статус сервисов
———————————————————
🟢 ASR (Whisper)      — OK  | tiny | CPU int8
🟢 LLM (Ollama)       — OK  | llama3.2:3b | Q4_K_M
🟢 LanguageTool       — OK  | v6.4
🟢 API Gateway        — OK  | v0.1.0
🔴 VAD (Silero)       — OFF | fallback: webrtcvad
———————————————————
🌡️ CPU: 12%  |  RAM: 2.1GB / 8GB
⏱️ Последний запрос: 340ms
```

**Graceful degradation и edge cases:**

| Сценарий                                            | Поведение клиента                                                                                                                                      | Tray / Toast                                         | Recovery                                                      |
|-----------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------|---------------------------------------------------------------|
| **Сеть упала** (Docker недоступен)                  | Retry 2 раза → показать `Offline` → продолжать слушать hotkey                                                                                          | 🔴 Offline toast                                     | Авто-проверка каждые 10s, возврат в `Idle` при восстановлении |
| **Падение сервиса во время записи**                 | Отменить текущий запрос, освободить аудио-буфер, вернуться в `Idle`                                                                                    | ⚠️ Error toast: «Ошибка обработки, попробуйте снова» | Следующий hotkey — новая попытка                              |
| **Внезапное закрытие (power loss)**                 | При нормальном выходе — cleanup аудио, освобождение hotkey hooks. При аварийном — Windows сам убивает процесс, нет persistent state для восстановления | —                                                    | При перезапуске — чистый старт                                |
| **Потеря фокуса окна**                              | `SendInput` не сработает → fallback на clipboard + paste                                                                                               | 📋 Toast: «Вставлено через буфер обмена»             | Пользователь вставляет вручную Ctrl+V                         |
| **Залипание hotkey** (пользователь забыл отпустить) | Таймаут записи: max 60 секунд → авто-стоп                                                                                                              | 🔴 Toast: «Запись остановлена (таймаут 60s)»         | Авто-возврат в `Idle`                                         |
| **Очень длинная фраза** (>30s)                      | VAD может не отработать → принудительный split по таймауту или отправка целиком                                                                        | ⏳ Processing дольше обычного                         | Нет действий                                                  |

**Архитектурные решения для устойчивости:**

- **Асинхронный HTTP клиент (`httpx` async)** — запросы в ASR/LLM не блокируют UI thread, tray остаётся отзывчивым
- **Таймауты на всех уровнях:**
    - HTTP connect timeout: 5s
    - HTTP read timeout: 30s (ASR), 60s (LLM)
    - Recording max duration: 60s
    - VAD silence timeout: 500ms
- **Отмена (cancellation):** если пользователь нажал «Паузу» или «Выход» во время `Processing` — текущий HTTP request
  отменяется (`client.close()`), tray мгновенно переходит в `Disabled`
- **Нет shared mutable state:** аудио-буфер создаётся заново на каждый hotkey, нет риска data corruption

- Иконки статуса: 🟢 OK / 🟡 Загрузка / 🔴 Ошибка / ⚪ Не используется
- Название текущей модели отображается рядом со статусом
- Клик по неисправному сервису — открывает его лог или перезапускает
- Автообновление каждые 5 секунд (опрос `/api/v1/health`)
- Если все сервисы OK — пункт «Статус» показывает 🟢, иначе 🔴

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

### 3.3 Логирование, retry и observability

**Структурированное логирование каждого шага:**

Каждый запрос (одно нажатие hotkey) получает `trace_id` (UUID4), который пробрасывается через все компоненты:

```text
Client:     [trace_id=abc-123] Hotkey pressed
Client:     [trace_id=abc-123] Audio capture started (duration: 3.2s)
Client:     [trace_id=abc-123] VAD: speech detected (confidence: 0.87)
Client:     [trace_id=abc-123] POST /api/v1/transcribe → API GW
API GW:     [trace_id=abc-123] Forwarding to ASR (model: base, language: auto)
ASR:        [trace_id=abc-123] Whisper inference: 340ms
API GW:     [trace_id=abc-123] Forwarding to LLM (model: llama3.2:3b)
LLM:        [trace_id=abc-123] Ollama generate: 890ms, tokens: 24
Client:     [trace_id=abc-123] Text injected via SendInput (42 chars, 120ms)
Client:     [trace_id=abc-123] Pipeline completed: total 1850ms
```

**Формат логов:**

```json
{
  "timestamp": "2026-05-20T17:45:01.123Z",
  "level": "INFO",
  "trace_id": "abc-123",
  "component": "client/audio",
  "event": "capture_started",
  "duration_ms": 3200,
  "sample_rate": 16000,
  "vad_threshold": 0.5
}
```

**Инструменты: `structlog` vs `loguru`:**

| Критерий           | `structlog`                                    | `loguru`                                      |
|--------------------|------------------------------------------------|-----------------------------------------------|
| **Назначение**     | Структурированные JSON-логи с контекстом       | Простой и красивый вывод + ротация            |
| **Конфигурация**   | Явная (processors, formatters)                 | Минимальная (один `logger.add`)               |
| **Ротация файлов** | ❌ Нет встроенной                               | ✅ `rotation`, `retention`, `compression`      |
| **JSON вывод**     | ✅ Нативно (best-in-class)                      | ✅ Через `serialize=True`                      |
| **Bind контекста** | ✅ `bind(trace_id=...)` — идеально для pipeline | ⚠️ `contextualize` (менее гибко)              |
| **Windows CLI**    | Читаемый JSON в консоли                        | Цветной pretty-print (удобнее для разработки) |
| **Рекомендация**   | **API Gateway, сервисы**                       | **Клиент (dev mode)**                         |

**Рекомендуемая стратегия:**

1. **API Gateway + Docker сервисы:** `structlog` — чистый JSON в stdout, без ротации (Docker сам управляет логами).
   ```python
   import structlog
   logger = structlog.get_logger()
   logger.info("asr_request", trace_id=tid, model="base", duration_ms=340)
   ```

2. **Windows Client:** `loguru` для dev-режима (красивый цветной вывод) + `structlog` для production JSON.
   ```python
   from loguru import logger
   logger.add("logs/client_{time}.log", rotation="10 MB", retention="1 week", serialize=True)
   ```

3. **Единый формат:** Оба инструмента настраиваются на вывод одинакового JSON-формата, чтобы логи клиента и сервера
   можно было агрегировать (например, в `jq` или будущий ELK).

**Место хранения логов:**
| Компонент | Локация | Ротация |
|-----------|---------|---------|
| Windows Client | `logs/client_YYYY-MM-DD.log` | 10 MB / 7 дней |
| API Gateway | stdout → Docker logs | Docker log driver |
| ASR / LLM | stdout → Docker logs | Docker log driver |

---

**Механизм повторных попыток (Retry):**

| Сервис               | Стратегия           | Параметры                                     |
|----------------------|---------------------|-----------------------------------------------|
| **ASR**              | Exponential backoff | max 3 attempts, base delay 0.5s, multiplier 2 |
| **LLM**              | Exponential backoff | max 2 attempts, base delay 1s, multiplier 2   |
| **LanguageTool**     | Linear retry        | max 2 attempts, delay 0.3s                    |
| **Docker (general)** | Linear retry        | max 2 attempts, delay 2s                      |
| **API Gateway**      | Circuit breaker     | 5 errors in 60s → open for 30s                |

**Retry сценарии:**

- `ConnectionError` / `Timeout` — retry
- `ConnectionRefused` (Docker-сервис ещё поднимается) — **1-2 retry с задержкой 2s**
- `HTTP 5xx` — retry
- `HTTP 503 Service Unavailable` (Docker перезапускается) — **retry 2 раза**
- `HTTP 4xx` (кроме 429) — **no retry**, логируем ошибку
- `HTTP 429 Too Many Requests` — retry с `Retry-After` header

**Особенность Docker-окружения:**
Контейнеры могут быть временно недоступны при:

- Первом старте (`docker-compose up` — сервисы поднимаются не одновременно)
- Авто-перезапуске (`restart: unless-stopped`)
- OOM kill / перезагрузке модели

При `ConnectionRefused` клиент **не показывает ошибку пользователю**, а молча retry'ит до 2 раз. Только если все попытки
исчерпаны — показывается `Offline` toast.

**Circuit Breaker (API Gateway → downstream):**

```text
Closed  → запросы идут нормально
Open    → после 5 ошибок подряд, все запросы отклоняются мгновенно
Half-Open → через 30s пробный запрос, если OK → Closed
```

При открытом Circuit Breaker:

- ASR: fallback на локальный кэш последних N фраз (если есть)
- LLM: fallback на `cleanup_mode: none` (raw ASR)
- Пользователю: tray toast «Сервис временно недоступен, работаю в offline-режиме»

**Конфигурация:**

```yaml
logging:
  level: "INFO"              # DEBUG | INFO | WARNING | ERROR
  format: "json"             # json | pretty
  directory: "./logs"
  rotation_mb: 10
  retention_days: 7

retry:
  asr:
    max_attempts: 3
    base_delay: 0.5
    multiplier: 2.0
  llm:
    max_attempts: 2
    base_delay: 1.0
    multiplier: 2.0

circuit_breaker:
  failure_threshold: 5
  recovery_timeout: 30
  half_open_max_calls: 1
```

**Timing Performance metrics (отдельный файл):**

Каждый запрос логирует время прохождения через все этапы pipeline в **отдельный файл** `logs/timing_YYYY-MM-DD.jsonl`:

| Этап               | Метрика   | Когда замеряется                           |
|--------------------|-----------|--------------------------------------------|
| `hotkey_press`     | `t0`      | Момент нажатия hotkey                      |
| `capture_start`    | `t1 - t0` | Начало записи с микрофона                  |
| `capture_duration` | `t2 - t1` | Длительность записи (пока зажат hotkey)    |
| `vad_process`      | `t3 - t2` | Обработка VAD после отпускания hotkey      |
| `encode_wav`       | `t4 - t3` | Кодирование буфера в WAV (in-memory)       |
| `network_upload`   | `t5 - t4` | Отправка аудио на API Gateway              |
| `asr_inference`    | `t6 - t5` | Whisper inference (включает queue time)    |
| `llm_cleanup`      | `t7 - t6` | LLM post-processing (если включено)        |
| `network_download` | `t8 - t7` | Получение ответа от API Gateway            |
| `text_inject`      | `t9 - t8` | Вставка текста через SendInput / clipboard |
| `total_e2e`        | `t9 - t0` | Полное время от нажатия hotkey до вставки  |

**Формат timing-лога (JSON Lines):**

  ```json
  {
  "timestamp": "2026-05-20T17:45:01.123Z",
  "trace_id": "abc-123",
  "total_ms": 1850,
  "stages": {
    "capture_ms": 3200,
    "vad_ms": 12,
    "encode_ms": 5,
    "upload_ms": 45,
    "asr_ms": 340,
    "llm_ms": 890,
    "download_ms": 15,
    "inject_ms": 120
  },
  "models": {
    "asr": "base",
    "llm": "llama3.2:3b"
  },
  "language": "ru",
  "audio_duration_ms": 3200,
  "text_length": 42
}
```

**Особенности:**

- Файл `logs/timing_*.jsonl` отделён от основных логов — удобно для анализа и построения графиков
- `capture_ms` может быть > `total_ms`, так как оно overlap'ит с реальным временем (пользователь говорит, пока идёт
  запись)
- `llm_ms = 0` если cleanup отключён или fallback на raw ASR
- Можно агрегировать в Excel / Grafana / просто `jq`:
  ```bash
  jq -r '.total_ms' logs/timing_*.jsonl | awk '{sum+=$1; count++} END {print sum/count}'
  ```

**Конфигурация:**

```yaml
timing:
  enabled: true
  file: "logs/timing.jsonl"
  rotation_mb: 50
  retention_days: 30
  stages:
    - hotkey_press
    - capture_start
    - capture_duration
    - vad_process
    - encode_wav
    - network_upload
    - asr_inference
    - llm_cleanup
    - network_download
    - text_inject
```

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
    "keyboard>=0.13",
    "pynput>=1.7", # fallback если keyboard не работает
    "httpx[http2]>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
    "onnxruntime>=1.18", # Silero VAD
]
```

### 5.2 Docker Images

| Сервис | Образ                                     | Порты   |
|--------|-------------------------------------------|---------|
| ASR    | `fedirz/faster-whisper-server:latest-cpu` | `8000`  |
| LLM    | `ollama/ollama`                           | `11434` |
| API GW | кастомный `Dockerfile` (FastAPI)          | `8080`  |

### 5.3 Инфраструктура хоста

- **Docker Desktop** с WSL2 backend
- **Python 3.14+** (клиент запускается natively на Windows, не в Docker)
- **RAM:** минимум 4GB (для tiny + 1B моделей), рекомендуется 8GB+ (для base + 3B)
- **CPU:** любой современный x64 процессор (Intel 6th gen+ / AMD Ryzen)
- **GPU:** не требуется

### 5.4 CPU-оптимизации

| Оптимизация                  | Применение                                      | Эффект                                      |
|------------------------------|-------------------------------------------------|---------------------------------------------|
| **INT8 квантование** (ASR)   | `faster-whisper` с `compute_type=int8`          | Снижение RAM на 50%, ускорение на CPU до 2x |
| **Q4_K_M квантование** (LLM) | Ollama с `q4_0` / `q4_k_m`                      | Модель 3B занимает ~1.6GB вместо 6GB        |
| **ONNX Runtime** (VAD)       | Silero VAD через `onnxruntime`                  | CPU inference, ~10MB RAM                    |
| **Thread limiting**          | `WHISPER_CPU_THREADS=4`, `OLLAMA_NUM_THREADS=0` | Предотвращение блокировки системы           |
| **Memory limits**            | Docker `deploy.resources.limits.memory`         | Предотвращение OOM на ноутбуках             |
| **Flash Attention**          | `OLLAMA_FLASH_ATTENTION=1`                      | Ускорение inference на CPU, снижение RAM    |
| **Model tiering**            | `tiny`/`1b` для слабых, `base`/`3b` для средних | Адаптация под железо пользователя           |

### 5.5 Альтернативные библиотеки (анализ)

#### `boppreh/keyboard` — Global Hotkeys

| Критерий            | `boppreh/keyboard`                            | `pynput`                              |
|---------------------|-----------------------------------------------|---------------------------------------|
| **Maintenance**     | ❌ Unmaintained (с 2020)                       | ✅ Active, Python 3.14                 |
| **Зависимости**     | Zero deps                                     | Несколько deps                        |
| **Windows**         | ✅ Отлично                                     | ✅ Работает                            |
| **Hold-to-record**  | ✅ Нативно (`on_press_key` / `on_release_key`) | ⚠️ Сложнее (listener + state machine) |
| **Complex hotkeys** | ✅ `ctrl+shift+m, ctrl+space`                  | ⚠️ Ограниченнее                       |
| **Python 3.14**     | ⚠️ Не тестирован, но вероятно работает        | ✅ Поддерживается                      |
| **Admin rights**    | ⚠️ Может потребоваться на некоторых системах  | ✅ Обычно не нужны                     |
| **Рекомендация**    | **Primary для hotkey**                        | Fallback / mouse events               |

**Почему `keyboard` — primary choice для hotkey:**

Основной паттерн VoiVoice — *hold to record*:

```python
import keyboard


def on_hotkey_press():
    tray.set_listening()
    audio.start_recording()


def on_hotkey_release():
    audio.stop_recording()
    tray.set_processing()
    process_and_inject(audio.get_buffer())


# Регистрация "зажал-отпустил"
keyboard.on_press_key("ctrl+alt+v", lambda _: on_hotkey_press())
keyboard.on_release_key("ctrl+alt+v", lambda _: on_hotkey_release())
```

На `pynput` тот же паттерн требует ручного отслеживания состояния модификаторов:

```python
from pynput import keyboard

pressed = set()


def on_press(key):
    pressed.add(key)
    if is_hotkey_match(pressed, HOTKEY):
        start_recording()


def on_release(key):
    if is_hotkey_match(pressed, HOTKEY):
        stop_recording()
    pressed.discard(key)
```

**Вывод для плана:**

- **`keyboard`** — primary для global hotkey (удобство API под hold-to-record, zero deps, Windows-first).
- **`pynput`** — остаётся в зависимостях как fallback: если `keyboard` не работает на конкретной системе (требует прав
  администратора, конфликт с античитом), клиент переключается на `pynput` через `config.yaml`.
- **Mouse events** (если понадобятся в v2) — только через `pynput` или отдельную библиотеку `mouse`.

---

### 5.6 RNNoise — шумоподавление (Pre-processing)

**RNNoise** — open-source RNN-шумоподавление от Xiph.org. Модель ~50KB, latency ~10ms, работает на CPU.

| Критерий          | RNNoise                           | `noisereduce` (spectral gating) | Без шумоподавления |
|-------------------|-----------------------------------|---------------------------------|--------------------|
| **Качество**      | ✅ Отличное (RNN)                  | ⚠️ Среднее                      | ❌ Сырой микрофон   |
| **Размер модели** | ~50KB                             | Нет модели                      | —                  |
| **Latency**       | ~10ms                             | ~100-500ms                      | 0ms                |
| **CPU нагрузка**  | Очень низкая                      | Средняя (numpy FFT)             | Нет                |
| **Real-time**     | ✅ Chunk-by-chunk                  | ⚠️ Требует весь буфер           | ✅                  |
| **Установка**     | ⚠️ Может требовать сборки         | ✅ `pip install noisereduce`     | ✅                  |
| **Ресемплинг**    | 48kHz → 16kHz (нужен ffmpeg/soxr) | Работает на любой частоте       | —                  |

**Рекомендуемая интеграция в pipeline:**

RNNoise добавляется **в клиент** (не в Docker), так как модель весит 50KB и работает в real-time без сетевых задержек:

```text
Mic Input (48kHz)
    ↓
RNNoise (шумоподавление, 48kHz)
    ↓
Resample to 16kHz (soxr / librosa)
    ↓
VAD (Silero, 16kHz)
    ↓
ASR (Whisper, 16kHz)
```

**Варианты реализации на Python:**

| Вариант                     | Сложность                            | Качество |
|-----------------------------|--------------------------------------|----------|
| `ffmpeg` + фильтр `arnndn`  | Низкая (требует ffmpeg 4.4+)         | Отличное |
| `rnnoise-python` (ctypes)   | Средняя                              | Отличное |
| `noisereduce` (pure Python) | Низкая                               | Среднее  |
| **Рекомендация**            | `ffmpeg arnndn` или `rnnoise-python` |          |

**Docker-альтернатива (если не получится в клиенте):**
Можно добавить микросервис `denoiser` в `docker-compose`, но это +1 network hop для real-time аудио. Клиентский вариант
предпочтительнее.

**Конфигурация:**

```yaml
audio:
  noise_reduction: "rnnoise"   # rnnoise | noisereduce | none
  input_sample_rate: 48000     # для RNNoise
  asr_sample_rate: 16000       # Whisper требует 16kHz
```

**Вывод:** RNNoise — must-have для ноутбучных микрофонов. Модель 50KB не влияет на дистрибутив, latency 10ms
пренебрежимо мала. Рекомендуется `rnnoise-python` или `ffmpeg arnndn` с последующим ресемплингом до 16kHz.

---

### 5.7 LanguageTool — альтернатива / дополнение LLM cleanup

**LanguageTool** — open-source проверщик грамматики/орфографии/стиля, работает локально (Java-based, Docker-образ
`erikvl87/languagetool`).

| Аспект              | LanguageTool                   | LLM (Ollama)                   |
|---------------------|--------------------------------|--------------------------------|
| **Скорость**        | ⚡ ~50-150ms                    | 🐢 ~500ms-2s (CPU)             |
| **Filler words**    | ❌ Не удаляет («ну типа», «эм») | ✅ Удаляет                      |
| **Пунктуация**      | ✅ Правила + ngrams             | ✅ Контекстный inference        |
| **Грамматика**      | ✅ Правила (30+ языков)         | ✅ Контекстное понимание        |
| **Стиль переписки** | ❌ Не адаптирует                | ✅ Адаптирует под контекст      |
| **RAM**             | ~1-1.5GB (JVM)                 | ~0.8-1.6GB (зависит от модели) |
| **CPU**             | Умеренная                      | Высокая (3B модель)            |
| **Bilingual**       | ✅ RU + EN из коробки           | ✅ Через prompt                 |

**Рекомендуемая стратегия для плана:**

Добавить LanguageTool как **опциональный** сервис в `docker-compose.yml` и дать пользователю выбор режима cleanup в
`config.yaml`:

```yaml
services:
  cleanup_mode: "llm"           # llm | languagetool | both | none
```

| Режим          | Когда использовать             | Pipeline                           |
|----------------|--------------------------------|------------------------------------|
| `llm`          | По умолчанию                   | ASR → LLM cleanup → вставка        |
| `languagetool` | Слабый ноутбук, нужна скорость | ASR → LanguageTool → вставка       |
| `both`         | Максимум качества              | ASR → LLM → LanguageTool → вставка |
| `none`         | Минимум latency                | ASR → вставка (raw)                |

**Docker для LanguageTool:**

```yaml
  languagetool:
    image: erikvl87/languagetool:latest
    ports:
      - "8010:8010"
    environment:
      - Java_Xms=512m
      - Java_Xmx=1g
    deploy:
      resources:
        limits:
          memory: 1.5G
```

**API:**

```
POST /v2/check
{
  "text": "ну типа отправь отчет завтра",
  "language": "ru-RU"
}
```

**Вывод:** LanguageTool — отличное дополнение к архитектуре. Быстрее LLM, предсказуемее, не требует GPU. Не заменяет LLM
полностью (не умеет semantic cleanup), но идеален как fallback для слабых ноутбуков или как финальная грамматическая
проверка после LLM.

---

### 5.7 Билингвальность (русский + английский)

Whisper из коробки поддерживает 99+ языков с автоопределением, но для русского/английского сочетания есть нюансы:

| Аспект              | Рекомендация                                                 | Почему                                                                              |
|---------------------|--------------------------------------------------------------|-------------------------------------------------------------------------------------|
| **ASR модель**      | `small` вместо `base` если RAM ≥ 8GB                         | На русском `base` иногда путает окончания и ударения; `small` заметно точнее        |
| **Язык (explicit)** | Параметр `language` в API (ru/en)                            | Ускоряет inference на ~20% vs `auto`, убирает ошибки определения на коротких фразах |
| **Язык (auto)**     | `language=auto` по умолчанию                                 | Удобно, но +100-300ms на определение; fallback если mixed speech                    |
| **LLM cleanup**     | Prompt: *"Preserve the original language of the transcript"* | Предотвращает перевод русского текста на английский при cleanup                     |
| **Code-switching**  | Ожидайте худшей точности                                     | Переключение языка внутри фразы ("давай сделаем deploy") — слабое место всех ASR    |
| **Кэширование**     | Кэшировать системный промпт LLM по языку                     | Снижает время подготовки prompt на повторных запросах                               |

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
- [ ] Логирование (`structlog` для сервисов, `loguru` для клиента, единый JSON формат)
- [ ] **Timing-логи:** замер каждого этапа pipeline в отдельный `logs/timing.jsonl`
- [ ] Обработка ошибок и retry logic
- [ ] Иконки для **всех 10 tray состояний** (SVG/PNG, 16x16, 32x32)
- [ ] OSD оверлей (`tkinter` / `PyQt`): listening indicator + partial transcript
- [ ] Звуковой бейкон (генерация sine wave, ascending/descending tones)
- [ ] Tray tooltip с динамическим статусом
- [ ] Toast-уведомления Windows (ошибки, статус моделей)
- [ ] Контекстное меню tray: пауза, язык, cleanup-режим, шумоподавление
- [ ] Установщик / `.bat` для запуска
- [ ] **Документация:** README + docs/ (configuration, troubleshooting, API, FAQ)
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
11. [ ] **Сеть упала:** приложение показывает `Offline` в tray, не зависает, восстанавливается при возвращении Docker.
12. [ ] **Сбой во время записи:** приложение не падает, освобождает буфер, возвращается в `Idle` с error toast.

---

## 13. Документация

Подробная документация — обязательный deliverable проекта, не откладываемый «на потом».

### 13.1 Структура документации

```
VoiVoice/
├── README.md              # ← Корневой README: главный вход в проект
├── docs/
│   ├── configuration.md   # Подробное описание всех опций config.yaml
│   ├── architecture.md    # Архитектурная схема, компоненты, pipeline
│   ├── troubleshooting.md # Решение типичных проблем
│   ├── api.md             # API reference (Client ↔ Gateway, Gateway ↔ Services)
│   ├── models.md          # Выбор моделей: tiny/base/small, 1B/3B, INT8/Q4_K_M
│   ├── faq.md             # Частые вопросы
│   └── CHANGELOG.md       # История изменений
```

### 13.2 Содержание по файлам

**`README.md`** (корень проекта — первое, что видит пользователь на GitHub)

- Заголовок + 1-2 предложения: что делает VoiVoice
- Бейджи: Python 3.14+, Windows, Docker, License
- Системные требования (Windows 10+, Docker Desktop + WSL2, RAM, CPU)
- Быстрая установка — **3 шага**:
    1. `git clone ...`
    2. `docker-compose up -d`
    3. `python -m src.client.main`
- Гифка или скриншот работы (hotkey → голос → текст в Notepad)
- Краткое описание ключевых фич (local-only, CPU, bilingual)
- Ссылка на полную документацию в `docs/`
- Ссылка на `docs/faq.md` для сомневающихся

**`docs/configuration.md`**

- Полное описание каждой секции `config.yaml`:
    - `hotkey` — как задать комбинацию, hold vs toggle mode
    - `audio` — sample_rate, VAD threshold, silence_timeout
    - `services` — выбор моделей ASR/LLM, URL сервисов
    - `cleanup_mode` — когда какой режим выбрать
    - `noise_reduction` — RNNoise vs none
    - `toasts`, `audio_feedback`, `timing` — настройка UX
- Примеры config для разных сценариев:
    - «Слабый ноутбук» (tiny + 1B + languagetool + no RNNoise)
    - «Максимум качества» (small + 3B + both cleanup + RNNoise)
    - «Только ASR» (no cleanup, fastest latency)

**`docs/troubleshooting.md`**
| Симптом | Причина | Решение |
|---------|---------|---------|
| Иконка не появляется в трее | Клиент упал при старте | Смотреть `logs/client_*.log` |
| «Сервисы недоступны» | Docker не запущен | `docker-compose up -d` |
| Микрофон не найден | PyAudio / драйверы | Проверить устройства в Windows |
| Текст вставляется медленно | CPU перегружен | Переключиться на tiny + 1B |
| Не работает hotkey | Конфликт с другим ПО | Сменить комбинацию в config.yaml |
| Whisper не распознаёт русский | Неверный language | Установить `language: ru` |

**`docs/api.md`**

- Полная спецификация endpoints (`/api/v1/transcribe`, `/health`)
- Примеры запросов/ответов `curl`
- Коды ошибок и их значения
- WebSocket (если появится streaming в v2)

**`docs/models.md`**

- Сравнительная таблица моделей ASR (tiny/base/small) по точности/latency/RAM
- Сравнительная таблица LLM (1B/3B) по качеству cleanup/latency/RAM
- Рекомендации по выбору под железо

**`docs/faq.md`**

- «Почему не Google Speech API?» — privacy, локальность
- «Можно ли без Docker?» — нет, ASR/LLM требуют изоляции
- «Работает ли на Windows 7?» — нет, Python 3.14+
- «Поддерживает ли macOS?» — нет, Windows-only

### 13.3 Когда писать

| Phase         | Что документировать                                     |
|---------------|---------------------------------------------------------|
| **Phase 0**   | README (скелет), architecture.md (схема)                |
| **Phase 1-2** | api.md, models.md                                       |
| **Phase 3**   | configuration.md (по мере добавления опций)             |
| **Phase 4**   | troubleshooting.md, faq.md, CHANGELOG, финальный README |

---

## 14. Следующий шаг

Перейти к **Phase 0** — создать `docker-compose.yml`, FastAPI Gateway, базовый скелет клиента и проверить end-to-end
связность.
