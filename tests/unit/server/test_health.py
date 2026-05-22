from fastapi.testclient import TestClient

from src.server.main import app

client = TestClient(app)


class TestHealthRouter:
    def test_health_ok(self, monkeypatch):
        async def mock_check(*args, **kwargs):
            return True

        import src.server.app.routers.health as health

        monkeypatch.setattr(health, '_check_service', mock_check)

        response = client.get('/api/v1/health')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert data['services']['asr'] == 'ok'
        assert data['services']['llm'] == 'ok'

    def test_health_degraded(self, monkeypatch):
        async def mock_check(*args, **kwargs):
            return False

        import src.server.app.routers.health as health

        monkeypatch.setattr(health, '_check_service', mock_check)

        response = client.get('/api/v1/health')
        assert response.status_code == 503
        data = response.json()
        assert data['status'] == 'degraded'
        assert data['services']['asr'] == 'error'
        assert data['services']['llm'] == 'error'

    def test_health_partial(self, monkeypatch):
        call_count = 0

        async def mock_check(url, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return 'asr' in url

        import src.server.app.routers.health as health

        monkeypatch.setattr(health, '_check_service', mock_check)

        response = client.get('/api/v1/health')
        assert response.status_code == 503
        data = response.json()
        assert data['status'] == 'degraded'
        assert data['services']['asr'] == 'ok'
        assert data['services']['llm'] == 'error'
