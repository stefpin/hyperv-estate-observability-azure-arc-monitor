import json
import pathlib
import uuid

ROOT = pathlib.Path(__file__).parent
SUB = "/subscriptions/<SUBSCRIPTION_ID>"
GROUP = "rg-hyperv-arc-monitor-demo"
WS = f"{SUB}/resourceGroups/{GROUP}/providers/Microsoft.OperationalInsights/workspaces/law-arc-monitor-lab"
CTWS = f"{SUB}/resourceGroups/{GROUP}/providers/Microsoft.OperationalInsights/workspaces/law-arc-ct-sea"
QUERIES = {}
ITEMS = []


def note(name, content):
    ITEMS.append({"type": 1, "name": name, "content": {"json": content}})


def chart(name, title, query, visual="timechart", arg=False, workspace=WS):
    QUERIES[name] = {"query": query, "arg": arg, "workspace": workspace}
    content = {
        "version": "KqlItem/1.0", "title": title, "query": query, "size": 0,
        "queryType": 1 if arg else 0,
        "resourceType": "microsoft.resourcegraph/resources" if arg else "microsoft.operationalinsights/workspaces",
        "crossComponentResources": [SUB if arg else workspace], "visualization": visual,
    }
    if not arg:
        content["timeContextFromParameter"] = "TimeRange"
    if visual == "timechart":
        content["chartSettings"] = {"showLegend": True, "showMetrics": False}
    ITEMS.append({"type": 3, "name": name, "content": content})


