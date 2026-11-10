$ErrorActionPreference = 'Stop'

$project = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $project 'build-final\dependencies'
$sourceRoot = Join-Path $buildRoot 'src'
$runtimeRoot = Join-Path $buildRoot 'soapy-runtime'
$soapySource = Join-Path $sourceRoot 'SoapySDR'
$sdrplaySource = Join-Path $sourceRoot 'SoapySDRPlay3'
$rtlsdrSource = Join-Path $sourceRoot 'SoapyRTLSDR'
$airspySource = Join-Path $sourceRoot 'SoapyAirspy'
$airspyHfSource = Join-Path $sourceRoot 'SoapyAirspyHF'
$limeSuiteSource = Join-Path $sourceRoot 'LimeSuite'
$plutoSource = Join-Path $sourceRoot 'SoapyPlutoSDR'
$uhdSource = Join-Path $sourceRoot 'SoapyUHD'
$soapyBuild = Join-Path $buildRoot 'SoapySDR-build'
$sdrplayBuild = Join-Path $buildRoot 'SoapySDRPlay3-build'
$rtlsdrBuild = Join-Path $buildRoot 'SoapyRTLSDR-build'
$airspyBuild = Join-Path $buildRoot 'SoapyAirspy-build'
$airspyHfBuild = Join-Path $buildRoot 'SoapyAirspyHF-build'
$limeBuild = Join-Path $buildRoot 'SoapyLMS7-build'
$plutoBuild = Join-Path $buildRoot 'SoapyPlutoSDR-build'
$uhdBuild = Join-Path $buildRoot 'SoapyUHDPrivate-build'
$vendorInclude = Join-Path $buildRoot 'vendor-include'
$pothosRoot = 'C:\Program Files\PothosSDR'
$pothosInclude = Join-Path $pothosRoot 'include'
$pothosLib = Join-Path $pothosRoot 'lib'
$pothosBin = Join-Path $pothosRoot 'bin'
$pothosSoapyDll = Join-Path $pothosBin 'SoapySDR.dll'
$patch = Join-Path $PSScriptRoot 'patches\SoapySDRPlay3-msvc.patch'
$limeWrapper = Join-Path $PSScriptRoot 'cmake\SoapyLMS7External'
$uhdWrapper = Join-Path $PSScriptRoot 'cmake\SoapyUHDExternal'
$boostRoot = Join-Path $buildRoot 'boost_1_75_0'
$boostLibraryDir = Join-Path $boostRoot 'lib64-msvc-14.2'
$boostArchive = Join-Path $buildRoot 'downloads\boost_1_75_0-msvc-14.2-64.exe'
$boostUrl = 'https://archives.boost.io/release/1.75.0/binaries/boost_1_75_0-msvc-14.2-64.exe'
$boostSha256 = '403DF37906EA7951C3C26BC046A5901A392E7E62DC386D22F8D7A0EAACD7696F'

