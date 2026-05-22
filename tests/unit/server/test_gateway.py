from fastapi.testclient import TestClient

from src.server.main import app

# Синхронный тестовый клиент FastAPI
client = TestClient(app)


def test_root():
    """Тест: корневой эндпоинт возвращает версию API."""
    response = client.get('/')
    assert response.status_code == 200
    assert response.json()['version'] == '0.1.0'


def test_health_degraded(monkeypatch):
    """Тест: при недоступности зависимых сервисов /health возвращает 503."""

    async def mock_check(*args, **kwargs):
        return False

    import src.server.app.routers.health as health

    # Подменяем проверку сервисов, чтобы она всегда возвращала False
    monkeypatch.setattr(health, '_check_service', mock_check)

    response = client.get('/api/v1/health')
    assert response.status_code == 503
    data = response.json()
    assert data['status'] == 'degraded'
