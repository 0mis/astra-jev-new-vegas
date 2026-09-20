param([Parameter(Mandatory=$true)][string]$ConfigDirectory)
$ErrorActionPreference='Stop'
if (Get-Process FalloutNV -ErrorAction SilentlyContinue) { throw 'Close FalloutNV before changing startup input settings.' }
$nvBackupStamp=Get-Date -Format 'yyyyMMddTHHmmss'
foreach ($nvName in @('Fallout.ini','FalloutPrefs.ini')) {
    $nvPath=Join-Path $ConfigDirectory $nvName
    $nvItem=Get-Item -LiteralPath $nvPath
    $nvReadOnly=$nvItem.IsReadOnly
    Copy-Item -LiteralPath $nvPath -Destination (Join-Path $PSScriptRoot ($nvName+'.before-input-'+$nvBackupStamp))
    $nvItem.IsReadOnly=$false
    try {
        $nvText=Get-Content -LiteralPath $nvPath -Raw
        foreach ($nvSetting in @(
            @('Controls','bUse Joystick','0'),
            @('Interface','bDisable360Controller','1'),
            @('General','SLocalSavePath','JevSaves\')
        )) {
            $nvPattern='(?m)^'+[regex]::Escape($nvSetting[1])+'=.*$'
            $nvLine=$nvSetting[1]+'='+$nvSetting[2]
            if ([regex]::IsMatch($nvText,$nvPattern)) {
                $nvText=[regex]::Replace($nvText,$nvPattern,$nvLine)
            } else {
                $nvHeader='['+$nvSetting[0]+']'
                if (-not $nvText.Contains($nvHeader)) { throw "Missing INI section $nvHeader" }
                $nvText=$nvText.Replace($nvHeader,$nvHeader+"`r`n"+$nvLine)
            }
        }
        [IO.File]::WriteAllText($nvPath,$nvText,[Text.Encoding]::ASCII)
    } finally { (Get-Item -LiteralPath $nvPath).IsReadOnly=$nvReadOnly }
}
Write-Output 'Input and separate-save settings updated; backups preserved. Recheck after the launcher regenerates Fallout.ini.'
