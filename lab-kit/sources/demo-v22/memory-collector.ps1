$ErrorActionPreference = 'Stop'
$root = 'C:\HV-Demo'
$query = @"
SELECT
 (SELECT value_in_use FROM sys.configurations WHERE name='max server memory (MB)') AS MaxMemoryMB,
 (SELECT SUM(CASE WHEN counter_name='Total Server Memory (KB)' THEN cntr_value ELSE 0 END)/1024.0 FROM sys.dm_os_performance_counters WHERE object_name LIKE '%:Memory Manager%') AS TotalMemoryMB,
 (SELECT SUM(CASE WHEN counter_name='Free Memory (KB)' THEN cntr_value ELSE 0 END)/1024.0 FROM sys.dm_os_performance_counters WHERE object_name LIKE '%:Memory Manager%') AS FreeMemoryMB,
 (SELECT SUM(CASE WHEN counter_name='Database Cache Memory (KB)' THEN cntr_value ELSE 0 END)/1024.0 FROM sys.dm_os_performance_counters WHERE object_name LIKE '%:Memory Manager%') AS CacheMemoryMB,
 (SELECT SUM(CASE WHEN counter_name='Stolen Server Memory (KB)' THEN cntr_value ELSE 0 END)/1024.0 FROM sys.dm_os_performance_counters WHERE object_name LIKE '%:Memory Manager%') AS StolenMemoryMB,
 grants.GrantAllocatedMB,
 grants.GrantUsedMB,
 grants.GrantCount,
 grants.PendingGrants,
 (SELECT physical_memory_in_use_kb/1024.0 FROM sys.dm_os_process_memory) AS ProcessMB,
 (SELECT available_physical_memory_kb/1024.0 FROM sys.dm_os_sys_memory) AS OsAvailableMB,
 (SELECT total_physical_memory_kb/1024.0 FROM sys.dm_os_sys_memory) AS PhysicalMB
FROM (
 SELECT ISNULL(SUM(granted_memory_kb),0)/1024.0 AS GrantAllocatedMB,
        ISNULL(SUM(used_memory_kb),0)/1024.0 AS GrantUsedMB,
        COUNT(CASE WHEN grant_time IS NOT NULL THEN 1 END) AS GrantCount,
        COUNT(CASE WHEN grant_time IS NULL THEN 1 END) AS PendingGrants
 FROM sys.dm_exec_query_memory_grants WHERE session_id<>@@SPID
) AS grants;
"@
while ($true) {
    $connection = New-Object Data.SqlClient.SqlConnection('Server=localhost;Integrated Security=true;Application Name=HV-Memory-Collector;Connect Timeout=15')
    try {
        $connection.Open()
        $command = $connection.CreateCommand()
        $command.CommandText = $query
        $command.CommandTimeout = 15
        $reader = $command.ExecuteReader()
        if (-not $reader.Read()) { throw 'SQL memory collector returned no row' }
        $stage = [IO.File]::ReadAllText("$root\stage.txt").Trim()
        $record = [ordered]@{
            TimeGenerated = [datetime]::UtcNow.ToString('o')
            Computer = $env:COMPUTERNAME
            Instance = 'MSSQLSERVER'
            Stage = $stage
        }
        for ($i = 0; $i -lt $reader.FieldCount; $i++) {
            if ($reader.IsDBNull($i)) { throw "SQL memory field $($reader.GetName($i)) returned NULL; no fabricated default recorded" }
            $record[$reader.GetName($i)] = [double]$reader.GetValue($i)
        }
        $reader.Close()
        $file = "$root\logs\sql-memory-$([datetime]::UtcNow.ToString('yyyyMMdd')).json"
        [IO.File]::AppendAllText($file, (ConvertTo-Json -InputObject $record -Compress) + "`r`n", (New-Object Text.UTF8Encoding($false)))
    }
    catch {
        [IO.File]::AppendAllText("$root\logs\collector-errors.log", [datetime]::UtcNow.ToString('o') + ' ' + $_.Exception.Message + "`r`n")
        throw
    }
    finally { $connection.Dispose() }
    Start-Sleep -Seconds 15
}
