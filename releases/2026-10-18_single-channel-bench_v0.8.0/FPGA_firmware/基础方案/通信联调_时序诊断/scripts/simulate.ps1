param([string]$VivadoBin = 'D:\vivado\Vivado\2022.2\bin')
. "$PSScriptRoot/common.ps1"
$projectRoot = Get-AsciiProjectRoot
$work = Join-Path $firmwareRoot '.sim_work'
New-Item -ItemType Directory -Path $work,"$firmwareRoot/reports" -Force | Out-Null
# The shell environment may omit this variable, causing the vendor loader to exit silently.
$env:PROCESSOR_ARCHITECTURE = 'AMD64'
Push-Location "$projectRoot/.sim_work"
try {
    & "$VivadoBin/xvlog.bat" ../rtl/g1_dac_spi.v
    if ($LASTEXITCODE -ne 0) { throw 'Verilog compilation failed.' }
    & "$VivadoBin/xvlog.bat" -sv ../tb/tb_spi.sv
    if ($LASTEXITCODE -ne 0) { throw 'Testbench compilation failed.' }
    & "$VivadoBin/xelab.bat" tb_spi -s spi_sim
    if ($LASTEXITCODE -ne 0) { throw 'Elaboration failed.' }
    $result = & "$VivadoBin/xsim.bat" spi_sim -runall 2>&1
    $result | Tee-Object "$firmwareRoot/reports/simulation.log"
    if ($LASTEXITCODE -ne 0 -or !(($result -join "`n") -match 'PASS: SPI bench')) { throw 'Simulation failed.' }
} finally {
    Pop-Location
    # Delete only the resolved, explicitly named simulation scratch directory.
    $resolvedWork = [IO.Path]::GetFullPath($work)
    $expectedWork = [IO.Path]::GetFullPath((Join-Path $firmwareRoot '.sim_work'))
    if ($resolvedWork -eq $expectedWork -and $resolvedWork.StartsWith([IO.Path]::GetFullPath($firmwareRoot) + [IO.Path]::DirectorySeparatorChar)) {
        Remove-Item -LiteralPath $resolvedWork -Recurse -Force
    }
}
