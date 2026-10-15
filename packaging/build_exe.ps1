$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$python = Join-Path $project '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Environnement .venv absent.' }
$version = (& $python -c "import sys,tomllib,pathlib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))['project']['version'])" (Join-Path $project 'pyproject.toml') | Select-Object -Last 1).Trim()
if ($version -notmatch '^(\d+)\.(\d+)\.(\d+)$') { throw "Version projet invalide: $version" }
$releaseSeries = "$($Matches[1]).$($Matches[2])"
$release = Join-Path $project "release-v$releaseSeries"
$work = Join-Path $project 'build-final'
# PyInstaller inspecte les dépendances du bridge natif. PothosSDR installe
# parfois une seconde sdrplay_api.dll incompatible ; elle ne doit jamais être
# choisie pendant l'analyse ni embarquée dans le portable.
$sdrplayApiDir = 'C:\Program Files\SDRplay\API\x64'
$cleanPath = (($env:PATH -split ';') | Where-Object { $_ -and $_ -notmatch 'PothosSDR' }) -join ';'
$env:PATH = "$sdrplayApiDir;$cleanPath"
& $python -c 'import PyInstaller; assert PyInstaller.__version__ == ''6.22.3'''
if ($LASTEXITCODE -ne 0) { throw 'Installer packaging/requirements-build.txt dans .venv.' }
& (Join-Path $project 'native\build_native.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Compilation native impossible.' }
New-Item -ItemType Directory -Force $release | Out-Null
New-Item -ItemType Directory -Force $work | Out-Null
$atomic = Join-Path $project 'native\build\ring_atomic-x64\Release\sdr_ring_atomic.dll'
$sdrplay = Join-Path $project 'native\build\sdrplay_bridge\Release\sdrplay_bridge.dll'
$schemas = Join-Path $project 'schemas'
$soapyCompat = Join-Path $project 'soapy_sdr_ctypes_compat\SoapySDR.py'
$common = @('--noconfirm','--clean','--paths',(Join-Path $project 'src'),'--add-binary',"$atomic;native",'--add-data',"$schemas;schemas",'--add-data',"$soapyCompat;soapy_compat")
& $python -m PyInstaller @common --windowed --name SDR_Bridge --distpath $release --workpath (Join-Path $work 'server') --specpath $work --add-binary "$sdrplay;native" --collect-all pyqtgraph (Join-Path $project 'launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'Build SDR_Bridge impossible.' }
# Ne jamais embarquer une copie tierce de l'API SDRplay : elle peut être
# incompatible avec le service/driver installé et provoquer une violation d'accès.
$bundledApi = Join-Path $release 'SDR_Bridge\_internal\sdrplay_api.dll'
if (Test-Path -LiteralPath $bundledApi) { Remove-Item -LiteralPath $bundledApi -Force }
$installedApi = 'C:\Program Files\SDRplay\API\x64\sdrplay_api.dll'
if (Test-Path -LiteralPath $installedApi) {
    Copy-Item -LiteralPath $installedApi -Destination $bundledApi -Force
} else {
    throw 'API SDRplay officielle absente : paquet natif non produit.'
}
& $python -m PyInstaller @common --console --name SDR_Bridge_Client --distpath $release --workpath (Join-Path $work 'client') --specpath $work (Join-Path $project 'client_launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'Build client local impossible.' }
& $python -m PyInstaller @common --console --name SDR_Bridge_Native_Client --distpath $release --workpath (Join-Path $work 'native-client') --specpath $work (Join-Path $project 'native_client_launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'Build client natif impossible.' }
$connectors = Join-Path $release 'Connectors'
$releaseFull = [System.IO.Path]::GetFullPath($release).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
$connectorsFull = [System.IO.Path]::GetFullPath($connectors)
if (-not $connectorsFull.StartsWith($releaseFull + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Dossier de connecteurs hors du répertoire de livraison: $connectorsFull"
}
if (Test-Path -LiteralPath $connectorsFull) { Remove-Item -LiteralPath $connectorsFull -Recurse -Force }
$hdsdrConnector = Join-Path $connectors 'HDSDR'
$sdrppConnector = Join-Path $connectors 'SDR++'
New-Item -ItemType Directory -Force (Join-Path $connectors 'ANTRACK') | Out-Null
New-Item -ItemType Directory -Force (Join-Path $hdsdrConnector 'bin'),(Join-Path $hdsdrConnector 'scripts') | Out-Null
New-Item -ItemType Directory -Force (Join-Path $sdrppConnector 'bin'),(Join-Path $sdrppConnector 'scripts') | Out-Null
Copy-Item -LiteralPath (Join-Path $project 'native\build\extio_bridge\Release\ExtIO_SDR_Bridge.dll') -Destination (Join-Path $hdsdrConnector 'bin') -Force
Copy-Item -LiteralPath (Join-Path $project 'native\extio_bridge\scripts\install.ps1') -Destination (Join-Path $hdsdrConnector 'scripts') -Force
Copy-Item -LiteralPath (Join-Path $project 'native\extio_bridge\scripts\uninstall.ps1') -Destination (Join-Path $hdsdrConnector 'scripts') -Force
Copy-Item -LiteralPath (Join-Path $project 'native\extio_bridge\README.md') -Destination $hdsdrConnector -Force
Copy-Item -LiteralPath (Join-Path $project 'clients\sdrpp_sdbu_source\bin\sdbu_source.dll') -Destination (Join-Path $sdrppConnector 'bin') -Force
Copy-Item -LiteralPath (Join-Path $project 'clients\sdrpp_sdbu_source\scripts\install.ps1') -Destination (Join-Path $sdrppConnector 'scripts') -Force
Copy-Item -LiteralPath (Join-Path $project 'clients\sdrpp_sdbu_source\scripts\uninstall.ps1') -Destination (Join-Path $sdrppConnector 'scripts') -Force
Copy-Item -LiteralPath (Join-Path $project 'clients\sdrpp_sdbu_source\README.md') -Destination $sdrppConnector -Force
Copy-Item -LiteralPath (Join-Path $project 'clients\antrack\SoapySDR.py') -Destination (Join-Path $connectors 'ANTRACK') -Force
Copy-Item -LiteralPath (Join-Path $project 'clients\antrack\sitecustomize.py') -Destination (Join-Path $connectors 'ANTRACK') -Force
Copy-Item -LiteralPath (Join-Path $project 'clients\antrack\install_antrack_bridge.ps1') -Destination (Join-Path $connectors 'ANTRACK') -Force
Copy-Item -LiteralPath (Join-Path $project 'docs\CLIENT_SETUP.md') -Destination $release -Force
Copy-Item -LiteralPath (Join-Path $project 'config.soapy-sdrpp.json') -Destination $release -Force
Copy-Item -LiteralPath (Join-Path $project 'config.native-sdrpp.json') -Destination $release -Force
Copy-Item -LiteralPath (Join-Path $project 'start-sdrbridge.ps1') -Destination $release -Force
$exe = Join-Path $release 'SDR_Bridge\SDR_Bridge.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw 'Executable principal absent.' }
$isccCandidates = @('C:\Program Files (x86)\Inno Setup 6\ISCC.exe','C:\Program Files\Inno Setup 6\ISCC.exe',(Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'))
$iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc "/DMyAppVersion=$version" "/DReleaseDir=..\release-v$releaseSeries" (Join-Path $project 'packaging\SDR_Bridge.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Build setup impossible.' }
} else {
    Write-Warning 'Inno Setup absent : paquet portable produit, sans setup.exe.'
}
Write-Host "Paquet portable : $release"
