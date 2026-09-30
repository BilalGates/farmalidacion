$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $projectRoot 'backend'
$maintenanceScript = Join-Path $PSScriptRoot 'run_cima_maintenance.py'

$env:APP_DATABASE_URL = 'sqlite:///../data/local/real-preview.db'
$env:APP_DATA_MODE = 'real'
$env:APP_LOAD_DEMO_FIXTURE = 'false'
$env:APP_LOAD_SHOWCASE_FIXTURE = 'false'

Push-Location $backendDirectory
try {
    & python $maintenanceScript --start-date '27/09/2026'
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
