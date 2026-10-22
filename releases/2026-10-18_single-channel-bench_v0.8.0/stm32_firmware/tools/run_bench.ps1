param([ValidatePattern('^COM[0-9]+$')][string]$Port='COM4', [int]$AmplitudeCode=224,
      [int]$BaselineCode=16, [int]$PeriodUs=1000, [double]$TauUs=12,
      [double]$Seconds=10, [switch]$ProbeOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python = Join-Path $projectRoot 'pc_app/.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'PC app Python environment not found; bench_link.py requires Python >=3.11 and pyserial.' }
$benchArguments = @("$PSScriptRoot/bench_link.py",'--port',$Port,'--amp-code',$AmplitudeCode,
    '--baseline-code',$BaselineCode,'--period-us',$PeriodUs,'--tau-us',$TauUs,'--seconds',$Seconds)
if ($ProbeOnly) { $benchArguments += '--probe-only' }
& $python @benchArguments
if ($LASTEXITCODE -ne 0) { throw 'Bench link test failed; inspect the message above.' }
