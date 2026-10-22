"""Managed identity service adapters with explicit scope and mutation boundaries."""

import base64
import contextlib
from email.utils import format_datetime
import json
import logging
import os
import threading
import time
from urllib.parse import urlencode, urlparse

import requests

from domain import (Conflict, ControlledError, DASHBOARD_UID, DATASOURCE_UID, FOLDER_UID, QUEUE,
                    SCOPE, SUB, WORKSPACES, canonical, parse_utc, utcnow)
from queries import parse_arg, parse_logs

LOGS_AUDIENCE = "https://api.loganalytics.io/.default"
ARM_AUDIENCE = "https://management.azure.com/.default"
GRAFANA_AUDIENCE = "ce34e7e5-485f-4d76-964f-b3d2b16d1e4f/.default"
LEASE_RENEW_SECONDS = 20


def credential():
    from azure.identity import AzureCliCredential, ManagedIdentityCredential
    return ManagedIdentityCredential() if os.environ.get("WEBSITE_HOSTNAME") else AzureCliCredential(
        subscription=SUB, process_timeout=30)


class AzureStore:
    def __init__(self, settings, identity):
        from azure.storage.blob import BlobServiceClient
        self.kind = settings.kind
        self.client = BlobServiceClient(
            f"https://{settings.account}.blob.core.windows.net", credential=identity,
            retry_total=0, connection_timeout=15, read_timeout=60)

    def _blob(self, container, name, write=False):
        allowed = {"producer": {"evidence", "reports", "ledger"},
                   "dispatcher": {"reports", "ledger", "approvals"}}[self.kind]
        if container not in allowed or (write and container == "approvals") or name.startswith("/"):
            raise ControlledError("Storage operation is not permitted for this app identity")
        if write and self.kind == "dispatcher" and container != "ledger":
            raise ControlledError("Dispatcher may only mutate ledger")
        return self.client.get_blob_client(container, name)

    def get(self, container, name):
        from azure.core.exceptions import ResourceNotFoundError
        try:
            download = self._blob(container, name).download_blob(max_concurrency=1)
            if download.size > 16 * 1024 * 1024:
                raise ControlledError("Stored object exceeds runtime size budget")
            return download.readall(), download.properties.etag
        except ResourceNotFoundError:
            return None, None

    def get_json(self, container, name):
        data, etag = self.get(container, name)
        return (json.loads(data), etag) if data is not None else (None, None)

    def create(self, container, name, data, content_type="application/json"):
        from azure.core.exceptions import ResourceExistsError, ResourceModifiedError
        from azure.storage.blob import ContentSettings
        try:
            result = self._blob(container, name, True).upload_blob(
                data, overwrite=False, content_settings=ContentSettings(content_type=content_type))
            return result["etag"]
        except (ResourceExistsError, ResourceModifiedError):
            raise Conflict("Object already exists") from None

    def create_json(self, container, name, value):
        return self.create(container, name, canonical(value))

    def replace_json(self, container, name, value, etag):
        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceModifiedError, ResourceNotFoundError
        try:
            result = self._blob(container, name, True).upload_blob(
                canonical(value), overwrite=True, etag=etag,
                match_condition=MatchConditions.IfNotModified)
            return result["etag"]
        except (ResourceModifiedError, ResourceNotFoundError):
            raise Conflict("Concurrent ledger update") from None

    @contextlib.contextmanager
    def rendering_lease(self):
        from azure.core.exceptions import HttpResponseError
        name = "locks/native-render"
        try:
            self.create("ledger", name, b"native rendering lock", "text/plain")
        except Conflict:
            pass
        blob = self._blob("ledger", name, True)
        lease, deadline = None, time.monotonic() + 90
        while lease is None:
            try:
                lease = blob.acquire_lease(lease_duration=60)
            except HttpResponseError as error:
                if error.status_code != 409 or time.monotonic() >= deadline:
                    raise ControlledError("Native render lease unavailable") from None
                time.sleep(3)
        stopped, lost = threading.Event(), threading.Event()

        def renew():
            from azure.core.exceptions import AzureError
            try:
                while not stopped.wait(LEASE_RENEW_SECONDS):
                    lease.renew()
            except (AzureError, RuntimeError) as error:
                logging.error("Native render lease renewal failed type=%s", type(error).__name__)
            finally:
                if not stopped.is_set():
                    lost.set()

        thread = threading.Thread(target=renew, daemon=True)
        thread.start()

        def check():
            if lost.is_set():
                raise ControlledError("Native render lease renewal failed")

        try:
            yield check
            check()
        finally:
            stopped.set()
            thread.join(timeout=5)
            lease.release()


