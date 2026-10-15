[CmdletBinding()]
param(
    [string]$SdrppRoot = 'E:\Radio\sdrpp_windows_x64_1.3.0\sdrpp_windows_x64',
    [string]$Configuration = 'Release'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$upstreamRoot = Join-Path $repoRoot '.deps\SDRPlusPlus'
$expectedCommit = 'a6df4d58e5f6b3045883a70aeb8fb41fd5dbf1d9'
$buildRoot = Join-Path $repoRoot 'build'
$importRoot = Join-Path $buildRoot 'import'
$binRoot = Join-Path $repoRoot 'bin'

if (-not (Test-Path -LiteralPath (Join-Path $SdrppRoot 'sdrpp_core.dll'))) {
    throw "sdrpp_core.dll introuvable dans $SdrppRoot"
}

if (-not (Test-Path -LiteralPath (Join-Path $upstreamRoot '.git'))) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $upstreamRoot) -Force | Out-Null
    & git clone --filter=blob:none https://github.com/AlexandreRouma/SDRPlusPlus.git $upstreamRoot
    if ($LASTEXITCODE -ne 0) { throw 'Échec du clone SDR++' }
}

$commit = (& git -C $upstreamRoot rev-parse HEAD).Trim()
if ($commit -ne $expectedCommit) {
    & git -C $upstreamRoot fetch origin $expectedCommit
    if ($LASTEXITCODE -ne 0) { throw 'Échec du fetch de la révision SDR++ attendue' }
    & git -C $upstreamRoot checkout --detach $expectedCommit
    if ($LASTEXITCODE -ne 0) { throw 'Échec du checkout de la révision SDR++ attendue' }
}

$vswhereCandidates = @(
    'C:\Program Files\Microsoft Visual Studio\Installer\vswhere.exe',
    'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
)
$vswhere = $vswhereCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $vswhere) { throw 'vswhere.exe introuvable' }
$vsRoot = (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
if (-not $vsRoot) { throw 'Outils C++ Visual Studio introuvables' }
$toolset = Get-ChildItem -LiteralPath (Join-Path $vsRoot 'VC\Tools\MSVC') -Directory |
    Sort-Object Name -Descending | Select-Object -First 1
$nativeTools = Join-Path $toolset.FullName 'bin\Hostx64\x64'
$dumpbin = Join-Path $nativeTools 'dumpbin.exe'
$libTool = Join-Path $nativeTools 'lib.exe'

New-Item -ItemType Directory -Path $importRoot,$binRoot -Force | Out-Null
$coreDll = Join-Path $SdrppRoot 'sdrpp_core.dll'
$defPath = Join-Path $importRoot 'sdrpp_core.def'
$libPath = Join-Path $importRoot 'sdrpp_core.lib'
$dumpOutput = & $dumpbin /nologo /exports $coreDll
$exports = foreach ($line in $dumpOutput) {
    if ($line -match '^\s+\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(\S+)(?:\s+=.*)?$') {
        $Matches[1]
    }
}
if (-not $exports -or $exports.Count -lt 100) {
    throw "Table d'exports SDR++ inattendue ($($exports.Count) symboles)"
}
$defLines = @('LIBRARY sdrpp_core', 'EXPORTS') + ($exports | ForEach-Object { "    $_" })
[System.IO.File]::WriteAllLines($defPath, $defLines, [System.Text.UTF8Encoding]::new($false))
& $libTool /nologo "/def:$defPath" /machine:x64 "/out:$libPath"
if ($LASTEXITCODE -ne 0) { throw "Échec de création de $libPath" }

& cmake -S $repoRoot -B $buildRoot -G 'Visual Studio 17 2022' -A x64 `
    "-DSDRPP_SOURCE_DIR=$upstreamRoot" `
    "-DSDRPP_INSTALL_DIR=$SdrppRoot" `
    "-DSDRPP_IMPORT_LIBRARY=$libPath" `
    -DBUILD_TESTING=ON
if ($LASTEXITCODE -ne 0) { throw 'Échec de configuration CMake' }

& cmake --build $buildRoot --config $Configuration --parallel
if ($LASTEXITCODE -ne 0) { throw 'Échec de compilation' }

& ctest --test-dir $buildRoot -C $Configuration --output-on-failure
if ($LASTEXITCODE -ne 0) { throw 'Échec des tests SDBU v2' }

$builtDll = Join-Path $buildRoot "$Configuration\sdbu_source.dll"
if (-not (Test-Path -LiteralPath $builtDll)) { throw "DLL compilée introuvable: $builtDll" }
Copy-Item -LiteralPath $builtDll -Destination (Join-Path $binRoot 'sdbu_source.dll') -Force

$hash = (Get-FileHash -LiteralPath (Join-Path $binRoot 'sdbu_source.dll') -Algorithm SHA256).Hash
Write-Host "DLL prête: $(Join-Path $binRoot 'sdbu_source.dll')"
Write-Host "SHA256: $hash"
