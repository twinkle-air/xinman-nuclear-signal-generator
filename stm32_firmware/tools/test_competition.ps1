$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$scratch = Join-Path $root '.test_competition_work'
New-Item -ItemType Directory -Path $scratch,"$root/reports" -Force | Out-Null
try {
    & 'D:\VScode\MinGW\bin\gcc.exe' '-std=c11' '-Wall' '-Wextra' '-Werror' '-DBASIC_SPI_BENCH=1' '-DNUCLEAR_BENCH=1' '-DCOMPETITION_BENCH=1' "-I$root/include" "$root/tests/test_competition.c" "$root/src/device.c" "$root/src/protocol.c" "$root/src/crc32.c" -o "$scratch/test_competition.exe"
    if ($LASTEXITCODE -ne 0) { throw 'Host test compilation failed' }
    & "$scratch/test_competition.exe" | Tee-Object "$root/reports/competition_host_test.log"
    if ($LASTEXITCODE -ne 0) { throw 'Host tests failed' }
} finally {
    $resolved = [IO.Path]::GetFullPath($scratch)
    if ($resolved -eq (Join-Path $root '.test_competition_work') -and $resolved.StartsWith($root + [IO.Path]::DirectorySeparatorChar)) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
