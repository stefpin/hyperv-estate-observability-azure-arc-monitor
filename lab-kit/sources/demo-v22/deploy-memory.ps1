$ErrorActionPreference = 'Stop'
$sub = '<SUBSCRIPTION_ID>'; $rg = 'rg-hyperv-arc-monitor-demo'
$ws = "/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.OperationalInsights/workspaces/law-arc-monitor-lab"
$machine = "/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.HybridCompute/machines/SQL2019-GUEST"
$columns = @(@{name='TimeGenerated';type='datetime'},@{name='Computer';type='string'},@{name='Instance';type='string'},@{name='Stage';type='string'})
foreach ($name in 'MaxMemoryMB','TotalMemoryMB','FreeMemoryMB','CacheMemoryMB','StolenMemoryMB','GrantAllocatedMB','GrantUsedMB','GrantCount','PendingGrants','ProcessMB','OsAvailableMB','PhysicalMB') { $columns += @{name=$name;type='real'} }
$table = @{properties=@{schema=@{name='HvSqlMemory_CL';columns=$columns};retentionInDays=30;totalRetentionInDays=30}}
$tableFile = "$PSScriptRoot\memory-table.json"
[IO.File]::WriteAllText($tableFile, (ConvertTo-Json $table -Depth 20), (New-Object Text.UTF8Encoding($false)))
& az rest --method put --url "$ws/tables/HvSqlMemory_CL`?api-version=2022-10-01" --body "@$tableFile" --only-show-errors -o none
if ($LASTEXITCODE -ne 0) { throw 'Creating SQL memory table failed' }
$counters = @()
foreach ($counter in 'Total Server Memory (KB)','Target Server Memory (KB)','Free Memory (KB)','Database Cache Memory (KB)','Stolen Server Memory (KB)','Granted Workspace Memory (KB)','Memory Grants Pending','Memory Grants Outstanding','Reserved Server Memory (KB)') { $counters += "\SQLServer:Memory Manager\$counter" }
foreach ($counter in 'Page life expectancy','Page reads/sec','Page writes/sec') { $counters += "\SQLServer:Buffer Manager\$counter" }
$counters += '\SQLServer:SQL Statistics\Batch Requests/sec','\SQLServer:General Statistics\User Connections','\Process(sqlservr)\% Processor Time','\Process(sqlservr)\Working Set - Private','\Process(sqlservr)\Private Bytes'
$dcr = @{
    kind='Windows'; location='<PRIMARY_REGION>'
    properties=@{
        description='SQL memory manager counters and aggregate query workspace grants; no query text.'
        streamDeclarations=@{'Custom-HvSqlMemory'=@{columns=$columns}}
        dataSources=@{
            performanceCounters=@(@{name='sqlCounters';streams=@('Microsoft-Perf');samplingFrequencyInSeconds=15;counterSpecifiers=$counters})
            logFiles=@(@{name='sqlMemoryJson';streams=@('Custom-HvSqlMemory');filePatterns=@('C:\HV-Demo\logs\sql-memory-*.json');format='json'})
        }
        destinations=@{logAnalytics=@(@{name='hv';workspaceResourceId=$ws})}
        dataFlows=@(
            @{streams=@('Microsoft-Perf');destinations=@('hv')},
            @{streams=@('Custom-HvSqlMemory');destinations=@('hv');transformKql='source';outputStream='Custom-HvSqlMemory_CL'}
        )
    }
}
$file = "$PSScriptRoot\dcr-sql-servers.json"
[IO.File]::WriteAllText($file, (ConvertTo-Json $dcr -Depth 30), (New-Object Text.UTF8Encoding($false)))
$ruleId = "/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.Insights/dataCollectionRules/dcr-sql-servers"
& az rest --method put --url "$ruleId`?api-version=2023-03-11" --body "@$file" --only-show-errors -o none
if ($LASTEXITCODE -ne 0) { throw 'Creating SQL DCR failed' }
& az monitor data-collection rule association create --subscription $sub --resource $machine --rule-id $ruleId --name assoc-SQL2019-GUEST-sql --only-show-errors -o none
if ($LASTEXITCODE -ne 0) { throw 'Associating SQL DCR failed' }
'SQL memory table and DCR created and associated.'
