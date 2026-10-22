$ErrorActionPreference='Stop'
$folder=(Join-Path $PSScriptRoot '..\..\..\reports-output')
New-Item -ItemType Directory -Force -Path $folder|Out-Null
$memory=@(& "$PSScriptRoot\query-la.ps1" -Query @'
HvSqlMemory_CL | where TimeGenerated > ago(4h)
| summarize Samples=count(),CommittedMiB=round(avg(TotalMemoryMB),2),CacheMiB=round(avg(CacheMemoryMB),2),PeakGrantedMiB=round(max(GrantAllocatedMB),2),PeakUsedMiB=round(max(GrantUsedMB),2),MinOSAvailableMiB=round(min(OsAvailableMB),2),MaxPendingGrants=max(PendingGrants) by Stage
'@)
$memory|Export-Csv "$folder\HV-SQL-Memory-Stages.csv" -NoTypeInformation -Encoding UTF8
$single=@(& "$PSScriptRoot\query-la.ps1" -Query @'
HvSqlMemory_CL | where TimeGenerated > ago(4h) and Stage == "query-grants" and GrantAllocatedMB > 100
| extend UnusedGrantMiB=GrantAllocatedMB-GrantUsedMB
| top 1 by UnusedGrantMiB desc
| project TimeGenerated,GrantedMiB=GrantAllocatedMB,UsedMiB=GrantUsedMB,UnusedGrantMiB,CommittedMiB=TotalMemoryMB,CacheMiB=CacheMemoryMB,OSAvailableMiB=OsAvailableMB
'@)
$single|Export-Csv "$folder\HV-SQL-Granted-Versus-Used.csv" -NoTypeInformation -Encoding UTF8
$contention=@(& "$PSScriptRoot\query-la.ps1" -Query @'
Perf | where TimeGenerated > ago(4h) and Computer == "HV-HOST-01"
| where ObjectName == "Hyper-V Hypervisor Virtual Processor" and CounterName == "CPU Wait Time Per Dispatch" and InstanceName contains ":"
| extend Guest=tostring(split(InstanceName,":")[0])
| summarize MeanWaitNs=round(avg(CounterValue)),P95WaitNs=round(percentile(CounterValue,95)),PeakWaitNs=round(max(CounterValue)),Samples=count() by Guest
'@)
$contention|Export-Csv "$folder\HV-Guest-Contention.csv" -NoTypeInformation -Encoding UTF8
$rhel=@(& "$PSScriptRoot\query-la.ps1" -Query 'HvLinuxDisk_CL | where TimeGenerated > ago(4h) | project TimeGenerated,Computer,Device,ReadIOPS,WriteIOPS,ReadAwaitMs,WriteAwaitMs,AvgQueueDepth,MountedVolumes | order by TimeGenerated asc')
$rhel|Export-Csv "$folder\HV-RHEL-Storage.csv" -NoTypeInformation -Encoding UTF8
$url='https://management.azure.com/subscriptions/<SUBSCRIPTION_ID>/resourceGroups/rg-hyperv-arc-monitor-demo/providers/Microsoft.AzureArcData/SqlServerInstances/SQL2019-GUEST/databases?api-version=2023-09-01-preview'
$json=& az rest --method get --url $url -o json --only-show-errors
if($LASTEXITCODE -ne 0){throw 'Reading SQL database inventory for report failed'}
$databases=(($json|Out-String)|ConvertFrom-Json).value
$databases|ForEach-Object{[pscustomobject]@{Database=$_.name;State=$_.properties.state;SizeMB=$_.properties.sizeMB;Compatibility=$_.properties.compatibilityLevel}}|
 Export-Csv "$folder\HV-SQL-Database-Inventory.csv" -NoTypeInformation -Encoding UTF8
Get-ChildItem $folder -Filter *.csv|ForEach-Object{"Report $($_.Name): $($_.Length) bytes."}
