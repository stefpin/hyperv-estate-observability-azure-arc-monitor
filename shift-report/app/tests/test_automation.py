import copy
import datetime as dt
import importlib
import io
import json
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import azure.functions as func
import fitz

from automation import (APPROVAL, FIRST_BOUNDARY, POLICY_ID, POLICY_PATH, REVISION, SENDER,
                        automation_status, integrity_record, load_policy)
from domain import (ControlledError, Settings, UTC, LT, canonical, new_job, parse_utc,
                    sha, stamp)
from runtime import Runtime, dispatch_key, job_key
from tests.fakes import Mailer, OfflineCase, Queue, Sources, Store, settings

BOUNDARY = parse_utc(FIRST_BOUNDARY)
CUTOFF = BOUNDARY - dt.timedelta(minutes=5)


def enabled(kind="dispatcher", **changes):
    return settings(kind, sender=SENDER, send_enabled=True, schedule_enabled=True,
                    auto_send_enabled=True,
                    auto_send_policy_sha256=sha(POLICY_PATH.read_bytes()), **changes)


class AutomationTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.store, self.queue, self.mailer = Store(), Queue(), Mailer()
        self.sources = Sources(new_job("scheduled", CUTOFF, FIRST_BOUNDARY))
        self.producer = Runtime(enabled("producer"), self.store, self.sources, self.queue,
                                clock=lambda: CUTOFF)
        self.dispatcher = Runtime(enabled(), self.store, mailer=self.mailer,
                                  clock=lambda: BOUNDARY)

    def ready(self, mode="scheduled"):
        prepared = (self.producer.collection_tick() if mode == "scheduled"
                    else self.producer.prepare({"mode": mode}))
        self.producer.generate(self.queue.messages[-1])
        return prepared["reportId"]

    def replace_json(self, container, name, value):
        _, etag = self.store.get(container, name)
        self.store.replace_json(container, name, value, etag)

    def approve(self, report_id):
        preview = self.dispatcher.preview(report_id)
        self.store.create_json("approvals", report_id + ".json", {
            "reportId": report_id, "approved": True, "to": preview["to"],
            "envelopeSha256": preview["envelopeSha256"]})

    def alter_envelope(self, report_id, change, reseal=False):
        envelope, _ = self.store.get_json("reports", report_id + "/envelope.json")
        state, _ = self.store.get_json("ledger", job_key(report_id))
        change(envelope)
        state["envelopeSha256"] = sha(canonical(envelope))
        if reseal:
            state["attachments"] = envelope["attachments"]
            state["inlineAssets"] = envelope["inlineAssets"]
            receipt = integrity_record(state, envelope, load_policy(self.dispatcher.settings))
            self.replace_json("reports", report_id + "/dispatch-integrity.json", receipt)
            state["dispatchIntegritySha256"] = sha(canonical(receipt))
        self.replace_json("reports", report_id + "/envelope.json", envelope)
        self.replace_json("ledger", job_key(report_id), state)

    def test_full_scheduled_flow_no_per_report_approval_and_no_evidence_read(self):
        report_id = self.ready()
        original_get = self.store.get
        def scoped_get(container, name):
            self.assertNotIn(container, ("evidence", "approvals"))
            return original_get(container, name)
        with patch.object(self.store, "get", side_effect=scoped_get):
            self.assertEqual(self.dispatcher.dispatch_tick()["status"], "Submitted")
            self.assertTrue(self.dispatcher.dispatch_tick()["deduplicated"])
        self.assertEqual(len(self.mailer.calls), 1)
        envelope, blobs, _, _ = self.mailer.calls[0]
        self.assertEqual(envelope["to"], ["operator@example.com"])
        self.assertEqual(envelope["sender"], SENDER)
        self.assertIn("Cutoff 21:55 LT", envelope["subject"])
        self.assertNotIn("[TEST]", envelope["subject"])
        self.assertIn("Host-to-SQL observability", envelope["htmlBody"])
        self.assertIn("Monitored with Azure Monitor", envelope["htmlBody"])
        self.assertEqual(envelope["htmlBody"].count('src="cid:'), 2)
        self.assertEqual(envelope["emailSummary"]["status"], "INSUFFICIENT EVIDENCE")
        self.assertEqual(len(envelope["attachments"]), 3)
        self.assertEqual(len(envelope["inlineAssets"]), 2)
        self.assertEqual(len(blobs), 5)
        pdf_name = f"HV-{report_id}.pdf"
        with fitz.open(stream=blobs[pdf_name], filetype="pdf") as document:
            self.assertEqual(len(document), 9)
        xlsx_name = next(name for name in blobs if name.endswith(".xlsx"))
        with zipfile.ZipFile(io.BytesIO(blobs[xlsx_name])) as archive:
            self.assertEqual(len([name for name in archive.namelist()
                                  if name.startswith("xl\\worksheets\\sheet".replace("\\", "/"))
                                  and name.endswith(".xml")]), 20)
        claim, _ = self.store.get_json("ledger", dispatch_key(report_id))
        self.assertEqual(claim["policyId"], POLICY_ID)
        self.assertEqual(claim["policySha256"], sha(POLICY_PATH.read_bytes()))
        self.assertEqual(claim["policyApprovedAt"], REVISION["approvedAt"])
        self.assertEqual(claim["authorizationMode"], "standingPolicy")
        self.assertTrue(claim["dispatchIntegritySha256"])
        self.assertFalse(any(container == "approvals" for container, _ in self.store.creates))

    def test_defaults_off_and_policy_explicitly_unpinned(self):
        with patch.dict(os.environ, {"APP_KIND": "dispatcher", "REPORT_STORAGE_ACCOUNT": "validaccount",
                                    "ACS_SENDER": SENDER}, clear=True):
            current = Settings.load()
        self.assertFalse(current.send_enabled)
        self.assertFalse(current.schedule_enabled)
        self.assertFalse(current.auto_send_enabled)
        self.assertEqual(current.auto_send_policy_sha256, "")
        status = automation_status(current, CUTOFF)
        self.assertEqual(status["status"], "Disabled")
        self.assertTrue(status["formatVerified"])
        self.assertFalse(status["policyVerified"])
        self.assertFalse(status["effectiveAutoSend"])

    def test_old_default_scheduled_path_still_requires_exact_approval(self):
        report_id = self.ready()
        self.dispatcher.settings = settings("dispatcher", sender=SENDER, send_enabled=True,
                                            schedule_enabled=True)
        with self.assertRaisesRegex(ControlledError, "explicit approval"):
            self.dispatcher.dispatch_tick()
        self.approve(report_id)
        self.assertEqual(self.dispatcher.dispatch_tick()["status"], "Submitted")

    def test_manual_never_inherits_standing_approval(self):
        report_id = self.ready()
        with self.assertRaisesRegex(ControlledError, "explicit approval"):
            self.dispatcher.dispatch(report_id)
        self.approve(report_id)
        self.assertEqual(self.dispatcher.dispatch(report_id)["status"], "Submitted")
        self.assertEqual(self.dispatcher.status(report_id)["dispatch"]["authorizationMode"],
                         "perReportApproval")

    def test_dryrun_never_inherits_scheduled_authorization(self):
        report_id = self.ready("dryrun")
        for scheduled in (True, False):
            with self.assertRaises(ControlledError):
                self.dispatcher.dispatch(report_id, scheduled=scheduled)
        self.assertEqual(self.mailer.calls, [])
        self.approve(report_id)
        self.assertEqual(self.dispatcher.dispatch(report_id)["status"], "Submitted")
        self.assertIn("[TEST]", self.mailer.calls[0][0]["subject"])

    def test_invalid_opt_in_never_falls_back_to_existing_report_approval(self):
        report_id = self.ready()
        self.approve(report_id)
        from dataclasses import replace
        for pin in ("", "f" * 64):
            self.dispatcher.settings = replace(enabled(), auto_send_policy_sha256=pin)
            with self.assertRaisesRegex(ControlledError, "AUTO_SEND_POLICY_SHA256"):
                self.dispatcher.dispatch_tick()
        self.assertEqual(self.mailer.calls, [])
        self.assertIsNone(self.store.get_json("ledger", dispatch_key(report_id))[0])

    def test_future_first_boundary_blocks_producer_and_dispatch(self):
        earlier = BOUNDARY - dt.timedelta(hours=8)
        self.producer.clock = lambda: earlier - dt.timedelta(minutes=5)
        with self.assertRaisesRegex(ControlledError, "effective start"):
            self.producer.collection_tick()
        with self.assertRaisesRegex(ControlledError, "effective start"):
            self.producer.prepare({"mode": "scheduled", "boundary": stamp(earlier)})
        self.producer.clock = lambda: earlier - dt.timedelta(minutes=10)
        with self.assertRaisesRegex(ControlledError, "effective start"):
            self.producer.preflight()
        self.dispatcher.clock = lambda: earlier
        with self.assertRaisesRegex(ControlledError, "effective start"):
            self.dispatcher.dispatch_tick()
        self.assertEqual(self.store.creates, [])
        self.assertEqual(self.sources.calls, [])
        self.assertEqual(self.queue.messages, [])

    def test_worker_does_not_collect_pre_activation_queued_report(self):
        earlier = BOUNDARY - dt.timedelta(hours=8)
        message = new_job("scheduled", earlier - dt.timedelta(minutes=5), stamp(earlier))
        self.store.create_json("ledger", job_key(message["reportId"]), {
            "status": "Queued", "job": message, "createdUtc": message["createdUtc"]})
        self.producer.clock = lambda: earlier - dt.timedelta(minutes=5)
        with self.assertRaisesRegex(ControlledError, "effective start"):
            self.producer.generate(message)
        self.assertEqual(self.sources.calls, [])

    def test_exact_cutoff_and_no_backfill_or_startup(self):
        for phase, runtime, moment in (
                ("preflight", self.producer, BOUNDARY - dt.timedelta(minutes=10)),
                ("collection_tick", self.producer, CUTOFF),
                ("dispatch_tick", self.dispatcher, BOUNDARY)):
            runtime.clock = lambda moment=moment: moment
            self.assertEqual(getattr(runtime, phase)(past_due=True)["status"], "Skipped")
            runtime.clock = lambda moment=moment: moment + dt.timedelta(minutes=1)
            self.assertEqual(getattr(runtime, phase)()["status"], "Skipped")
        for moment in (CUTOFF - dt.timedelta(seconds=1), BOUNDARY):
            self.producer.clock = lambda moment=moment: moment
            with self.assertRaises(ValueError):
                self.producer.prepare({"mode": "scheduled", "boundary": FIRST_BOUNDARY})
        self.assertEqual(self.store.creates, [])

    def test_exact_dispatch_minute_and_report_id(self):
        report_id = self.ready()
        for moment in (BOUNDARY - dt.timedelta(seconds=1), BOUNDARY + dt.timedelta(minutes=1)):
            self.dispatcher.clock = lambda moment=moment: moment
            with self.assertRaises(ControlledError):
                self.dispatcher.dispatch(report_id, scheduled=True)
        self.dispatcher.clock = lambda: BOUNDARY
        with self.assertRaises(ControlledError):
            self.dispatcher.dispatch("shift-20260725T070000Z", scheduled=True)
        self.assertEqual(self.mailer.calls, [])

    def test_boundary_rechecked_after_slow_blob_download(self):
        report_id = self.ready()
        get = self.store.get
        def delayed(container, name):
            if name.endswith(".xlsx"):
                self.dispatcher.clock = lambda: BOUNDARY + dt.timedelta(minutes=1)
            return get(container, name)
        with patch.object(self.store, "get", side_effect=delayed):
            with self.assertRaisesRegex(ControlledError, "minute expired"):
                self.dispatcher.dispatch_tick()
        self.assertEqual(self.mailer.calls, [])
        self.assertIsNone(self.store.get_json("ledger", dispatch_key(report_id))[0])

    def test_slow_durable_claim_must_not_send_after_dispatch_minute(self):
        report_id = self.ready()
        create = self.store.create_json
        def delayed(container, name, value):
            etag = create(container, name, value)
            if name == dispatch_key(report_id):
                self.dispatcher.clock = lambda: BOUNDARY + dt.timedelta(minutes=1)
            return etag
        with patch.object(self.store, "create_json", side_effect=delayed):
            with self.assertRaisesRegex(ControlledError, "no submission"):
                self.dispatcher.dispatch_tick()
        self.assertEqual(self.mailer.calls, [])
        claim, _ = self.store.get_json("ledger", dispatch_key(report_id))
        self.assertEqual(claim["status"], "Failed")

    def test_scheduled_generation_cannot_become_ready_after_boundary(self):
        self.producer.collection_tick()
        render = self.sources.render
        def late_render(dashboard, job):
            self.producer.clock = lambda: BOUNDARY
            return render(dashboard, job)
        with patch.object(self.sources, "render", side_effect=late_render):
            with self.assertRaisesRegex(ControlledError, "Ready deadline"):
                self.producer.generate(self.queue.messages[-1])
        state, _ = self.store.get_json("ledger", job_key(self.queue.messages[-1]["reportId"]))
        self.assertEqual(state["status"], "Failed")

    def test_slow_receipt_persistence_cannot_publish_late_ready(self):
        self.producer.collection_tick()
        create = self.store.create_json
        def delayed(container, name, value):
            etag = create(container, name, value)
            if name.endswith("/dispatch-integrity.json"):
                self.producer.clock = lambda: BOUNDARY
            return etag
        with patch.object(self.store, "create_json", side_effect=delayed):
            with self.assertRaisesRegex(ControlledError, "Ready deadline"):
                self.producer.generate(self.queue.messages[-1])
        state, _ = self.store.get_json("ledger", job_key(self.queue.messages[-1]["reportId"]))
        self.assertEqual(state["status"], "Failed")

    def test_old_ready_dryrun_mode_and_bad_source_interval_rejected(self):
        report_id = self.ready()
        state, _ = self.store.get_json("ledger", job_key(report_id))
        for key, value in (("mode", "dryrun"), ("sourceEndUtc", FIRST_BOUNDARY),
                           ("sourceStartUtc", "2026-07-25T06:00:00Z"),
                           ("boundaryUtc", "2026-07-25T07:00:00Z")):
            altered = copy.deepcopy(state)
            altered["job"][key] = value
            self.replace_json("ledger", job_key(report_id), altered)
            with self.assertRaises((ControlledError, ValueError)):
                self.dispatcher.dispatch_tick()
        self.assertEqual(self.mailer.calls, [])

    def test_ready_deadlines_and_original_evidence_hash_enforced(self):
        report_id = self.ready()
        state, _ = self.store.get_json("ledger", job_key(report_id))
        for key, value in (("createdUtc", stamp(CUTOFF - dt.timedelta(seconds=1))),
                           ("freezeAtUtc", stamp(CUTOFF - dt.timedelta(seconds=1))),
                           ("extractedUtc", stamp(BOUNDARY)),
                           ("finishedUtc", stamp(BOUNDARY)),
                           ("evidenceSha256", "0" * 64),
                           ("dispatchIntegritySha256", "0" * 64)):
            self.replace_json("ledger", job_key(report_id), {**state, key: value})
            with self.assertRaises(ControlledError):
                self.dispatcher.dispatch_tick()
        self.assertEqual(self.mailer.calls, [])

    def test_missing_immutable_integrity_receipt_rejected(self):
        report_id = self.ready()
        del self.store.data[("reports", report_id + "/dispatch-integrity.json")]
        with self.assertRaisesRegex(ControlledError, "integrity receipt"):
            self.dispatcher.dispatch_tick()
        self.assertEqual(self.mailer.calls, [])

    def test_body_subject_html_tamper_rejected_even_with_resealed_metadata(self):
        report_id = self.ready()
        for field in ("body", "htmlBody", "subject"):
            with self.subTest(field=field):
                self.alter_envelope(report_id, lambda e, field=field: e.update({field: e[field] + " changed"}),
                                    reseal=True)
                with self.assertRaisesRegex(ControlledError, "approved renderer"):
                    self.dispatcher.dispatch_tick()
                self.alter_envelope(report_id, lambda e, field=field: e.update(
                    {field: e[field][:-len(" changed")]}), reseal=True)
        self.assertEqual(self.mailer.calls, [])

    def test_summary_tamper_not_authorized_by_template_version(self):
        report_id = self.ready()
        self.alter_envelope(report_id, lambda e: e["emailSummary"].update(
            {"status": "MONITORED SIGNALS NORMAL"}))
        with self.assertRaisesRegex(ControlledError, "integrity receipt"):
            self.dispatcher.dispatch_tick()
        self.assertEqual(self.mailer.calls, [])

    def test_branding_summary_tamper_rejected_even_when_resealed(self):
        report_id = self.ready()
        self.alter_envelope(report_id, lambda e: e["emailSummary"].update({"motto": "changed"}),
                            reseal=True)
        with self.assertRaisesRegex(ControlledError, "branding/health/provenance"):
            self.dispatcher.dispatch_tick()

    def test_recipient_sender_template_logo_metadata_rejected(self):
        report_id = self.ready()
        original = copy.deepcopy(self.store.data)
        changes = [
            lambda e: e.update(to=["other@example.com"]),
            lambda e: e.update(sender="other@example.com"),
            lambda e: e.update(templateVersion="hv-table-email-v2"),
            lambda e: e["inlineAssets"][0].update(sha256="0" * 64),
            lambda e: e["inlineAssets"][0].update(contentId="other"),
            lambda e: e.update(inlineAssets=e["inlineAssets"][:1]),
        ]
        for change in changes:
            self.store.data = copy.deepcopy(original)
            self.alter_envelope(report_id, change, reseal=True)
            with self.assertRaises(ControlledError):
                self.dispatcher.dispatch_tick()
        self.assertEqual(self.mailer.calls, [])

    def test_artifact_and_inline_bytes_tamper_no_submission(self):
        report_id = self.ready()
        envelope, _ = self.store.get_json("reports", report_id + "/envelope.json")
        for asset in envelope["attachments"] + envelope["inlineAssets"]:
            key = ("reports", asset["blob"])
            original = self.store.data[key]
            self.store.data[key] = (b"tampered", "other")
            with self.assertRaisesRegex(ControlledError, "Attachment integrity"):
                self.dispatcher.dispatch_tick()
            self.store.data[key] = original
        self.assertEqual(self.mailer.calls, [])

    def test_mandatory_pdf_xlsx_names_types_positive_sizes_and_budget(self):
        report_id = self.ready()
        original = copy.deepcopy(self.store.data)
        changes = [
            lambda e: e.update(attachments=e["attachments"][:1]),
            lambda e: e["attachments"][0].update(contentType="text/plain"),
            lambda e: e["attachments"][0].update(size=-1),
            lambda e: e["attachments"][0].update(size=6 * 1024 * 1024),
            lambda e: e["attachments"][0].update(name="other.pdf"),
        ]
        for change in changes:
            self.store.data = copy.deepcopy(original)
            self.alter_envelope(report_id, change, reseal=True)
            with self.assertRaises(ControlledError):
                self.dispatcher.dispatch_tick()
        self.assertEqual(self.mailer.calls, [])

    def test_pinned_file_change_or_logo_change_invalidates_enabled_policy(self):
        for target in ("automation.fingerprints", "automation.brand_images"):
            with patch(target, return_value={} if target.endswith("fingerprints") else []):
                result = automation_status(enabled(), CUTOFF)
                self.assertEqual(result["status"], "InvalidPolicy")
                self.assertFalse(result["effectiveAutoSend"])
                with self.assertRaises(ControlledError):
                    self.producer.collection_tick()
        self.assertEqual(self.queue.messages, [])

    def test_policy_pin_and_immutable_approval_metadata(self):
        policy, digest = load_policy(enabled())
        self.assertEqual(policy["approval"], APPROVAL)
        self.assertEqual(digest, sha(POLICY_PATH.read_bytes()))
        altered = copy.deepcopy(policy)
        altered["approval"]["approvedAt"] = "2026-07-25T00:00:00Z"
        with patch.object(type(POLICY_PATH), "read_bytes", return_value=canonical(altered)):
            with self.assertRaisesRegex(ControlledError, "approval/contract"):
                load_policy(enabled())

    def test_approved_revision_preserves_history_and_distinguishes_manual_approval(self):
        policy, _ = load_policy(enabled())
        self.assertEqual(policy["envelopeSchemaVersion"], 3)
        self.assertEqual(policy["reportFiles"], [".pdf", ".xlsx", "-workbook.pdf"])
        self.assertEqual(policy["approval"], APPROVAL)
        self.assertEqual(policy["revision"]["status"], "awaiting-operator-activation")
        self.assertEqual(policy["revision"]["userReply"], "Example approval reply recorded by the operator")
        self.assertIn("not manual test dispatch", policy["revision"]["approvalScope"])
        self.assertIn("not a new preview approval", policy["revision"]["approvalMeaning"])
        from dataclasses import replace
        with self.assertRaisesRegex(ControlledError, "AUTO_SEND_POLICY_SHA256"):
            load_policy(replace(enabled(), auto_send_policy_sha256=
                                policy["revision"]["previousPolicySha256"]))

    def test_missing_workbook_pdf_metadata_rejected_even_with_resealed_receipt(self):
        report_id = self.ready()
        self.alter_envelope(report_id, lambda e: e.update(
            attachments=[a for a in e["attachments"] if not a["name"].endswith("-workbook.pdf")]),
            reseal=True)
        with self.assertRaisesRegex(ControlledError, "count"):
            self.dispatcher.dispatch_tick()
        self.assertEqual(self.mailer.calls, [])
        self.assertIsNone(self.store.get_json("ledger", dispatch_key(report_id))[0])

    def test_durable_concurrent_claim_sends_only_once(self):
        report_id = self.ready()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.dispatcher.dispatch_tick(), range(4)))
        self.assertEqual(sum(not r.get("deduplicated", False) for r in results), 1)
        self.assertEqual(len(self.mailer.calls), 1)
        self.assertEqual(self.dispatcher.status(report_id)["dispatch"]["policyId"], POLICY_ID)

    def test_uncertain_submission_never_blindly_resends(self):
        report_id = self.ready()
        self.mailer.fail = True
        with self.assertRaisesRegex(ControlledError, "no resend"):
            self.dispatcher.dispatch_tick()
        self.assertEqual(self.dispatcher.dispatch_tick()["status"], "DeliveryUncertain")
        self.dispatcher.clock = lambda: BOUNDARY + dt.timedelta(days=1)
        self.approve(report_id)
        self.assertEqual(self.dispatcher.dispatch(report_id)["status"], "DeliveryUncertain")
        self.assertEqual(len(self.mailer.calls), 1)

    def test_missing_ready_records_failure_without_notice_or_stale_substitution(self):
        with self.assertRaisesRegex(ControlledError, "not Ready"):
            self.dispatcher.dispatch_tick()
        self.assertEqual(self.mailer.calls, [])
        self.assertEqual(self.dispatcher.dispatch_tick()["status"], "Failed")

    def test_interrupted_sending_claim_becomes_uncertain_with_policy_retained(self):
        report_id = self.ready()
        self.store.create_json("ledger", dispatch_key(report_id), {
            "status": "Sending", "reportId": report_id, "policyId": POLICY_ID,
            "policySha256": sha(POLICY_PATH.read_bytes()),
            "firstSentUtc": stamp(BOUNDARY - dt.timedelta(minutes=4))})
        self.assertEqual(self.dispatcher.dispatch_tick()["status"], "DeliveryUncertain")
        self.assertEqual(self.mailer.calls, [])
        claim, _ = self.store.get_json("ledger", dispatch_key(report_id))
        self.assertEqual(claim["policyId"], POLICY_ID)

    def test_automation_read_only_and_first_boundary_times(self):
        before = copy.deepcopy(self.store.data)
        result = automation_status(enabled("producer"), parse_utc("2026-07-25T10:10:00Z"))
        self.assertEqual(result["status"], "Enabled")
        self.assertTrue(result["policyVerified"])
        self.assertTrue(result["formatVerified"])
        self.assertEqual(result["nextCollection"], {"utc": "2026-07-25T14:55:00Z",
                                                  "lt": "2026-07-25 21:55 LT"})
        self.assertEqual(result["nextDispatch"], {"utc": FIRST_BOUNDARY,
                                                "lt": "2026-07-25 22:00 LT"})
        self.assertEqual(result["firstBoundary"], result["nextDispatch"])
        self.assertEqual(len(result["fingerprints"]), 20)
        self.assertEqual(before, self.store.data)
        self.assertEqual(self.sources.calls, [])
        self.assertEqual(self.mailer.calls, [])

    def test_six_am_lt_date_crossing_and_cutoff(self):
        result = automation_status(enabled(), parse_utc("2026-07-25T15:01:00Z"))
        self.assertEqual(result["nextDispatch"], {"utc": "2026-07-25T23:00:00Z",
                                                "lt": "2026-07-26 06:00 LT"})
        self.assertEqual(result["nextCollection"], {"utc": "2026-07-25T22:55:00Z",
                                                  "lt": "2026-07-26 05:55 LT"})
        moment = parse_utc(result["nextCollection"]["utc"])
        self.producer.clock = lambda: moment
        self.sources = Sources(new_job("scheduled", moment, "2026-07-25T23:00:00Z"))
        self.producer.sources = self.sources
        report_id = self.ready()
        self.dispatcher.clock = lambda: parse_utc("2026-07-25T23:00:00Z")
        self.assertEqual(self.dispatcher.dispatch_tick()["status"], "Submitted")
        self.assertEqual(report_id, "shift-20260725T230000Z")
        self.assertIn("26 Jul 2026 - Cutoff 05:55 LT", self.mailer.calls[0][0]["subject"])
        job = self.queue.messages[-1]
        self.assertEqual(job["sourceStartUtc"], "2026-07-25T15:00:00Z")
        self.assertEqual(job["sourceEndUtc"], "2026-07-25T22:55:00Z")

    def test_next_time_rollover_exact_minutes_and_non_utc_clock(self):
        result = automation_status(enabled(), BOUNDARY.astimezone(LT))
        self.assertEqual(result["nextDispatch"]["utc"], FIRST_BOUNDARY)
        self.assertEqual(result["nextCollection"]["utc"], "2026-07-25T22:55:00Z")
        result = automation_status(enabled(), CUTOFF + dt.timedelta(seconds=45))
        self.assertEqual(result["nextCollection"]["utc"], stamp(CUTOFF))
        result = automation_status(enabled(), parse_utc("2026-07-25T23:01:00Z"))
        self.assertEqual(result["nextDispatch"]["utc"], "2026-07-26T07:00:00Z")
        self.assertEqual(result["nextDispatch"]["lt"], "2026-07-26 14:00 LT")
        early = automation_status(enabled(), parse_utc("2026-07-09T00:00:00Z"))
        self.assertEqual(early["nextDispatch"]["utc"], FIRST_BOUNDARY)


