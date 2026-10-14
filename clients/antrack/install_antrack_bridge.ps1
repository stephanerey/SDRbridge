param(
    [string]$AntrackRoot = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Python\Antrack')
)
$ErrorActionPreference = 'Stop'
$site = Join-Path $AntrackRoot '.venv\Lib\site-packages'
$target = Join-Path $site 'SoapySDR.py'
if (-not (Test-Path -LiteralPath $site)) { throw "ANTRACK virtual environment not found: $site" }
if (Test-Path -LiteralPath $target) {
    $backup = Join-Path $site 'SoapySDR.direct_sdrplay.backup.py'
    $isBridge = Select-String -LiteralPath $target -SimpleMatch 'Drop-in SoapySDR subset that reads SDR_Bridge' -Quiet
    if (-not $isBridge -and -not (Test-Path -LiteralPath $backup)) {
        Copy-Item -LiteralPath $target -Destination $backup
    }
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'SoapySDR.py') -Destination $target -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'sitecustomize.py') -Destination (Join-Path $site 'sitecustomize.py') -Force
Write-Host "ANTRACK bridge installed: $target"
