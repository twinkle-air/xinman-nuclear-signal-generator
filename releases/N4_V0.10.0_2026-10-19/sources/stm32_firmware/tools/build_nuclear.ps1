$ErrorActionPreference = 'Stop'
$env:Path = 'C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin;' + $env:Path
$root = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Path "$root/reports" -Force | Out-Null
Push-Location $root
try {
    $ninjaPath = (Get-Command ninja.exe -ErrorAction Stop).Source
    cmake -S . -B build-nuclear -G Ninja '-DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake' '-DCMAKE_BUILD_TYPE=Release' '-DNUCLEAR_BENCH=ON' "-DCMAKE_MAKE_PROGRAM=$ninjaPath"
    if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed' }
    cmake --build build-nuclear 2>&1 | Tee-Object "$root/reports/nuclear_build.log"
    if ($LASTEXITCODE -ne 0) { throw 'STM32 bench build failed' }
} finally { Pop-Location }
