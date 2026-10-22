param([string]$CollectorBase64, [string]$CollectorPasswordHex)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($env:COMPUTERNAME -ne 'SQL2019-GUEST') { throw 'Wrong guest; nothing changed' }
if ($CollectorPasswordHex -notmatch '^x([0-9a-f]{2})+$') { throw 'Collector password missing' }
$h = $CollectorPasswordHex.Substring(1); $b = New-Object byte[] ($h.Length / 2)
for ($i = 0; $i -lt $b.Length; $i++) { $b[$i] = [Convert]::ToByte($h.Substring(2 * $i, 2), 16) }
$password = [Text.Encoding]::ASCII.GetString($b)
$root = 'C:\HV-Demo'
New-Item -ItemType Directory -Force -Path $root, "$root\logs" | Out-Null
$oldTask=Get-ScheduledTask -TaskName HV-SQL-Memory-Collector -ErrorAction SilentlyContinue
if($oldTask -and $oldTask.State -eq 'Running'){Stop-ScheduledTask -TaskName HV-SQL-Memory-Collector}
$user = 'HvSqlCollector'
if (-not (Get-LocalUser -Name $user -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $user -Password (ConvertTo-SecureString $password -AsPlainText -Force) -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
}
# Add only this account to the batch-logon right, preserving every existing principal.
$export = "$root\batch-rights-export.inf"
& secedit.exe /export /cfg $export /areas USER_RIGHTS /quiet
if ($LASTEXITCODE -ne 0) { throw 'Could not export batch-logon permissions' }
$line = Get-Content $export | Where-Object { $_ -match '^SeBatchLogonRight\s*=' } | Select-Object -First 1
$existing = if ($line) { @((($line -split '=',2)[1].Trim()) -split ',' | Where-Object { $_ }) } else { @() }
$sid = '*' + (Get-LocalUser -Name $user).SID.Value
if ($existing -notcontains $sid -and $existing -notcontains $user) {
    $config = "[Unicode]`r`nUnicode=yes`r`n[Version]`r`nsignature=`"`$CHICAGO`$`"`r`nRevision=1`r`n[Privilege Rights]`r`nSeBatchLogonRight = " + (($existing + $sid) -join ',') + "`r`n"
    [IO.File]::WriteAllText("$root\batch-rights.inf", $config, [Text.Encoding]::Unicode)
    & secedit.exe /configure /db "$root\batch-rights.sdb" /cfg "$root\batch-rights.inf" /areas USER_RIGHTS /quiet
    if ($LASTEXITCODE -ne 0) { throw 'Could not grant collector batch-logon permission' }
}
[IO.File]::WriteAllBytes("$root\memory-collector.ps1", [Convert]::FromBase64String($CollectorBase64))
if (-not (Test-Path "$root\stage.txt")) { [IO.File]::WriteAllText("$root\stage.txt", 'idle') }
& icacls.exe $root /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' "${env:COMPUTERNAME}\${user}:(OI)(CI)RX" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not secure demo scripts' }
& icacls.exe "$root\logs" /grant:r "${env:COMPUTERNAME}\${user}:(OI)(CI)M" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not grant collector log access' }
$connection = New-Object Data.SqlClient.SqlConnection('Server=localhost;Integrated Security=true;Connect Timeout=30')
try {
    $connection.Open()
    $command = $connection.CreateCommand()
    $command.CommandText = @"
IF NOT EXISTS(SELECT 1 FROM sys.server_principals WHERE name=N'SQL2019-GUEST\HvSqlCollector')
 CREATE LOGIN [SQL2019-GUEST\HvSqlCollector] FROM WINDOWS;
GRANT VIEW SERVER STATE TO [SQL2019-GUEST\HvSqlCollector];
GRANT CONNECT SQL TO [SQL2019-GUEST\HvSqlCollector];
IF DB_ID('OrdersDemo') IS NULL CREATE DATABASE OrdersDemo
 ON (NAME='OrdersDemo',FILENAME='E:\SQLData\OrdersDemo.mdf',SIZE=256MB,FILEGROWTH=256MB)
 LOG ON (NAME='OrdersDemo_log',FILENAME='L:\SQLLog\OrdersDemo.ldf',SIZE=128MB,FILEGROWTH=128MB);
IF DB_ID('BillingDemo') IS NULL CREATE DATABASE BillingDemo
 ON (NAME='BillingDemo',FILENAME='E:\SQLData\BillingDemo.mdf',SIZE=32MB,FILEGROWTH=64MB)
 LOG ON (NAME='BillingDemo_log',FILENAME='L:\SQLLog\BillingDemo.ldf',SIZE=32MB,FILEGROWTH=64MB);
IF DB_ID('ReportingDemo') IS NULL CREATE DATABASE ReportingDemo
 ON (NAME='ReportingDemo',FILENAME='E:\SQLData\ReportingDemo.mdf',SIZE=32MB,FILEGROWTH=64MB)
 LOG ON (NAME='ReportingDemo_log',FILENAME='L:\SQLLog\ReportingDemo.ldf',SIZE=32MB,FILEGROWTH=64MB);
ALTER DATABASE OrdersDemo SET RECOVERY SIMPLE;
ALTER DATABASE BillingDemo SET RECOVERY SIMPLE;
ALTER DATABASE ReportingDemo SET RECOVERY SIMPLE;
"@
    $command.CommandTimeout = 300
    $null = $command.ExecuteNonQuery()
    $command.CommandText = 'SELECT total_physical_memory_kb/1024.0 FROM sys.dm_os_sys_memory'
    $physical = [double]$command.ExecuteScalar()
    $cap = [int][math]::Floor($physical * 0.8)
    $command.CommandText = 'SELECT available_physical_memory_kb/1024.0 FROM sys.dm_os_sys_memory'
    $available = [double]$command.ExecuteScalar()
    if ($available -lt 3072) { throw "Only $([math]::Round($available)) MB is currently available; investigate OS headroom before increasing SQL ceiling" }
    $command.CommandText = "EXEC sp_configure 'show advanced options',1; RECONFIGURE; EXEC sp_configure 'max server memory (MB)', $cap; RECONFIGURE;"
    $null = $command.ExecuteNonQuery()
    "SQL memory ceiling=$cap MB (80% of detected $([math]::Round($physical)) MB physical RAM); available now=$([math]::Round($available)) MB."
}
finally { $connection.Dispose() }
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$root\memory-collector.ps1`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName HV-SQL-Memory-Collector -Action $action -Trigger $trigger -Settings $settings -User "$env:COMPUTERNAME\$user" -Password $password -RunLevel Limited -Force | Out-Null
$password = $null
Start-ScheduledTask -TaskName HV-SQL-Memory-Collector
Start-Sleep -Seconds 30
$task = Get-ScheduledTask -TaskName HV-SQL-Memory-Collector
$log = Get-ChildItem "$root\logs\sql-memory-*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $log -or $task.State -ne 'Running') { throw 'Memory collector is not running or has not produced logs' }
$last = Get-Content $log.FullName -Tail 1 | ConvertFrom-Json
"Collector=$($task.State); total=$($last.TotalMemoryMB) MB; free=$($last.FreeMemoryMB) MB; grant allocated=$($last.GrantAllocatedMB) MB; used=$($last.GrantUsedMB) MB."
'SQL-MEMORY-SETUP-DONE'
