$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

docker compose up --build --detach
docker compose ps

Write-Host ""
Write-Host "SIGRAM-AM (desarrollo) disponible en http://127.0.0.1:8089" -ForegroundColor Cyan
Write-Host "API y documentación de desarrollo en http://127.0.0.1:8002/docs" -ForegroundColor Cyan
