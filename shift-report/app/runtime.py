"""Durable producer/dispatcher state machines; no sends without exact approval."""

import logging
import time
import uuid
from azure.core.exceptions import AzureError
from requests import RequestException

from artifacts import dashboard, merge_pdf, workbook
from automation import integrity_record, scheduled_policy, verify_scheduled
from domain import (Conflict, ControlledError, LIMITATIONS, MAX_ATTACHMENTS, assess,
                    build_envelope, canonical, due_boundary, new_job, parse_utc,
                    sha, stamp, utcnow, valid_id, validate_job, verify_approval)
from domain import envelope_payload, validate_inline_assets, validate_report_attachments
from email_assets import brand_images
from queries import contracts
from workbook_pdf import render_workbook_pdf

LOG = logging.getLogger("hvobs.shift")
GENERATION_ERRORS = (ControlledError, RuntimeError, ValueError, KeyError, TypeError, OSError,
                     AzureError, RequestException)


def job_key(report_id):
    return f"jobs/{valid_id(report_id)}.json"


def dispatch_key(report_id):
    return f"dispatch/{valid_id(report_id)}.json"


def safe_failure(error):
    return str(error) if isinstance(error, ControlledError) else f"Runtime failure ({type(error).__name__})"


class Runtime:
    def __init__(self, settings, store, sources=None, queue=None, mailer=None, clock=utcnow):
        self.settings, self.store, self.sources = settings, store, sources
        self.queue, self.mailer, self.clock = queue, mailer, clock

    def require(self, kind):
        if self.settings.kind != kind:
            raise ControlledError("Endpoint is not available in this app")

    def prepare(self, body):
        self.require("producer")
        if not isinstance(body, dict) or set(body) - {"mode", "boundary", "jobId"}:
            raise ValueError("Only mode, boundary and jobId are accepted")
        mode = body.get("mode")
        if mode == "scheduled" and not self.settings.schedule_enabled:
            raise ControlledError("Scheduled collection disabled")
        job = new_job(mode, self.clock(), body.get("boundary"), body.get("jobId"))
        if mode == "scheduled":
            scheduled_policy(self.settings, parse_utc(job["boundaryUtc"]))
        key = job_key(job["reportId"])
        state = {"status": "Queued", "job": job, "createdUtc": job["createdUtc"]}
        try:
            etag = self.store.create_json("ledger", key, state)
        except Conflict:
            prior, _ = self.store.get_json("ledger", key)
            return {"reportId": job["reportId"], "jobId": prior["job"]["jobId"],
                    "status": prior["status"], "deduplicated": True}
        try:
            self.queue.enqueue(job)
        except (AzureError, OSError, ControlledError) as error:
            self.store.replace_json("ledger", key, {
                **state, "status": "Failed", "error": "Queue submission failed or uncertain; no automatic retry",
                "finishedUtc": stamp(self.clock())}, etag)
            raise ControlledError("Queue submission failed or uncertain; inspect durable status") from error
        return {"reportId": job["reportId"], "jobId": job["jobId"], "status": "Queued",
                "deduplicated": False}

    def generate(self, message):
        self.require("producer")
        validate_job(message)
        key = job_key(message["reportId"])
        state, etag = self.store.get_json("ledger", key)
        if not state or canonical(state["job"]) != canonical(message):
            raise ControlledError("Queue job does not match registered durable job")
        if state["status"] != "Queued":
            return {"reportId": message["reportId"], "status": state["status"], "deduplicated": True}
        state = {**state, "status": "Generating", "startedUtc": stamp(self.clock())}
        try:
            etag = self.store.replace_json("ledger", key, state, etag)
        except Conflict:
            return {"reportId": message["reportId"], "status": "AlreadyClaimed", "deduplicated": True}
        started = time.monotonic()
        try:
            policy = None
            if message["mode"] == "scheduled":
                if not self.settings.schedule_enabled:
                    raise ControlledError("Scheduled generation disabled")
                policy = scheduled_policy(self.settings, parse_utc(message["boundaryUtc"]))
            logos = brand_images()
            now = self.clock()
            if message["mode"] == "scheduled" and now >= parse_utc(message["boundaryUtc"]):
                raise ControlledError("Scheduled extraction missed its boundary; no backfill")
            if now < parse_utc(message["sourceEndUtc"]):
                raise ControlledError("Source cutoff is still in the future")
            # freezeAt is the extraction START, not the HTTP request or render time.
            freeze = stamp(now)
            compiled = contracts(message, freeze)
            datasets, provenance = {}, []
            if hasattr(self.sources, "deadline"):
                self.sources.deadline = time.monotonic() + 225
            for item in compiled:
                if time.monotonic() - started > 225:
                    raise ControlledError("Sequential extraction exceeded its time budget")
                rows = self.sources.collect(item, message)
                datasets[item["id"]] = rows
                timestamps = sorted(str(row[k]) for row in rows for k in
                                    ("TimeGenerated", "Latest", "LastSeen", "SnapshotAt", "Updated", "InventoryUpdated")
                                    if row.get(k))
                provenance.append({
                    "id": item["id"], "service": item["service"], "querySha256": item["querySha256"],
                    "rows": len(rows), "recordsSha256": sha(canonical(rows)),
                    "sourceMinUtc": timestamps[0] if timestamps else None,
                    "sourceMaxUtc": timestamps[-1] if timestamps else None,
                    "frozen": item["service"] == "logs",
                    "caveat": None if item["service"] == "logs" else "Current indexed inventory snapshot",
                })
            evidence = {
                "schemaVersion": 1, "job": message, "freezeAtUtc": freeze,
                "extractedUtc": stamp(self.clock()), "timezone": "UTC+7",
                "queryManifestSha256": sha(canonical(compiled)), "queries": compiled,
                "datasets": datasets, "provenance": provenance, "limitations": LIMITATIONS,
                "health": assess(datasets, message),
            }
            native_dashboard, parity = dashboard(evidence)
            evidence["chartParity"] = parity
            evidence_data = canonical(evidence)
            if len(evidence_data) > 16 * 1024 * 1024:
                raise ControlledError("Complete evidence exceeds 16 MiB budget; no rows truncated")
            self.store.create("evidence", f"{message['reportId']}/snapshot.json", evidence_data)
            xlsx, counts = workbook(evidence, compiled, parity)
            if counts != {p["id"]: p["rows"] for p in provenance}:
                raise ControlledError("Full-row evidence/XLSX reconciliation failed")
            with self.store.rendering_lease() as check_lease:
                check_lease()
                if hasattr(self.sources, "deadline"):
                    self.sources.deadline = min(time.monotonic() + 275, started + 540)
                native = self.sources.render(native_dashboard, message)
                check_lease()
                pdf = merge_pdf(evidence, native)
                check_lease()
            remaining = MAX_ATTACHMENTS - len(pdf) - len(xlsx) - sum(len(data) for _, data in logos)
            if remaining <= 0:
                raise ControlledError("Reports and inline images exceed 5 MiB unencoded")
            workbook_copy = render_workbook_pdf(xlsx, max_bytes=remaining)
            attachments = []
            for ending, content, content_type in (
                (".pdf", pdf, "application/pdf"),
                (".xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("-workbook.pdf", workbook_copy, "application/pdf"),
            ):
                name = f"HV-{message['reportId']}{ending}"
                path = f"{message['reportId']}/{name}"
                self.store.create("reports", path, content, content_type)
                attachments.append({"name": name, "blob": path, "size": len(content),
                                    "sha256": sha(content), "contentType": content_type})
            inline_assets = []
            for asset, content in logos:
                path = f"{message['reportId']}/inline/{asset['name']}"
                self.store.create("reports", path, content, asset["contentType"])
                inline_assets.append({
                    "name": asset["name"], "blob": path, "size": len(content),
                    "sha256": sha(content), "contentType": asset["contentType"], "contentId": asset["contentId"],
                })
            envelope = build_envelope(self.settings, evidence, attachments, inline_assets, workbook_copy=True)
            envelope_sha = sha(canonical(envelope))
            self.store.create_json("reports", f"{message['reportId']}/envelope.json", envelope)
            finished = self.clock()
            if message["mode"] == "scheduled" and finished >= parse_utc(message["boundaryUtc"]):
                raise ControlledError("Scheduled generation missed Ready deadline; no late send")
            state = {
                **state, "status": "Ready", "finishedUtc": stamp(finished),
                "buildSeconds": round(time.monotonic() - started, 3), "health": evidence["health"],
                "evidenceSha256": sha(evidence_data), "attachments": attachments,
                "envelopeSha256": envelope_sha, "freezeAtUtc": freeze,
                "sourceEndUtc": message["sourceEndUtc"], "nativeChartPages": 8,
                "inlineAssets": envelope["inlineAssets"],
                "extractedUtc": evidence["extractedUtc"],
            }
            receipt = integrity_record(state, envelope, policy)
            self.store.create_json("reports", f"{message['reportId']}/dispatch-integrity.json", receipt)
            state["dispatchIntegritySha256"] = sha(canonical(receipt))
            if message["mode"] == "scheduled" and self.clock() >= parse_utc(message["boundaryUtc"]):
                raise ControlledError("Scheduled receipt persistence missed Ready deadline; no late send")
            self.store.replace_json("ledger", key, state, etag)
            return {"reportId": message["reportId"], "status": "Ready", "health": evidence["health"]["status"]}
        except GENERATION_ERRORS as error:
            LOG.error("Generation failed reportId=%s type=%s", message["reportId"], type(error).__name__)
            self.store.replace_json("ledger", key, {
                **state, "status": "Failed", "error": safe_failure(error),
                "finishedUtc": stamp(self.clock()), "buildSeconds": round(time.monotonic() - started, 3)}, etag)
            raise

    def status(self, report_id):
        state, state_etag = self.store.get_json("ledger", job_key(report_id))
        sent, _ = self.store.get_json("ledger", dispatch_key(report_id))
        if not state and not sent:
            raise ControlledError("Report not found")
        if state and state["status"] in ("Queued", "Generating"):
            threshold = 900 if state["status"] == "Queued" else 600
            anchor = state.get("startedUtc", state["createdUtc"])
            if (self.clock() - parse_utc(anchor)).total_seconds() > threshold:
                expired = {**state, "status": "Failed", "finishedUtc": stamp(self.clock()),
                           "error": "Expired queue or interrupted build; no backfill/automatic regeneration"}
                try:
                    self.store.replace_json("ledger", job_key(report_id), expired, state_etag)
                    state = expired
                except Conflict:
                    state, _ = self.store.get_json("ledger", job_key(report_id))
        # No envelope body, continuation token, auth header or raw service response.
        public = {"reportId": report_id, "status": state["status"] if state else "NotPrepared"}
        for field in ("createdUtc", "startedUtc", "finishedUtc", "buildSeconds", "health",
                      "error", "envelopeSha256", "attachments", "inlineAssets", "freezeAtUtc", "sourceEndUtc"):
            if state and field in state:
                public[field] = state[field]
        if sent:
            public["dispatch"] = {k: sent[k] for k in (
                "status", "firstSentUtc", "finishedUtc", "operationId", "acsStatus", "error",
                "submissionMeaning", "authorizationMode", "policyId", "policySha256",
                "policyApprovedAt", "dispatchIntegritySha256", "evidenceSha256") if k in sent}
            if sent["status"] == "Sending" and (
                    self.clock() - parse_utc(sent["firstSentUtc"])).total_seconds() >= 240:
                public["dispatch"]["status"] = "DeliveryUncertain"
                public["dispatch"]["error"] = "Submission tracking interrupted; no automatic resend"
        return public

    def preview(self, report_id):
        self.require("dispatcher")
        valid_id(report_id)
        state, _ = self.store.get_json("ledger", job_key(report_id))
        if not state or state["status"] != "Ready":
            raise ControlledError("Exact report is not Ready; no stale attachment permitted")
        envelope, _ = self.store.get_json("reports", f"{report_id}/envelope.json")
        if not envelope or sha(canonical(envelope)) != state["envelopeSha256"]:
            raise ControlledError("Envelope integrity check failed")
        if (envelope["reportId"] != report_id or envelope["to"] != list(self.settings.recipients)
                or envelope["sender"] != self.settings.sender):
            raise ControlledError("Envelope sender/recipient configuration mismatch")
        if envelope["attachments"] != sorted(state["attachments"], key=lambda a: a["name"]):
            raise ControlledError("Ledger/artifact set mismatch")
        validate_report_attachments(envelope)
        inline = validate_inline_assets(envelope)
        if inline != state.get("inlineAssets", []):
            raise ControlledError("Ledger/inline brand image mismatch")
        return {**envelope, "envelopeSha256": state["envelopeSha256"],
                "allowedReportId": report_id, "sendEnabled": self.settings.send_enabled,
                "deliveryGuarantee": "None; ACS accepted submission is not Delivered"}

    def artifact(self, report_id, filename):
        preview = self.preview(report_id)
        attachment = next((a for a in preview["attachments"] + preview.get("inlineAssets", []) if a["name"] == filename), None)
        if attachment is None:
            raise ControlledError("Only exact Ready report attachments or inline logos can be downloaded")
        data, _ = self.store.get("reports", attachment["blob"])
        if data is None or len(data) != attachment["size"] or sha(data) != attachment["sha256"]:
            raise ControlledError("Attachment integrity check failed")
        return data, attachment

    def _late(self, report_id):
        state = {"status": "Failed", "reportId": report_id, "finishedUtc": stamp(self.clock()),
                 "error": "Exact report not Ready at dispatch; no stale attachments or unapproved notice"}
        try:
            self.store.create_json("ledger", dispatch_key(report_id), state)
        except Conflict:
            pass

    def dispatch(self, report_id, scheduled=False):
        self.require("dispatcher")
        valid_id(report_id)
        if not self.settings.send_enabled:
            raise ControlledError("SEND_ENABLED is false; no send attempted")
        if not self.settings.acs_endpoint:
            raise ControlledError("ACS_ENDPOINT must be configured")
        policy = None
        if scheduled:
            due = due_boundary(self.clock(), "dispatch")
            if (not self.settings.schedule_enabled or due is None or
                    report_id != "shift-" + due.strftime("%Y%m%dT%H%M%SZ")):
                raise ControlledError("No scheduled backfill or unsafe cycle")
            policy = scheduled_policy(self.settings, due)
        prior, prior_etag = self.store.get_json("ledger", dispatch_key(report_id))
        if prior:
            if prior["status"] == "Sending" and (
                    self.clock() - parse_utc(prior["firstSentUtc"])).total_seconds() >= 240:
                prior = {**prior, "status": "DeliveryUncertain",
                         "error": "Submission tracking interrupted; no automatic resend"}
                try:
                    self.store.replace_json("ledger", dispatch_key(report_id), prior, prior_etag)
                except Conflict:
                    pass
            return {"reportId": report_id, "status": prior["status"], "deduplicated": True}
        state, _ = self.store.get_json("ledger", job_key(report_id))
        if not state or state["status"] != "Ready":
            self._late(report_id)
            raise ControlledError("Exact report not Ready; controlled late failure recorded, no notice sent")
        preview = self.preview(report_id)
        envelope = envelope_payload(preview)
        validate_report_attachments(envelope, require_three=scheduled)
        authorization = {"authorizationMode": "perReportApproval"}
        receipt = None
        if policy is not None:
            receipt, _ = self.store.get_json("reports", report_id + "/dispatch-integrity.json")
            authorization = verify_scheduled(self.settings, self.clock(), report_id,
                                             state, envelope, receipt, policy)
        else:
            approval, _ = self.store.get_json("approvals", report_id + ".json")
            if not approval:
                raise ControlledError("No explicit approval for this reportId")
            verify_approval(approval, envelope)
        blobs = {}
        inline_assets = validate_inline_assets(envelope)
        for attachment in envelope["attachments"] + inline_assets:
            expected_prefix = report_id + ("/inline/" if attachment in inline_assets else "/")
            if attachment["blob"] != expected_prefix + attachment["name"]:
                raise ControlledError("Attachment path is outside this report")
            data, _ = self.store.get("reports", attachment["blob"])
            if data is None or len(data) != attachment["size"] or sha(data) != attachment["sha256"]:
                raise ControlledError("Attachment integrity check failed")
            blobs[attachment["name"]] = data
        if scheduled:
            if due_boundary(self.clock(), "dispatch") != due:
                raise ControlledError("Scheduled dispatch minute expired before durable claim")
            if policy is not None:
                policy = scheduled_policy(self.settings, due)
                authorization = verify_scheduled(self.settings, self.clock(), report_id,
                                                 state, envelope, receipt, policy)
        claim = {"reportId": report_id, "status": "Sending", "firstSentUtc": stamp(self.clock()),
                 "repeatabilityRequestId": str(uuid.uuid4()), "envelopeSha256": preview["envelopeSha256"],
                 "repeatabilityWindowSeconds": 300, **authorization}
        claim["operationId"] = claim["repeatabilityRequestId"]
        try:
            etag = self.store.create_json("ledger", dispatch_key(report_id), claim)
        except Conflict:
            prior, _ = self.store.get_json("ledger", dispatch_key(report_id))
            return {"reportId": report_id, "status": prior["status"], "deduplicated": True}
        if scheduled and due_boundary(self.clock(), "dispatch") != due:
            self.store.replace_json("ledger", dispatch_key(report_id), {
                **claim, "status": "Failed", "finishedUtc": stamp(self.clock()),
                "error": "Dispatch minute expired after durable claim; no submission and no resend"}, etag)
            raise ControlledError("Dispatch minute expired after durable claim; no submission and no resend")
        try:
            proof = self.mailer.submit(envelope, blobs, claim["repeatabilityRequestId"], claim["firstSentUtc"])
            completed = {**claim, **proof, "status": "Submitted", "finishedUtc": stamp(self.clock())}
            self.store.replace_json("ledger", dispatch_key(report_id), completed, etag)
            return {"reportId": report_id, "status": "Submitted", **proof}
        except (AzureError, OSError, ControlledError, RequestException) as error:
            LOG.error("Dispatch uncertain reportId=%s type=%s", report_id, type(error).__name__)
            uncertain = {**claim, "status": "DeliveryUncertain", "finishedUtc": stamp(self.clock()),
                         "error": "ACS send failed or timed out after durable claim; operator investigation required, no resend"}
            self.store.replace_json("ledger", dispatch_key(report_id), uncertain, etag)
            raise ControlledError(uncertain["error"]) from None

    def preflight(self, past_due=False):
        self.require("producer")
        boundary = due_boundary(self.clock(), "preflight")
        if past_due or not self.settings.schedule_enabled or boundary is None:
            return {"status": "Skipped"}
        scheduled_policy(self.settings, boundary)
        key = "preflight/" + boundary.strftime("%Y%m%dT%H%M%SZ") + ".json"
        status = {"status": "Checking", "boundaryUtc": stamp(boundary)}
        try:
            etag = self.store.create_json("ledger", key, status)
        except Conflict:
            return {"status": "Deduplicated"}
        try:
            self.sources.preflight()
            self.store.replace_json("ledger", key, {**status, "status": "Passed",
                                    "checkedUtc": stamp(self.clock()),
                                    "caveat": "Read preflight; Grafana Editor, render licensing and ACS sender still require deployment validation"}, etag)
            return {"status": "Passed"}
        except GENERATION_ERRORS as error:
            self.store.replace_json("ledger", key, {**status, "status": "Failed",
                                                    "error": safe_failure(error)}, etag)
            raise

    def collection_tick(self, past_due=False):
        boundary = due_boundary(self.clock(), "collect")
        if past_due or not self.settings.schedule_enabled or boundary is None:
            return {"status": "Skipped"}
        return self.prepare({"mode": "scheduled", "boundary": stamp(boundary)})

    def dispatch_tick(self, past_due=False):
        boundary = due_boundary(self.clock(), "dispatch")
        if past_due or not self.settings.schedule_enabled or not self.settings.send_enabled or boundary is None:
            return {"status": "Skipped"}
        return self.dispatch("shift-" + boundary.strftime("%Y%m%dT%H%M%SZ"), scheduled=True)
