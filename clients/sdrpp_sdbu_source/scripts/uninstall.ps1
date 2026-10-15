[CmdletBinding()]
param(
    [string]$SdrppRoot = 'E:\Radio\sdrpp_windows_x64_1.3.0\sdrpp_windows_x64'
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath($SdrppRoot)
$manifestPath = Join-Path $root 'sdbu_source.install.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Manifeste introuvable: $manifestPath" }

$active = Get-CimInstance Win32_Process -Filter "Name='sdrpp.exe'" |
    Where-Object { $_.ExecutablePath -and [System.IO.Path]::GetFullPath($_.ExecutablePath).StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) }
if ($active) { throw 'Fermez cette installation SDR++ avant le retour arrière.' }

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$dllPath = [string]$manifest.dll
$configBackup = [string]$manifest.config_backup
$previousDll = [string]$manifest.previous_dll_backup
if (-not (Test-Path -LiteralPath $configBackup)) { throw "Sauvegarde de configuration introuvable: $configBackup" }

if (Test-Path -LiteralPath $dllPath) {
    Remove-Item -LiteralPath $dllPath
}
if ($previousDll -and (Test-Path -LiteralPath $previousDll)) {
    Move-Item -LiteralPath $previousDll -Destination $dllPath
}
Copy-Item -LiteralPath $configBackup -Destination (Join-Path $root 'config.json') -Force
Remove-Item -LiteralPath $manifestPath
Write-Host 'Retour arrière SDRbridge SDBU v2 terminé.'

