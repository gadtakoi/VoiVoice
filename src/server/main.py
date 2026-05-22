import structlog
from app.routers import health, transcribe
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Настройка структурированного логирования в формате JSON
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Создание приложения FastAPI — API-шлюз для локальных сервисов диктовки
app = FastAPI(
    title='VoiVoice API Gateway',
    description='Unified API gateway for VoiVoice local voice dictation services',
    version='0.1.0',
)

# Разрешаем CORS для всех источников (локальное приложение)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Подключаем маршруты
app.include_router(health.router)
app.include_router(transcribe.router)


@app.get('/')
async def root():
    """Корневой эндпоинт — возвращает базовую информацию о сервисе."""
    return {'message': 'VoiVoice API Gateway', 'version': '0.1.0'}
