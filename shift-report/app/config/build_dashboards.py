"""Build local, read-only Grafana classic dashboards and export/query contracts.

No SDK, network, subprocess, credentials, or source-file writes are used.
Reference builder: running it needs an exported source workbook (--input; that file is not part of this
repository) and it writes dashboard JSON next to this script. The runtime only imports render_query()
to bind the identical queries to a fixed export interval.
"""

import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import urllib.parse


HERE = Path(__file__).resolve().parent
SUB = "<SUBSCRIPTION_ID>"
RG = "rg-hyperv-arc-monitor-demo"
SCOPE = f"/subscriptions/{SUB}/resourceGroups/{RG}"
MAIN = SCOPE + "/providers/Microsoft.OperationalInsights/workspaces/law-arc-monitor-lab"
CT = SCOPE + "/providers/Microsoft.OperationalInsights/workspaces/law-arc-ct-sea"
WORKSPACES = {
    MAIN: "00000000-0000-0000-0000-000000000009",
    CT: "00000000-0000-0000-0000-000000000018",
}
MACHINES = (
    "HV-HOST-01", "RHEL94-GUEST", "SQL2019-GUEST",
    "WIN2019-GUEST", "WIN2022-GUEST", "WIN2025-GUEST-01",
)
MEMBERS = MACHINES[3:]
GUESTS = MACHINES[1:]
DS = {"type": "grafana-azure-monitor-datasource", "uid": "hv-azure-monitor"}
MAIN_UID = "hv-operations-cockpit"
REPORT_UID = "hv-operations-report"
SCHEMA_SOURCES = [
    "https://raw.githubusercontent.com/grafana/grafana/v11.6.0/public/app/plugins/datasource/azuremonitor/dataquery.gen.ts",
    "https://raw.githubusercontent.com/grafana/grafana/v12.1.0/public/app/plugins/datasource/azuremonitor/dataquery.gen.ts",
]


