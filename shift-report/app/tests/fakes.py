import contextlib
import copy
import datetime as dt
import json
import threading
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

import fitz

from domain import (Conflict, MACHINES, Settings, UTC, assess, canonical, new_job, stamp)
from queries import contracts
from health_rules import policy

NOW = dt.datetime(2026, 7, 25, 6, 55, tzinfo=UTC)


class OfflineCase(TestCase):
    def setUp(self):
        super().setUp()
        self.network = patch("requests.sessions.Session.request",
                             side_effect=AssertionError("Unit tests must not use network"))
        self.network.start()
        self.addCleanup(self.network.stop)


def settings(kind="producer", **kwargs):
    return replace(Settings(kind, "hvprivatereport", "sender@example.com",
                            "https://test.communication.azure.com", ("operator@example.com",),
                            False, False), **kwargs)


def job():
    return new_job("scheduled", NOW, "2026-07-25T07:00:00Z")


def datasets(j=None):
    j = j or job()
    result = {c["id"]: [] for c in contracts(j, stamp(NOW))}
    pairs = [(m, s) for m in MACHINES for s in ("Heartbeat", "Perf")]
    pairs += [("SQL2019-GUEST", "SQL memory"), ("RHEL94-GUEST", "Linux disk")]
    result["data-quality"] = [{"Computer": m, "Stream": s, "Quality": "FRESH",
                               "Latest": stamp(NOW - dt.timedelta(minutes=1)),
                               "LastIngested": stamp(NOW), "Samples": 475, "ObservedBuckets": 95} for m, s in pairs]
    result["summary"] = [{"Computer": m, "Reporting": "FRESH", "Samples": 475,
                           "LastSeen": stamp(NOW - dt.timedelta(minutes=1)), "AgeMinutes": 1} for m in MACHINES]
    start = dt.datetime.fromisoformat(j["sourceStartUtc"].replace("Z", "+00:00"))
    for i in range(95):
        t = stamp(start + dt.timedelta(minutes=5 * i))
        for machine in MACHINES:
            result["cpu"].append({"TimeGenerated": t, "Computer": machine,
                                   "Metric": "Host hypervisor CPU" if machine == "HV-HOST-01" else "OS CPU",
                                   "Unit": "percent", "Value": 20., "Samples": 5})
            result["memory"].append({"TimeGenerated": t, "Computer": machine, "UsedPercent": 50.})
        result["sql-memory"].append({"TimeGenerated": t, "CapMiB": 9829., "CommittedMiB": 3000.,
                                      "ProcessMiB": 3500., "CacheMiB": 1800., "FreeMiB": 800.,
                                      "PendingGrants": 0, "PendingGrantsMin": 0, "Samples": 5})
        result["sql-grants"].append({"TimeGenerated": t, "GrantedMiB": 30., "UsedMiB": 12.})
        result["cluster-storage"].append({"TimeGenerated": t, "GroupIOPS": 10.,
                                           "ObservedMembers": 3, "ExpectedMembers": 3,
                                           "RateWeightedLatencyMs": 4.})
    result["contention"] = [{"Guest": m, "P95Ns": 100., "MeanNs": 80., "PeakNs": 200.}
                            for m in MACHINES[1:]]
    result["storage"] = [{"Computer": m, "Layer": "Host physical disk" if i == 0 else "Guest",
                           "Device": "Disk0", "TotalIOPS": 0., "ReadLatencyMs": None,
                           "TransferLatencyMs": None, "Latest": stamp(NOW - dt.timedelta(minutes=1))}
                          for i, m in enumerate(MACHINES)]
    result["sql-activity"] = [{"Counter": "User Connections", "Unit": "count", "Mean": 4., "Peak": 50.,
                               "Latest": stamp(NOW - dt.timedelta(minutes=1))}]
    result["inventory"] = [{"Machine": m, "Status": "Connected"} for m in MACHINES]
    result["management"] = [{"Item": "=HYPERLINK(\"https://evil\",\"click\")", "State": "+cmd",
                              "Detail": "@SUM(1,1)", "TimeGenerated": stamp(NOW - dt.timedelta(minutes=1))}]
    result["alert-health"] = [
        {"RuleName": r["name"], "Severity": r["severity"], "WindowMinutes": r["windowMinutes"],
         "Threshold": r["threshold"], "Operator": r["operator"], "Evaluated": True,
         "Triggered": False, "Observed": True, "Value": 0}
        for r in policy()["rules"]
    ]
    return result


def evidence(j=None):
    j = j or job()
    data = datasets(j)
    return {"job": j, "freezeAtUtc": stamp(NOW), "datasets": data, "health": assess(data, j)}


def native_pdf(count=8, text="Native Grafana frozen chart"):
    doc = fitz.open()
    for i in range(count):
        page = doc.new_page(width=842, height=595)
        page.insert_text((30, 30), f"{text} {i+1}")
    data = doc.tobytes()
    doc.close()
    return data


class Store:
    def __init__(self):
        self.data = {}
        self.serial = 0
        self.lock = threading.RLock()
        self.render_lock = threading.Lock()
        self.creates = []

    def get(self, container, name):
        with self.lock:
            data, etag = self.data.get((container, name), (None, None))
            return data, etag

    def get_json(self, container, name):
        data, etag = self.get(container, name)
        return (json.loads(data), etag) if data is not None else (None, None)

    def create(self, container, name, data, content_type="application/json"):
        with self.lock:
            if (container, name) in self.data:
                raise Conflict("Already exists")
            self.serial += 1
            self.data[container, name] = (data, str(self.serial))
            self.creates.append((container, name))
            return str(self.serial)

    def create_json(self, container, name, value):
        return self.create(container, name, canonical(value))

    def replace_json(self, container, name, value, etag):
        with self.lock:
            if self.data.get((container, name), (None, None))[1] != etag:
                raise Conflict("Concurrent ledger update")
            self.serial += 1
            self.data[container, name] = (canonical(value), str(self.serial))
            return str(self.serial)

    @contextlib.contextmanager
    def rendering_lease(self):
        with self.render_lock:
            yield lambda: None


class Queue:
    def __init__(self):
        self.messages = []
        self.fail = False

    def enqueue(self, j):
        if self.fail:
            raise TimeoutError("private token should not leak")
        self.messages.append(copy.deepcopy(j))


class Sources:
    def __init__(self, j=None):
        self.data = datasets(j)
        self.calls = []
        self.fail = None
        self.rendered = 0

    def collect(self, contract, j):
        self.calls.append(contract["id"])
        if self.fail == contract["id"]:
            raise RuntimeError("raw service response containing credential")
        return copy.deepcopy(self.data[contract["id"]])

    def render(self, dashboard, j):
        self.rendered += 1
        return native_pdf()

    def preflight(self):
        return None


class Mailer:
    def __init__(self):
        self.calls = []
        self.fail = False
        self.lock = threading.Lock()

    def submit(self, envelope, blobs, request_id, first_sent):
        with self.lock:
            self.calls.append((envelope, blobs, request_id, first_sent))
        if self.fail:
            raise TimeoutError("ambiguous")
        return {"operationId": request_id, "acsStatus": "Succeeded",
                "submissionMeaning": "ACS accepted submission; NOT Delivered or inbox proof"}
