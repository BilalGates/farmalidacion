<#
.SYNOPSIS
    Abre Fuentes con una copia aislada de la base REAL de vista previa.

.DESCRIPTION
    Copia real-preview.db una sola vez a sources-preview.db; nunca sobrescribe
    ninguna de las dos. Levanta el perfil Compose preview en 5174/8001.
#>
[CmdletBinding()]
param([switch] $SkipBuild)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$DataDirectory = Join-Path $RepositoryRoot 'data/local'
$SourceDatabase = Join-Path $DataDirectory 'real-preview.db'
$PreviewDatabase = Join-Path $DataDirectory 'sources-preview.db'

if (-not (Test-Path -LiteralPath $PreviewDatabase)) {
    if (-not (Test-Path -LiteralPath $SourceDatabase)) {
        throw 'No se encontró data/local/real-preview.db para crear la vista previa.'
    }
    Copy-Item -LiteralPath $SourceDatabase -Destination $PreviewDatabase
    if ((Get-Item -LiteralPath $PreviewDatabase).Length -ne (Get-Item -LiteralPath $SourceDatabase).Length) {
        throw 'La copia de la base no tiene el tamaño esperado; revise el disco antes de arrancar.'
    }
    Write-Host 'Copia aislada creada: data/local/sources-preview.db'
}

Push-Location $RepositoryRoot
try {
    $arguments = @('compose', '-p', 'pharma-validator-sources', '--profile', 'preview', 'up', '-d')
    if (-not $SkipBuild) { $arguments += '--build' }
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose no pudo arrancar la vista previa.' }

    $ready = $false
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        try {
            $info = Invoke-RestMethod 'http://127.0.0.1:8001/database-info' -TimeoutSec 3
            $front = Invoke-WebRequest 'http://127.0.0.1:5174' -UseBasicParsing -TimeoutSec 3
            if ($info.consistent -and $info.mode -eq 'real' -and $info.records_real -gt 0 -and $front.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw 'La vista previa no confirmó datos REAL y frontend disponibles.' }

    Write-Host "Vista previa preparada: $($info.records_real) registros reales."
    Write-Host 'Fuentes: http://127.0.0.1:5174/#/datos/fuentes'
    Write-Host 'API: http://127.0.0.1:8001/docs'
}
finally {
    Pop-Location
}
