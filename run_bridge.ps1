param(
    [ValidateSet('simulated','soapy','native','replay','file')][string]$Source = 'simulated',
    [switch]$Headless,
    [string]$Config = '',
    [string]$Udp = '',
    [string]$IqFile = '',
    [long]$IqCenterFrequency = 0,
    [switch]$IqLoop,
    [int]$UdpRate = 0,
    [int]$UdpDatagramBytes = 0,
    [int]$UdpQueueBlocks = 0
)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { $runtime = 'python' }
$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
$arguments = @('-m','sdr_bridge','--source',$Source)
if ($Config) { $arguments += @('--config',$Config) }
if ($Headless) { $arguments += '--headless' }
if ($Udp) { $arguments += @('--udp',$Udp) }
if ($IqFile) { $arguments += @('--iq-file',$IqFile) }
if ($IqCenterFrequency -gt 0) { $arguments += @('--iq-center-frequency',$IqCenterFrequency) }
if ($IqLoop) { $arguments += '--iq-loop' }
if ($UdpRate -gt 0) { $arguments += @('--udp-rate',$UdpRate) }
if ($UdpDatagramBytes -gt 0) { $arguments += @('--udp-datagram-bytes',$UdpDatagramBytes) }
if ($UdpQueueBlocks -gt 0) { $arguments += @('--udp-queue-blocks',$UdpQueueBlocks) }
& $runtime @arguments
