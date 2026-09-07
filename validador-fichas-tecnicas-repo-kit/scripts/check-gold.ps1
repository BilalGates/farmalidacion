<# Ejecuta el checker GOLD sobre la selección materializada. #>
[CmdletBinding()]
param(
    [int] $ExpectedUnitsPerDocument = 0,
    [string[]] $Reviewers = @()
)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$GoldDirectory = Join-Path $RepositoryRoot 'data/local/gold-set-407'
$Selection = Join-Path $GoldDirectory 'gold-selection.json'
$Sections = Join-Path $GoldDirectory 'gold-sections.json'
$Annotations = @(Get-ChildItem $GoldDirectory -Filter 'annotations-*.jsonl' -ErrorAction SilentlyContinue)

$arguments = @(
    (Join-Path $PSScriptRoot 'check_gold.py'),
    '--selection', $Selection,
    '--sections', $Sections
)
if ($Annotations.Count -gt 0) {
    $arguments += '--annotations'
    $arguments += $Annotations.FullName
}
if ($ExpectedUnitsPerDocument -gt 0) {
    $arguments += '--expected-units-per-document'
    $arguments += [string] $ExpectedUnitsPerDocument
}
if ($Reviewers.Count -gt 0) {
    $arguments += '--reviewers'
    $arguments += $Reviewers
}

$env:PYTHONPATH = Join-Path $RepositoryRoot 'backend/src'
& python @arguments
exit $LASTEXITCODE
