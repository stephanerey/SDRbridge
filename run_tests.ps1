$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { $runtime = 'python' }
$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
& $runtime -m unittest discover -s (Join-Path $PSScriptRoot 'tests') -v

