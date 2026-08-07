# Iniciar backend de SIGRAM-AM usando un entorno virtual local valido.
# Debe ejecutarse desde el directorio raiz del proyecto.

$pythonCandidates = @(
    ".venv-local\Scripts\python.exe",
    ".venv\Scripts\python.exe"
)
$python = $null
foreach ($candidate in $pythonCandidates) {
    if (Test-Path $candidate) {
        & $candidate --version *> $null
        if ($LASTEXITCODE -eq 0) {
            $python = $candidate
            break
        }
    }
}

if (-not $python) {
    throw "No hay un entorno virtual valido. Cree .venv-local e instale backend\requirements.txt."
}

Write-Host "Iniciando backend de SIGRAM-AM en http://127.0.0.1:8000..." -ForegroundColor Green
& $python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
