$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$AppRoot\.venv\Scripts\python.exe" -m nucsignal_app.main

