import httpx
import pytest

from src.client.api_client import APIClient


@pytest.fixture
def client():
    return APIClient("http://localhost:8080")


@pytest.mark.asyncio
async def test_health_success(respx_mock):
    respx_mock.get("http://localhost:8080/api/v1/health").mock(
        return_value=httpx.Response(200, json={"status": "ok", "services": {}})
    )
    result = await client().health()
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_transcribe_success(respx_mock):
    respx_mock.post("http://localhost:8080/api/v1/transcribe").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "raw": "hello",
                "cleaned": "Hello.",
                "language": "en",
            },
        )
    )
    result = await client().transcribe(b"fake wav data")
    assert result["raw"] == "hello"
    assert result["cleaned"] == "Hello."
