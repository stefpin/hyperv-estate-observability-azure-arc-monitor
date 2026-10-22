. "$PSScriptRoot\guest-sql.ps1"
$root='C:\HV-Demo'
New-Item -ItemType Directory -Path $root,"$root\logs" -Force | Out-Null
$user='HvSqlCollector'
$secure=Read-Host 'Private HvSqlCollector password (existing account must use its existing password)' -AsSecureString
if(-not(Get-LocalUser $user -ErrorAction SilentlyContinue)){
    New-LocalUser -Name $user -Password $secure -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
}
Copy-Item "$PSScriptRoot\memory-collector.ps1" "$root\memory-collector.ps1" -Force
if(-not(Test-Path "$root\stage.txt")){[IO.File]::WriteAllText("$root\stage.txt",'idle')}
& icacls.exe $root /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' "SQL2019-GUEST\${user}:(OI)(CI)RX" | Out-Null
if($LASTEXITCODE -ne 0){throw 'Collector script ACL failed.'}
& icacls.exe "$root\logs" /grant:r "SQL2019-GUEST\${user}:(OI)(CI)M" | Out-Null
if($LASTEXITCODE -ne 0){throw 'Collector log ACL failed.'}
Invoke-LabSql "IF NOT EXISTS(SELECT 1 FROM sys.server_principals WHERE name=N'SQL2019-GUEST\HvSqlCollector') CREATE LOGIN [SQL2019-GUEST\HvSqlCollector] FROM WINDOWS;
 GRANT CONNECT SQL TO [SQL2019-GUEST\HvSqlCollector]; GRANT VIEW SERVER STATE TO [SQL2019-GUEST\HvSqlCollector];"
foreach($name in 'OrdersDemo','BillingDemo','ReportingDemo'){
    Invoke-LabSql "IF DB_ID('$name') IS NULL CREATE DATABASE [$name]
 ON (NAME=N'$name',FILENAME=N'E:\SQLData\$name.mdf',SIZE=32MB,FILEGROWTH=64MB)
 LOG ON (NAME=N'${name}_log',FILENAME=N'L:\SQLLog\$name.ldf',SIZE=32MB,FILEGROWTH=64MB);
 ALTER DATABASE [$name] SET RECOVERY SIMPLE;"
}
$ram=[int](Invoke-LabSqlScalar 'SELECT total_physical_memory_kb/1024 FROM sys.dm_os_sys_memory')
$free=[double](Invoke-LabSqlScalar 'SELECT available_physical_memory_kb/1024.0 FROM sys.dm_os_sys_memory')
if($free -lt 3072){throw 'OS headroom below safe setup preflight; inspect before increasing ceiling.'}
$cap=[int][Math]::Floor($ram*0.8)
Invoke-LabSql "EXEC sp_configure 'show advanced options',1;RECONFIGURE;EXEC sp_configure 'max server memory (MB)',$cap;RECONFIGURE;"
$action=New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\HV-Demo\memory-collector.ps1"'
$trigger=New-ScheduledTaskTrigger -AtStartup
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try{
    $pw=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    Register-ScheduledTask -TaskName HV-SQL-Memory-Collector -Action $action -Trigger $trigger -Settings $settings -User "SQL2019-GUEST\$user" -Password $pw -RunLevel Limited -Force | Out-Null
}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$pw=$null}
Start-ScheduledTask HV-SQL-Memory-Collector
Start-Sleep -Seconds 30
$log=Get-ChildItem "$root\logs\sql-memory-*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(-not $log -or (Get-ScheduledTask HV-SQL-Memory-Collector).State -ne 'Running'){throw 'Collector verification failed.'}
Write-Output "Collector Running; ceiling=$cap MB; log timestamp=$($log.LastWriteTime.ToUniversalTime().ToString('o'))"