$soapyCommit = '1cf5a539a21414ff509ff7d0eedfc5fa8edb90c6'
$sdrplayCommit = '48bd8b41072534018de1d74deb3dea5874d9e0e0'
$rtlsdrCommit = '5b544e3d3a7ae97952742f42f8bb110fe62c3cd8'
$airspyCommit = '9a906cac218bf07a7acd31efa1f2954c3a44ea4b'
$airspyHfCommit = '0b3daf0b47c3c1d0857c873bb184f6a86a37333c'
$limeSuiteCommit = '3c53defaa338060d7d70481c68fedb6aebb41e7a'
$plutoCommit = '0046115838a3c024e5f5869701c45a8d85060d6e'
$uhdCommit = 'd6f7feaf016e1559ea479007196def1cc55a463c'
$cmakeCandidates = @(
    'C:\Program Files\CMake\bin\cmake.exe',
    'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe',
    'C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe',
    'C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
)
$cmake = $cmakeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $cmake) { throw 'CMake/Visual Studio Build Tools x64 est requis pour construire le runtime Soapy privé.' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git est requis pour construire le runtime Soapy privé.' }
$sdrplayHeader = 'C:\Program Files\SDRplay\API\inc\sdrplay_api.h'
$sdrplayLibrary = 'C:\Program Files\SDRplay\API\x64\sdrplay_api.lib'
$hasSdrplaySdk = (Test-Path -LiteralPath $sdrplayHeader) -and (Test-Path -LiteralPath $sdrplayLibrary)
if (-not $hasSdrplaySdk) {
    Write-Warning 'SDK SDRplay absent : le runtime générique sera construit sans SoapySDRPlay3.'
}
$requiredPothosFiles = @(
    (Join-Path $pothosInclude 'rtl-sdr.h'),
    (Join-Path $pothosInclude 'libairspy\airspy.h'),
    (Join-Path $pothosInclude 'libairspyhf\airspyhf.h'),
    (Join-Path $pothosInclude 'lime\LimeSuite.h'),
    (Join-Path $pothosInclude 'iio.h'),
    (Join-Path $pothosInclude 'ad9361.h'),
    (Join-Path $pothosInclude 'libusb-1.0\libusb.h'),
    (Join-Path $pothosLib 'rtlsdr.lib'),
    (Join-Path $pothosBin 'airspy.lib'),
    (Join-Path $pothosBin 'airspyhf.lib'),
    (Join-Path $pothosLib 'LimeSuite.lib'),
    (Join-Path $pothosLib 'libiio.lib'),
    (Join-Path $pothosLib 'libad9361.lib'),
    (Join-Path $pothosLib 'libusb-1.0.lib'),
    (Join-Path $pothosInclude 'uhd\device.hpp'),
    (Join-Path $pothosLib 'uhd.lib'),
    (Join-Path $pothosBin 'uhd.dll')
    $pothosSoapyDll
)
$missingPothosFiles = @($requiredPothosFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missingPothosFiles) {
    throw "Le SDK PothosSDR x64 est incomplet. Fichiers absents : $($missingPothosFiles -join ', ')"
}

function Clear-GeneratedDirectory([string]$path) {
    $target = [System.IO.Path]::GetFullPath($path).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
    $safeRoot = [System.IO.Path]::GetFullPath($buildRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
    if (-not $target.StartsWith($safeRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Répertoire généré hors du build SDRbridge : $target"
    }
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

foreach ($generatedDirectory in @(
    $runtimeRoot,$soapyBuild,$sdrplayBuild,$rtlsdrBuild,$airspyBuild,
    $airspyHfBuild,$limeBuild,$plutoBuild,$uhdBuild,$vendorInclude
)) {
    Clear-GeneratedDirectory $generatedDirectory
}

New-Item -ItemType Directory -Force $sourceRoot,$runtimeRoot | Out-Null

function Get-PinnedSource([string]$url, [string]$destination, [string]$commit) {
    if (-not (Test-Path -LiteralPath (Join-Path $destination '.git'))) {
        git clone --no-checkout $url $destination
        if ($LASTEXITCODE -ne 0) { throw "Clonage impossible : $url" }
    }
    git -C $destination fetch --depth 1 origin $commit
    if ($LASTEXITCODE -ne 0) { throw "Révision introuvable : $commit" }
    git -C $destination checkout --detach --force $commit
    if ($LASTEXITCODE -ne 0) { throw "Checkout impossible : $commit" }
}

function Build-SoapyModule([string]$source, [string]$build, [string[]]$cmakeArguments) {
    & $cmake -S $source -B $build -A x64 `
        "-DSoapySDR_DIR=$soapyCmake" `
        "-DCMAKE_INSTALL_PREFIX=$runtimeRoot" `
        '-DCMAKE_POLICY_VERSION_MINIMUM=3.5' `
        '-DCMAKE_CXX_FLAGS=/permissive- /EHsc' `
        @cmakeArguments
    if ($LASTEXITCODE -ne 0) { throw "Configuration du module Soapy impossible : $source" }
    & $cmake --build $build --config Release --target INSTALL --parallel --clean-first
    if ($LASTEXITCODE -ne 0) { throw "Compilation du module Soapy impossible : $source" }
}

function Get-BoostSdk {
    $boostHeader = Join-Path $boostRoot 'boost\version.hpp'
    $boostThreadLibrary = Join-Path $boostLibraryDir 'boost_thread-vc142-mt-x64-1_75.lib'
    if ((Test-Path -LiteralPath $boostHeader) -and (Test-Path -LiteralPath $boostThreadLibrary)) {
        return
    }
    New-Item -ItemType Directory -Force (Split-Path -Parent $boostArchive) | Out-Null
    if (-not (Test-Path -LiteralPath $boostArchive)) {
        Invoke-WebRequest -Uri $boostUrl -OutFile $boostArchive
    }
    $actualHash = (Get-FileHash -LiteralPath $boostArchive -Algorithm SHA256).Hash
    if ($actualHash -ne $boostSha256) {
        throw "Archive Boost 1.75 invalide (SHA-256 $actualHash)."
    }
    $target = [System.IO.Path]::GetFullPath($boostRoot)
    $safeRoot = [System.IO.Path]::GetFullPath($buildRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
    if (-not $target.StartsWith($safeRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Répertoire Boost hors du build SDRbridge : $target"
    }
    $process = Start-Process -FilePath $boostArchive `
        -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/DIR=$target") `
        -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $boostThreadLibrary)) {
        throw 'Extraction du SDK Boost 1.75 x64 impossible.'
    }
}

Get-PinnedSource 'https://github.com/pothosware/SoapySDR.git' $soapySource $soapyCommit
if ($hasSdrplaySdk) {
    Get-PinnedSource 'https://github.com/pothosware/SoapySDRPlay3.git' $sdrplaySource $sdrplayCommit
}
Get-PinnedSource 'https://github.com/pothosware/SoapyRTLSDR.git' $rtlsdrSource $rtlsdrCommit
Get-PinnedSource 'https://github.com/pothosware/SoapyAirspy.git' $airspySource $airspyCommit
Get-PinnedSource 'https://github.com/pothosware/SoapyAirspyHF.git' $airspyHfSource $airspyHfCommit
Get-PinnedSource 'https://github.com/myriadrf/LimeSuite.git' $limeSuiteSource $limeSuiteCommit
Get-PinnedSource 'https://github.com/pothosware/SoapyPlutoSDR.git' $plutoSource $plutoCommit
Get-PinnedSource 'https://github.com/pothosware/SoapyUHD.git' $uhdSource $uhdCommit
Get-BoostSdk

if ($hasSdrplaySdk) {
    git -C $sdrplaySource apply --check $patch 2>$null
    if ($LASTEXITCODE -eq 0) {
        git -C $sdrplaySource apply $patch
        if ($LASTEXITCODE -ne 0) { throw 'Application du patch SoapySDRPlay3 impossible.' }
    }
    else {
        git -C $sdrplaySource apply --reverse --check $patch 2>$null
        if ($LASTEXITCODE -ne 0) { throw 'Le patch SoapySDRPlay3 ne correspond pas à la révision épinglée.' }
    }
}

& $cmake -S $soapySource -B $soapyBuild -A x64 "-DCMAKE_INSTALL_PREFIX=$runtimeRoot" '-DCMAKE_POLICY_VERSION_MINIMUM=3.5'
if ($LASTEXITCODE -ne 0) { throw 'Configuration de SoapySDR impossible.' }
& $cmake --build $soapyBuild --config Release --target INSTALL --parallel --clean-first
if ($LASTEXITCODE -ne 0) { throw 'Compilation de SoapySDR impossible.' }

$soapyCmake = Join-Path $runtimeRoot 'cmake'
if ($hasSdrplaySdk) {
    & $cmake -S $sdrplaySource -B $sdrplayBuild -A x64 "-DSoapySDR_DIR=$soapyCmake" "-DCMAKE_INSTALL_PREFIX=$runtimeRoot" '-DCMAKE_POLICY_VERSION_MINIMUM=3.5'
    if ($LASTEXITCODE -ne 0) { throw 'Configuration de SoapySDRPlay3 impossible.' }
    & $cmake --build $sdrplayBuild --config Release --target INSTALL --parallel --clean-first
    if ($LASTEXITCODE -ne 0) { throw 'Compilation de SoapySDRPlay3 impossible.' }
}

# PothosSDR contains development headers for the vendor libraries and its own
# SoapySDR 0.8 headers in the same include tree.  Copy only the required vendor
# headers into isolated staging directories so every module is unambiguously
# compiled against SDRbridge's private SoapySDR 0.8 ABI.
New-Item -ItemType Directory -Force `
    (Join-Path $vendorInclude 'rtlsdr'), `
    (Join-Path $vendorInclude 'airspy\libairspy'), `
    (Join-Path $vendorInclude 'airspyhf\libairspyhf'), `
    (Join-Path $vendorInclude 'lime\lime'), `
    (Join-Path $vendorInclude 'pluto\libusb-1.0'), `
    (Join-Path $vendorInclude 'uhd\uhd') | Out-Null
Copy-Item -LiteralPath (Join-Path $pothosInclude 'rtl-sdr.h'),(Join-Path $pothosInclude 'rtl-sdr_export.h') -Destination (Join-Path $vendorInclude 'rtlsdr') -Force
Copy-Item -Path (Join-Path $pothosInclude 'libairspy\*') -Destination (Join-Path $vendorInclude 'airspy\libairspy') -Force
Copy-Item -Path (Join-Path $pothosInclude 'libairspyhf\*') -Destination (Join-Path $vendorInclude 'airspyhf\libairspyhf') -Force
Copy-Item -Path (Join-Path $pothosInclude 'lime\*') -Destination (Join-Path $vendorInclude 'lime\lime') -Recurse -Force
Copy-Item -LiteralPath (Join-Path $pothosInclude 'iio.h'),(Join-Path $pothosInclude 'ad9361.h'),(Join-Path $pothosInclude 'ad9361-wrapper.h') -Destination (Join-Path $vendorInclude 'pluto') -Force
Copy-Item -Path (Join-Path $pothosInclude 'libusb-1.0\*') -Destination (Join-Path $vendorInclude 'pluto\libusb-1.0') -Force
Copy-Item -Path (Join-Path $pothosInclude 'uhd\*') -Destination (Join-Path $vendorInclude 'uhd\uhd') -Recurse -Force

Build-SoapyModule $rtlsdrSource $rtlsdrBuild @(
    "-DRTLSDR_INCLUDE_DIR=$(Join-Path $vendorInclude 'rtlsdr')",
    "-DRTLSDR_LIBRARY=$(Join-Path $pothosLib 'rtlsdr.lib')"
)
Build-SoapyModule $airspySource $airspyBuild @(
    "-DLibAIRSPY_INCLUDE_DIRS=$(Join-Path $vendorInclude 'airspy')",
    "-DLibAIRSPY_LIBRARIES=$(Join-Path $pothosBin 'airspy.lib')"
)
Build-SoapyModule $airspyHfSource $airspyHfBuild @(
    "-DLibAIRSPYHF_INCLUDE_DIRS=$(Join-Path $vendorInclude 'airspyhf')",
    "-DLibAIRSPYHF_LIBRARIES=$(Join-Path $pothosBin 'airspyhf.lib')"
)
Build-SoapyModule $limeWrapper $limeBuild @(
    "-DLIMESUITE_SOURCE_DIR=$limeSuiteSource",
    "-DLIMESUITE_INCLUDE_DIR=$(Join-Path $vendorInclude 'lime')",
    "-DLIMESUITE_LIBRARY=$(Join-Path $pothosLib 'LimeSuite.lib')"
)
Build-SoapyModule $plutoSource $plutoBuild @(
    "-DLibIIO_INCLUDE_DIR=$(Join-Path $vendorInclude 'pluto')",
    "-DLibIIO_LIBRARY=$(Join-Path $pothosLib 'libiio.lib')",
    "-DLibAD9361_INCLUDE_DIR=$(Join-Path $vendorInclude 'pluto')",
    "-DLibAD9361_LIBRARY=$(Join-Path $pothosLib 'libad9361.lib')",
    "-DLibUSB_INCLUDE_DIR=$(Join-Path $vendorInclude 'pluto\libusb-1.0')",
    "-DLibUSB_LIBRARY=$(Join-Path $pothosLib 'libusb-1.0.lib')"
)
Build-SoapyModule $uhdWrapper $uhdBuild @(
    "-DSOAPYUHD_SOURCE_DIR=$uhdSource",
    "-DUHD_INCLUDE_DIR=$(Join-Path $vendorInclude 'uhd')",
    "-DUHD_LIBRARY=$(Join-Path $pothosLib 'uhd.lib')",
    "-DBOOST_INCLUDE_DIR=$boostRoot",
    "-DCMAKE_MODULE_LINKER_FLAGS=/LIBPATH:$boostLibraryDir"
)

# The application uses SoapySDR through the C ABI.  The locally compiled
# 0.8.1 SDK supplies headers and import libraries for every private module,
# while the matching Pothos VC16 runtime is used in the delivered package.
# This avoids an access violation observed in the C registry when the same
# core is rebuilt with the newer VS 18 toolset, without ever loading Pothos'
# system modules0.8 directory.
Copy-Item -LiteralPath $pothosSoapyDll -Destination (Join-Path $runtimeRoot 'bin\SoapySDR.dll') -Force

$utility = Join-Path $runtimeRoot 'bin\SoapySDRUtil.exe'
$env:SOAPY_SDR_ROOT = $runtimeRoot
$env:PATH = "$(Join-Path $runtimeRoot 'bin');C:\Program Files\SDRplay\API\x64;$pothosBin;$env:PATH"
$runtimeInfo = (& $utility --info 2>&1 | Out-String)
Write-Host $runtimeInfo
if ($LASTEXITCODE -ne 0) { throw 'Le runtime Soapy privé ne passe pas son auto-test.' }
$expectedFactories = @('rtlsdr','airspy','airspyhf','lime','plutosdr','uhd')
if ($hasSdrplaySdk) { $expectedFactories += 'sdrplay' }
foreach ($factory in $expectedFactories) {
    if ($runtimeInfo -notmatch "(?m)^Available factories.*\b$factory\b") {
        throw "Factory Soapy absente après compilation : $factory"
    }
}

Write-Host "Runtime Soapy privé : $runtimeRoot"
