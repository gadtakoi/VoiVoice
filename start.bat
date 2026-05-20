@echo off
chcp 65001 >nul
echo Starting VoiVoice...
echo Make sure Docker Desktop is running and services are up:
echo   docker-compose up -d
echo.
python -m src.client.main
pause
