"""Evaluate the original demo alert queries at the report's frozen source cutoff."""

import datetime as dt
import json
import re
from pathlib import Path

from domain import ControlledError, MACHINES, SCOPE, WORKSPACES, parse_utc, sha, stamp


def policy():
    return json.loads((Path(__file__).parent / "config" / "alert-rules.json").read_text("utf-8"))


def alert_contract(job, freeze):
    config = policy()
    functions, branches, expected = [], [], []
    distinct = {}
    for rule in config["rules"]:
        source_key = (rule["query"], rule["windowMinutes"])
        if source_key not in distinct:
            number = len(distinct)
            distinct[source_key] = number
            start = stamp(parse_utc(job["sourceEndUtc"]) - dt.timedelta(minutes=rule["windowMinutes"]))
            end = job["sourceEndUtc"]
            tables = re.compile(r"\b(Perf|Heartbeat|HvSqlMemory_CL)\s*\|")
            count = len(tables.findall(rule["query"]))
            if count < 1:
                raise ControlledError("Unknown health-rule source.")
            bounded = tables.sub(
                lambda match: "(" + match[1] + " | where TimeGenerated >= datetime(" + start
                + ") and TimeGenerated < datetime(" + end + ") "
                + "and isnotnull(ingestion_time()) and ingestion_time() <= datetime(" + freeze + ") "
                + "and Computer in~ (" + ",".join(json.dumps(m) for m in MACHINES) + ")) |",
                rule["query"],
            ).replace("now()", "datetime(" + end + ")")
            functions.append(f"let fn{number}=(){{{bounded}}};\nlet data{number}=materialize(fn{number}());")
        number = distinct[source_key]
        branches.append(f"(data{number} | extend Value=todouble(Value),RuleName={json.dumps(rule['name'])})")
        expected.append(",".join((
            json.dumps(rule["name"]), str(rule["severity"]), str(rule["windowMinutes"]),
            str(float(rule["threshold"])), json.dumps(rule["operator"]),
        )))
    query = "\n".join(functions) + "\nlet observed=union " + ",\n".join(branches) + ";\n"
    query += (
        "datatable(RuleName:string,Severity:long,WindowMinutes:long,Threshold:real,Operator:string)[\n"
        + ",\n".join(expected) + "\n]\n"
        "| join kind=leftouter observed on RuleName\n"
        "| extend Evaluated=true,Observed=isnotnull(Value),"
        "Triggered=case(Operator=='GreaterThan',Value>Threshold,Operator=='LessThan',Value<Threshold,false)\n"
        "| extend Triggered=coalesce(Triggered,false),PolicySha256=" + json.dumps(config["sha256"])
        + ",ObservedAtUtc=datetime(" + job["sourceEndUtc"] + ")\n"
        "| project-away RuleName1\n| order by RuleName asc"
    )
    return {
        "id": "alert-health", "sheet": "Alert Health", "service": "logs",
        "workspace": [next(iter(WORKSPACES))], "workspaceGuids": [next(iter(WORKSPACES.values()))],
        "subscriptions": [], "query": query, "querySha256": sha(query.encode()),
    }