class JobQueue:
    def __init__(self, settings, identity):
        from azure.storage.queue import QueueClient
        self.client = QueueClient(f"https://{settings.account}.queue.core.windows.net",
                                  QUEUE, credential=identity, retry_total=0,
                                  connection_timeout=15, read_timeout=30)

    def enqueue(self, job):
        # host.json messageEncoding=none matches this UTF-8 JSON payload.
        self.client.send_message(canonical(job).decode(), time_to_live=900)


class Sources:
    def __init__(self, settings, identity, session=None, sleep=time.sleep):
        self.settings, self.identity = settings, identity
        self.session, self.sleep = session or requests.Session(), sleep
        self.deadline = None
        self.report_dashboard_id = None

    def request(self, method, url, audience, payload=None, *, read=True, timeout=45,
                binary=False, allow404=False):
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment
                or parsed.port not in (None, 443)):
            raise ControlledError("Only approved HTTPS endpoints are permitted")
        grafana = urlparse(self.settings.grafana_endpoint).hostname
        if parsed.hostname == "api.loganalytics.io":
            if (audience != LOGS_AUDIENCE or method != "POST" or not read or
                    parsed.path not in {f"/v1/workspaces/{w}/query" for w in WORKSPACES.values()}):
                raise ControlledError("Unapproved Logs endpoint")
        elif parsed.hostname == "management.azure.com":
            if audience != ARM_AUDIENCE or not read:
                raise ControlledError("ARM mutation prohibited")
            if parsed.path == "/providers/Microsoft.ResourceGraph/resources":
                if (method != "POST" or payload.get("subscriptions") != [SUB]
                        or SUB not in payload.get("query", "") or SCOPE.split("/")[-1] not in payload["query"]):
                    raise ControlledError("Unscoped ARG request")
            elif method != "GET" or not parsed.path.lower().startswith(SCOPE.lower() + "/"):
                raise ControlledError("ARM read exceeds approved resource group")
            if any(x in parsed.path.lower() for x in ("runcommands", "listkeys", "guest", "/sql")):
                raise ControlledError("Guest/SQL/credential endpoint prohibited")
        elif parsed.hostname == grafana:
            if audience != GRAFANA_AUDIENCE:
                raise ControlledError("Wrong Grafana audience")
            if method == "POST":
                frozen_read = read and parsed.path == "/api/ds/query"
                if frozen_read:
                    for query in payload.get("queries", []):
                        logs = query.get("azureLogAnalytics", {})
                        if (query.get("datasource", {}).get("uid") != DATASOURCE_UID or
                                logs.get("resources") != [next(iter(WORKSPACES))] or
                                not logs.get("query", "").startswith(
                                    "datatable(TimeGenerated:datetime,Series:string,Value:real)[")):
                            raise ControlledError("Only frozen report data queries permitted")
                elif (read or parsed.path != "/api/dashboards/db" or
                      payload.get("dashboard", {}).get("uid") != DASHBOARD_UID or
                      payload.get("folderUid", FOLDER_UID) != FOLDER_UID or
                      payload.get("dashboard", {}).get("id") != self.report_dashboard_id):
                    raise ControlledError("Only dedicated new report dashboard saves are permitted")
            elif method != "GET" or parsed.path not in {
                    f"/api/dashboards/uid/{DASHBOARD_UID}", "/api/reports/render/pdfs",
                    "/api/dashboards/uid/hv-operations-cockpit",
                    "/api/dashboards/uid/hv-operations-report",
                    f"/api/datasources/uid/{DATASOURCE_UID}", "/api/health"}:
                raise ControlledError("Unapproved Grafana endpoint")
        else:
            raise ControlledError("Unapproved service endpoint")
        headers = {"Authorization": "Bearer " + self.identity.get_token(audience).token,
                   "Accept": "application/pdf" if binary else "application/json"}
        for attempt in range(3):
            remaining = self.deadline - time.monotonic() if self.deadline else 300
            if remaining <= 2:
                raise ControlledError("Service operation exceeded bounded execution deadline")
            try:
                response = self.session.request(method, url, json=payload, headers=headers,
                                                timeout=min(timeout, 240, remaining - 1), allow_redirects=False)
            except requests.RequestException:
                raise ControlledError("Service transport failed; no result assumed") from None
            if allow404 and response.status_code == 404:
                return None
            if read and response.status_code in (429, 503) and attempt < 2:
                try:
                    delay = min(20, max(1, int(response.headers.get("Retry-After", "3"))))
                except ValueError:
                    delay = 3
                self.sleep(delay)
                continue
            if response.status_code != 200:
                raise ControlledError(f"Scoped service request failed HTTP {response.status_code}")
            if len(response.content) > 16 * 1024 * 1024:
                raise ControlledError("Service response exceeds runtime size budget")
            if binary:
                if not response.content.startswith(b"%PDF-"):
                    raise ControlledError("Native renderer did not return PDF")
                return response.content
            try:
                return response.json()
            except ValueError:
                raise ControlledError("Service response is not valid JSON") from None
        raise ControlledError("Read retry budget exhausted")

    def collect(self, contract, job):
        if contract["service"] == "logs":
            workspace = contract["workspaceGuids"][0]
            return parse_logs(self.request(
                "POST", f"https://api.loganalytics.io/v1/workspaces/{workspace}/query", LOGS_AUDIENCE,
                {"query": contract["query"],
                 "timespan": job["sourceStartUtc"] + "/" + job["sourceEndUtc"]}))
        return parse_arg(self.request(
            "POST", "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01",
            ARM_AUDIENCE, {"subscriptions": [SUB], "query": contract["query"],
                           "options": {"resultFormat": "objectArray", "$top": 1000}}))

    def preflight(self):
        self.request("GET", self.settings.grafana_endpoint + f"/api/datasources/uid/{DATASOURCE_UID}",
                     GRAFANA_AUDIENCE)

    def access_proof(self):
        result = {}
        for uid in ("hv-operations-cockpit", "hv-operations-report", DASHBOARD_UID):
            value = self.request("GET", self.settings.grafana_endpoint + "/api/dashboards/uid/" + uid,
                                 GRAFANA_AUDIENCE)
            result[uid] = {
                "canSave": value["meta"]["canSave"],
                "folderUid": value["meta"].get("folderUid"),
            }
        return result

    def render(self, dashboard, job):
        url = self.settings.grafana_endpoint
        expected_points = [panel.pop("_expectedPoints") for panel in dashboard["panels"]]
        existing = self.request("GET", url + f"/api/dashboards/uid/{DASHBOARD_UID}",
                                GRAFANA_AUDIENCE, allow404=True)
        if existing:
            if existing["dashboard"]["uid"] != DASHBOARD_UID:
                raise ControlledError("Unexpected dashboard identity")
            dashboard["version"] = existing["dashboard"]["version"]
            self.report_dashboard_id = existing["dashboard"]["id"]
            dashboard["id"] = self.report_dashboard_id
        else:
            self.report_dashboard_id = None
        self.request("POST", url + "/api/dashboards/db", GRAFANA_AUDIENCE,
                     {"dashboard": dashboard, "folderUid": FOLDER_UID, "overwrite": False,
                      "message": "Immutable shift snapshot " + job["reportId"]}, read=False)
        saved = self.request("GET", url + f"/api/dashboards/uid/{DASHBOARD_UID}", GRAFANA_AUDIENCE)
        for actual, expected in zip(saved["dashboard"]["panels"], dashboard["panels"]):
            if actual["targets"] != expected["targets"]:
                raise ControlledError("Saved dashboard frozen query mismatch")
        if len(saved["dashboard"]["panels"]) != 8:
            raise ControlledError("Expected eight native chart pages")
        self.verify_frozen_frames(dashboard, job, expected_points)
        dashboards = [{"dashboard": {"uid": DASHBOARD_UID}, "reportVariables": {},
                       "timeRange": {k: str(int(parse_utc(job[v]).timestamp() * 1000))
                                     for k, v in (("from", "sourceStartUtc"), ("to", "sourceEndUtc"))}}]
        params = urlencode({"orientation": "landscape", "layout": "simple", "scaleFactor": "100",
                            "dashboards": json.dumps(dashboards, separators=(",", ":"))})
        return self.request("GET", url + "/api/reports/render/pdfs?" + params,
                            GRAFANA_AUDIENCE, timeout=240, binary=True)

    def verify_frozen_frames(self, dashboard, job, expected_points):
        import copy
        import collections
        # Validate the same frozen KQL through the actual datasource identity,
        # before rendering. A native PDF with an error/no-data panel is not Ready.
        for panel, expected in zip(dashboard["panels"], expected_points):
            query = copy.deepcopy(panel["targets"][0])
            query["azureLogAnalytics"]["resultFormat"] = "table"
            query["intervalMs"] = 300000
            query["maxDataPoints"] = 10000
            result = self.request(
                "POST", self.settings.grafana_endpoint + "/api/ds/query", GRAFANA_AUDIENCE,
                {"queries": [query], "from": str(int(parse_utc(job["sourceStartUtc"]).timestamp() * 1000)),
                 "to": str(int(parse_utc(job["sourceEndUtc"]).timestamp() * 1000))}, timeout=20)
            entry = result.get("results", {}).get("A", {})
            if entry.get("error") or entry.get("status", 200) != 200 or "frames" not in entry:
                raise ControlledError("Grafana frozen datasource query failed")
            observed = []
            for frame in entry["frames"]:
                if frame.get("schema", {}).get("meta", {}).get("notices"):
                    raise ControlledError("Grafana datasource returned query notices; completeness unproven")
                names = [field["name"] for field in frame["schema"]["fields"]]
                values = frame["data"]["values"]
                if set(names) != {"TimeGenerated", "Series", "Value"} or len(values) != 3:
                    raise ControlledError("Unexpected Grafana frozen data schema")
                if len({len(column) for column in values}) != 1:
                    raise ControlledError("Grafana frozen frame column mismatch")
                for row in zip(*values):
                    cells = dict(zip(names, row))
                    moment = cells["TimeGenerated"]
                    moment = (int(parse_utc(moment).timestamp() * 1000) if isinstance(moment, str) else int(moment))
                    observed.append((moment, cells["Series"], float(cells["Value"])))
            expected = [(int(parse_utc(t).timestamp() * 1000), s, float(v)) for t, s, v in expected]
            if collections.Counter(observed) != collections.Counter(expected):
                raise ControlledError("Native datasource/frozen XLSX chart counts or values do not reconcile")


