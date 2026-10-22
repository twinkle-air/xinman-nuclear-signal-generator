$ErrorActionPreference = 'Stop'
$toolchainBin = 'C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin'
if (Test-Path -LiteralPath $toolchainBin) {
    $env:Path = "$toolchainBin;$env:Path"
}
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    cmake --preset release
    cmake --build --preset release
} finally {
    Pop-Location
}
