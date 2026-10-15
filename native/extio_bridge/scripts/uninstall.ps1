[CmdletBinding()]
param(
    [string]$HdsdrRoot = 'C:\Program Files (x86)\HDSDR'
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath($HdsdrRoot)
$manifestPath = Join-Path $root 'ExtIO_SDR_Bridge.install.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Manifeste introuvable: $manifestPath" }

$active = Get-CimInstance Win32_Process -Filter "Name='HDSDR.exe'" |
    Where-Object { $_.ExecutablePath -and [System.IO.Path]::GetFullPath($_.ExecutablePath).StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) }
if ($active) { throw 'Fermez HDSDR avant le retour arrière.' }

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$dllPath = [string]$manifest.dll
$backup = [string]$manifest.previous_dll_backup

if (Test-Path -LiteralPath $dllPath) { Remove-Item -LiteralPath $dllPath }
if ($backup) {
    if (-not (Test-Path -LiteralPath $backup)) { throw "Sauvegarde précédente introuvable: $backup" }
    Move-Item -LiteralPath $backup -Destination $dllPath
}
Remove-Item -LiteralPath $manifestPath
Write-Host 'Retour arrière ExtIO_SDR_Bridge terminé.'
