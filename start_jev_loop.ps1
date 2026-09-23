param([int]$GamePid, [string]$RecordingFolder, [int]$Seconds=600, [switch]$World)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'loop_watchdog.py') --ensure
if ($LASTEXITCODE -ne 0) { throw 'Independent loop watchdog is unavailable; inspect before gameplay.' }
$jevEncrypted = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'typesafe-key.dpapi') -Raw).Trim()
$jevSecure = ConvertTo-SecureString $jevEncrypted
$jevCredential = [pscredential]::new('typesafe', $jevSecure)
$env:TYPESAFE_API_KEY = $jevCredential.GetNetworkCredential().Password
try {
    $jevLoopArgs=@('--pid',$GamePid,'--recording',$RecordingFolder,'--seconds',$Seconds)
    if ($World) {$jevLoopArgs+='--world'}
    & (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'jev_loop.py') @jevLoopArgs
    if ($LASTEXITCODE -ne 0) { throw 'Jev loop stopped; inspect loop-status.json before resuming.' }
} finally {
    $env:TYPESAFE_API_KEY = $null
    $jevCredential = $null
    $jevSecure = $null
}
