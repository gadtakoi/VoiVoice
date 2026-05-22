import json
import time
from pathlib import Path

from loguru import logger


class TimingLogger:
    """Логгер времени выполнения этапов обработки (для отладки и мониторинга)."""

    def __init__(self, directory: str = './logs', enabled: bool = True):
        """Инициализация.

        Args:
            directory: Папка для записи JSONL-файлов.
            enabled: Включить ли сбор метрик.
        """
        self.enabled = enabled
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._file = None
        self._current_trace: str | None = None
        self._start_times: dict[str, float] = {}

    def _get_file(self):
        """Лениво открывает файл логов на текущую дату (дозапись)."""
        if self._file is None or self._file.closed:
            filename = self.directory / f'timing_{time.strftime("%Y-%m-%d")}.jsonl'
            self._file = open(filename, 'a', encoding='utf-8')
        return self._file

    def start(self, trace_id: str):
        """Начинает новую трассировку.

        Args:
            trace_id: Уникальный идентификатор запроса.
        """
        self._current_trace = trace_id
        self._start_times = {'trace_id': trace_id, 't0': time.perf_counter()}

    def mark(self, stage: str):
        """Отмечает временную метку этапа относительно t0.

        Args:
            stage: Название этапа.
        """
        if not self.enabled or not self._current_trace:
            return
        self._start_times[stage] = time.perf_counter()

    def finish(self, text_length: int = 0, language: str | None = None):
        """Завершает трассировку и записывает JSONL-запись в файл.

        Args:
            text_length: Длина распознанного текста.
            language: Язык транскрипции.
        """
        if not self.enabled or not self._current_trace:
            return
        t0 = self._start_times.get('t0', 0)
        now = time.perf_counter()

        # Вычисляем смещения всех этапов относительно старта
        stages = {}
        for key, val in self._start_times.items():
            if key in ('trace_id', 't0'):
                continue
            stages[key] = int((val - t0) * 1000)

        record = {
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S') + f'.{int((now % 1) * 1000):03d}Z',
            'trace_id': self._current_trace,
            'total_ms': int((now - t0) * 1000),
            'stages': stages,
            'text_length': text_length,
            'language': language,
        }

        try:
            f = self._get_file()
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            f.flush()
        except Exception as exc:
            logger.warning('timing_log_failed', error=str(exc))

        self._current_trace = None
        self._start_times = {}

    def close(self):
        """Закрывает файл логов."""
        if self._file and not self._file.closed:
            self._file.close()