def qstr(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def enum(values):
    return ",".join(qstr(x) for x in values)


def scope_filter(machines=MACHINES, selected=False):
    # Custom tables may have an empty _ResourceId; their ARM workspace and exact
    # Computer allowlist still bound the query. A populated ID must match the RG.
    rid = "tolower(tostring(column_ifexists('_ResourceId','')))"
    result = (
        f"Computer in~ ({enum(machines)}) and "
        f"(isempty({rid}) or {rid} startswith {qstr(SCOPE.lower() + '/')})"
    )
    if selected:
        result += " and Computer in~ (${machine:singlequote})"
    return result


def source(table, machines=MACHINES, selected=False, workspace=None):
    name = f"workspace({qstr(workspace)}).{table}" if workspace else table
    return f"{name}\n| where $__timeFilter(TimeGenerated)\n| where {scope_filter(machines, selected)}"


def adapt_legacy(query, machines=MACHINES, selected=False):
    query = query.replace("TimeGenerated {TimeRange}",
                          "$__timeFilter(TimeGenerated) and " + scope_filter(machines, selected))
    query = query.replace("{TimeRange:grain}", "$__interval")
    if "{TimeRange" in query or "$__timeFilter" not in query:
        raise ValueError("Unsupported workbook time syntax")
    if "CPU Wait Time Per Dispatch" in query:
        pattern = r"(\| extend Guest=tostring\(split\(InstanceName,[\"']:[\"']\)\[0\]\))"
        query, count = re.subn(pattern, r"\1\n| where Guest in~ (" + enum(GUESTS) + ")", query)
        if count != 1:
            raise ValueError("Wait query guest scope could not be verified")
    return query


def render_query(query, start, end, interval="1m", machines=None, members=None):
    """Bind Grafana macros for a fixed, reproducible Logs/ARG export.

    No expression or free-form filter is accepted. The caller executes the
    returned KQL through its own read-only, scope-restricted query client.
    """
    def utc(value):
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Export timestamps require an explicit UTC offset")
        return parsed.astimezone(dt.timezone.utc)

    begin, finish = utc(start), utc(end)
    if finish <= begin:
        raise ValueError("Export end must be later than start")
    if not re.fullmatch(r"[1-9][0-9]*(?:ms|s|m|h|d)", interval):
        raise ValueError("Interval must be a positive fixed Kusto timespan")
    for name, requested, allowed in (
        ("machine", machines, MACHINES), ("member", members, MEMBERS),
    ):
        values = tuple(allowed if requested is None else requested)
        if not values or any(v not in allowed for v in values):
            raise ValueError(f"Invalid {name} enum")
        query = query.replace("${" + name + ":singlequote}", enum(values))
    from_literal = "datetime(" + begin.isoformat().replace("+00:00", "Z") + ")"
    to_literal = "datetime(" + finish.isoformat().replace("+00:00", "Z") + ")"
    query = re.sub(
        r"\$__timeFilter\((\w+)\)",
        lambda m: f"{m[1]} between ({from_literal} .. {to_literal})", query,
    )
    query = query.replace("$__timeFrom()", from_literal).replace("$__timeTo()", to_literal)
    query = query.replace("$__interval", interval)
    if "$__" in query or "${" in query:
        raise ValueError("Unresolved or unsupported Grafana macro")
    return query


def target(query, service="logs", resources=None, result_format="time_series"):
    base = {"refId": "A", "datasource": DS, "hide": False}
    if service == "arg":
        # In both Grafana 11 and 12 subscriptions is TOP-LEVEL, not a property
        # of AzureResourceGraphQuery. The latter only contains query/format.
        base.update({
            "queryType": "Azure Resource Graph", "subscriptions": [SUB],
            "azureResourceGraph": {"query": query, "resultFormat": "table"},
        })
    else:
        base.update({
            "queryType": "Azure Log Analytics",
            "azureLogAnalytics": {
                "query": query, "resultFormat": result_format,
                "resources": resources or [MAIN],
                "dashboardTime": True, "timeColumn": "TimeGenerated",
            },
        })
    return base


def colors(percent=False):
    return {
        "mode": "absolute",
        "steps": [
            {"color": "green", "value": None},
            {"color": "orange", "value": 75 if percent else 1},
            {"color": "red", "value": 90 if percent else 2},
        ],
    }


def panel(pid, title, query=None, kind="timeseries", unit="short",
          semantics="", service="logs", resources=None, fields=None):
    default = {
        "unit": unit, "noValue": "No data", "decimals": 1,
        "color": {"mode": "palette-classic"},
        "thresholds": colors(unit == "percent"),
        "mappings": [],
    }
    if unit == "percent":
        default.update({"min": 0, "max": 100})
    p = {
        "id": pid, "title": title, "type": kind, "transparent": False,
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
        "description": semantics, "fieldConfig": {"defaults": default, "overrides": []},
        "options": {}, "links": [],
    }
    if query is not None:
        fmt = "time_series" if kind in ("timeseries", "state-timeline") else "table"
        p.update({"datasource": DS, "targets": [target(query, service, resources, fmt)],
                  "maxDataPoints": 400, "interval": "1m"})
    if kind == "timeseries":
        default["custom"] = {
            "drawStyle": "line", "lineInterpolation": "linear",
            "lineWidth": 2, "fillOpacity": 10, "showPoints": "never",
            "spanNulls": False, "insertNulls": 180000,
            "stacking": {"mode": "none", "group": "A"},
            "axisPlacement": "auto", "scaleDistribution": {"type": "linear"},
            "hideFrom": {"legend": False, "tooltip": False, "viz": False},
        }
        p["options"] = {
            "legend": {"displayMode": "table", "placement": "bottom",
                       "calcs": ["lastNotNull", "max"], "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        }
    elif kind == "table":
        default["custom"] = {"align": "auto", "cellOptions": {"type": "auto"},
                             "inspect": False}
        p["options"] = {"showHeader": True, "cellHeight": "sm",
                        "footer": {"show": False, "reducer": ["sum"]}}
        default["unit"] = "none"
    elif kind == "bargauge":
        default["color"] = {"mode": "fixed", "fixedColor": "blue"}
        default["min"] = 0
        p["options"] = {
            "displayMode": "gradient", "orientation": "horizontal",
            "reduceOptions": {"values": True, "calcs": ["lastNotNull"], "fields": "/^P95Ns$/"},
            "showUnfilled": True, "valueMode": "color", "namePlacement": "auto",
        }
    elif kind == "stat":
        default["color"] = {"mode": "fixed", "fixedColor": "blue"}
        p["options"] = {
            "colorMode": "value", "graphMode": "none", "textMode": "auto",
            "orientation": "auto", "justifyMode": "auto",
            "reduceOptions": {"values": True, "calcs": ["lastNotNull"], "fields": ""},
        }
    elif kind == "state-timeline":
        default["color"] = {"mode": "thresholds"}
        default["thresholds"] = {
            "mode": "absolute", "steps": [
                {"color": "green", "value": None}, {"color": "#6D6F73", "value": 1},
            ],
        }
        default["mappings"] = [{
            "type": "value", "options": {
                "0": {"text": "Sample observed", "color": "green", "index": 0},
                "1": {"text": "No sample in bucket", "color": "#6D6F73", "index": 1},
            },
        }]
        p["options"] = {
            "mergeValues": True, "showValue": "never", "rowHeight": 0.8,
            "alignValue": "left", "legend": {"displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "single", "sort": "none"},
        }
    for field, config in (fields or {}).items():
        p["fieldConfig"]["overrides"].append({
            "matcher": {"id": "byName", "options": field},
            "properties": [{"id": key, "value": value} for key, value in config.items()],
        })
    return p


def text(pid, title, content):
    p = panel(pid, title, kind="text")
    p["options"] = {"mode": "markdown", "content": content}
    return p


def place(p, x, y, w=12, h=8):
    p["gridPos"] = {"x": x, "y": y, "w": w, "h": h}
    return p


def dashboard(uid, title, panels, workbook_id, report=False):
    pdf_spec = (
        '[{"dashboard":{"uid":"hv-operations-report"},'
        '"reportVariables":{"machine":${machine:json},"member":${member:json}},'
        '"timeRange":{"from":"${__from}","to":"${__to}"}}]'
    )
    pdf_parameter = urllib.parse.quote(pdf_spec, safe="")
    for macro in ("${machine:json}", "${member:json}", "${__from}", "${__to}"):
        pdf_parameter = pdf_parameter.replace(urllib.parse.quote(macro, safe=""), macro)
    pdf_link = {
        "title": "Download native PDF", "type": "link", "icon": "doc",
        "url": "/api/reports/render/pdfs?orientation=landscape&layout=simple&scaleFactor=100&dashboards=" + pdf_parameter,
        "targetBlank": True, "includeVars": False, "keepTime": False,
        "tooltip": "Native Grafana report; current filters and epoch-based fixed time. No email.",
    }
    def variable(name, values, label):
        return {
            "name": name, "label": label, "type": "custom", "hide": 0,
            "query": ",".join(values), "multi": True, "includeAll": True,
            "current": {"text": "All", "value": "$__all", "selected": True},
            "options": [{"text": "All", "value": "$__all", "selected": True}] + [
                {"text": v, "value": v, "selected": False} for v in values
            ], "skipUrlSync": False,
        }
    return {
        "id": None, "uid": uid, "title": title, "version": 1, "schemaVersion": 39,
        "description": "Read-only existing-data evidence. No guest, SQL, collection, alert or maintenance changes.",
        "tags": ["hyperv-estate", "existing-telemetry", "read-only", "evidence"],
        "timezone": "Etc/GMT-7", "style": "dark", "editable": False,
        "graphTooltip": 1, "fiscalYearStartMonth": 0, "liveNow": False,
        "refresh": "" if report else "2m",
        "time": {"from": "now-1h", "to": "now"},
        "timepicker": {"refresh_intervals": ["2m", "5m", "15m", "30m"],
                      "hidden": False},
        "templating": {"list": [
            variable("machine", MACHINES, "Selected machines · OS metrics only"),
            variable("member", MEMBERS, "Selected Windows members · detail only"),
        ]},
        "links": [
            pdf_link,
            {"title": "Operations cockpit" if report else "PDF & Excel evidence",
             "type": "link", "url": "/d/" + (MAIN_UID if report else REPORT_UID),
             "icon": "dashboard", "includeVars": True, "keepTime": True, "targetBlank": False},
            {"title": "Original Azure workbook", "type": "link",
             "url": "https://portal.azure.com/#resource" + workbook_id,
             "targetBlank": True, "includeVars": False, "keepTime": False},
            {"title": "Existing alert rules · unchanged", "type": "link",
             "url": "https://portal.azure.com/#view/Microsoft_Azure_Monitoring/AzureMonitoringBrowseBlade/~/alertsV2",
             "targetBlank": True, "includeVars": False, "keepTime": False},
        ],
        # No fabricated annotations and no implicit extra query fanout.
        "annotations": {"list": []}, "panels": panels,
    }


def legacy_items(document):
    data = document["serializedData"]
    data = json.loads(data) if isinstance(data, str) else data
    items = []
    def walk(children):
        for item in children:
            content = item.get("content", {})
            if isinstance(content, dict):
                if "query" in content:
                    items.append(item)
                walk(content.get("items", []))
    walk(data["items"])
    if len(items) != 31:
        raise ValueError(f"Expected exactly 31 source panels; received {len(items)}")
    return items


def heartbeat_query():
    return (
        "let expected=datatable(Computer:string)[" + enum(MACHINES) + "];\n"
        "let observed=" + source("Heartbeat") + "\n"
        "| extend Computer=toupper(Computer),Ingested=ingestion_time()\n"
        "| summarize arg_max(TimeGenerated,OSType,Ingested),Samples=count() by Computer\n"
        "| project Computer,LastSeen=TimeGenerated,Samples,OSType,LastIngested=Ingested;\n"
        "expected | join kind=leftouter observed on Computer\n"
        "| extend Samples=coalesce(Samples,0),"
        "AgeMinutes=round(datetime_diff('second',$__timeTo(),LastSeen)/60.0,1),"
        "IngestionLagSeconds=datetime_diff('second',LastIngested,LastSeen)\n"
        "| extend Reporting=case(isnull(LastSeen),'MISSING',AgeMinutes>5,'STALE','FRESH')\n"
        "| project Computer,Reporting,LastSeen,AgeMinutes,Samples,OSType,IngestionLagSeconds\n"
        "| order by Computer asc"
    )


def latency_query(layer):
    if layer == "host":
        obj, names = "PhysicalDisk", (
            "Avg. Disk sec/Read", "Avg. Disk sec/Write", "Disk Reads/sec", "Disk Writes/sec")
        return source("Perf", ("HV-HOST-01",)) + f"""
| where ObjectName == '{obj}' and InstanceName != '_Total'
| where CounterName in ({enum(names)})
| extend Direction=iff(CounterName contains 'Read','Read','Write')
| summarize L=avgif(CounterValue,CounterName startswith 'Avg.'),
    Ops=sumif(CounterValue,CounterName endswith '/sec')
    by InstanceName,Direction,bin(TimeGenerated,$__interval)
| project TimeGenerated,Series=strcat(InstanceName,' / ',Direction),
    LatencyMs=iff(Ops>0,L*1000,real(null))
| order by TimeGenerated asc"""
    if layer == "vhdx":
        return source("Perf", ("HV-HOST-01",)) + """
| where ObjectName == 'Hyper-V Virtual Storage Device' and InstanceName endswith '.vhdx'
| where CounterName in ('Latency','Read Operations/Sec','Write Operations/Sec')
| summarize L=avgif(CounterValue,CounterName=='Latency'),
    Ops=sumif(CounterValue,CounterName!='Latency')
    by InstanceName,bin(TimeGenerated,$__interval)
| project TimeGenerated,InstanceName,LatencyMs=iff(Ops>0,L*1000,real(null))
| order by TimeGenerated asc"""
    return source("Perf", MACHINES[2:], True) + """
| where ObjectName == 'LogicalDisk' and InstanceName != '_Total'
| where CounterName in ('Avg. Disk sec/Transfer','Disk Transfers/sec')
| summarize L=avgif(CounterValue,CounterName=='Avg. Disk sec/Transfer'),
    Ops=sumif(CounterValue,CounterName=='Disk Transfers/sec')
    by Computer,InstanceName,bin(TimeGenerated,$__interval)
| project TimeGenerated,Volume=strcat(Computer,' / ',InstanceName),
    LatencyMs=iff(Ops>0,L*1000,real(null))
| order by TimeGenerated asc"""


def storage_query():
    return source("Perf") + """
| where (Computer=='HV-HOST-01' and ObjectName in ('PhysicalDisk','Hyper-V Virtual Storage Device'))
    or (Computer!='HV-HOST-01' and ObjectName=='LogicalDisk')
| where InstanceName!='_Total'
| where ObjectName!='Hyper-V Virtual Storage Device' or InstanceName endswith '.vhdx'
| where CounterName in ('Disk Reads/sec','Disk Writes/sec','Disk Transfers/sec',
    'Avg. Disk sec/Read','Avg. Disk sec/Write','Avg. Disk sec/Transfer',
    'Read Operations/Sec','Write Operations/Sec','Latency')
| extend Layer=case(ObjectName=='PhysicalDisk','Host physical disk',
    ObjectName=='LogicalDisk','Windows guest volume','Hyper-V virtual disk')
| summarize ReadIOPS=avgif(CounterValue,CounterName in ('Disk Reads/sec','Read Operations/Sec')),
    WriteIOPS=avgif(CounterValue,CounterName in ('Disk Writes/sec','Write Operations/Sec')),
    TransferIOPS=avgif(CounterValue,CounterName=='Disk Transfers/sec'),
    ReadSeconds=avgif(CounterValue,CounterName=='Avg. Disk sec/Read'),
    WriteSeconds=avgif(CounterValue,CounterName=='Avg. Disk sec/Write'),
    TransferSeconds=avgif(CounterValue,CounterName in ('Avg. Disk sec/Transfer','Latency')),
    Latest=max(TimeGenerated),Samples=count() by Computer,Device=InstanceName,Layer
| extend TotalIOPS=iff(Layer=='Hyper-V virtual disk',ReadIOPS+WriteIOPS,TransferIOPS)
| project Computer,Layer,Device,ReadIOPS,WriteIOPS,TotalIOPS,
    ReadLatencyMs=iff(ReadIOPS>0 and isfinite(ReadSeconds),ReadSeconds*1000,real(null)),
    WriteLatencyMs=iff(WriteIOPS>0 and isfinite(WriteSeconds),WriteSeconds*1000,real(null)),
    TransferLatencyMs=iff(TotalIOPS>0 and isfinite(TransferSeconds),TransferSeconds*1000,real(null)),Latest,Samples
| union (
""" + source("HvLinuxDisk_CL", ("RHEL94-GUEST",)) + """
| where AccountingScope=='block-device'
| extend RO=ReadIOPS*IntervalSeconds,WO=WriteIOPS*IntervalSeconds
| summarize ReadIOPS=avg(ReadIOPS),WriteIOPS=avg(WriteIOPS),
    RO=sum(RO),WO=sum(WO),RW=sum(ReadAwaitMs*RO),WW=sum(WriteAwaitMs*WO),
    Latest=max(TimeGenerated),Samples=count() by Computer,Device
| project Computer,Layer='RHEL block device (aliases not additive)',Device,
    ReadIOPS,WriteIOPS,TotalIOPS=ReadIOPS+WriteIOPS,
    ReadLatencyMs=iff(RO>0,RW/RO,real(null)),
    WriteLatencyMs=iff(WO>0,WW/WO,real(null)),
    TransferLatencyMs=real(null),Latest,Samples)
| order by Layer asc,Computer asc,Device asc"""


def quality_query():
    expectations = [(m, "Heartbeat") for m in MACHINES]
    expectations += [(m, "Perf") for m in MACHINES]
    expectations += [("SQL2019-GUEST", "SQL memory"), ("RHEL94-GUEST", "Linux disk"),
                     ("SQL2019-GUEST", "CT service inventory")]
    rows = ",".join(qstr(m) + "," + qstr(t) for m, t in expectations)
    parts = []
    for table, label, machines, workspace in (
        ("Heartbeat", "Heartbeat", MACHINES, MAIN), ("Perf", "Perf", MACHINES, MAIN),
        ("HvSqlMemory_CL", "SQL memory", ("SQL2019-GUEST",), MAIN),
        ("HvLinuxDisk_CL", "Linux disk", ("RHEL94-GUEST",), MAIN),
        ("ConfigurationData", "CT service inventory", ("SQL2019-GUEST",), CT),
    ):
        q = source(table, machines, workspace=workspace)
        if table == "ConfigurationData":
            q += "\n| where SvcName in ('MSSQLSERVER','SQLSERVERAGENT','SqlServerExtension')"
        parts.append("(" + q + f"\n| extend Stream={qstr(label)}\n"
                     "| project Computer,Stream,TimeGenerated,Ingested=ingestion_time())")
    return (
        "let expected=datatable(Computer:string,Stream:string)[" + rows + "];\n"
        "let actual=union " + ",\n".join(parts) + "\n"
        "| summarize Latest=max(TimeGenerated),LastIngested=max(Ingested),Samples=count() by Computer,Stream;\n"
        "expected | join kind=leftouter actual on Computer,Stream\n"
        "| extend Samples=coalesce(Samples,0),AgeMinutes=round(datetime_diff('second',$__timeTo(),Latest)/60.0,1)\n"
        "| extend Quality=case(isnull(Latest),'MISSING',"
        "Stream=='CT service inventory','INVENTORY SNAPSHOT',AgeMinutes>5,'STALE','FRESH')\n"
        "| project Computer,Stream,Quality,Latest,AgeMinutes,Samples,LastIngested\n"
        "| order by Computer asc,Stream asc"
    )


def build(input_path, output):
    original = input_path.read_bytes()
    workbook = json.loads(original.decode("utf-8-sig"))
    items = legacy_items(workbook)
    by_name = {i["name"]: i for i in items}
    panels, specs = {}, {}
    table_names = {"wait-summary", "memory-evidence", "sql-databases", "arc", "heartbeat",
                   "rhel-device-detail", "ct-file-changes", "ct-sql-services",
                   "update-assessment", "update-history"}
    units = {
        "host-cpu": "percent", "wait": "ns", "wait-summary": "ns", "guest-cpu": "percent",
        "cluster-cpu": "percent", "cluster-memory": "percent",
        "memory-cap": "mbytes", "memory-breakdown": "mbytes", "query-grants": "mbytes",
        "memory-headroom": "mbytes", "sql-counters": "mbytes",
        "host-storage-iops": "iops", "host-storage-latency": "ms",
        "vhdx-iops": "iops", "vhdx-latency": "ms", "windows-iops": "iops",
        "windows-latency": "ms", "rhel-device-iops": "iops", "rhel-device-latency": "ms",
        "windows-guest-memory": "percent", "rhel-guest-memory": "percent",
        "cluster-contention": "ns",
    }
    scope_titles = {
        "host-cpu": "HOST · Hypervisor CPU",
        "wait": "HOST-SIDE · All five guests · Mean dispatch wait",
        "wait-summary": "HOST-SIDE · All five guests · Contention evidence",
        "guest-cpu": "SELECTED MACHINES · OS processor utilization",
        "cluster-cpu": "LOGICAL WINDOWS GROUP · CPU · All three equal members",
        "cluster-memory": "LOGICAL WINDOWS GROUP · Physical RAM in use · All three",
        "memory-cap": "SQL FIXED SCOPE · Ceiling, manager committed & process",
        "memory-breakdown": "SQL FIXED SCOPE · Manager memory components (overlap)",
        "query-grants": "SQL FIXED SCOPE · Peak grant & paired workspace use",
        "memory-evidence": "SQL FIXED SCOPE · Observed stages · Separate maxima",
        "memory-headroom": "SQL FIXED SCOPE · OS headroom & grant counts",
        "host-storage-iops": "HOST · Physical disk IOPS",
        "host-storage-latency": "HOST · Physical disk latency · Active I/O only",
        "vhdx-latency": "HOST-SIDE · All VHDX latency · Original ×1000 conversion",
        "vhdx-iops": "HOST-SIDE · All VHDX read/write IOPS",
        "windows-latency": "SELECTED WINDOWS GUESTS · Volume latency",
        "windows-iops": "SELECTED WINDOWS GUESTS · Volume IOPS",
        "sql-counters": "SQL FIXED SCOPE · Independent AMA memory counters",
        "sql-databases": "SQL · Asynchronous Arc database inventory · Not SQL query proof",
        "arc": "ALL SIX · Arc inventory, region & logical-group tags",
        "heartbeat": "ALL SIX EXPECTED · Reporting freshness at interval end",
        "rhel-device-iops": "RHEL FIXED SCOPE · Block-device IOPS · Do not sum aliases",
        "rhel-device-latency": "RHEL FIXED SCOPE · Operation-weighted disk latency",
        "rhel-device-detail": "RHEL FIXED SCOPE · Latest device / mount mapping",
        "windows-guest-memory": "SELECTED WINDOWS MACHINES · Physical RAM in use",
        "rhel-guest-memory": "SELECTED RHEL · Guest-reported used RAM",
        "cluster-contention": "LOGICAL WINDOWS GROUP · Host-side sampled dispatch wait",
        "ct-file-changes": "SQL · Existing file-change evidence · Southeast Asia",
        "ct-sql-services": "SQL · Latest existing service inventory · Southeast Asia",
        "update-assessment": "SQL · Existing missing-update inventory · No assessment initiated",
        "update-history": "SQL · Actual recorded installation history · No schedule claim",
    }
    arg_scope = f"subscriptionId == '{SUB}' and resourceGroup =~ '{RG}'"
    database_query = f"""Resources
| where {arg_scope} and type =~ 'microsoft.azurearcdata/sqlserverinstances/databases'
| where id contains '/sqlserverinstances/SQL2019-GUEST/'
| project Database=name,State=tostring(properties.state),SizeMB=todouble(properties.sizeMB),
    Compatibility=toint(properties.compatibilityLevel),
    InventoryUpdated=todatetime(properties.lastDatabaseUploadTime)
| order by Database asc"""
    freshness = heartbeat_query()
    freshness_fields = {
        "AgeMinutes": {"unit": "m", "decimals": 1},
        "Samples": {"unit": "short", "decimals": 0},
        "IngestionLagSeconds": {"unit": "s"},
        "Reporting": {
            "custom.cellOptions": {"type": "color-background"},
            "mappings": [{"type": "value", "options": {
                "FRESH": {"text": "FRESH", "color": "green", "index": 0},
                "STALE": {"text": "STALE", "color": "orange", "index": 1},
                "MISSING": {"text": "MISSING", "color": "red", "index": 2},
            }}],
        },
    }
    for idx, item in enumerate(items):
        name, content = item["name"], item["content"]
        service = "arg" if content["queryType"] in (1, 12) else "logs"
        resources = content.get("crossComponentResources", [MAIN]) if service == "logs" else []
        semantics = content["title"] + ". "
        fields = {}
        if service == "arg":
            query = database_query if name == "sql-databases" else content["query"]
            if name != "sql-databases":
                query = re.sub(r"^(\w+)\s*\|", r"\1 | where " + arg_scope + "\n|", query, count=1)
            if name == "arc":
                query += f"\n| where Machine in~ ({enum(MACHINES)}) | order by Machine asc"
            semantics += "Azure Resource Graph asynchronous inventory; not a live guest/SQL connection; not time-windowed."
        else:
            fixed = ("SQL2019-GUEST",) if name.startswith(("memory-", "query-", "sql-", "ct-")) else (
                ("RHEL94-GUEST",) if name.startswith("rhel-") else MACHINES)
            selected = name in ("guest-cpu", "windows-guest-memory", "rhel-guest-memory",
                                "windows-iops", "windows-latency")
            query = adapt_legacy(content["query"], fixed, selected)
            semantics += "Only existing records within the selected interval; gaps are not zero."
            if name == "heartbeat":
                query = freshness
                fields = freshness_fields
                semantics += " Expected six are LEFT JOINED to observations. Missing cannot be green. Age is relative to interval END, not proof of current availability."
            if name == "host-storage-latency":
                query = latency_query("host")
            elif name == "vhdx-latency":
                query = latency_query("vhdx")
                semantics += " Preserves workbook Latency ×1000; counter-source unit should be confirmed before changing this conversion."
            elif name == "windows-latency":
                query = latency_query("windows")
            if name == "query-grants":
                semantics += " arg_max selects GrantUsedMB from the SAME record as peak GrantAllocatedMB per bucket; independent maxima are not substituted."
            if name == "memory-evidence":
                semantics += " Per-stage GrantedMB and UsedMB are separate maxima and NOT paired; use the grant panel for paired snapshots. Stage is an ingested label, not fabricated workload timing."
            if name.startswith(("memory-", "query-")) or name == "sql-counters":
                semantics += " Legacy MB fields mean MiB (1024² bytes). Manager committed is not active-query use; process footprint overlaps manager allocations. Never stack or add these categories."
            if name.startswith("cluster-"):
                semantics += " Fixed logical comparison group WIN2019/WIN2022/WIN2025 only; equal baseline 4 vCPU/8 GiB, NOT WSFC. Missing members are not zero; inspect group coverage."
            if name == "memory-headroom":
                fields = {"PendingGrants": {"unit": "short", "custom.axisPlacement": "right"},
                          "GrantCount": {"unit": "short", "custom.axisPlacement": "right"}}
            if name == "rhel-device-detail":
                query = query.replace("| project Computer,Device,", "| project Latest=TimeGenerated,Computer,Device,")
                query = query.replace("ReadAwaitMs,WriteAwaitMs,",
                                      "ReadAwaitMs=iff(ReadIOPS>0,ReadAwaitMs,real(null)),"
                                      "WriteAwaitMs=iff(WriteIOPS>0,WriteAwaitMs,real(null)),")
                query += "\n| order by Computer asc,Device asc"
            table_fields = {
                "wait-summary": {f: {"unit": "ns"} for f in ("MeanNs", "P95Ns", "PeakNs")},
                "memory-evidence": {
                    **{f: {"unit": "mbytes"} for f in (
                        "CommittedMB", "CacheMB", "GrantedMB", "UsedMB", "MinOSAvailableMB")},
                    "Samples": {"unit": "short", "decimals": 0},
                    "MaxPendingGrants": {"unit": "short", "decimals": 0},
                },
                "rhel-device-detail": {
                    "ReadIOPS": {"unit": "iops"}, "WriteIOPS": {"unit": "iops"},
                    "ReadAwaitMs": {"unit": "ms"}, "WriteAwaitMs": {"unit": "ms"},
                    "AvgQueueDepth": {"unit": "short"}, "UtilizationPct": {"unit": "percent"},
                },
            }
            fields.update(table_fields.get(name, {}))
            if name not in table_names:
                query += "\n| order by TimeGenerated asc"
        p = panel(100 + idx, scope_titles[name], query,
                  "table" if name in table_names else "timeseries",
                  units.get(name, "none"), semantics, service, resources, fields)
        panels[name] = p
        specs[name] = {"legacyName": name, "legacyTitle": content["title"],
                       "legacyQueryType": content["queryType"],
                       "legacyQuerySha256": hashlib.sha256(content["query"].encode()).hexdigest()}

    def extra(name, pid, title, query, kind="timeseries", unit="short", semantics="",
              service="logs", resources=None, fields=None):
        panels[name] = panel(pid, title, query, kind, unit, semantics, service, resources, fields)
        return panels[name]

    host_memory = source("Perf", ("HV-HOST-01",)) + """
| where ObjectName=='Memory' and CounterName=='Available Bytes'
| summarize UsedPercent=100.0*(1-avg(CounterValue)/68719476736.0)
    by bin(TimeGenerated,$__interval)
| order by TimeGenerated asc"""
    extra("host-memory", 200, "HOST · Physical RAM in use · Baseline 64 GiB", host_memory,
          unit="percent", semantics="Available Bytes / fixed existing-workbook 64 GiB capacity. Physical RAM use, not committed memory. Host is unaffected by machine selection.")
    queue = source("Perf", selected=True) + """
| where ObjectName=='System' and CounterName=='Processor Queue Length'
| summarize Queue=avg(CounterValue),PeakQueue=max(CounterValue)
    by Computer,bin(TimeGenerated,$__interval)
| order by TimeGenerated asc"""
    extra("cpu-queue", 201, "SELECTED MACHINES · Processor queue · Sampled count",
          queue, unit="short", semantics="Existing System / Processor Queue Length. Sampled runnable queue, not CPU-ready %. No data means counter not ingested, not zero.")
    ranking = panels["wait-summary"]["targets"][0]["azureLogAnalytics"]["query"] + "\n| order by P95Ns desc"
    extra("wait-ranking", 202, "HOST-SIDE · All five guests · P95 sampled dispatch wait",
          ranking, "bargauge", "ns",
          "P95 across existing sampled virtual-processor counters over the interval. Nanoseconds per dispatch, NOT CPU-ready %, and not a transaction latency distribution.")
    network_bytes = source("Perf", selected=True) + """
| where ObjectName in ('Network Interface','Network Adapter','Network')
| where CounterName in ('Bytes Total/sec','Bytes Received/sec','Bytes Sent/sec')
| where InstanceName !in ('_Total','total')
| extend Series=strcat(Computer,' / ',InstanceName,' / ',CounterName)
| summarize BytesPerSecond=avg(CounterValue) by Series,bin(TimeGenerated,$__interval)
| order by TimeGenerated asc"""
    extra("network", 203, "SELECTED MACHINES · Existing interface byte counters", network_bytes,
          unit="Bps", semantics="Per-interface byte rates. Total and directional counters overlap; do not sum. Does not imply HTTP monitoring or external connectivity testing.")
    network_errors = source("Perf", selected=True) + """
| where ObjectName in ('Network Interface','Network Adapter','Network')
| where CounterName in ('Packets Outbound Errors','Packets Received Errors',
    'Packets Received Discarded','Packets Outbound Discarded')
| extend Series=strcat(Computer,' / ',InstanceName,' / ',CounterName)
| summarize ObservedCounter=avg(CounterValue) by Series,bin(TimeGenerated,$__interval)
| order by TimeGenerated asc"""
    extra("network-errors", 204, "SELECTED MACHINES · Existing interface errors / discards",
          network_errors, unit="short", semantics="Raw sampled packet error/discard counter values; not invented rates. A missing series is not a clean bill of health.")
    activity = source("Perf", ("SQL2019-GUEST",)) + """
| where (ObjectName=='SQLServer:SQL Statistics' and CounterName=='Batch Requests/sec')
    or (ObjectName=='SQLServer:General Statistics' and CounterName=='User Connections')
    or (ObjectName=='SQLServer:Buffer Manager' and CounterName=='Page life expectancy')
    or (ObjectName=='SQLServer:Memory Manager' and CounterName in
        ('Memory Grants Pending','Memory Grants Outstanding','Target Server Memory (KB)'))
| extend Unit=case(CounterName=='Batch Requests/sec','requests/s',
    CounterName=='Page life expectancy','seconds',
    CounterName=='Target Server Memory (KB)','MiB','count')
| extend Value=iff(CounterName=='Target Server Memory (KB)',CounterValue/1024.0,CounterValue)
| summarize Mean=avg(Value),Peak=max(Value),Latest=max(TimeGenerated),Samples=count()
    by Counter=CounterName,Unit
| order by Counter asc"""
    extra("sql-activity", 205, "SQL FIXED SCOPE · Batch, users, PLE & memory pressure",
          activity, "table", "none",
          "Only already-ingested Perf counters. PLE is seconds, not a universal health threshold. Missing counter rows mean no evidence. Target memory is not actual process use.")
    group_summary = source("Perf", MEMBERS) + """
| where (ObjectName=='Processor Information' and CounterName=='% Processor Time' and InstanceName=='_Total')
    or (ObjectName=='Memory' and CounterName=='Available Bytes')
| summarize MeanCPU=avgif(CounterValue,CounterName=='% Processor Time'),
    MeanAvailableBytes=avgif(CounterValue,CounterName=='Available Bytes'),
    CPURecords=countif(CounterName=='% Processor Time'),
    MemoryRecords=countif(CounterName=='Available Bytes'),Latest=max(TimeGenerated) by Computer
| extend PhysicalUsedPercent=100.0*(1-MeanAvailableBytes/8589934592.0),
    BaselineVCPU=4,BaselineRAMGiB=8
| project Computer,MeanCPU,PhysicalUsedPercent,BaselineVCPU,BaselineRAMGiB,CPURecords,MemoryRecords,Latest
| join kind=rightouter (datatable(ExpectedMember:string)[
""" + enum(MEMBERS) + """]) on $left.Computer==$right.ExpectedMember
| project Member=ExpectedMember,MeanCPU,PhysicalUsedPercent,
    BaselineVCPU=4,BaselineRAMGiB=8,CPURecords=coalesce(CPURecords,0),
    MemoryRecords=coalesce(MemoryRecords,0),Latest
| order by Member asc"""
    extra("group-summary", 206, "LOGICAL WINDOWS GROUP · Three expected members & coverage",
          group_summary, "table", "none",
          "Three equal baseline 4-vCPU/8-GiB Windows guests, NOT WSFC. Rows are expected-member metadata left/right joined to observations. Missing metrics remain null, not zero. Aggregates elsewhere average observed members.")
    member_cpu = source("Perf", MEMBERS) + """
| where Computer in~ (${member:singlequote})
| where ObjectName=='Processor Information' and CounterName=='% Processor Time' and InstanceName=='_Total'
| summarize CPU=avg(CounterValue) by Computer,bin(TimeGenerated,$__interval)
| order by TimeGenerated asc"""
    extra("member-cpu", 207, "SELECTED WINDOWS MEMBERS · CPU detail (not the fixed-group aggregate)",
          member_cpu, unit="percent", semantics="Member selector applies only here. Fixed all-three group comparisons and host-side all-guest counters are deliberately unaffected.")
    history = (
        "let expected=datatable(Computer:string)[" + enum(MACHINES) + "];\n"
        "let lower=bin($__timeFrom(),$__interval);\n"
        "let firstBucket=iff(lower<$__timeFrom(),lower+$__interval,lower);\n"
        "let buckets=range TimeGenerated from firstBucket "
        "to (bin($__timeTo(),$__interval)-$__interval) step $__interval;\n"
        "let observed=" + source("Heartbeat") + "\n"
        "| summarize Samples=count() by Computer,bin(TimeGenerated,$__interval);\n"
        "expected | extend key=1 | join kind=inner (buckets | extend key=1) on key\n"
        "| join kind=leftouter observed on Computer,TimeGenerated\n"
        "| project TimeGenerated,Computer,Observed=iff(isnull(Samples),1,0)\n"
        "| order by TimeGenerated asc"
    )
    extra("heartbeat-history", 208, "ALL SIX · Heartbeat sample coverage · Completed buckets",
          history, "state-timeline", "none",
          "Categorical observed/no-sample state per completed time bucket. Gray means no heartbeat sample, not a fabricated outage. Expected machine/bucket scaffold is metadata, not collected telemetry; final incomplete bucket excluded.")
    disk_inventory = f"""Resources
| where {arg_scope} and type =~ 'microsoft.compute/disks'
| project Disk=name,Region=location,SKU=tostring(sku.name),Tier=tostring(properties.tier),
    SizeGiB=toint(properties.diskSizeGB),ConfiguredIOPS=toint(properties.diskIOPSReadWrite),
    ConfiguredMBps=toint(properties.diskMBpsReadWrite)
| order by Disk asc"""
    extra("disk-inventory", 209, "HOST BACKING DISKS · ARG configuration · Not measured performance",
          disk_inventory, "table", service="arg",
          semantics="Read-only Resource Graph disk metadata. P10/P20, size and configured limits only appear if actually returned by ARG; no static SKU or live-status claims.")
    storage = storage_query()
    extra("storage-comparison", 210, "ALL LAYERS · Storage comparison · Never add layers or aliases",
          storage, "table", "none",
          "Host physical, Hyper-V virtual, Windows logical and RHEL block-device views are separate accounting layers. Zero or missing operation counts yield null latency. RHEL latency is operation weighted. Windows/host latency is sampled counter average ×1000, not operation weighted. VHDX conversion preserves workbook evidence.",
          fields={f: {"unit": "ms", "noValue": "N/A"} for f in ("ReadLatencyMs", "WriteLatencyMs", "TransferLatencyMs")})
    quality = quality_query()
    extra("data-quality", 211, "EXPECTED STREAMS · Age, gaps & inventory snapshots",
          quality, "table", "none",
          "Exact expected machine/stream matrix, left joined to actual records. Age is relative to selected interval end. CT inventory is asynchronous; no change events are expected on every interval. This query explicitly reads only the two existing RG workspaces.",
          resources=[MAIN, CT])
    windows_capacity, windows_memory = panels["windows-guest-memory"]["targets"][0]["azureLogAnalytics"]["query"].split(";", 1)
    memory_all = (
        windows_capacity + ";\n" + windows_memory.strip() + "\n"
        "| union (" + panels["rhel-guest-memory"]["targets"][0]["azureLogAnalytics"]["query"].replace(
            "by bin(TimeGenerated,$__interval)", "by Computer,bin(TimeGenerated,$__interval)") + ")\n"
        "| order by TimeGenerated asc"
    )
    extra("all-memory", 212, "SELECTED MACHINES · Physical RAM use · Windows / RHEL",
          memory_all, unit="percent",
          semantics="Windows Available Bytes divided by source-workbook configured capacity; Linux native % Used Memory. No committed-memory or process-memory stacking. Unknown capacity is not guessed.")
    capacities = (
        "let capacity=datatable(Computer:string,BaselineRAMGiB:real,BaselineVCPU:long)["
        "'HV-HOST-01',64.0,long(null),'SQL2019-GUEST',12.0,4,"
        "'WIN2019-GUEST',8.0,4,'WIN2022-GUEST',8.0,4,'WIN2025-GUEST-01',8.0,4,"
        "'RHEL94-GUEST',real(null),long(null)];\n"
        "let observed=" + source("Perf") + """
| where ObjectName=='Memory' and CounterName in ('Available Bytes','Available MBytes Memory','% Used Memory')
| summarize WindowsAvailableBytes=avgif(CounterValue,CounterName=='Available Bytes'),
    LinuxAvailableMiB=avgif(CounterValue,CounterName=='Available MBytes Memory'),
    LinuxUsedPercent=avgif(CounterValue,CounterName=='% Used Memory'),
    Latest=max(TimeGenerated) by Computer;
capacity | join kind=leftouter observed on Computer
| extend AvailableGiB=iff(isnotnull(WindowsAvailableBytes),WindowsAvailableBytes/1073741824.0,
    LinuxAvailableMiB/1024.0)
| project Computer,BaselineRAMGiB,BaselineVCPU,AvailableGiB,LinuxUsedPercent,Latest
| order by Computer asc"""
    )
    extra("capacity", 213, "ALL SIX · Configured capacity baseline vs observed available RAM",
          capacities, "table", "none",
          "Windows RAM capacities are the existing workbook's configured denominator; 4-vCPU values are confirmed SQL/Windows group baselines, not inferred from utilization. Host vCPU and RHEL capacity are deliberately null when not established. Latest is last memory sample within the interval.")
    management = (
        "(" + panels["ct-file-changes"]["targets"][0]["azureLogAnalytics"]["query"] +
        "\n| project TimeGenerated,Computer,Evidence='File change',"
        "Item=FileSystemPath,State=ConfigChangeType,Detail=tostring(FieldsChanged))\n"
        "| union (" + panels["ct-sql-services"]["targets"][0]["azureLogAnalytics"]["query"] +
        "\n| project TimeGenerated,Computer,Evidence='Service inventory',"
        "Item=SvcName,State=SvcState,Detail=SvcStartupType)\n| order by TimeGenerated desc"
    )
    extra("management", 214, "SQL · Existing changes & service evidence · Read-only",
          management, "table", "none",
          "Only already-ingested Southeast Asia ConfigurationChange/ConfigurationData. No changes, assessments, service commands or maintenance runs are initiated. Empty file-change rows do not prove an error.",
          resources=[CT])
    extra("reporting-counts", 215, "ALL SIX EXPECTED · Reporting counts at interval end",
          freshness + "\n| summarize Fresh=countif(Reporting=='FRESH'),"
          "Stale=countif(Reporting=='STALE'),Missing=countif(Reporting=='MISSING'),Expected=count()",
          "stat", "short", "Counts are derived from the six expected machine rows, not from an observed-only denominator. Freshness threshold is 5 minutes relative to interval end.",
          fields={
              "Fresh": {"color": {"mode": "thresholds"}, "thresholds": {
                  "mode": "absolute", "steps": [
                      {"color": "red", "value": None}, {"color": "orange", "value": 1},
                      {"color": "green", "value": 6},
                  ]}},
              "Stale": {"color": {"mode": "thresholds"}, "thresholds": {
                  "mode": "absolute", "steps": [
                      {"color": "green", "value": None}, {"color": "orange", "value": 1},
                  ]}},
              "Missing": {"color": {"mode": "thresholds"}, "thresholds": {
                  "mode": "absolute", "steps": [
                      {"color": "green", "value": None}, {"color": "red", "value": 1},
                  ]}},
          })
    cpu_export = source("Perf", selected=True) + """
| where (ObjectName=='Hyper-V Hypervisor Logical Processor' and Computer=='HV-HOST-01'
    and CounterName=='% Total Run Time' and InstanceName=='_Total')
    or (ObjectName in ('Processor Information','Processor') and CounterName=='% Processor Time'
    and InstanceName in ('_Total','total'))
    or (ObjectName=='System' and CounterName=='Processor Queue Length')
| extend Metric=case(ObjectName=='Hyper-V Hypervisor Logical Processor','Host hypervisor CPU',
    ObjectName=='System','Processor queue','OS CPU'),
    Unit=iff(ObjectName=='System','count','percent')
| summarize Value=avg(CounterValue),Samples=count()
    by Computer,Metric,Unit,bin(TimeGenerated,$__interval)
| order by TimeGenerated asc,Computer asc,Metric asc"""
    grant_export = source("HvSqlMemory_CL", ("SQL2019-GUEST",)) + """
| extend SnapshotAt=TimeGenerated
| summarize arg_max(GrantAllocatedMB,GrantUsedMB,SnapshotAt) by bin(TimeGenerated,$__interval)
| project TimeGenerated,SnapshotAt,GrantedMiB=GrantAllocatedMB,UsedMiB=GrantUsedMB
| order by TimeGenerated asc"""
    sql_memory_export = source("HvSqlMemory_CL", ("SQL2019-GUEST",)) + """
| summarize CapMiB=avg(MaxMemoryMB),CommittedMiB=avg(TotalMemoryMB),ProcessMiB=avg(ProcessMB),
    FreeMiB=avg(FreeMemoryMB),CacheMiB=avg(CacheMemoryMB),OtherInternalMiB=avg(StolenMemoryMB),
    NonFreeCommittedMiB=avg(TotalMemoryMB-FreeMemoryMB),OSAvailableMiB=avg(OsAvailableMB),
    PhysicalMiB=avg(PhysicalMB),PendingGrants=max(PendingGrants),Samples=count(),
    Latest=max(TimeGenerated) by bin(TimeGenerated,$__interval)
| order by TimeGenerated asc"""

    scope_note = (
        "### Existing telemetry · six machines · one isolated viewing layer\n"
        f"**{RG}** · the primary region host/guests; SQL Arc + Change Tracking inventory in Southeast Asia. "
        "**Read-only:** no guest commands, SQL connections, simulations, agents, DCRs, network, maintenance, "
        "alert edits or new collection. This is a demonstration lab, not an approved production architecture.\n\n"
        "**Trust the evidence:** gaps are not zero; freshness uses interval end; inventory is asynchronous. "
        "Machine selection affects only panels marked SELECTED. Host-side and all-three-group panels retain fixed scope. "
        "The Windows group is logical, **not WSFC**. SQL cap is taken from data, not a painted 9,829-MiB target."
    )
    group_storage = (
        "let volumeRates=" + source("Perf", MEMBERS) + """
| where ObjectName=='LogicalDisk' and InstanceName!='_Total'
    and CounterName=='Disk Transfers/sec'
| summarize IOPS=avg(CounterValue) by Computer,Volume=InstanceName,bin(TimeGenerated,$__interval);
let volumeLatency=""" + source("Perf", MEMBERS) + """
| where ObjectName=='LogicalDisk' and InstanceName!='_Total'
    and CounterName=='Avg. Disk sec/Transfer'
| summarize LatencyMs=avg(CounterValue)*1000 by Computer,Volume=InstanceName,bin(TimeGenerated,$__interval);
volumeRates | join kind=leftouter volumeLatency on Computer,Volume,TimeGenerated
| summarize ObservedIOPS=sum(IOPS),LatencyNumerator=sum(LatencyMs*IOPS),
    ObservedMembers=dcount(Computer),DistinctVolumes=count() by TimeGenerated
| extend GroupIOPS=iff(ObservedMembers==3,ObservedIOPS,real(null)),
    RateWeightedLatencyMs=iff(ObservedMembers==3 and ObservedIOPS>0,
        LatencyNumerator/ObservedIOPS,real(null)),ExpectedMembers=3
| project TimeGenerated,GroupIOPS,RateWeightedLatencyMs,ObservedMembers,ExpectedMembers,DistinctVolumes
| order by TimeGenerated asc"""
    )
    extra("group-storage", 240, "LOGICAL WINDOWS GROUP · Distinct guest-volume IOPS & sampled latency",
          group_storage, "table", semantics=(
              "Only logical guest volumes from the three Windows members; excludes _Total and all host/VHDX layers. "
              "GroupIOPS is suppressed when a member is missing. Latency is weighted by sampled volume IOPS, "
              "not a percentile of individual operations; idle group latency is null. Not a WSFC shared-storage view."),
          fields={"GroupIOPS": {"unit": "iops"}, "RateWeightedLatencyMs": {"unit": "ms"},
                  "ObservedMembers": {"unit": "short"}, "ExpectedMembers": {"unit": "short"}})
    main_panels = [
        place(text(1, "Operations evidence & safety boundary", scope_note), 0, 0, 24, 5),
        place(panels["reporting-counts"], 0, 5, 24, 4),
        place(panels["heartbeat"], 0, 9, 24, 7),
        place(panels["host-cpu"], 0, 16, 12, 8),
        place(panels["host-memory"], 12, 16, 12, 8),
    ]
    sections = [
        ("01  ESTATE & CAPACITY  |  selected OS metrics · fixed logical group", [
            "guest-cpu", "windows-guest-memory", "rhel-guest-memory", "capacity", "all-memory",
            "network", "network-errors", "cluster-cpu", "cluster-memory", "group-summary", "member-cpu"]),
        ("02  CPU CONTENTION  |  host-side nanoseconds, never CPU-ready %", [
            "wait-ranking", "wait", "wait-summary", "cpu-queue", "cluster-contention"]),
        ("03  SQL MEMORY & ACTIVITY  |  fixed SQL scope · MiB · no overlapping stacks", [
            "memory-cap", "memory-breakdown", "query-grants", "memory-headroom",
            "memory-evidence", "sql-counters", "sql-activity", "sql-databases"]),
        ("04  STORAGE LAYERS  |  physical ≠ virtual ≠ logical · idle latency is unknown", [
            "storage-comparison", "group-storage", "host-storage-iops", "host-storage-latency",
            "vhdx-iops", "vhdx-latency", "windows-iops", "windows-latency",
            "rhel-device-iops", "rhel-device-latency", "rhel-device-detail", "disk-inventory"]),
        ("05  ARC, MANAGEMENT & DATA QUALITY  |  actual existing records only", [
            "arc", "heartbeat-history", "data-quality", "ct-file-changes", "ct-sql-services", "management",
            "update-assessment", "update-history"]),
    ]
    y = 24
    for number, (title, names) in enumerate(sections):
        children = []
        if number == 2:
            children.append(place(text(20, "SQL memory interpretation",
                "**Ceiling ≠ committed ≠ process footprint ≠ executing-query use.** "
                "MiB means 1024² bytes. Retained cache/internal allocations overlap. "
                "Grant use is paired to the peak-granted record, not an independent maximum. "
                "No stacked area implies these categories can be added."), 0, y + 1, 24, 3))
        if number == 3:
            children.append(place(text(21, "Storage accounting boundary",
                "Host disks, VHDXs, guest volumes and Linux mapper aliases are **not additive**. "
                "SQL data/log VHDXs share the same backing data disk; logical separation is not physical isolation. "
                "Quiet directions have null latency; the existing Hyper-V latency ×1000 conversion is preserved."), 0, y + 1, 24, 3))
        child_y = y + 1 + (3 if children else 0)
        for pos, name in enumerate(names):
            children.append(place(panels[name], (pos % 2) * 12, child_y + (pos // 2) * 9, 12, 9))
        if number == 4:
            last_y = max(c["gridPos"]["y"] + c["gridPos"]["h"] for c in children)
            children.append(place(text(22, "Collection & alert boundary",
                "**RHEL HTTP:** local-only evidence; no cloud ingestion is enabled, so no HTTP chart is shown. "
                "**Alerts:** existing rules/action groups remain unchanged; use the portal link, not a fabricated feed. "
                "Resource Graph and Change Tracking are asynchronous inventories, not direct SQL or guest-state proof."), 0, last_y, 24, 4))
        main_panels.append({
            "id": 900 + number, "title": title, "type": "row", "collapsed": True,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": children,
        })
        y += 1
    main = dashboard(MAIN_UID, "Infrastructure & SQL Operations Cockpit",
                     main_panels, workbook["id"])

    report_names = [
        "reporting-counts", "heartbeat", "guest-cpu", "wait-ranking", "all-memory", "memory-cap", "query-grants",
        "storage-comparison", "group-summary", "group-storage", "sql-activity", "arc", "sql-databases",
        "management", "data-quality",
    ]
    report_panels = [place(text(1, "Fixed-window evidence report",
        "**Read-only existing telemetry · UTC+7 · no automatic refresh.** "
        "Capture one fixed UTC interval for this dashboard, PDF and XLSX. Report sheets retain exact KQL, units "
        "and scope from query-manifest.json. Tables are visual excerpts; Excel retains all exported rows. "
        "No source changes or new collection. "
        "**Inventory is asynchronous; missing ≠ healthy.** "
        "Physical memory is not SQL committed memory; dispatch wait is nanoseconds, not CPU-ready %. "
        "Storage layers and mapper aliases must not be summed."), 0, 0, 24, 4)]
    report_refs = {}
    ry = 4
    for pos, name in enumerate(report_names):
        p = copy.deepcopy(panels[name])
        p["id"] = 10 + pos
        if name == "guest-cpu":
            p["title"] = "CPU · Selected OS metrics plus fixed host hypervisor"
            extra_target = copy.deepcopy(panels["host-cpu"]["targets"][0])
            extra_target["refId"] = "B"
            p["targets"].append(extra_target)
            p["description"] += " Host hypervisor comparison remains fixed scope; no process CPU normalization is applied."
        height = 4 if name == "reporting-counts" else (
            7 if name in ("heartbeat", "storage-comparison", "data-quality") else 6)
        place(p, 0, ry, 24, height)
        report_panels.append(p)
        report_refs[name] = p["id"]
        ry += height
    report_panels.append(place(text(2, "Evidence limitations & unchanged controls",
        "**Logical Windows group:** three equal 4-vCPU/8-GiB members, not WSFC; missing members are explicit. "
        "**SQL:** cap/committed/process overlap and are not additive; query workspace use is paired to peak grants. "
        "**Management:** only existing file/service records; update inventory/history are exported separately. "
        "**RHEL HTTP:** not cloud-ingested; intentionally no HTTP chart. "
        "Existing alerts, collection, maintenance and networking are unchanged. "
        "No-data and stale samples must remain visible in PDF/Excel; successful rendering is not live-query validation."), 0, ry, 24, 4))
    report = dashboard(REPORT_UID, "PDF & Excel Evidence Report",
                       report_panels, workbook["id"], True)
    branding_path = output / "branding-panel.json"
    if branding_path.exists():
        branding_template = json.loads(branding_path.read_text(encoding="utf-8"))
        for document in (main, report):
            existing_ids = [p["id"] for p in flatten(document["panels"])]
            for p in flatten(document["panels"]):
                p["gridPos"]["y"] += 6
            branding_panel = copy.deepcopy(branding_template)
            branding_panel["id"] = max(existing_ids) + 1
            branding_panel["gridPos"] = {"x": 0, "y": 0, "w": 24, "h": 6}
            document["panels"].insert(0, branding_panel)

    datasets = []
    def dataset(key, sheet, name=None, query=None, service="logs", resources=None,
                unit="mixed", semantics=None):
        base = panels[name] if name else None
        if base:
            t = base["targets"][0]
            service = "arg" if t["queryType"] == "Azure Resource Graph" else "logs"
            model = t["azureResourceGraph"] if service == "arg" else t["azureLogAnalytics"]
            query = query or model["query"]
            resources = model.get("resources", [])
            semantics = semantics or base["description"]
        datasets.append({
            "id": key, "sheet": sheet, "service": service,
            "workspace": (resources or [MAIN]) if service == "logs" else [],
            "workspaceGuids": [WORKSPACES[r] for r in (resources or [MAIN])] if service == "logs" else [],
            "subscriptions": [SUB] if service == "arg" else [],
            "query": query, "resultFormat": "table", "unit": unit,
            "semantics": semantics, "mainPanelId": base["id"] if base else None,
            "reportPanelId": report_refs.get(name), "target": target(query, service, resources, "table"),
        })

    dataset("summary", "Summary", "heartbeat", unit="minutes/count")
    dataset("inventory", "Inventory", "arc", unit="inventory")
    dataset("sql-databases", "SQL Databases", "sql-databases", unit="source MB")
    dataset("cpu", "CPU", "guest-cpu", query=cpu_export, unit="percent/count",
            semantics="OS CPU, fixed-scope host hypervisor CPU and sampled processor queue as separate metrics. Counter names, units and sample counts retained; no process-CPU/CPU-ready conversion.")
    dataset("contention", "Contention", "wait-summary", unit="ns")
    dataset("memory", "Memory", "all-memory", unit="percent")
    dataset("sql-memory", "SQL Memory", "memory-cap", query=sql_memory_export, unit="MiB/count",
            semantics="Ceiling, manager committed, process, free/cache/internal and nonfree fields are overlapping, not additive. All legacy MB fields interpreted as MiB. Dynamic ceiling comes from the same existing records.")
    dataset("sql-grants", "SQL Grants", "query-grants", query=grant_export, unit="MiB",
            semantics="Peak GrantAllocatedMB per bucket; GrantUsedMB and SnapshotAt are from that exact record. NOT independently maximized use.")
    dataset("storage", "Storage", "storage-comparison", unit="IOPS/ms")
    dataset("cluster", "Logical Group", "group-summary", unit="percent/vCPU/GiB")
    dataset("cluster-storage", "Group Storage", "group-storage", unit="IOPS/ms")
    dataset("sql-activity", "SQL Activity", "sql-activity", unit="per-row Unit")
    dataset("management", "Management", "management", unit="existing inventory/events")
    dataset("update-assessment", "Update Assessment", "update-assessment", unit="inventory")
    dataset("update-history", "Update History", "update-history", unit="inventory/count")
    dataset("data-quality", "Data Quality", "data-quality", unit="minutes/count")

    panel_queries = []
    for d in (main, report):
        for p in flatten(d["panels"]):
            for t in p.get("targets", []):
                service = "arg" if t["queryType"] == "Azure Resource Graph" else "logs"
                model = t["azureResourceGraph"] if service == "arg" else t["azureLogAnalytics"]
                panel_queries.append({
                    "dashboardUid": d["uid"], "panelId": p["id"], "title": p["title"],
                    "refId": t["refId"], "service": service,
                    "workspace": model.get("resources", []),
                    "workspaceGuids": [WORKSPACES[r] for r in model.get("resources", [])],
                    "subscriptions": t.get("subscriptions", []), "query": model["query"],
                    "resultFormat": model["resultFormat"], "unit": p["fieldConfig"]["defaults"]["unit"],
                    "fieldUnits": {ov["matcher"]["options"]: {
                        prop["id"]: prop["value"] for prop in ov["properties"]
                        if prop["id"] in ("unit", "decimals")
                    } for ov in p["fieldConfig"]["overrides"]},
                    "semantics": p["description"],
                    "reportSheets": [ds["sheet"] for ds in datasets
                                     if ds["mainPanelId"] == p["id"] and d["uid"] == MAIN_UID
                                     or ds["reportPanelId"] == p["id"] and d["uid"] == REPORT_UID],
                    "target": t,
                })
    manifest = {
        "schemaVersion": 1, "datasource": DS, "resourceGroupArmId": SCOPE,
        "timezone": "Etc/GMT-7", "defaultTime": {"from": "now-1h", "to": "now"},
        "safety": {"readOnly": True, "collectionChanges": False, "guestCommands": False,
                   "directSqlConnections": False, "alertChanges": False},
        "pluginSchema": {
            "verifiedPublicSources": SCHEMA_SOURCES,
            "logs": "azureLogAnalytics.resources is an array of workspace ARM IDs; resultFormat is time_series or table.",
            "arg": "subscriptions belongs to the TOP-LEVEL target in Grafana 11/12, NOT inside azureResourceGraph.",
        },
        "binding": {
            "helper": "build_dashboards.render_query(query,start,end,interval,machines,members)",
            "timestamps": "ISO 8601 with explicit offset, normalized to UTC; caller pins same interval for PDF/XLSX.",
            "interval": "Positive fixed Kusto duration, normally 1m. Use same value for dashboard/export parity.",
            "machineEnum": list(MACHINES), "memberEnum": list(MEMBERS),
            "grafanaInterpolation": "${machine:singlequote} / ${member:singlequote}; custom enums, no free-form KQL.",
            "inventoryTime": "ARG inventories are asynchronous current indexed snapshots and intentionally not event-time-filtered.",
            "nulls": "Keep null as blank/no-data, never coerce missing telemetry or idle latency to 0.",
            "excel": "Write genuine XLSX using exact dataset rows, separate sheets, retain UTC timestamps and units; do not rename CSV to xlsx.",
            "pagination": "Caller must follow Azure Logs truncation/partial-error and ARG pagination indicators before claiming completeness.",
        },
        "panels": panel_queries, "exportDatasets": datasets,
        "reportSourcePanels": len(report_names), "reportSourceTargets": sum(len(p.get("targets", [])) for p in report_panels),
        "reportSheetMapping": {ds["sheet"]: {
            "datasetId": ds["id"], "mainPanelId": ds["mainPanelId"], "reportPanelId": ds["reportPanelId"],
        } for ds in datasets},
        "unverifiedLive": [
            "No Azure Logs/ARG queries were executed by the local builder.",
            "Grafana rendering, MI permissions, table existence and actual counter availability require validation in your environment.",
            "Hyper-V Virtual Storage Device Latency ×1000 is preserved from workbook; verify source units independently.",
            "Custom records with empty _ResourceId are accepted only in the named RG workspace and exact machine allowlist.",
        ],
    }
    parity = {
        "sourceWorkbookId": workbook["id"],
        "sourceFile": str(input_path), "sourceSha256": hashlib.sha256(original).hexdigest(),
        "sourcePanelCount": len(items), "sourceTypes": {"Logs": 27, "ARG": 3, "ARM": 1},
        "dashboardUid": MAIN_UID,
        "mappings": [
            {**specs[name], "newPanelId": panels[name]["id"], "newTitle": panels[name]["title"],
             "newService": "arg" if panels[name]["targets"][0]["queryType"] == "Azure Resource Graph" else "logs",
             "equivalence": (
                 "Confirmed database Resource Graph representation; asynchronous inventory, not direct SQL proof."
                 if name == "sql-databases" else
                 "Expected six LEFT JOIN observations; missing machines now explicit."
                 if name == "heartbeat" else
                 "Original conversion/aggregation retained; latency is null when paired operations are absent or zero."
                 if name in ("host-storage-latency", "vhdx-latency", "windows-latency") else
                 "Original query semantics retained with explicit RG/workspace/machine scope, Grafana time macros and honest labels."
             )}
            for name in specs
        ],
    }
    validation = validate(main, report, manifest, parity, items)
    if input_path.read_bytes() != original:
        raise RuntimeError("Source workbook unexpectedly changed")
    output.mkdir(parents=True, exist_ok=True)
    for filename, value in (
        ("main-dashboard.json", main), ("report-dashboard.json", report),
        ("query-manifest.json", manifest), ("parity-map.json", parity),
        ("validation.json", validation),
    ):
        (output / filename).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                                       encoding="utf-8")
    return validation


def flatten(panels):
    for p in panels:
        yield p
        yield from flatten(p.get("panels", []))


def validate(main, report, manifest, parity, items):
    counts = {}
    for dashboard_doc in (main, report):
        all_panels = list(flatten(dashboard_doc["panels"]))
        ids = [p["id"] for p in all_panels]
        assert len(ids) == len(set(ids)), "Panel IDs must be unique"
        def grid(children):
            for idx, p in enumerate(children):
                r = p["gridPos"]
                assert 0 <= r["x"] and r["x"] + r["w"] <= 24 and r["h"] > 0
                for other in children[idx + 1:]:
                    s = other["gridPos"]
                    overlap = (r["x"] < s["x"] + s["w"] and s["x"] < r["x"] + r["w"]
                               and r["y"] < s["y"] + s["h"] and s["y"] < r["y"] + r["h"])
                    assert not overlap, f"Overlapping sibling panels {p['id']} / {other['id']}"
                grid(p.get("panels", []))
        grid(dashboard_doc["panels"])
        json.loads(json.dumps(dashboard_doc, allow_nan=False))
        counts[dashboard_doc["uid"]] = len(all_panels)
    assert {i["name"] for i in items} == {m["legacyName"] for m in parity["mappings"]}
    assert len(parity["mappings"]) == 31
    initial = sum(len(p.get("targets", [])) for p in main["panels"] if p["type"] != "row")
    assert initial < 10
    assert 10 <= manifest["reportSourcePanels"] <= 15
    assert len(report["panels"]) < 20
    assert 10 <= len(manifest["exportDatasets"]) <= 16
    for entry in manifest["panels"] + manifest["exportDatasets"]:
        query, service = entry["query"], entry["service"]
        assert RG.lower() in query.lower()
        assert "{TimeRange" not in query
        assert not re.search(r"\(\s*let\s", query), "let statements cannot be inside table parentheses"
        if service == "logs":
            assert "$__timeFilter(TimeGenerated)" in query
            assert "Computer in~ (" in query
            assert all(r in WORKSPACES for r in entry["workspace"])
            assert entry["resultFormat"] in ("table", "time_series")
        else:
            assert SUB in query and "resourceGroup =~" in query
            assert entry["target"]["subscriptions"] == [SUB]
            assert "subscriptions" not in entry["target"]["azureResourceGraph"]
        resolved = render_query(query, "2026-07-24T14:00:00Z", "2026-07-24T15:00:00Z")
        assert "$__" not in resolved and "${" not in resolved and "{TimeRange" not in resolved
        for subscription in re.findall(r"/subscriptions/([^/'\"\s]+)", query, re.I):
            assert subscription == SUB
        for group in re.findall(r"/resourcegroups/([^/'\"\s]+)", query, re.I):
            assert group.lower() == RG.lower()
    return {
        "status": "LOCAL_STRUCTURE_VALIDATED_LIVE_QUERIES_NOT_RUN",
        "legacyPanelsMapped": 31, "dashboardPanelCountsIncludingRowsAndText": counts,
        "initialMainQueryFanout": initial, "collapsedDetailRows": 5,
        "reportSourcePanels": manifest["reportSourcePanels"],
        "reportSourceTargets": manifest["reportSourceTargets"],
        "reportTotalPanels": len(report["panels"]), "exportDatasets": len(manifest["exportDatasets"]),
        "panelQueryDefinitions": len(manifest["panels"]),
        "checks": ["JSON parses, finite numbers only", "31/31 legacy coverage",
                   "unique panel IDs", "non-overlapping sibling grids, including collapsed-row children",
                   "all query resource scopes restricted to supplied RG",
                   "all Logs sources explicit time and machine scope",
                   "fixed-time rendering resolves every query", "source workbook unchanged"],
        "schemaCorrection": "ARG subscriptions is top-level in Grafana 11/12.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE.parent / "workbook-before.json")
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    # All generated outputs stay in the directory owned by this builder.
    if args.output.resolve() != HERE:
        parser.error("--output must be the owned dashboard-build directory")
    print(json.dumps(build(args.input.resolve(), args.output.resolve()), indent=2))
