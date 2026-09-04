<#
.SYNOPSIS
    Arranca Farmalidacion en modo REAL sobre los maestros ya importados.

.DESCRIPTION
    Un unico comando para el flujo completo: comprueba que exista la base real,
    ofrece crearla si falta, aplica migraciones, levanta backend y frontend en
    contenedores y espera a que ambos respondan.

    La ingesta NO se ejecuta en cada arranque. Los maestros tardan ~25 minutos
    en cargarse y el resultado persiste en data/local/real.db, que se monta
    desde el host precisamente para sobrevivir a `docker compose down -v`.
    Solo se propone cargar cuando la base no existe o esta vacia.

.PARAMETER Ingest
    Ejecuta la carga de maestros sin preguntar. Util en un arranque desatendido.
    La ingesta es idempotente: sobre una base ya cargada reutiliza los lotes
    existentes y termina en segundos.

.PARAMETER SkipBuild
    Reutiliza las imagenes ya construidas en lugar de reconstruirlas.

.EXAMPLE
    ./scripts/start-real.ps1

.EXAMPLE
    ./scripts/start-real.ps1 -Ingest
#>
[CmdletBinding()]
param(
    [switch] $Ingest,
    [switch] $SkipBuild
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$RealDatabase = Join-Path $RepositoryRoot 'data/local/real.db'
$RawDirectory = Join-Path $RepositoryRoot 'data/reference/raw'
$BackendUrl = 'http://127.0.0.1:8000'
$FrontendUrl = 'http://127.0.0.1:5173'

function Write-Step { param([string] $Message) Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok { param([string] $Message) Write-Host "    $Message" -ForegroundColor Green }
function Write-Note { param([string] $Message) Write-Host "    $Message" -ForegroundColor Yellow }

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
    # ------------------------------------------------------------------ 1. base
    Write-Step 'Comprobando la base de datos real'

    $needsIngest = $false
    if (-not (Test-Path $RealDatabase)) {
        Write-Note 'No existe data/local/real.db.'
        $needsIngest = $true
    }
    else {
        # Un fichero presente no basta: una base migrada pero sin importar deja
        # la aplicacion en el mismo estado vacio que motivo este script.
        $size = (Get-Item $RealDatabase).Length
        if ($size -lt 1MB) {
            Write-Note "data/local/real.db existe pero parece vacia ($size bytes)."
            $needsIngest = $true
        }
        else {
            $megabytes = [math]::Round($size / 1MB)
            Write-Ok "data/local/real.db presente ($megabytes MB)."
        }
    }

    if ($needsIngest) {
        if (-not (Test-Path $RawDirectory)) {
            Write-Host ''
            Write-Host "No se encuentra $RawDirectory." -ForegroundColor Red
            Write-Host 'Los maestros Excel son entradas locales y no se versionan.' -ForegroundColor Red
            Write-Host 'Copie los ficheros maestros a data/reference/raw y repita.' -ForegroundColor Red
            exit 1
        }

        $run = [bool] $Ingest
        if (-not $run) {
            Write-Host ''
            Write-Host 'La carga de los maestros tarda unos 25 minutos y solo hace falta una vez.'
            $answer = Read-Host 'Ejecutar la carga ahora? [s/N]'
            $run = $answer -match '^[sSyY]'
        }

        if (-not $run) {
            Write-Host ''
            Write-Host 'Arranque cancelado. Para cargar los maestros:' -ForegroundColor Yellow
            Write-Host '  $env:APP_DATABASE_URL = "sqlite:///./data/local/real.db"' -ForegroundColor Yellow
            Write-Host '  python -m pharma_validator_api.cli.ingest_real_data' -ForegroundColor Yellow
            exit 1
        }

        Write-Step 'Cargando los maestros Excel (esto tarda ~25 minutos)'
        $env:APP_DATABASE_URL = 'sqlite:///./data/local/real.db'
        $env:PYTHONPATH = Join-Path $RepositoryRoot 'backend/src'
        python -m pharma_validator_api.cli.ingest_real_data
        if ($LASTEXITCODE -ne 0) { throw 'La carga de maestros ha fallado.' }
        Write-Ok 'Maestros cargados.'
    }

    # --------------------------------------------------- 2. migraciones y arranque
    # El servicio aplica `alembic upgrade head` en su propio arranque, de modo
    # que las migraciones quedan cubiertas por el contenedor.
    Write-Step 'Levantando backend y frontend en modo REAL'

    $arguments = @('compose', '--profile', 'real', 'up', '-d')
    if (-not $SkipBuild) { $arguments += '--build' }
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw 'docker compose ha fallado.' }

    # ------------------------------------------------------------ 3. healthchecks
    Write-Step 'Esperando a que los servicios respondan'

    $backendOk = Wait-Endpoint "$BackendUrl/health" 'Backend'
    $frontendOk = Wait-Endpoint $FrontendUrl 'Frontend'
    if (-not ($backendOk -and $frontendOk)) {
        Write-Host ''
        Write-Host 'Revise los registros con: docker compose --profile real logs' -ForegroundColor Yellow
        exit 1
    }

    # ---------------------------------------------------- 4. base que se esta sirviendo
    Write-Step 'Comprobando que base esta sirviendo el backend'
    $info = Invoke-RestMethod -Uri "$BackendUrl/database-info" -TimeoutSec 5

    Write-Host ''
    Write-Host "    modo      : $($info.mode)"
    Write-Host "    base      : $($info.database) ($($info.backend))"
    Write-Host "    registros : $($info.records_total) (reales $($info.records_real), demo $($info.records_demo))"
    Write-Host "    lotes     : $($info.import_batches)"

    if (-not $info.consistent) {
        Write-Host ''
        Write-Host 'AVISO: el backend arranca en modo REAL pero no encuentra registros reales.' -ForegroundColor Red
        Write-Host 'Ejecute este script con -Ingest para cargar los maestros.' -ForegroundColor Red
        exit 1
    }

    Write-Host ''
    Write-Host 'Farmalidacion en modo REAL:' -ForegroundColor Green
    Write-Host "    Aplicacion  : $FrontendUrl"
    Write-Host "    API         : $BackendUrl/docs"
    Write-Host "    Diagnostico : $BackendUrl/database-info"
    Write-Host ''
    Write-Host 'Para detenerlo: docker compose --profile real down'
}
finally {
    Pop-Location
}
