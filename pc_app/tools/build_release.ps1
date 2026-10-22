param([switch]$StageOnly)

$ErrorActionPreference = "Stop"

$AppRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WorkspaceRoot = Split-Path -Parent $AppRoot
$Python = Join-Path $AppRoot ".venv\Scripts\python.exe"
$Stage = Join-Path $AppRoot "dist_release"
$StageExe = Join-Path $Stage "核信号工作台.exe"
$TargetExe = Join-Path $WorkspaceRoot "核信号工作台.exe"
$SmokeResult = Join-Path $Stage "exe_smoke_result.json"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "未找到项目虚拟环境：$Python"
}
$ExpectedVersion = (& $Python -c "import nucsignal_app; print(nucsignal_app.__version__)").Trim()

& $Python -m compileall -q (Join-Path $AppRoot "launcher.py") (Join-Path $AppRoot "src") (Join-Path $AppRoot "tests")
if ($LASTEXITCODE -ne 0) { throw "Python编译检查失败" }

$env:QT_QPA_PLATFORM = "offscreen"
$TestTemp = Join-Path $AppRoot ("test-temp-" + [guid]::NewGuid().ToString("N"))
& $Python -m pytest -q --basetemp $TestTemp (Join-Path $AppRoot "tests")
$TestExitCode = $LASTEXITCODE
if (Test-Path -LiteralPath $TestTemp) { Remove-Item -LiteralPath $TestTemp -Recurse -Force }
if ($TestExitCode -ne 0) { throw "自动测试失败" }
Remove-Item Env:QT_QPA_PLATFORM

& $Python -m PyInstaller --noconfirm --clean --onefile --windowed --noupx `
    --name "核信号工作台" `
    --paths (Join-Path $AppRoot "src") `
    --distpath $Stage `
    --workpath (Join-Path $AppRoot "build") `
    --specpath $AppRoot `
    (Join-Path $AppRoot "launcher.py")
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $StageExe)) {
    throw "EXE构建失败"
}

if (Test-Path -LiteralPath $SmokeResult) {
    Remove-Item -LiteralPath $SmokeResult -Force
}
$Process = Start-Process -FilePath $StageExe -ArgumentList @("--smoke-test", $SmokeResult) -WindowStyle Hidden -Wait -PassThru
if ($Process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $SmokeResult)) {
    throw "暂存EXE启动自检失败"
}
$Smoke = Get-Content -Raw -LiteralPath $SmokeResult | ConvertFrom-Json
$RequiredModes = @("模拟", "单通道台架", "USB CDC", "ST-Link VCP")
if ($Smoke.app_version -ne $ExpectedVersion) {
    throw "暂存EXE版本错误：$($Smoke.app_version)"
}
foreach ($Mode in $RequiredModes) {
    if ($Mode -notin $Smoke.device_modes) {
        throw "暂存EXE缺少连接模式：$Mode"
    }
}
if (-not $Smoke.tutorial_available -or "硬件连接" -notin $Smoke.tutorial_sections) {
    throw "暂存EXE缺少完整教程入口"
}
if (-not $Smoke.manual_port_entry -or $Smoke.csv_export -ne "导出双通道 CSV") {
    throw "暂存EXE缺少串口手动输入或双通道CSV功能"
}
if ($Smoke.builtin_nuclides.Count -lt 9 -or -not $Smoke.fwhm_direct_control) {
    throw "暂存EXE缺少新增核素或FWHM直接调节功能"
}
if (-not $Smoke.plot_interactive -or $Smoke.workflow_steps.Count -ne 5) {
    throw "暂存EXE缺少交互式波形预览或操作流程图"
}
if ($Smoke.plot_colors[0] -ne "#d62828" -or $Smoke.plot_colors[1] -ne "#0057b8") {
    throw "暂存EXE通道颜色不符合CH1红色/CH2蓝色要求"
}

$ResolvedWorkspace = [System.IO.Path]::GetFullPath($WorkspaceRoot)
if (-not $Smoke.bench_panel_available -or "单通道台架" -notin $Smoke.tutorial_sections) {
    throw "暂存EXE缺少台架面板或教程"
}
if (-not $Smoke.n4_tools_available) { throw "暂存EXE缺少N4实测校准工具" }
$ResolvedTarget = [System.IO.Path]::GetFullPath($TargetExe)
if (-not $ResolvedTarget.StartsWith($ResolvedWorkspace, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "目标EXE不在工作区内，拒绝覆盖：$ResolvedTarget"
}
if ($StageOnly) {
    $TargetExe = $StageExe
} else {
    Copy-Item -LiteralPath $StageExe -Destination $TargetExe -Force
}

$Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $TargetExe
$Item = Get-Item -LiteralPath $TargetExe
[PSCustomObject]@{
    Version = $Smoke.app_version
    DeviceModes = $Smoke.device_modes -join ", "
    Target = $Item.FullName
    Size = $Item.Length
    SHA256 = $Hash.Hash
    Modified = $Item.LastWriteTime
}
