param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')][string]$Instance = 'default',
    [ValidateRange(0,18000)][int]$PortOffset = 0,
    [string]$DeviceId = '',
    [string]$Config = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = @(
    (Join-Path $root 'SDR_Bridge\SDR_Bridge.exe'),
    (Join-Path $root 'release-v0.4\SDR_Bridge\SDR_Bridge.exe')
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Config) { $Config = Join-Path $root 'config.soapy-sdrpp.json' }
if (-not $exe) { throw "Executable SDRbridge introuvable depuis: $root" }
if (-not (Test-Path -LiteralPath $Config)) { throw "Configuration introuvable: $Config" }
$arguments = @('--config', ('"' + $Config + '"'), '--instance', $Instance, '--port-offset', [string]$PortOffset)
if ($DeviceId) { $arguments += @('--device-id', $DeviceId) }
Start-Process -FilePath $exe -ArgumentList $arguments
Write-Host "SDRbridge instance '$Instance' démarrée (offset de ports $PortOffset)."
