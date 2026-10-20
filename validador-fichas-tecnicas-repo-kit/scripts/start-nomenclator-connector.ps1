param(
    [Parameter(Mandatory = $true)]
    [string]$FarmalidacionUrl
)

$ErrorActionPreference = 'Stop'
$origin = ([Uri]$FarmalidacionUrl).GetLeftPart([UriPartial]::Authority)
$install = Join-Path $env:LOCALAPPDATA 'Farmalidacion\NomenclatorConnector'
$venv = Join-Path $install 'venv'
$python = Join-Path $venv 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw 'Instale Python 3.11 o posterior para iniciar el conector.'
    }
    New-Item -ItemType Directory -Path $install -Force | Out-Null
    py -3 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Instale Python 3.11 o posterior.' }
    & $python -m pip install 'mssql-python>=1.7,<2'
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar el controlador SQL Server.' }
}

& $python (Join-Path $PSScriptRoot 'nomenclator_local_connector.py') --origin $origin
