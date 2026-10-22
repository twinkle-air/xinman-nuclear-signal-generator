$ErrorActionPreference = 'Stop'
$firmwareRoot = Split-Path $PSScriptRoot -Parent
function Get-AsciiProjectRoot {
    # ASCII marker avoids decoding Chinese paths printed by subst.exe.
    $projectId = (Get-Content -LiteralPath "$firmwareRoot/.project-id" -Raw).Trim()
    $letters = @('R','S','U','V','W','Y','Z')
    foreach ($letter in $letters) {
        $marker = $letter + ':\.project-id'
        if ((Test-Path -LiteralPath $marker) -and (Get-Content -LiteralPath $marker -Raw).Trim() -eq $projectId) {
            return ($letter + ':\')
        }
    }
    foreach ($letter in $letters) {
        if (!(Test-Path -LiteralPath ($letter + ':\'))) {
            & subst ($letter + ':') $firmwareRoot
            if ($LASTEXITCODE -ne 0) { throw 'Could not create the ASCII drive alias.' }
            $marker = $letter + ':\.project-id'
            if (!(Test-Path -LiteralPath $marker) -or (Get-Content -LiteralPath $marker -Raw).Trim() -ne $projectId) {
                throw 'Drive alias does not point to the expected project.'
            }
            return ($letter + ':\')
        }
    }
    throw 'No free drive letter for the FPGA project.'
}
