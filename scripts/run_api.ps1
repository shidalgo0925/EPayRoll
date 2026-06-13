#!/usr/bin/env pwsh
# Inicia API EPayRoll
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:PYTHONPATH = Join-Path $Root "src"
if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "postgresql://epayroll:epayroll@localhost:5432/epayroll"
}
Write-Host "EPayRoll API — http://127.0.0.1:8000/docs" -ForegroundColor Cyan
python -m uvicorn epayroll.api.main:app --reload --host 127.0.0.1 --port 8000
