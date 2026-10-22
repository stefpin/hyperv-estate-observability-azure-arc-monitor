"""Compile audited query templates; inject cutoffs at every physical Logs source."""

import copy
import json
import re
from pathlib import Path

from config.build_dashboards import render_query
from domain import ControlledError, SCOPE, SUB, WORKSPACES, canonical, parse_utc, sha

CONFIG = Path(__file__).resolve().parent / "config"
SOURCES = ("Heartbeat", "Perf", "HvSqlMemory_CL", "HvLinuxDisk_CL",
           "ConfigurationChange", "ConfigurationData")
SOURCE_PATTERN = re.compile(
    r"(?<![\w'\"])(?P<table>" + "|".join(SOURCES) + r")\s*\|\s*where\s+\$__timeFilter\(TimeGenerated\)")


def manifest():
    return json.loads((CONFIG / "query-manifest.json").read_text(encoding="utf-8-sig"))


def compile_query(template, job, freeze):
    parse_utc(freeze)
    matches = list(SOURCE_PATTERN.finditer(template))
    macros = template.count("$__timeFilter(TimeGenerated)")
    if not matches or len(matches) != macros:
        raise ControlledError("Unrecognized Logs source or time predicate")
    # Each known physical table token must be followed immediately by a time filter.
    physical = re.findall(r"(?<![\w'\"])(?:" + "|".join(SOURCES) + r")\s*\|", template)
    if len(physical) != len(matches):
        raise ControlledError("A Logs source has no bounded time predicate")
    start, end = job["sourceStartUtc"], job["sourceEndUtc"]
    bounded = SOURCE_PATTERN.sub(
        lambda m: f"{m['table']} | where TimeGenerated >= datetime({start}) "
        f"and TimeGenerated < datetime({end}) "
        f"and isnotnull(ingestion_time()) and ingestion_time() <= datetime({freeze})", template)
    return render_query(bounded, start, end, interval="5m")


def contracts(job, freeze):
    from health_rules import alert_contract
    output = []
    for source in manifest()["exportDatasets"]:
        item = {k: copy.deepcopy(source[k]) for k in
                ("id", "sheet", "service", "workspace", "workspaceGuids", "query", "subscriptions")}
        if item["service"] == "logs":
            if any(w not in WORKSPACES for w in item["workspace"]):
                raise ControlledError("Unapproved Logs workspace")
            if item["id"] in ("cpu", "memory"):
                changes = (
                    [("Value=avg(CounterValue),Samples=count()",
                      "Value=avg(CounterValue),Samples=count(),LastSampleUtc=max(TimeGenerated)")]
                    if item["id"] == "cpu" else [
                        ("summarize Available=avg(CounterValue) by",
                         "summarize Available=avg(CounterValue),LastSampleUtc=max(TimeGenerated) by"),
                        ("project TimeGenerated,Computer,UsedPercent=",
                         "project TimeGenerated,Computer,LastSampleUtc,UsedPercent="),
                        ("summarize UsedPercent=avg(CounterValue) by",
                         "summarize UsedPercent=avg(CounterValue),LastSampleUtc=max(TimeGenerated) by"),
                    ]
                )
                for old, new in changes:
                    if item["query"].count(old) != 1:
                        raise ControlledError("CPU/RAM query no longer matches the audited sample-timestamp transform")
                    item["query"] = item["query"].replace(old, new)
            if item["id"] == "sql-memory":
                item["query"] = item["query"].replace(
                    "PendingGrants=max(PendingGrants)",
                    "PendingGrants=max(PendingGrants),PendingGrantsMin=min(PendingGrants)")
            if item["id"] == "data-quality":
                item["query"] = item["query"].replace(
                    "Samples=count() by Computer,Stream",
                    "Samples=count(),ObservedBuckets=dcount(bin(TimeGenerated,5m)) by Computer,Stream")
                item["query"] = item["query"].replace(
                    "Latest,AgeMinutes,Samples,LastIngested",
                    "Latest,AgeMinutes,Samples,LastIngested,ObservedBuckets")
            item["query"] = compile_query(item["query"], job, freeze)
        elif item["service"] == "arg":
            if item["subscriptions"] != [SUB] or SUB not in item["query"] or SCOPE.split("/")[-1] not in item["query"]:
                raise ControlledError("ARG scope is not approved")
        else:
            raise ControlledError("Unsupported source service")
        item["querySha256"] = sha(item["query"].encode())
        output.append(item)
    output.append(alert_contract(job, freeze))
    return output


def parse_logs(payload):
    if not isinstance(payload, dict) or payload.get("error") or payload.get("partialError"):
        raise ControlledError("Logs query failed or returned partial errors")
    if any(payload.get(k) for k in ("@odata.nextLink", "nextLink", "$skipToken", "truncated")):
        raise ControlledError("Logs query returned incomplete data")
    tables = payload.get("tables")
    if not isinstance(tables, list) or len(tables) != 1 or tables[0].get("name") != "PrimaryResult":
        raise ControlledError("Logs statistics/status/truncation tables or missing PrimaryResult")
    table = tables[0]
    columns = table.get("columns", [])
    names = [c["name"] for c in columns]
    if len(set(names)) != len(names) or not names:
        raise ControlledError("Invalid Logs schema")
    result = []
    for row in table.get("rows", []):
        if len(row) != len(names):
            raise ControlledError("Logs row/schema mismatch")
        result.append(dict(zip(names, row)))
    if len(result) >= 500000 or len(canonical(payload)) >= 60 * 1024 * 1024:
        raise ControlledError("Logs result reached query service limits")
    return result


def parse_arg(payload):
    if payload.get("error") or payload.get("$skipToken") or str(payload.get("resultTruncated", False)).lower() == "true":
        raise ControlledError("ARG partial/truncated inventory; refusing incomplete report")
    data = payload.get("data")
    if not isinstance(data, list) or int(payload.get("totalRecords", len(data))) != len(data):
        raise ControlledError("ARG count/schema mismatch")
    return data