TIME = "TimeGenerated {TimeRange}"
GRAIN = "{TimeRange:grain}"
note("intro", "# Hyper-V and SQL estate report - v2.2\nHost plus five nested guests physically in the primary region. Original five Arc records: the primary region; SQL guest Arc/SQL services: Southeast Asia. SQL custom metrics: the primary region; Change Tracking: Southeast Asia. This is a demonstration lab, not a production architecture.")
ITEMS.append({"type": 9, "name": "time", "content": {
    "version": "KqlParameterItem/1.0", "parameters": [{
        "id": str(uuid.uuid4()), "version": "KqlParameterItem/1.0", "name": "TimeRange",
        "label": "Time range", "type": 4, "isRequired": True,
        "typeSettings": {"selectableValues": [{"durationMs": n} for n in (3600000, 14400000, 86400000, 604800000)], "allowCustom": True},
        "value": {"durationMs": 14400000},
    }], "style": "pills",
}})
chart("host-cpu", "Host hypervisor processor utilization (%)", f'''Perf | where {TIME} and Computer == "HV-HOST-01"
| where ObjectName == "Hyper-V Hypervisor Logical Processor" and CounterName == "% Total Run Time" and InstanceName == "_Total"
| summarize CPU=avg(CounterValue) by bin(TimeGenerated,{GRAIN})''')
chart("wait", "Per-guest scheduling wait (nanoseconds per dispatch, not CPU-ready %)", f'''Perf | where {TIME} and Computer == "HV-HOST-01"
| where ObjectName == "Hyper-V Hypervisor Virtual Processor" and CounterName == "CPU Wait Time Per Dispatch" and InstanceName contains ":"
| extend Guest=tostring(split(InstanceName,":")[0])
| summarize WaitNs=avg(CounterValue) by Guest,bin(TimeGenerated,{GRAIN})''')
chart("wait-summary", "Per-guest contention evidence", f'''Perf | where {TIME} and Computer == "HV-HOST-01"
| where ObjectName == "Hyper-V Hypervisor Virtual Processor" and CounterName == "CPU Wait Time Per Dispatch" and InstanceName contains ":"
| extend Guest=tostring(split(InstanceName,":")[0])
| summarize MeanNs=round(avg(CounterValue)),P95Ns=round(percentile(CounterValue,95)),PeakNs=max(CounterValue) by Guest''', "table")
chart("guest-cpu", "Guest-reported processor utilization (%)", f'''Perf | where {TIME}
| where ObjectName in ("Processor Information","Processor") and CounterName == "% Processor Time" and InstanceName in ("_Total","total")
| summarize CPU=avg(CounterValue) by Computer,bin(TimeGenerated,{GRAIN})''')
chart("cluster-cpu", "WIN-CLUSTER-01 - three equal 4-vCPU Windows members (%)", f'''Perf | where {TIME}
| where Computer in ("WIN2019-GUEST","WIN2022-GUEST","WIN2025-GUEST-01")
| where ObjectName == "Processor Information" and CounterName == "% Processor Time" and InstanceName == "_Total"
| summarize MemberCPU=avg(CounterValue) by Computer,bin(TimeGenerated,{GRAIN})
| summarize ClusterCPU=avg(MemberCPU),BusiestMemberCPU=max(MemberCPU) by TimeGenerated''')
chart("cluster-memory", "WIN-CLUSTER-01 physical RAM in use (%) - not committed memory", f'''Perf | where {TIME}
| where Computer in ("WIN2019-GUEST","WIN2022-GUEST","WIN2025-GUEST-01")
| where ObjectName == "Memory" and CounterName == "Available Bytes"
| summarize UsedPercent=100.0*(1-avg(CounterValue)/8589934592.0) by Computer,bin(TimeGenerated,{GRAIN})
| summarize ClusterMemory=avg(UsedPercent),BusiestMemberMemory=max(UsedPercent) by TimeGenerated''')
note("memory-intro", "## SQL memory: allocated is not the same as executing-query use\nTotal Server Memory = SQL-manager committed memory. Total minus Free includes retained cache and internal allocations; it is NOT a universal active-workload metric. Query Used versus Granted below covers sort/hash workspace only. These categories overlap: do not sum them. The configured ceiling is not an allocation. SQL process memory can include allocations outside that ceiling.")
chart("memory-cap", "Configured ceiling, SQL-manager committed and process footprint (MiB)", f'''HvSqlMemory_CL | where {TIME}
| summarize MaxMemoryMB=avg(MaxMemoryMB),CommittedMB=avg(TotalMemoryMB),ProcessMB=avg(ProcessMB) by bin(TimeGenerated,{GRAIN})''')
chart("memory-breakdown", "SQL-manager free, database cache and other/internal memory (MiB)", f'''HvSqlMemory_CL | where {TIME}
| summarize FreeMB=avg(FreeMemoryMB),CacheMB=avg(CacheMemoryMB),OtherInternalMB=avg(StolenMemoryMB),NonFreeCommittedMB=avg(TotalMemoryMB-FreeMemoryMB) by bin(TimeGenerated,{GRAIN})''')
chart("query-grants", "Query workspace: peak granted and paired actual-use snapshot per time bucket (MiB)", f'''HvSqlMemory_CL | where {TIME}
| summarize arg_max(GrantAllocatedMB,GrantUsedMB) by bin(TimeGenerated,{GRAIN})
| project TimeGenerated,GrantedMB=GrantAllocatedMB,UsedMB=GrantUsedMB''')
chart("memory-evidence", "Memory stages and observed allocation/use", f'''HvSqlMemory_CL | where {TIME}
| summarize Samples=count(),CommittedMB=round(avg(TotalMemoryMB),1),CacheMB=round(avg(CacheMemoryMB),1),GrantedMB=round(max(GrantAllocatedMB),1),UsedMB=round(max(GrantUsedMB),1),MinOSAvailableMB=round(min(OsAvailableMB),1),MaxPendingGrants=max(PendingGrants) by Stage
| order by Stage asc''', "table")
chart("memory-headroom", "SQL guest OS headroom (MiB) and grant-pressure count", f'''HvSqlMemory_CL | where {TIME}
| summarize OSAvailableMB=avg(OsAvailableMB),PendingGrants=max(PendingGrants),GrantCount=max(GrantCount) by bin(TimeGenerated,{GRAIN})''')
note("storage-intro", "## Storage measurements by layer\nGuest volumes, Hyper-V virtual disks and host disks describe different layers. Do not add their IOPS together. Disk averages require meaningful I/O; a quiet zero-latency point does not prove storage is fast. Data and log VHDXs share the same host P20 backing disk, so they are separate logical volumes, not physically isolated storage.")
chart("host-storage-iops", "Host disks read/write IOPS", f'''Perf | where {TIME} and Computer == "HV-HOST-01"
| where ObjectName == "PhysicalDisk" and CounterName in ("Disk Reads/sec","Disk Writes/sec") and InstanceName != "_Total"
| extend Series=strcat(InstanceName," / ",CounterName)
| summarize IOPS=avg(CounterValue) by Series,bin(TimeGenerated,{GRAIN})''')
chart("host-storage-latency", "Host disks read/write latency (ms)", f'''Perf | where {TIME} and Computer == "HV-HOST-01"
| where ObjectName == "PhysicalDisk" and CounterName in ("Avg. Disk sec/Read","Avg. Disk sec/Write") and InstanceName != "_Total"
| extend Series=strcat(InstanceName," / ",CounterName)
| summarize LatencyMs=avg(CounterValue)*1000 by Series,bin(TimeGenerated,{GRAIN})''')
chart("vhdx-latency", "Hyper-V virtual disk latency (ms)", f'''Perf | where {TIME} and Computer == "HV-HOST-01"
| where ObjectName == "Hyper-V Virtual Storage Device" and CounterName == "Latency" and InstanceName endswith ".vhdx"
| summarize LatencyMs=avg(CounterValue)*1000 by InstanceName,bin(TimeGenerated,{GRAIN})''')
chart("vhdx-iops", "Hyper-V virtual disk read/write IOPS", f'''Perf | where {TIME} and Computer == "HV-HOST-01"
| where ObjectName == "Hyper-V Virtual Storage Device" and CounterName in ("Read Operations/Sec","Write Operations/Sec") and InstanceName endswith ".vhdx"
| extend Series=strcat(InstanceName," / ",CounterName)
| summarize IOPS=avg(CounterValue) by Series,bin(TimeGenerated,{GRAIN})''')
chart("windows-latency", "Windows guest volume latency (ms)", f'''Perf | where {TIME}
| where Computer != "HV-HOST-01" and ObjectName == "LogicalDisk" and CounterName == "Avg. Disk sec/Transfer" and InstanceName != "_Total"
| extend Volume=strcat(Computer," / ",InstanceName)
| summarize LatencyMs=avg(CounterValue)*1000 by Volume,bin(TimeGenerated,{GRAIN})''')
chart("windows-iops", "Windows guest volume IOPS", f'''Perf | where {TIME}
| where Computer != "HV-HOST-01" and ObjectName == "LogicalDisk" and CounterName == "Disk Transfers/sec" and InstanceName != "_Total"
| extend Volume=strcat(Computer," / ",InstanceName)
| summarize IOPS=avg(CounterValue) by Volume,bin(TimeGenerated,{GRAIN})''')
chart("sql-counters", "SQL memory counters independently collected by AMA", f'''Perf | where {TIME} and Computer == "SQL2019-GUEST"
| where ObjectName == "SQLServer:Memory Manager" and CounterName in ("Total Server Memory (KB)","Free Memory (KB)","Database Cache Memory (KB)","Stolen Server Memory (KB)")
| summarize MemoryMiB=avg(CounterValue)/1024 by CounterName,bin(TimeGenerated,{GRAIN})''')
database_path = f"{SUB}/resourceGroups/{GROUP}/providers/Microsoft.AzureArcData/SqlServerInstances/SQL2019-GUEST/databases?api-version=2023-09-01-preview"
database_query = {
    "version": "ARMEndpoint/1.0", "data": None, "headers": [], "method": "GET",
    "path": database_path, "urlParams": [], "batchDisabled": False,
    "transformers": [{"type": "jsonpath", "settings": {
        "tablePath": "$.value[*]", "columns": [
            {"path": "$.name", "columnid": "Database"},
            {"path": "$.properties.state", "columnid": "State"},
            {"path": "$.properties.sizeMB", "columnid": "SizeMB"},
            {"path": "$.properties.compatibilityLevel", "columnid": "Compatibility"},
        ],
    }}],
}
ITEMS.append({"type": 3, "name": "sql-databases", "content": {
    "version": "KqlItem/1.0", "title": "Live SQL database inventory (Arc ARM API)",
    "query": json.dumps(database_query), "size": 0, "queryType": 12, "visualization": "table",
}})
QUERIES["sql-databases"] = {"arm": True, "arg": False, "query": database_path}
chart("arc", "Arc inventory and region/cluster membership", f'''resources | where type =~ "microsoft.hybridcompute/machines" and resourceGroup =~ "{GROUP}"
| project Machine=name,Region=location,Status=tostring(properties.status),Cluster=tostring(tags.cluster),OS=tostring(properties.osSku)''', "table", True)
chart("heartbeat", "Reporting health - all six machines", f'''Heartbeat | where {TIME}
| summarize LastSeen=max(TimeGenerated),Samples=count() by Computer,OSType | order by Computer asc''', "table")
note("reporting", "Export individual result tables using their Export to Excel menu; chart data can be opened as a table. The custom memory table is in law-arc-monitor-lab. Change Tracking has a separate Southeast Asia workspace. SQL's native Arc performance dashboard supplements this workbook; it uses its own telemetry pipeline, not this Log Analytics table.")

