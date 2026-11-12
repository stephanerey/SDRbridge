$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$python = Join-Path $project '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Environnement .venv absent.' }
$version = (& $python -c "import sys,tomllib,pathlib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))['project']['version'])" (Join-Path $project 'pyproject.toml') | Select-Object -Last 1).Trim()
if ($version -notmatch '^(\d+)\.(\d+)\.(\d+)(?:\.dev\d+)?$') { throw "Version projet invalide: $version" }
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
& (Join-Path $project 'packaging\build_soapy_runtime.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Compilation du runtime Soapy privé impossible.' }
New-Item -ItemType Directory -Force $release | Out-Null
New-Item -ItemType Directory -Force $work | Out-Null
$atomic = Join-Path $project 'native\build\ring_atomic-x64\Release\sdr_ring_atomic.dll'
$sdrplay = Join-Path $project 'native\build\sdrplay_bridge\Release\sdrplay_bridge.dll'
$schemas = Join-Path $project 'schemas'
$soapyCompat = Join-Path $project 'soapy_sdr_ctypes_compat\SoapySDR.py'
$helpFr = Join-Path $project 'docs\HELP_FR.md'
$helpEn = Join-Path $project 'docs\HELP_EN.md'
$hardwareFr = Join-Path $project 'docs\HARDWARE_COMPATIBILITY_FR.md'
$hardwareEn = Join-Path $project 'docs\HARDWARE_COMPATIBILITY.md'
$validationFr = Join-Path $project 'docs\verification\GENERIC_SOAPY_VALIDATION_FR.md'
$validationEn = Join-Path $project 'docs\verification\GENERIC_SOAPY_VALIDATION.md'
$license = Join-Path $project 'LICENSE'
$notices = Join-Path $project 'THIRD_PARTY_NOTICES.md'
$appIcon = Join-Path $project 'assets\branding\sdrbridge.ico'
$soapyRuntime = Join-Path $project 'build-final\dependencies\soapy-runtime'
$soapyDll = Join-Path $soapyRuntime 'bin\SoapySDR.dll'
$soapyModuleDir = Get-ChildItem -LiteralPath (Join-Path $soapyRuntime 'lib\SoapySDR') -Directory -Filter 'modules*' -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
if (-not $soapyModuleDir) { throw 'Répertoire de modules Soapy privé absent.' }
$soapyModuleDirName = $soapyModuleDir.Name
$soapyModules = @(Get-ChildItem -LiteralPath $soapyModuleDir -File -Filter '*.dll' -ErrorAction SilentlyContinue)
if (-not (Test-Path -LiteralPath $soapyDll) -or -not ($soapyModules.Name -contains 'sdrPlaySupport.dll')) { throw 'Runtime Soapy privé incomplet.' }
if (-not (Test-Path -LiteralPath $appIcon)) { throw 'Icône SDRbridge absente.' }
$common = @(
    '--noconfirm','--clean','--paths',(Join-Path $project 'src'),
    '--add-binary',"$atomic;native",
    '--add-data',"$schemas;schemas"
)
$serverResources = @(
    '--add-binary',"$soapyDll;soapy_runtime\bin",
    '--add-data',"$soapyCompat;soapy_compat",
    '--add-data',"$helpFr;docs",
    '--add-data',"$helpEn;docs",
    '--add-data',"$license;legal",
    '--add-data',"$notices;legal",
    '--add-data',"$appIcon;assets\branding"
)
foreach ($soapyModule in $soapyModules) {
    # Package every ABI-compatible module produced by the private runtime
    # build. Driver additions no longer require another hard-coded PyInstaller
    # entry, while the separate modules0.8 installed by Pothos remain isolated.
    $serverResources += @('--add-binary',"$($soapyModule.FullName);soapy_runtime\lib\SoapySDR\$soapyModuleDirName")
}
& $python -m PyInstaller @common @serverResources --windowed --icon $appIcon --name SDR_Bridge --distpath $release --workpath (Join-Path $work 'server') --specpath $work --add-binary "$sdrplay;native" (Join-Path $project 'launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'Build SDR_Bridge impossible.' }
# PyQt 5.15.2 fournit un runtime MSVC 14.26 dans son sous-dossier Qt. Le
# runtime Soapy est compilé avec le toolset courant (14.51) et peut crasher si
# le hook PyInstaller lui impose ces anciennes DLL avant son chargement.
# Déploiement app-local du runtime VC courant, rétrocompatible avec Qt.
$qtRuntimeDir = Join-Path $release 'SDR_Bridge\_internal\PyQt5\Qt5\bin'
foreach ($runtimeName in @('MSVCP140.dll','MSVCP140_1.dll','VCRUNTIME140.dll','VCRUNTIME140_1.dll')) {
    $runtimeSource = Join-Path $env:WINDIR "System32\$runtimeName"
    if (-not (Test-Path -LiteralPath $runtimeSource)) { throw "Runtime Visual C++ absent : $runtimeSource" }
    Copy-Item -LiteralPath $runtimeSource -Destination (Join-Path $qtRuntimeDir $runtimeName) -Force
}
# Ne jamais embarquer une copie de l'API SDRplay : elle peut être incompatible
# avec le service/driver installé. Le runtime privé charge l'API officielle du
# système et l'installeur explique ce prérequis aux utilisateurs d'un RSP.
$bundledApi = Join-Path $release 'SDR_Bridge\_internal\sdrplay_api.dll'
if (Test-Path -LiteralPath $bundledApi) { Remove-Item -LiteralPath $bundledApi -Force }
# PyInstaller suit la dépendance du module SDRplay et recopie aussi SoapySDR.dll
# à la racine de _internal. Deux instances du même cœur Soapy créent deux
# registres de modules distincts et peuvent provoquer une violation d'accès à
# l'énumération. La seule copie autorisée reste celle du runtime privé.
$duplicateSoapy = Join-Path $release 'SDR_Bridge\_internal\SoapySDR.dll'
if (Test-Path -LiteralPath $duplicateSoapy) { Remove-Item -LiteralPath $duplicateSoapy -Force }
$installedApi = 'C:\Program Files\SDRplay\API\x64\sdrplay_api.dll'
if (-not (Test-Path -LiteralPath $installedApi)) {
    throw 'API SDRplay officielle absente : paquet natif non produit.'
}
& $python -m PyInstaller @common --console --name SDR_Bridge_Client --distpath $release --workpath (Join-Path $work 'client') --specpath $work (Join-Path $project 'client_launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'Build client local impossible.' }
& $python -m PyInstaller @common --console --name SDR_Bridge_Native_Client --distpath $release --workpath (Join-Path $work 'native-client') --specpath $work (Join-Path $project 'native_client_launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'Build client natif impossible.' }
# Défense en profondeur : aucune copie de l'API propriétaire SDRplay ne doit
# se trouver dans les trois paquets, même si l'analyse de dépendances de
# PyInstaller évolue. SDRbridge utilise toujours l'installation officielle.
Get-ChildItem -LiteralPath $release -Recurse -File -Filter 'sdrplay_api.dll' | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Force
}
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
Copy-Item -LiteralPath $helpFr,$helpEn,$hardwareFr,$hardwareEn,$license,$notices,(Join-Path $project 'AUTHORS.md'),(Join-Path $project 'COPYRIGHT') -Destination $release -Force
New-Item -ItemType Directory -Force (Join-Path $release 'verification') | Out-Null
Copy-Item -LiteralPath $validationFr,$validationEn -Destination (Join-Path $release 'verification') -Force
New-Item -ItemType Directory -Force (Join-Path $release 'licenses') | Out-Null
Copy-Item -LiteralPath (Join-Path $project 'build-final\dependencies\src\SoapySDR\LICENSE_1_0.txt') -Destination (Join-Path $release 'licenses\SoapySDR-BSL-1.0.txt') -Force
Copy-Item -LiteralPath (Join-Path $project 'build-final\dependencies\src\SoapySDRPlay3\LICENSE.txt') -Destination (Join-Path $release 'licenses\SoapySDRPlay3-MIT.txt') -Force
Copy-Item -LiteralPath (Join-Path $project 'build-final\dependencies\src\SoapyRTLSDR\LICENSE.txt') -Destination (Join-Path $release 'licenses\SoapyRTLSDR-MIT.txt') -Force
Copy-Item -LiteralPath (Join-Path $project 'build-final\dependencies\src\SoapyAirspy\LICENSE.txt') -Destination (Join-Path $release 'licenses\SoapyAirspy-MIT.txt') -Force
Copy-Item -LiteralPath (Join-Path $project 'build-final\dependencies\src\SoapyAirspyHF\LICENSE.txt') -Destination (Join-Path $release 'licenses\SoapyAirspyHF-MIT.txt') -Force
Copy-Item -LiteralPath (Join-Path $project 'build-final\dependencies\src\LimeSuite\COPYING') -Destination (Join-Path $release 'licenses\LimeSuite-Apache-2.0.txt') -Force
Copy-Item -LiteralPath (Join-Path $project 'build-final\dependencies\src\SoapyPlutoSDR\LICENSE') -Destination (Join-Path $release 'licenses\SoapyPlutoSDR-LGPL-2.1.txt') -Force
Copy-Item -LiteralPath (Join-Path $project 'build-final\dependencies\src\SoapyUHD\COPYING') -Destination (Join-Path $release 'licenses\SoapyUHD-GPL-3.0.txt') -Force
Copy-Item -LiteralPath (Join-Path $project 'build-final\dependencies\boost_1_75_0\LICENSE_1_0.txt') -Destination (Join-Path $release 'licenses\Boost-BSL-1.0.txt') -Force
Copy-Item -LiteralPath (Join-Path $project 'packaging\licenses\Airspy-BSD-3-Clause.txt') -Destination (Join-Path $release 'licenses\Airspy-BSD-3-Clause.txt') -Force
Copy-Item -LiteralPath 'C:\Program Files\PothosSDR\licenses\airspyhf\LICENSE' -Destination (Join-Path $release 'licenses\AirspyHF-BSD-3-Clause.txt') -Force
Copy-Item -LiteralPath 'C:\Program Files\PothosSDR\licenses\rtl-sdr\COPYING' -Destination (Join-Path $release 'licenses\RTL-SDR-GPL-2.0.txt') -Force
Copy-Item -LiteralPath 'C:\Program Files\PothosSDR\licenses\libusb\COPYING' -Destination (Join-Path $release 'licenses\libusb-LGPL-2.1.txt') -Force
Copy-Item -LiteralPath 'C:\Program Files\PothosSDR\licenses\libiio\COPYING.txt' -Destination (Join-Path $release 'licenses\libiio-LGPL-2.1.txt') -Force
Copy-Item -LiteralPath 'C:\Program Files\PothosSDR\licenses\libad9361\LICENSE' -Destination (Join-Path $release 'licenses\libad9361-LGPL-2.1.txt') -Force
Copy-Item -LiteralPath 'C:\Program Files\PothosSDR\licenses\LimeSuite\COPYING' -Destination (Join-Path $release 'licenses\LimeSuite-Apache-2.0-runtime.txt') -Force
Copy-Item -LiteralPath 'C:\Program Files\PothosSDR\licenses\uhd\LICENSE' -Destination (Join-Path $release 'licenses\UHD-GPL-3.0-or-later.txt') -Force
Copy-Item -LiteralPath 'C:\Program Files\PothosSDR\licenses\Pthreads\COPYING.LIB' -Destination (Join-Path $release 'licenses\pthreads-win32-LGPL-2.1.txt') -Force
Copy-Item -LiteralPath (Join-Path $project '.venv\Lib\site-packages\PyQt5_Qt5-5.15.2.dist-info\LICENSE') -Destination (Join-Path $release 'licenses\Qt-5.15.2.txt') -Force
$redistNotice = Get-ChildItem 'C:\Program Files (x86)\Microsoft Visual Studio\*\BuildTools\Licenses\*\Redist.txt' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($redistNotice) { Copy-Item -LiteralPath $redistNotice.FullName -Destination (Join-Path $release 'licenses\Microsoft-Visual-Cpp-Runtime.txt') -Force }
$defaultSoapyConfig = Join-Path $project 'packaging\defaults\config.soapy-sdrpp.json'
if (-not (Test-Path -LiteralPath $defaultSoapyConfig)) { throw 'Configuration Soapy par défaut absente.' }
Copy-Item -LiteralPath $defaultSoapyConfig -Destination (Join-Path $release 'config.soapy-sdrpp.json') -Force
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
