param([switch]$ProbeOnly, [ValidateSet('release','bench')][string]$Profile = 'release')

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$buildFolder = if ($Profile -eq 'bench') { 'build-bench' } else { 'build-gcc' }
$imagePath = Join-Path $projectRoot "$buildFolder\nucsignal_f405.hex"
if (-not (Test-Path -LiteralPath $imagePath)) {
    throw 'HEX file not found. Run the Release build task first.'
}

$programmerPath = $null
$programmerCommand = Get-Command 'STM32_Programmer_CLI.exe' -ErrorAction SilentlyContinue
if ($programmerCommand) {
    $programmerPath = $programmerCommand.Source
}

if (-not $programmerPath) {
    $standardPath = 'C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe'
    if (Test-Path -LiteralPath $standardPath) {
        $programmerPath = $standardPath
    }
}

if (-not $programmerPath) {
    $bundleRoot = Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\programmer'
    if (Test-Path -LiteralPath $bundleRoot) {
        $bundledProgrammer = Get-ChildItem -LiteralPath $bundleRoot -Filter 'STM32_Programmer_CLI.exe' -File -Recurse |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($bundledProgrammer) {
            $programmerPath = $bundledProgrammer.FullName
        }
    }
}

if (-not $programmerPath) {
    throw 'STM32 Programmer CLI was not found. Install STM32CubeProgrammer or the VS Code STM32 programmer bundle.'
}

Write-Host "Programmer: $programmerPath"
Write-Host "Image:      $imagePath"
if ($ProbeOnly) {
    Write-Host 'Probe-only check passed. No device was modified.'
    exit 0
}
& $programmerPath -c port=SWD mode=UR reset=HWrst -w $imagePath -v -rst
if ($LASTEXITCODE -ne 0) {
    throw "Programming failed with exit code $LASTEXITCODE."
}
