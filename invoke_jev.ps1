param([int]$GamePid, [string]$RequestFile, [string]$RecordingFolder)
$ErrorActionPreference = 'Stop'
$jevEncrypted = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'typesafe-key.dpapi') -Raw).Trim()
$jevSecure = ConvertTo-SecureString $jevEncrypted
$jevCredential = [pscredential]::new('typesafe', $jevSecure)
$env:TYPESAFE_API_KEY = $jevCredential.GetNetworkCredential().Password
try {
    & (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'decide_game.py') --pid $GamePid --request $RequestFile --recording $RecordingFolder
    if ($LASTEXITCODE -ne 0) { throw 'Jev decision failed; no game input was sent.' }
} finally {
    $env:TYPESAFE_API_KEY = $null
    $jevCredential = $null
    $jevSecure = $null
}
