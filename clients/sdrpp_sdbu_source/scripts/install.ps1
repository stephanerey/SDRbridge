[CmdletBinding()]
param(
    [string]$SdrppRoot = 'E:\Radio\sdrpp_windows_x64_1.3.0\sdrpp_windows_x64',
    [string]$DllPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'bin\sdbu_source.dll')
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath($SdrppRoot)
$dll = [System.IO.Path]::GetFullPath($DllPath)
$modules = Join-Path $root 'modules'
$configPath = Join-Path $root 'config.json'
$destination = Join-Path $modules 'sdbu_source.dll'
$manifestPath = Join-Path $root 'sdbu_source.install.json'

if (-not (Test-Path -LiteralPath (Join-Path $root 'sdrpp.exe'))) { throw "sdrpp.exe introuvable dans $root" }
if (-not (Test-Path -LiteralPath (Join-Path $root 'sdrpp_core.dll'))) { throw "sdrpp_core.dll introuvable dans $root" }
if (-not (Test-Path -LiteralPath $dll)) { throw "DLL à installer introuvable: $dll" }
if (-not (Test-Path -LiteralPath $modules -PathType Container)) { throw "Dossier modules introuvable: $modules" }
if (-not (Test-Path -LiteralPath $configPath)) { throw "Configuration SDR++ introuvable: $configPath" }

$active = Get-CimInstance Win32_Process -Filter "Name='sdrpp.exe'" |
    Where-Object { $_.ExecutablePath -and [System.IO.Path]::GetFullPath($_.ExecutablePath).StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) }
if ($active) {
    throw "SDR++ 1.3.0 est actif depuis ce dossier; fermez-le avant installation. PID: $($active.ProcessId -join ', ')"
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$configBackup = $null
$dllBackup = $null
if (Test-Path -LiteralPath $manifestPath) {
    $existingManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $configBackup = [string]$existingManifest.config_backup
    $dllBackup = [string]$existingManifest.previous_dll_backup
    if (-not $configBackup -or -not (Test-Path -LiteralPath $configBackup)) {
        throw 'Le manifeste existant ne référence plus une sauvegarde de configuration valide.'
    }
}
else {
    $configBackup = "$configPath.sdbu-backup-$stamp"
    Copy-Item -LiteralPath $configPath -Destination $configBackup
    if (Test-Path -LiteralPath $destination) {
        $dllBackup = "$destination.sdbu-backup-$stamp"
        Copy-Item -LiteralPath $destination -Destination $dllBackup
    }
}

Copy-Item -LiteralPath $dll -Destination $destination -Force

$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json -AsHashtable
if (-not $config.ContainsKey('moduleInstances')) {
    $config['moduleInstances'] = [ordered]@{}
}
$config['moduleInstances']['SDRbridge SDBU v2'] = [ordered]@{
    enabled = $true
    module = 'sdbu_source'
}
$json = $config | ConvertTo-Json -Depth 100
[System.IO.File]::WriteAllText($configPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

$manifest = [ordered]@{
    installed_at = (Get-Date).ToString('o')
    sdrpp_root = $root
    dll = $destination
    dll_sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
    previous_dll_backup = $dllBackup
    config_backup = $configBackup
}
[System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 10) + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

Write-Host "Installé: $destination"
Write-Host "Instance ajoutée: SDRbridge SDBU v2"
Write-Host "Sauvegarde de configuration: $configBackup"
Write-Host "Manifeste de retour arrière: $manifestPath"
