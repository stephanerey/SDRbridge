$ErrorActionPreference = 'Stop'

$project = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $project 'build-final\dependencies'
$sourceRoot = Join-Path $buildRoot 'src'
$runtimeRoot = Join-Path $buildRoot 'soapy-runtime'
$soapySource = Join-Path $sourceRoot 'SoapySDR'
$sdrplaySource = Join-Path $sourceRoot 'SoapySDRPlay3'
$soapyBuild = Join-Path $buildRoot 'SoapySDR-build'
$sdrplayBuild = Join-Path $buildRoot 'SoapySDRPlay3-build'
$patch = Join-Path $PSScriptRoot 'patches\SoapySDRPlay3-msvc.patch'

$soapyCommit = 'cf0c0eb5279aa202d5b3a48aee423294b10244eb'
$sdrplayCommit = '48bd8b41072534018de1d74deb3dea5874d9e0e0'
$cmakeCandidates = @(
    'C:\Program Files\CMake\bin\cmake.exe',
    'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe',
    'C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe',
    'C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
)
$cmake = $cmakeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $cmake) { throw 'CMake/Visual Studio Build Tools x64 est requis pour construire le runtime Soapy privé.' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git est requis pour construire le runtime Soapy privé.' }
if (-not (Test-Path -LiteralPath 'C:\Program Files\SDRplay\API\inc\sdrplay_api.h')) {
    throw 'SDRplay API 3.15 doit être installé avant de construire SoapySDRPlay3.'
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

Get-PinnedSource 'https://github.com/pothosware/SoapySDR.git' $soapySource $soapyCommit
Get-PinnedSource 'https://github.com/pothosware/SoapySDRPlay3.git' $sdrplaySource $sdrplayCommit

git -C $sdrplaySource apply --check $patch 2>$null
if ($LASTEXITCODE -eq 0) {
    git -C $sdrplaySource apply $patch
    if ($LASTEXITCODE -ne 0) { throw 'Application du patch SoapySDRPlay3 impossible.' }
}
else {
    git -C $sdrplaySource apply --reverse --check $patch 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Le patch SoapySDRPlay3 ne correspond pas à la révision épinglée.' }
}

& $cmake -S $soapySource -B $soapyBuild -A x64 "-DCMAKE_INSTALL_PREFIX=$runtimeRoot"
if ($LASTEXITCODE -ne 0) { throw 'Configuration de SoapySDR impossible.' }
& $cmake --build $soapyBuild --config Release --target INSTALL --parallel --clean-first
if ($LASTEXITCODE -ne 0) { throw 'Compilation de SoapySDR impossible.' }

$soapyCmake = Join-Path $runtimeRoot 'cmake'
& $cmake -S $sdrplaySource -B $sdrplayBuild -A x64 "-DSoapySDR_DIR=$soapyCmake" "-DCMAKE_INSTALL_PREFIX=$runtimeRoot"
if ($LASTEXITCODE -ne 0) { throw 'Configuration de SoapySDRPlay3 impossible.' }
& $cmake --build $sdrplayBuild --config Release --target INSTALL --parallel --clean-first
if ($LASTEXITCODE -ne 0) { throw 'Compilation de SoapySDRPlay3 impossible.' }

$utility = Join-Path $runtimeRoot 'bin\SoapySDRUtil.exe'
$env:SOAPY_SDR_ROOT = $runtimeRoot
$env:PATH = "$(Join-Path $runtimeRoot 'bin');C:\Program Files\SDRplay\API\x64;$env:PATH"
& $utility --info
if ($LASTEXITCODE -ne 0) { throw 'Le runtime Soapy privé ne passe pas son auto-test.' }

Write-Host "Runtime Soapy privé : $runtimeRoot"