# Optional extra panels from workbook-extra-panels.json are appended when that file exists.
extension_file = ROOT / "workbook-extra-panels.json"
if extension_file.exists():
    for panel in json.loads(extension_file.read_text(encoding="utf-8")):
        chart(panel["name"], panel["title"], panel["query"], panel.get("visual", "timechart"), panel.get("arg", False), panel.get("workspace", WS))
book = {"version": "Notebook/1.0", "items": ITEMS, "fallbackResourceIds": [WS],
        "$schema": "https://github.com/Microsoft/Application-Insights-Workbooks/blob/master/schema/workbook.json"}
(ROOT / "workbook-hyperv-estate-v2.2.json").write_text(json.dumps(book, indent=2), encoding="utf-8")
(ROOT / "workbook-queries.json").write_text(json.dumps(QUERIES, indent=2), encoding="utf-8")
resource = {"location": "<PRIMARY_REGION>", "kind": "shared", "properties": {
    "displayName": "Hyper-V and SQL Estate Report", "serializedData": json.dumps(book),
    "version": "1.0", "category": "workbook", "sourceId": "Azure Monitor",
}}
(ROOT / "workbook-resource.json").write_text(json.dumps(resource, indent=2), encoding="utf-8")
print(f"Workbook panels: {len(QUERIES)}; all resources filtered to {GROUP}.")
