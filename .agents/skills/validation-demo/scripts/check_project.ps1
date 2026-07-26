param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"

Write-Host "[check] Python compile"
python -m compileall src main.py

if (-not $SkipFrontend) {
    Write-Host "[check] Frontend lint/build"
    Push-Location frontend
    try {
        npm run lint
        npm run build
    }
    finally {
        Pop-Location
    }
}

Write-Host "[check] done"
