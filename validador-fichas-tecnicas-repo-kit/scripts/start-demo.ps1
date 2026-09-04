<#
.SYNOPSIS
    Arranca Farmalidacion en modo DEMO con datos de demostracion.

.DESCRIPTION
    Levanta backend y frontend contra una base propia y desechable (demo.db en
    un volumen de Docker), sembrada con los fixtures de demostracion. No toca
    data/local/real.db ni necesita los maestros Excel.

    Los datos que se ven aqui NO provienen de los maestros ni de CIMA, y la
    interfaz lo declara de forma permanente.

.PARAMETER SkipBuild
    Reutiliza las imagenes ya construidas en lugar de reconstruirlas.

.PARAMETER Reset
    Descarta el volumen de la demo antes de arrancar, dejando la base como
    recien sembrada. Solo afecta a la demo: la base real vive fuera del volumen.

.EXAMPLE
    ./scripts/start-demo.ps1
#>
[CmdletBinding()]
param(
    [switch] $SkipBuild,
    [switch] $Reset
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$BackendUrl = 'http://127.0.0.1:8000'
$FrontendUrl = 'http://127.0.0.1:5173'

function Write-Step { param([string] $Message) Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok { param([string] $Message) Write-Host "    $Message" -ForegroundColor Green }

function Wait-Endpoint {
    param([string] $Url, [string] $Label, [int] $Attempts = 60)
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) { Write-Ok "$Label responde."; return $true }
        }
        catch { Start-Sleep -Seconds 2 }
    }
    Write-Host "    $Label no ha respondido tras $Attempts intentos." -ForegroundColor Red
    return $false
}

Push-Location $RepositoryRoot
try {
    if ($Reset) {
        Write-Step 'Descartando el volumen de la demo'
        & docker compose --profile demo down -v
    }

    Write-Step 'Levantando backend y frontend en modo DEMO'
    $arguments = @('compose', '--profile', 'demo', 'up', '-d')
    if (-not $SkipBuild) { $arguments += '--build' }
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw 'docker compose ha fallado.' }

    Write-Step 'Esperando a que los servicios respondan'
    $backendOk = Wait-Endpoint "$BackendUrl/health" 'Backend'
    $frontendOk = Wait-Endpoint $FrontendUrl 'Frontend'
    if (-not ($backendOk -and $frontendOk)) {
        Write-Host ''
        Write-Host 'Revise los registros con: docker compose --profile demo logs' -ForegroundColor Yellow
        exit 1
    }

    $info = Invoke-RestMethod -Uri "$BackendUrl/database-info" -TimeoutSec 5
    Write-Host ''
    Write-Host "    modo      : $($info.mode)"
    Write-Host "    base      : $($info.database) ($($info.backend))"
    Write-Host "    registros : $($info.records_total) (reales $($info.records_real), demo $($info.records_demo))"

    Write-Host ''
    Write-Host 'Farmalidacion en modo DEMO (datos de demostracion):' -ForegroundColor Yellow
    Write-Host "    Aplicacion  : $FrontendUrl"
    Write-Host "    API         : $BackendUrl/docs"
    Write-Host "    Diagnostico : $BackendUrl/database-info"
    Write-Host ''
    Write-Host 'Para detenerlo: docker compose --profile demo down'
}
finally {
    Pop-Location
}
