param([double]$WaitThresholdNs = 110000)
$ErrorActionPreference='Stop'
$sub='<SUBSCRIPTION_ID>';$rg='rg-hyperv-arc-monitor-demo'
$ws="/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.OperationalInsights/workspaces/law-arc-monitor-lab"
$rules=@(
 @{Name='hv-host-cpu-high';Threshold=80;Window='PT10M';Metric='Value';Query='Perf | where Computer == "HV-HOST-01" and ObjectName == "Hyper-V Hypervisor Logical Processor" and CounterName == "% Total Run Time" and InstanceName == "_Total" | summarize Value=avg(CounterValue)'},
 @{Name='hv-guest-cpu-high';Threshold=80;Window='PT10M';Metric='Value';Dimensions=@('Computer');Query='Perf | where ObjectName in ("Processor Information","Processor") and CounterName == "% Processor Time" and InstanceName in ("_Total","total") | summarize Value=avg(CounterValue) by Computer'},
 @{Name='hv-cluster-cpu-high';Threshold=80;Window='PT10M';Metric='Value';Query='Perf | where Computer in ("WIN2019-GUEST","WIN2022-GUEST","WIN2025-GUEST-01") and ObjectName == "Processor Information" and CounterName == "% Processor Time" and InstanceName == "_Total" | summarize MemberCPU=avg(CounterValue) by Computer | summarize Value=avg(MemberCPU)'},
 @{Name='hv-cluster-memory-high';Threshold=85;Window='PT10M';Metric='Value';Query='Perf | where Computer in ("WIN2019-GUEST","WIN2022-GUEST","WIN2025-GUEST-01") and ObjectName == "Memory" and CounterName == "Available Bytes" | summarize MemberMemory=100.0*(1-avg(CounterValue)/8589934592.0) by Computer | summarize Value=avg(MemberMemory)'},
 @{Name='hv-windows-memory-high';Threshold=85;Window='PT10M';Metric='Value';Dimensions=@('Computer');Query=@'
let capacity=datatable(Computer:string,Bytes:real)["HV-HOST-01",68719476736.0,"SQL2019-GUEST",12884901888.0,"WIN2019-GUEST",8589934592.0,"WIN2022-GUEST",8589934592.0,"WIN2025-GUEST-01",8589934592.0];
Perf | where ObjectName == "Memory" and CounterName == "Available Bytes" | summarize Available=avg(CounterValue) by Computer | join kind=inner capacity on Computer | project Computer,Value=100.0*(1-Available/Bytes)
'@},
 @{Name='hv-heartbeat-missing';Threshold=10;Window='PT10M';Override='P1D';Metric='Value';Dimensions=@('Computer');Query=@'
let expected=datatable(Computer:string)["HV-HOST-01","SQL2019-GUEST","WIN2019-GUEST","WIN2022-GUEST","WIN2025-GUEST-01","RHEL94-GUEST"];
let lastbeats=Heartbeat | summarize Seen=max(TimeGenerated) by Computer;
expected | join kind=leftouter lastbeats on Computer | project Computer,Value=iff(isnull(Seen),1440.0,todouble(datetime_diff('second',now(),Seen))/60.0)
'@},
 @{Name='hv-guest-contention-high';Threshold=$WaitThresholdNs;Window='PT5M';Metric='Value';Dimensions=@('Guest');Query='Perf | where Computer == "HV-HOST-01" and ObjectName == "Hyper-V Hypervisor Virtual Processor" and CounterName == "CPU Wait Time Per Dispatch" and InstanceName contains ":" | extend Guest=tostring(split(InstanceName,":")[0]) | summarize Value=percentile(CounterValue,95) by Guest'},
 @{Name='hv-cluster-contention-high';Threshold=$WaitThresholdNs;Window='PT5M';Metric='Value';Query='Perf | where Computer == "HV-HOST-01" and ObjectName == "Hyper-V Hypervisor Virtual Processor" and CounterName == "CPU Wait Time Per Dispatch" and InstanceName contains ":" | extend Guest=tostring(split(InstanceName,":")[0]) | where Guest in ("WIN2019-GUEST","WIN2022-GUEST","WIN2025-GUEST-01") | summarize Value=percentile(CounterValue,95)'},
 @{Name='hv-sql-grants-pending';Threshold=0;Window='PT5M';Metric='Value';Query='HvSqlMemory_CL | summarize Value=min(PendingGrants)'},
 @{Name='hv-sql-os-memory-low';Threshold=1024;Operator='LessThan';Window='PT10M';Metric='Value';Query='HvSqlMemory_CL | summarize Value=avg(OsAvailableMB)'},
 @{Name='hv-disk-latency-high';Threshold=20;Window='PT5M';Metric='Value';Dimensions=@('Computer','ObjectName','InstanceName');Query=@'
let latency=Perf | where ObjectName in ("PhysicalDisk","LogicalDisk") and InstanceName != "_Total" and CounterName == "Avg. Disk sec/Transfer" | summarize Value=avg(CounterValue)*1000 by Computer,ObjectName,InstanceName;
let activity=Perf | where ObjectName in ("PhysicalDisk","LogicalDisk") and InstanceName != "_Total" and CounterName == "Disk Transfers/sec" | summarize IOPS=avg(CounterValue) by Computer,ObjectName,InstanceName;
latency | join kind=inner activity on Computer,ObjectName,InstanceName | where IOPS > 1 | project Computer,ObjectName,InstanceName,Value
'@}
)
$critical=@()
foreach($rule in $rules|Where-Object{$_.Name -in 'hv-host-cpu-high','hv-guest-cpu-high','hv-cluster-cpu-high','hv-cluster-memory-high','hv-windows-memory-high','hv-disk-latency-high'}){
 $copy=@{};foreach($key in $rule.Keys){$copy[$key]=$rule[$key]}
 $copy.Name=$rule.Name.Replace('-high','-critical');$copy.Severity=1
 $copy.Threshold=if($rule.Name -eq 'hv-disk-latency-high'){50}else{90}
 $critical+=$copy
}
$rules+=$critical
$evidence=@()
foreach($rule in $rules){
 $criterion=@{query=$rule.Query;timeAggregation='Average';metricMeasureColumn=$rule.Metric;operator='GreaterThan';threshold=$rule.Threshold;failingPeriods=@{numberOfEvaluationPeriods=1;minFailingPeriodsToAlert=1}}
 if($rule.ContainsKey('Operator')){$criterion.operator=$rule.Operator}
 if($rule.ContainsKey('Dimensions')){$criterion.dimensions=@($rule.Dimensions|ForEach-Object{@{name=$_;operator='Include';values=@('*')}})}
 $body=@{location='<PRIMARY_REGION>';properties=@{displayName=$rule.Name;description='Demo: operational starting threshold. Notifications are attached separately (see docs/setup/19-alerts.md).';severity=2;enabled=$true;evaluationFrequency='PT5M';windowSize=$rule.Window;scopes=@($ws);criteria=@{allOf=@($criterion)};autoMitigate=$true;actions=@{actionGroups=@()}}}
 if($rule.ContainsKey('Override')){$body.properties.overrideQueryTimeRange=$rule.Override}
 if($rule.ContainsKey('Severity')){$body.properties.severity=$rule.Severity}
 $file="$PSScriptRoot\$($rule.Name).json"
 [IO.File]::WriteAllText($file,(ConvertTo-Json $body -Depth 30),(New-Object Text.UTF8Encoding($false)))
 & az rest --method put --url "https://management.azure.com/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.Insights/scheduledQueryRules/$($rule.Name)?api-version=2023-12-01" --body "@$file" -o none --only-show-errors
 if($LASTEXITCODE -ne 0){throw "Creating alert $($rule.Name) failed"}
 $evidence+=@{Name=$rule.Name;Threshold=$rule.Threshold;Window=$rule.Window;EmailEnabled=$false}
 "Created portal-only alert $($rule.Name)."
}
[IO.File]::WriteAllText("$PSScriptRoot\alert-evidence.json",(ConvertTo-Json -InputObject $evidence -Depth 8),(New-Object Text.UTF8Encoding($false)))
