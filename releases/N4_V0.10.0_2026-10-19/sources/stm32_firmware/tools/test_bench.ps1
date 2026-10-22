$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$scratch = Join-Path $root '.test_work'
New-Item -ItemType Directory -Path $scratch,"$root/reports" -Force | Out-Null
try {
    & 'D:\VScode\MinGW\bin\gcc.exe' '-std=c11' '-Wall' '-Wextra' '-Werror' '-DBASIC_SPI_BENCH=1' "-I$root/include" "$root/tests/test_bench.c" "$root/src/device.c" "$root/src/protocol.c" "$root/src/crc32.c" -o "$scratch/test_bench.exe"
    if ($LASTEXITCODE -ne 0) { throw 'Host test compilation failed' }
    & "$scratch/test_bench.exe" | Tee-Object "$root/reports/bench_host_test.log"
    if ($LASTEXITCODE -ne 0) { throw 'Host tests failed' }
} finally {
    $resolved = [IO.Path]::GetFullPath($scratch)
    if ($resolved -eq (Join-Path $root '.test_work') -and $resolved.StartsWith($root + [IO.Path]::DirectorySeparatorChar)) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
