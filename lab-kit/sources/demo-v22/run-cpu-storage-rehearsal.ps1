$ErrorActionPreference='Stop'
. "$PSScriptRoot\..\sql-install\arc-run.ps1"
$environment=@{}
foreach($line in [IO.File]::ReadAllLines((Join-Path $PSScriptRoot '..\..\..\ENVIRONMENT.txt'))){
 if($line -match '^([A-Z0-9_]+)=(.*)$'){$environment[$matches[1]]=$matches[2]}
}
function Hex([string]$s){'x'+(([Text.Encoding]::ASCII.GetBytes($s)|ForEach-Object{$_.ToString('x2')}) -join '')}
$protected=@{
 Win2019PasswordHex=(Hex $environment.WIN2019_GUEST_PASSWORD)
 Win2022PasswordHex=(Hex $environment.WIN2022_GUEST_PASSWORD)
 Win2025PasswordHex=(Hex $environment.WIN2025_GUEST_PASSWORD)
}
$evidence=@()
$start=[datetime]::UtcNow
$result=Invoke-HvArc -Machine HV-HOST-01 -Name cpu-rehearsal -ScriptPath "$PSScriptRoot\host-cpu-rehearsal.ps1" -Parameters @{LoadSeconds=900} -Protected $protected -Timeout 2400
$result.Output
$evidence+=@{Scenario='CPU';StartUtc=$start.ToString('o');EndUtc=[datetime]::UtcNow.ToString('o');Output=$result.Output}
[IO.File]::WriteAllText("$PSScriptRoot\cpu-storage-rehearsal.json",(ConvertTo-Json -InputObject $evidence -Depth 8),(New-Object Text.UTF8Encoding($false)))
Remove-HvArcCommand -Machine $result.Machine -Name $result.Name
Start-Sleep -Seconds 90
$start=[datetime]::UtcNow
$result=Invoke-HvArc -Machine SQL2019-GUEST -Name storage-rehearsal -ScriptPath "$PSScriptRoot\guest-storage-rehearsal.ps1" -Parameters @{Seconds=180} -Timeout 1200
$result.Output
$evidence+=@{Scenario='Storage';StartUtc=$start.ToString('o');EndUtc=[datetime]::UtcNow.ToString('o');Output=$result.Output}
[IO.File]::WriteAllText("$PSScriptRoot\cpu-storage-rehearsal.json",(ConvertTo-Json -InputObject $evidence -Depth 8),(New-Object Text.UTF8Encoding($false)))
Remove-HvArcCommand -Machine $result.Machine -Name $result.Name
