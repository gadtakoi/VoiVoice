$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-Not (Test-Path $python)) {
    Write-Error "Python not found in .venv. Please create venv first."
    exit 1
}

& $python -m pip install -e .
