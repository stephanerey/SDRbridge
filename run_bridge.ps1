param(
    [ValidateSet('simulated','soapy','native','replay')][string]$Source = 'simulated',
    [switch]$Headless,
    [string]$Udp = ''
)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { $runtime = 'python' }
$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
$arguments = @('-m','sdr_bridge','--source',$Source)
if ($Headless) { $arguments += '--headless' }
if ($Udp) { $arguments += @('--udp',$Udp) }
& $runtime @arguments
