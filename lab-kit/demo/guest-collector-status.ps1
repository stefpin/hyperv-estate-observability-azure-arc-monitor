$ErrorActionPreference = 'Stop'
$task=Get-ScheduledTask -TaskName HV-SQL-Memory-Collector
$info=Get-ScheduledTaskInfo -TaskName HV-SQL-Memory-Collector
"Task=$($task.State); user=$($task.Principal.UserId); logon=$($task.Principal.LogonType); last=$($info.LastRunTime.ToString('s')); result=$($info.LastTaskResult)"
if (Test-Path 'C:\HV-Demo\logs\collector-errors.log') { Get-Content 'C:\HV-Demo\logs\collector-errors.log' -Tail 5 }
Get-ChildItem 'C:\HV-Demo\logs' | Select-Object Name,Length,LastWriteTime | Format-Table
Get-Service Schedule | Format-Table Name,Status
Get-LocalUser HvSqlCollector | Format-List Name,Enabled,PasswordExpires
(Get-ScheduledTask -TaskName HV-SQL-Memory-Collector).Settings | Format-List StartWhenAvailable,RunOnlyIfIdle,DisallowStartIfOnBatteries,AllowDemandStart,Enabled
& secedit.exe /export /cfg 'C:\HV-Demo\batch-current.inf' /areas USER_RIGHTS /quiet
Get-Content 'C:\HV-Demo\batch-current.inf' | Where-Object {$_ -match 'SeBatchLogonRight|SeDenyBatchLogonRight'}
"Collector SID=$((Get-LocalUser HvSqlCollector).SID.Value)"
Get-WinEvent -FilterHashtable @{LogName='Security';Id=4625;StartTime=(Get-Date).AddMinutes(-30)} -ErrorAction SilentlyContinue |
    Where-Object {$_.Message -match 'HvSqlCollector'} | Select-Object -First 2 | ForEach-Object {
        [xml]$xml=$_.ToXml()
        foreach($node in $xml.Event.EventData.Data){if($node.Name -in 'TargetUserName','Status','SubStatus','LogonType'){"$($node.Name)=$($node.'#text')"}}
    }
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-TaskScheduler/Operational';StartTime=(Get-Date).AddMinutes(-20)} -ErrorAction SilentlyContinue |
    Where-Object {$_.Message -match 'HV-SQL-Memory'} | Select-Object -First 4 Id,Message | Format-List
