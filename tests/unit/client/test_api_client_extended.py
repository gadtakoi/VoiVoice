import httpx
import pytest

from src.client.api_client import APIClient


@pytest.fixture
def client():
    return APIClient('http://localhost:8080')


class TestAPIClientGetClient:
    @pytest.mark.asyncio
    async def test_get_client_creates_new(self, client):
        c = await client._get_client()
        assert c is not None
        assert isinstance(c, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_get_client_reuses(self, client):
        c1 = await client._get_client()
        c2 = await client._get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_get_client_reopens_closed(self, client):
        c1 = await client._get_client()
        await c1.aclose()
        c2 = await client._get_client()
        assert c2 is not c1
        assert not c2.is_closed


class TestAPIClientClose:
    @pytest.mark.asyncio
    async def test_close_when_open(self, client):
        await client._get_client()
        await client.close()
        assert client._client.is_closed

    @pytest.mark.asyncio
    async def test_close_when_already_closed(self, client):
        await client._get_client()
        await client.close()
        await client.close()
        assert client._client.is_closed

    @pytest.mark.asyncio
    async def test_close_when_none(self, client):
        await client.close()
        assert client._client is None


class TestAPIClientTranscribeRetry:
    @pytest.mark.asyncio
    async def test_transcribe_retry_then_success(self, respx_mock, client):
        respx_mock.post('http://localhost:8080/api/v1/transcribe').mock(
            side_effect=[
                httpx.ConnectError('conn err'),
                httpx.Response(200, json={'raw': 'hello', 'cleaned': 'Hello.'}),
            ]
        )
        result = await client.transcribe(b'data', max_attempts=2, base_delay=0.01, multiplier=1.0)
        assert result['raw'] == 'hello'

    @pytest.mark.asyncio
    async def test_transcribe_all_retries_fail(self, respx_mock, client):
        respx_mock.post('http://localhost:8080/api/v1/transcribe').mock(side_effect=httpx.ConnectError('conn err'))
        with pytest.raises(httpx.ConnectError):
            await client.transcribe(b'data', max_attempts=2, base_delay=0.01, multiplier=1.0)

    @pytest.mark.asyncio
    async def test_transcribe_http_error_no_retry(self, respx_mock, client):
        respx_mock.post('http://localhost:8080/api/v1/transcribe').mock(return_value=httpx.Response(500, text='error'))
        with pytest.raises(httpx.HTTPStatusError):
            await client.transcribe(b'data')

    @pytest.mark.asyncio
    async def test_transcribe_prompt_and_hotwords(self, respx_mock, client):
        respx_mock.post('http://localhost:8080/api/v1/transcribe').mock(
            return_value=httpx.Response(200, json={'raw': 'hello'})
        )
        result = await client.transcribe(b'data', prompt='test prompt', hotwords='word1')
        assert result['raw'] == 'hello'
