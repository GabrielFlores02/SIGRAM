$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

docker compose up --build --detach
docker compose ps

Write-Host ""
Write-Host "SIGRAM-AM disponible en http://127.0.0.1:8088" -ForegroundColor Cyan
Write-Host "API y documentación en http://127.0.0.1:8001/docs" -ForegroundColor Cyan
