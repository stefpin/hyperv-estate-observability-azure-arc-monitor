$ErrorActionPreference='Stop'
. "$PSScriptRoot\..\context.ps1"
$output=Invoke-LabArcScript -Machine SQL2019-GUEST `
    -ScriptPath "$PSScriptRoot\..\sources\demo-v22\guest-final-health.ps1" -TimeoutSeconds 900
$output
$safe=@{
    Utc=[datetime]::UtcNow.ToString('o');Output=($output|Out-String)
    NoSqlStopRequested=$true;NoGuestRebootRequested=$true
}
[IO.File]::WriteAllText("$PSScriptRoot\sql-continuity.json",
    (ConvertTo-Json $safe -Depth 8),(New-Object Text.UTF8Encoding($false)))
