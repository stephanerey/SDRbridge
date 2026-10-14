$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $root 'release-v0.3\SDR_Bridge\SDR_Bridge.exe'
$config = Join-Path $root 'config.native-sdrpp.json'
if (-not (Test-Path -LiteralPath $exe)) { throw "Executable introuvable: $exe" }
if (-not (Test-Path -LiteralPath $config)) { throw "Configuration introuvable: $config" }
if (Get-Process -Name SDR_Bridge -ErrorAction SilentlyContinue) {
    Write-Host 'SDRbridge est déjà lancé. Utilise Alt-Tab pour afficher sa fenêtre.'
    exit 0
}
Start-Process -FilePath $exe -ArgumentList @('--config', $config)
Write-Host 'SDRbridge démarré. Fenêtre graphique en cours d ouverture.'
