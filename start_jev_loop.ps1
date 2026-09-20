param([int]$GamePid, [string]$RecordingFolder, [int]$Seconds=600)
$ErrorActionPreference = 'Stop'
$jevEncrypted = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'typesafe-key.dpapi') -Raw).Trim()
$jevSecure = ConvertTo-SecureString $jevEncrypted
$jevCredential = [pscredential]::new('typesafe', $jevSecure)
$env:TYPESAFE_API_KEY = $jevCredential.GetNetworkCredential().Password
try {
    & (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'jev_loop.py') --pid $GamePid --recording $RecordingFolder --seconds $Seconds
    if ($LASTEXITCODE -ne 0) { throw 'Jev loop stopped; inspect loop-status.json before resuming.' }
} finally {
    $env:TYPESAFE_API_KEY = $null
    $jevCredential = $null
    $jevSecure = $null
}
