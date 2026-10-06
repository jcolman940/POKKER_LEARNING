# Builds the native core in Release and runs the performance benchmark.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $Root 'core/build/dev'
cmake -S (Join-Path $Root 'core') -B $build
cmake --build $build --config Release --target pokercore_bench
& (Join-Path $build 'Release/pokercore_bench.exe') @args
