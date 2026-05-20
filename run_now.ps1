$projectRoot = "C:\Users\BSPB\PycharmProjects\VoiVoice"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
Set-Location $projectRoot

Write-Host "Clearing cache..."
Get-ChildItem -Path src -Recurse -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Starting VoiVoice..."
& $python -m src.client.main
