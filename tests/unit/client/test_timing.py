import json

from src.client.timing import TimingLogger


class TestTimingLogger:
    def test_init_creates_directory(self, tmp_path):
        log_dir = tmp_path / 'timings'
        TimingLogger(directory=str(log_dir))
        assert log_dir.exists()

    def test_start_sets_trace(self):
        tl = TimingLogger(enabled=True)
        tl.start('trace-123')
        assert tl._current_trace == 'trace-123'
        assert 't0' in tl._start_times

    def test_mark_when_disabled(self):
        tl = TimingLogger(enabled=False)
        tl.mark('stage')
        assert not tl._start_times

    def test_mark_when_no_trace(self):
        tl = TimingLogger(enabled=True)
        tl.mark('stage')
        assert 'stage' not in tl._start_times

    def test_mark_adds_stage(self):
        tl = TimingLogger(enabled=True)
        tl.start('trace-123')
        tl.mark('upload')
        assert 'upload' in tl._start_times

    def test_finish_when_disabled(self, tmp_path):
        tl = TimingLogger(directory=str(tmp_path), enabled=False)
        tl.finish()
        assert not list(tmp_path.iterdir())

    def test_finish_when_no_trace(self, tmp_path):
        tl = TimingLogger(directory=str(tmp_path), enabled=True)
        tl.finish()
        assert not list(tmp_path.iterdir())

    def test_finish_writes_jsonl(self, tmp_path):
        tl = TimingLogger(directory=str(tmp_path), enabled=True)
        tl.start('trace-123')
        tl.mark('stage1')
        tl.finish(text_length=10, language='ru')

        files = list(tmp_path.iterdir())
        assert len(files) == 1
        content = files[0].read_text(encoding='utf-8')
        record = json.loads(content.strip())
        assert record['trace_id'] == 'trace-123'
        assert record['text_length'] == 10
        assert record['language'] == 'ru'
        assert 'total_ms' in record
        assert 'stages' in record
        assert 'stage1' in record['stages']

    def test_close_no_file(self):
        tl = TimingLogger()
        assert tl.close() is None

    def test_close_closes_file(self, tmp_path):
        tl = TimingLogger(directory=str(tmp_path), enabled=True)
        tl.start('t')
        tl.finish()
        assert tl._file is not None
        tl.close()
        assert tl._file.closed