class AutomationFunctionTests(OfflineCase):
    def module(self, kind):
        import function_app
        with patch.dict(os.environ, {"APP_KIND": kind}, clear=True):
            return importlib.reload(function_app)

    def test_function_auth_get_both_apps_and_unchanged_safe_timers(self):
        for kind in ("producer", "dispatcher"):
            module = self.module(kind)
            bindings = [b for f in module.app.get_functions()
                        for b in json.loads(f.get_function_json())["bindings"]]
            automation = next(b for b in bindings if b.get("route") == "automation")
            self.assertEqual([method.lower() for method in automation["methods"]], ["get"])
            self.assertEqual(automation["authLevel"].lower(), "function")
            self.assertTrue(all(not b["runOnStartup"] and b["useMonitor"]
                                for b in bindings if b["type"] == "timerTrigger"))
            with patch.object(module, "runtime", side_effect=AssertionError("Must not construct clients")), \
                    patch.object(module.Settings, "load", return_value=enabled(kind)), \
                    patch.object(module, "utcnow", return_value=CUTOFF):
                response = module.automation(func.HttpRequest("GET", "http://localhost/api/automation", body=b""))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.get_body())["policyId"], POLICY_ID)
            self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_invalid_policy_http_explicit_failure_not_success_fallback(self):
        module = self.module("dispatcher")
        from dataclasses import replace
        with patch.object(module.Settings, "load", return_value=replace(enabled(), auto_send_policy_sha256="")), \
                patch.object(module, "utcnow", return_value=CUTOFF):
            response = module.automation(func.HttpRequest("GET", "http://localhost/api/automation", body=b""))
        self.assertEqual(response.status_code, 409)
        result = json.loads(response.get_body())
        self.assertEqual(result["status"], "InvalidPolicy")
        self.assertFalse(result["effectiveAutoSend"])
        self.assertIsNone(result["nextDispatch"])

    def test_http_post_dispatch_cannot_request_automatic_bypass(self):
        module = self.module("dispatcher")
        for body in ({"reportId": "shift-20260725T150000Z", "scheduled": True},
                     {"reportId": "shift-20260725T150000Z", "autoSend": True}):
            with patch.object(module, "runtime") as runtime:
                response = module.dispatch(func.HttpRequest("POST", "http://localhost/api/dispatch",
                                                           body=canonical(body)))
                runtime.assert_not_called()
            self.assertEqual(response.status_code, 400)
