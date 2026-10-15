[CmdletBinding()]
param(
    [string]$HdsdrRoot = 'C:\Program Files (x86)\HDSDR',
    [string]$DllPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'bin\ExtIO_SDR_Bridge.dll')
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath($HdsdrRoot)
$dll = [System.IO.Path]::GetFullPath($DllPath)
$hdsdr = Join-Path $root 'HDSDR.exe'
$destination = Join-Path $root 'ExtIO_SDR_Bridge.dll'
$manifestPath = Join-Path $root 'ExtIO_SDR_Bridge.install.json'

if (-not (Test-Path -LiteralPath $hdsdr)) { throw "HDSDR.exe introuvable dans $root" }
if (-not (Test-Path -LiteralPath $dll)) { throw "DLL ExtIO introuvable: $dll" }

$active = Get-CimInstance Win32_Process -Filter "Name='HDSDR.exe'" |
    Where-Object { $_.ExecutablePath -and [System.IO.Path]::GetFullPath($_.ExecutablePath).StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) }
if ($active) {
    throw "HDSDR est actif depuis ce dossier; fermez-le avant installation. PID: $($active.ProcessId -join ', ')"
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = $null
if (Test-Path -LiteralPath $manifestPath) {
    $existingManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $backup = [string]$existingManifest.previous_dll_backup
    if ($backup -and -not (Test-Path -LiteralPath $backup)) {
        throw 'Le manifeste existant ne référence plus une sauvegarde valide.'
    }
}
elseif (Test-Path -LiteralPath $destination) {
    $backup = "$destination.sdrbridge-backup-$stamp"
    Copy-Item -LiteralPath $destination -Destination $backup
}

try {
    Copy-Item -LiteralPath $dll -Destination $destination -Force
}
catch [System.UnauthorizedAccessException] {
    throw "Accès refusé. Fermez HDSDR puis relancez PowerShell en tant qu’administrateur."
}

$manifest = [ordered]@{
    installed_at = (Get-Date).ToString('o')
    hdsdr_root = $root
    dll = $destination
    dll_sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
    previous_dll_backup = $backup
}
[System.IO.File]::WriteAllText(
    $manifestPath,
    ($manifest | ConvertTo-Json -Depth 10) + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Installé: $destination"
Write-Host "SHA-256: $($manifest.dll_sha256)"
if ($backup) { Write-Host "Sauvegarde précédente: $backup" }
Write-Host "Manifeste de retour arrière: $manifestPath"
