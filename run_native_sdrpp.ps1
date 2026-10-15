$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $project 'release-v0.4\SDR_Bridge\SDR_Bridge.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "Paquet absent : $exe" }
& $exe --config (Join-Path $project 'config.native-sdrpp.json')
