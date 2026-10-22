param([string]$GowinBin = 'D:\gowin\Gowin_V1.9.10.02_x64\IDE\bin')
. "$PSScriptRoot/common.ps1"
$projectRoot = Get-AsciiProjectRoot
New-Item -ItemType Directory -Path "$firmwareRoot/reports" -Force | Out-Null
$started = Get-Date
& "$GowinBin/gw_sh.exe" "$projectRoot/scripts/build.tcl" 2>&1 | Tee-Object "$firmwareRoot/reports/build.log"
if ($LASTEXITCODE -ne 0) { throw 'Gowin compilation failed.' }
$bitstream = Get-Item -LiteralPath "$firmwareRoot/impl/pnr/g1_dac_spi.fs"
if ($bitstream.LastWriteTime -lt $started) { throw 'Gowin did not generate a fresh bitstream.' }
$timing = Get-Content -LiteralPath "$firmwareRoot/impl/pnr/g1_dac_spi.tr" -Raw
if ($timing -notmatch '<Numbers of Setup Violated Endpoints>:0\s' -or
    $timing -notmatch '<Numbers of Hold Violated Endpoints>:0\s') {
    throw 'Timing failed: do not use this bitstream on hardware.'
}
Write-Output "Built: $($bitstream.FullName)"
