from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from src.server.main import app

client = TestClient(app)


class TestTranscribeRouter:
    def test_transcribe_empty_audio(self, monkeypatch):
        async def mock_asr(*args, **kwargs):
            return {'text': ''}

        import src.server.app.routers.transcribe as tr

        monkeypatch.setattr(tr, '_call_asr', mock_asr)

        response = client.post('/api/v1/transcribe', files={'file': ('test.wav', b'data', 'audio/wav')})
        assert response.status_code == 200
        data = response.json()
        assert data['raw'] == ''
        assert data['cleaned'] == ''

    def test_transcribe_with_cleanup(self, monkeypatch):
        async def mock_asr(*args, **kwargs):
            return {'text': 'hello world'}

        async def mock_llm(text, model):
            return 'Hello, world!'

        import src.server.app.routers.transcribe as tr

        monkeypatch.setattr(tr, '_call_asr', mock_asr)
        monkeypatch.setattr(tr, '_call_llm_cleanup', mock_llm)

        response = client.post(
            '/api/v1/transcribe',
            files={'file': ('test.wav', b'data', 'audio/wav')},
            data={'cleanup': 'true'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data['raw'] == 'hello world'
        assert data['cleaned'] == 'Hello, world!'
        assert data['cleanup_skipped'] is False

    def test_transcribe_cleanup_disabled(self, monkeypatch):
        async def mock_asr(*args, **kwargs):
            return {'text': 'hello world'}

        import src.server.app.routers.transcribe as tr

        monkeypatch.setattr(tr, '_call_asr', mock_asr)

        response = client.post(
            '/api/v1/transcribe',
            files={'file': ('test.wav', b'data', 'audio/wav')},
            data={'cleanup': 'false'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data['raw'] == 'hello world'
        assert data['cleaned'] == 'hello world'
        assert data['cleanup_skipped'] is True

    def test_transcribe_asr_http_error(self, monkeypatch):
        async def mock_asr(*args, **kwargs):
            raise httpx.HTTPStatusError('error', request=None, response=MagicMock(status_code=500))

        import src.server.app.routers.transcribe as tr

        monkeypatch.setattr(tr, '_call_asr', mock_asr)

        response = client.post('/api/v1/transcribe', files={'file': ('test.wav', b'data', 'audio/wav')})
        assert response.status_code == 502

    def test_transcribe_asr_request_error(self, monkeypatch):
        async def mock_asr(*args, **kwargs):
            raise httpx.RequestError('conn error')

        import src.server.app.routers.transcribe as tr

        monkeypatch.setattr(tr, '_call_asr', mock_asr)

        response = client.post('/api/v1/transcribe', files={'file': ('test.wav', b'data', 'audio/wav')})
        assert response.status_code == 503

    def test_transcribe_llm_fallback(self, monkeypatch):
        async def mock_asr(*args, **kwargs):
            return {'text': 'hello'}

        async def mock_llm(*args, **kwargs):
            raise RuntimeError('llm down')

        import src.server.app.routers.transcribe as tr

        monkeypatch.setattr(tr, '_call_asr', mock_asr)
        monkeypatch.setattr(tr, '_call_llm_cleanup', mock_llm)

        response = client.post(
            '/api/v1/transcribe',
            files={'file': ('test.wav', b'data', 'audio/wav')},
            data={'cleanup': 'true'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data['raw'] == 'hello'
        assert data['cleaned'] == 'hello'
        assert data['cleanup_skipped'] is True


class TestCallASR:
    @pytest.mark.asyncio
    async def test_call_asr_basic(self, respx_mock):
        import src.server.app.routers.transcribe as tr

        respx_mock.post(f'{tr.ASR_URL}/v1/audio/transcriptions').mock(
            return_value=httpx.Response(200, json={'text': 'hello'})
        )
        result = await tr._call_asr(b'data', 'ru', 'small')
        assert result['text'] == 'hello'

    @pytest.mark.asyncio
    async def test_call_asr_with_options(self, respx_mock):
        import src.server.app.routers.transcribe as tr

        respx_mock.post(f'{tr.ASR_URL}/v1/audio/transcriptions').mock(
            return_value=httpx.Response(200, json={'text': 'hello'})
        )
        result = await tr._call_asr(b'data', 'auto', 'small', prompt='p', vad_filter=True, hotwords='hw')
        assert result['text'] == 'hello'


class TestCallLLMCleanup:
    @pytest.mark.asyncio
    async def test_call_llm_cleanup_success(self, respx_mock):
        import src.server.app.routers.transcribe as tr

        respx_mock.post(f'{tr.LLM_URL}/api/generate').mock(
            return_value=httpx.Response(200, json={'response': 'Cleaned text.'})
        )
        result = await tr._call_llm_cleanup('raw text', 'model')
        assert result == 'Cleaned text.'

    @pytest.mark.asyncio
    async def test_call_llm_cleanup_missing_key(self, respx_mock):
        import src.server.app.routers.transcribe as tr

        respx_mock.post(f'{tr.LLM_URL}/api/generate').mock(return_value=httpx.Response(200, json={}))
        result = await tr._call_llm_cleanup('raw text', 'model')
        assert result == 'raw text'
