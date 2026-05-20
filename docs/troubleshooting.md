# Troubleshooting

## Common Issues

| Symptom                        | Cause                          | Solution                              |
|--------------------------------|--------------------------------|---------------------------------------|
| Tray icon missing              | Client crashed on startup      | Check `logs/client_*.log`             |
| "Services unavailable"         | Docker not running             | Run `docker-compose up -d`            |
| Microphone not found           | Driver issue                   | Check Windows sound settings          |
| Slow text insertion            | CPU overloaded                 | Switch to `tiny` + `1b` models        |
| Hotkey not working             | Conflict with other software   | Change combination in `config.yaml`   |
| Russian not recognized         | Wrong language setting         | Set `language: ru` or use tray menu   |
| Docker services won't start    | Port conflict                  | Check ports 8000, 8080, 11434, 8010   |

## Logs

Client logs: `logs/client_YYYY-MM-DD.log`
Timing logs: `logs/timing_YYYY-MM-DD.jsonl`

## Getting Help

1. Check logs first
2. Verify Docker services: `docker-compose ps`
3. Test API health: `curl http://localhost:8080/api/v1/health`
