$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$cmake = 'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
if (-not (Test-Path -LiteralPath $cmake)) { throw 'Visual Studio CMake not found' }
& $cmake -S (Join-Path $PSScriptRoot 'ring_atomic') -B (Join-Path $PSScriptRoot 'build\ring_atomic-x64') -G 'Visual Studio 18 2026' -A x64
if ($LASTEXITCODE -ne 0) { throw 'Ring atomic x64 configuration failed' }
& $cmake --build (Join-Path $PSScriptRoot 'build\ring_atomic-x64') --config Release
if ($LASTEXITCODE -ne 0) { throw 'Ring atomic x64 build failed' }
& $cmake -S (Join-Path $PSScriptRoot 'ring_atomic') -B (Join-Path $PSScriptRoot 'build\ring_atomic-Win32') -G 'Visual Studio 18 2026' -A Win32
if ($LASTEXITCODE -ne 0) { throw 'Ring atomic Win32 configuration failed' }
& $cmake --build (Join-Path $PSScriptRoot 'build\ring_atomic-Win32') --config Release
if ($LASTEXITCODE -ne 0) { throw 'Ring atomic Win32 build failed' }
& $cmake -S (Join-Path $PSScriptRoot 'sdrplay_bridge') -B (Join-Path $PSScriptRoot 'build\sdrplay_bridge') -G 'Visual Studio 18 2026' -A x64
if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed' }
& $cmake --build (Join-Path $PSScriptRoot 'build\sdrplay_bridge') --config Release
if ($LASTEXITCODE -ne 0) { throw 'Native SDRplay bridge build failed' }
& $cmake -S (Join-Path $PSScriptRoot 'extio_bridge') -B (Join-Path $PSScriptRoot 'build\extio_bridge') -G 'Visual Studio 18 2026' -A Win32
if ($LASTEXITCODE -ne 0) { throw 'ExtIO CMake configuration failed' }
& $cmake --build (Join-Path $PSScriptRoot 'build\extio_bridge') --config Release
if ($LASTEXITCODE -ne 0) { throw 'ExtIO bridge build failed' }