class Mailer:
    def __init__(self, settings, identity):
        self.settings, self.identity = settings, identity

    def submit(self, envelope, blobs, request_id, first_sent):
        from azure.communication.email import EmailClient
        if (utcnow() - parse_utc(first_sent)).total_seconds() > 240:
            raise ControlledError("Repeatability window expired; no resend permitted")
        if envelope.get("schemaVersion") == 3:
            from domain import sha, validate_inline_assets, validate_report_attachments
            documents = validate_report_attachments(envelope, require_three=True)
            assets = validate_inline_assets(envelope)
            for artifact in documents + assets:
                data = blobs.get(artifact["name"])
                if (not isinstance(data, bytes) or len(data) != artifact["size"]
                        or sha(data) != artifact["sha256"]):
                    raise ControlledError("Report or inline image integrity check failed before mail submission")
        first = format_datetime(parse_utc(first_sent), usegmt=True)
        # ACS documents Repeatability-* (not x-ms-*). Preserve both spellings for
        # operational traceability, but the documented pair provides idempotency.
        headers = {"Repeatability-Request-ID": request_id, "Repeatability-First-Sent": first,
                   "x-ms-repeatability-request-id": request_id, "x-ms-repeatability-first-sent": first}
        message = {
            "senderAddress": envelope["sender"],
            "recipients": {"to": [{"address": x} for x in envelope["to"]]},
            "content": {"subject": envelope["subject"], "plainText": envelope["body"]},
            "attachments": [{"name": a["name"], "contentType": a["contentType"],
                             "contentInBase64": base64.b64encode(blobs[a["name"]]).decode()}
                            for a in envelope["attachments"]],
        }
        if envelope.get("schemaVersion") in (2, 3):
            from domain import validate_inline_assets
            message["content"]["html"] = envelope["htmlBody"]
            for asset in validate_inline_assets(envelope):
                message["attachments"].append({
                    "name": asset["name"], "contentType": asset["contentType"], "contentId": asset["contentId"],
                    "contentInBase64": base64.b64encode(blobs[asset["name"]]).decode(),
                })
        client = EmailClient(self.settings.acs_endpoint, self.identity, retry_total=0,
                             connection_timeout=15, read_timeout=60, polling_interval=2)
        try:
            poller = client.begin_send(message, operation_id=request_id, headers=headers)
            result = poller.result(timeout=90)
            if not poller.done() or result.get("status") != "Succeeded":
                raise ControlledError("ACS operation is incomplete or failed")
            return {"operationId": result["id"], "acsStatus": result["status"],
                    "submissionMeaning": "ACS accepted submission; NOT Delivered or inbox proof"}
        finally:
            client.close()
