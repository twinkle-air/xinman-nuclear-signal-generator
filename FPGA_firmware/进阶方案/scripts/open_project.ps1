param([string]$GowinBin = 'D:\gowin\Gowin_V1.9.10.02_x64\IDE\bin')
. "$PSScriptRoot/common.ps1"
$projectRoot = Get-AsciiProjectRoot
Write-Output "In Gowin, use File > Open and choose: ${projectRoot}g1_dual_dac_stage1.gprj"
