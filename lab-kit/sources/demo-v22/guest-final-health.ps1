$ErrorActionPreference='Stop'
foreach($name in 'MSSQLSERVER','SQLSERVERAGENT','SqlServerExtension'){
 $service=Get-CimInstance Win32_Service -Filter "Name='$name'"
 if($service.State -ne 'Running' -or $service.StartMode -ne 'Auto'){throw "Service $name is not Running/Auto"}
 "Service $name Running/Auto."
}
$process=Get-Process sqlservr
"SQL process start UTC=$($process.StartTime.ToUniversalTime().ToString('o')); last boot UTC=$((Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o'))."
$task=Get-ScheduledTask HV-SQL-Memory-Collector
if($task.State -ne 'Running'){throw 'Memory collector not running'}
$stage=[IO.File]::ReadAllText('C:\HV-Demo\stage.txt').Trim()
if($stage -ne 'idle'){throw "Memory workload stage is still $stage"}
$connection=New-Object Data.SqlClient.SqlConnection('Server=localhost;Integrated Security=true;Connect Timeout=30')
try{
 $connection.Open();$command=$connection.CreateCommand()
 $command.CommandText="SELECT CONVERT(nvarchar(50),SERVERPROPERTY('ProductVersion')), (SELECT value_in_use FROM sys.configurations WHERE name='max server memory (MB)'),(SELECT COUNT(*) FROM sys.databases WHERE state<>0),IS_SRVROLEMEMBER('sysadmin','SQL2019-GUEST\HvSqlCollector');"
 $reader=$command.ExecuteReader();$null=$reader.Read()
 "SQL build=$($reader.GetValue(0)); maxMemoryMB=$($reader.GetValue(1)); offlineDatabases=$($reader.GetValue(2)); collectorSysadmin=$($reader.GetValue(3))."
 if([int]$reader.GetValue(1) -ne 9829 -or [int]$reader.GetValue(2) -ne 0 -or [int]$reader.GetValue(3) -ne 0){throw 'SQL safety state differs from intended configuration'}
 $reader.Close()
 $command.CommandText='SELECT COUNT_BIG(*) FROM OrdersDemo.dbo.OrderLines'
 "Synthetic OrderLines rows=$($command.ExecuteScalar())."
 $command.CommandText="SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE program_name='HV-DEMO-MEMORY' AND session_id<>@@SPID"
 if([int]$command.ExecuteScalar() -ne 0){throw 'A demonstration SQL session remains connected'}
}
finally{$connection.Dispose()}
$last=(Get-Content (Get-ChildItem 'C:\HV-Demo\logs\sql-memory-*.json'|Sort-Object LastWriteTime -Descending|Select-Object -First 1).FullName -Tail 1)|ConvertFrom-Json
"Collector stage=$stage; active query grants=$($last.GrantCount); pending=$($last.PendingGrants); OS available=$([math]::Round($last.OsAvailableMB)) MiB."
if($last.PendingGrants -ne 0){throw 'SQL memory grants are pending after rehearsal'}
if(Get-ChildItem 'E:\HV-IO-Demo' -Filter *.bin -ErrorAction SilentlyContinue){throw 'Storage test files remain'}
'FINAL-DEMO-HEALTH-OK'
