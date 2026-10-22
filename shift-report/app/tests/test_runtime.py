import copy
import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from domain import Conflict, ControlledError, MAX_ATTACHMENTS, canonical, sha, stamp
from runtime import Runtime, dispatch_key, job_key
from tests.fakes import NOW, Mailer, OfflineCase, Queue, Sources, Store, job, settings


class RuntimeTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.store, self.queue, self.sources, self.mailer = Store(), Queue(), Sources(), Mailer()
        self.producer = Runtime(settings(schedule_enabled=True), self.store, self.sources, self.queue,
                                clock=lambda: NOW)
        self.dispatcher = Runtime(settings("dispatcher", send_enabled=True, schedule_enabled=True),
                                  self.store, mailer=self.mailer, clock=lambda: NOW + dt.timedelta(minutes=5))

    def prepare(self):
        return self.producer.prepare({"mode": "scheduled", "boundary": job()["boundaryUtc"]})

    def ready(self):
        prepared = self.prepare()
        self.producer.generate(self.queue.messages[0])
        return prepared["reportId"]

    def approve(self, report_id):
        preview = self.dispatcher.preview(report_id)
        self.store.create_json("approvals", report_id + ".json", {
            "reportId": report_id, "approved": True, "to": preview["to"],
            "envelopeSha256": preview["envelopeSha256"]})

    def test_prepare_fast_queue_only_and_scheduled_dedup(self):
        first, second = self.prepare(), self.prepare()
        self.assertFalse(first["deduplicated"])
        self.assertTrue(second["deduplicated"])
        self.assertEqual(len(self.queue.messages), 1)
        self.assertEqual(self.sources.calls, [])
        self.assertEqual(self.producer.status(first["reportId"])["status"], "Queued")

    def test_prepare_queue_uncertainty_is_durable_failure(self):
        self.queue.fail = True
        with self.assertRaises(ControlledError):
            self.prepare()
        status = self.producer.status(job()["reportId"])
        self.assertEqual(status["status"], "Failed")
        self.assertNotIn("private token", json.dumps(status))
        self.assertTrue(self.prepare()["deduplicated"])

    def test_invalid_prepare_and_kind_gates(self):
        with self.assertRaises(ValueError):
            self.producer.prepare({"mode": "dryrun", "to": "other@example.com"})
        with self.assertRaises(ControlledError):
            self.dispatcher.prepare({"mode": "dryrun"})
        with self.assertRaises(ControlledError):
            self.producer.dispatch(job()["reportId"])

    def test_full_generation_immutable_pair_and_hashes(self):
        report_id = self.ready()
        state, _ = self.store.get_json("ledger", job_key(report_id))
        snapshot, _ = self.store.get("evidence", report_id + "/snapshot.json")
        self.assertEqual(state["status"], "Ready")
        self.assertEqual(state["evidenceSha256"], sha(snapshot))
        self.assertEqual(state["health"]["status"], "MONITORED SIGNALS NORMAL")
        self.assertEqual(len(self.sources.calls), 17)
        self.assertEqual(state["nativeChartPages"], 8)
        self.assertEqual(len(state["attachments"]), 3)
        for item in state["attachments"]:
            data, _ = self.store.get("reports", item["blob"])
            self.assertEqual(item["sha256"], sha(data))
            self.assertEqual(item["size"], len(data))
        self.producer.generate(self.queue.messages[0])
        self.assertEqual(self.sources.rendered, 1)
        with self.assertRaises(Conflict):
            self.store.create("evidence", report_id + "/snapshot.json", b"replacement")

    def test_generation_claim_concurrent_only_one_build(self):
        self.prepare()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.producer.generate(self.queue.messages[0]), range(4)))
        self.assertEqual(sum(r.get("status") == "Ready" and not r.get("deduplicated") for r in results), 1)
        self.assertEqual(self.sources.rendered, 1)

    def test_authenticated_artifact_read_does_not_send_or_approve(self):
        report_id = self.ready()
        attachments = self.dispatcher.preview(report_id)["attachments"]
        for attachment in attachments:
            data, metadata = self.dispatcher.artifact(report_id, attachment["name"])
            self.assertEqual(sha(data), attachment["sha256"])
            self.assertEqual(metadata, attachment)
        self.assertEqual(self.mailer.calls, [])
        self.assertIsNone(self.store.get_json("approvals", report_id + ".json")[0])
        for name in ("envelope.json", "../snapshot.json", "report.pdf", None):
            with self.assertRaises(ControlledError):
                self.dispatcher.artifact(report_id, name)

    def test_artifact_tamper_fails(self):
        report_id = self.ready()
        attachment = self.dispatcher.preview(report_id)["attachments"][0]
        self.store.data[("reports", attachment["blob"])] = (b"tampered", "changed")
        with self.assertRaises(ControlledError):
            self.dispatcher.artifact(report_id, attachment["name"])

    def test_queue_payload_tamper_rejected(self):
        self.prepare()
        altered = copy.deepcopy(self.queue.messages[0])
        altered["jobId"] = "other"
        with self.assertRaises(ControlledError):
            self.producer.generate(altered)
        self.assertEqual(self.sources.calls, [])

    def test_source_failure_no_success_fallback_or_leaked_error(self):
        self.sources.fail = "memory"
        self.prepare()
        with self.assertRaises(RuntimeError):
            self.producer.generate(self.queue.messages[0])
        status = self.producer.status(job()["reportId"])
        self.assertEqual(status["status"], "Failed")
        self.assertNotIn("credential", json.dumps(status))
        self.assertEqual(self.sources.rendered, 0)

    def test_missed_queue_shift_no_backfill(self):
        self.prepare()
        self.producer.clock = lambda: NOW + dt.timedelta(minutes=5)
        with self.assertRaises(ControlledError):
            self.producer.generate(self.queue.messages[0])
        self.assertEqual(self.producer.status(job()["reportId"])["status"], "Failed")
        self.assertEqual(self.sources.calls, [])

    def test_preview_exact_never_sends(self):
        report_id = self.ready()
        preview = self.dispatcher.preview(report_id)
        stored, _ = self.store.get_json("reports", report_id + "/envelope.json")
        for key in stored:
            self.assertEqual(preview[key], stored[key])
        self.assertEqual(preview["allowedReportId"], report_id)
        self.assertEqual(preview["to"], ["operator@example.com"])
        self.assertEqual(self.mailer.calls, [])

    def test_send_disabled_or_missing_approval_fails_closed(self):
        report_id = self.ready()
        self.dispatcher.settings = settings("dispatcher")
        with self.assertRaises(ControlledError):
            self.dispatcher.dispatch(report_id)
        self.dispatcher.settings = settings("dispatcher", send_enabled=True)
        with self.assertRaises(ControlledError):
            self.dispatcher.dispatch(report_id)
        self.assertEqual(self.mailer.calls, [])

    def test_dispatch_submitted_not_delivered_and_never_duplicate(self):
        report_id = self.ready()
        self.approve(report_id)
        result = self.dispatcher.dispatch(report_id)
        self.assertEqual(result["status"], "Submitted")
        self.assertIn("NOT Delivered", result["submissionMeaning"])
        self.assertTrue(self.dispatcher.dispatch(report_id)["deduplicated"])
        self.assertEqual(len(self.mailer.calls), 1)

    def test_dispatch_concurrency_only_one_send(self):
        report_id = self.ready()
        self.approve(report_id)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.dispatcher.dispatch(report_id), range(8)))
        self.assertEqual(len(self.mailer.calls), 1)
        self.assertEqual(sum(not r.get("deduplicated") for r in results), 1)

    def test_timeout_delivery_uncertain_never_resends_even_after_window(self):
        report_id = self.ready()
        self.approve(report_id)
        self.mailer.fail = True
        with self.assertRaises(ControlledError):
            self.dispatcher.dispatch(report_id)
        self.dispatcher.clock = lambda: NOW + dt.timedelta(days=1)
        self.assertEqual(self.dispatcher.dispatch(report_id)["status"], "DeliveryUncertain")
        self.assertEqual(len(self.mailer.calls), 1)

    def test_interrupted_sending_converts_to_uncertain_without_send(self):
        report_id = self.ready()
        self.approve(report_id)
        self.store.create_json("ledger", dispatch_key(report_id), {
            "reportId": report_id, "status": "Sending", "firstSentUtc": stamp(NOW)})
        result = self.dispatcher.dispatch(report_id)
        self.assertEqual(result["status"], "DeliveryUncertain")
        self.assertEqual(self.mailer.calls, [])

    def test_tampered_attachment_no_send(self):
        report_id = self.ready()
        self.approve(report_id)
        ledger, _ = self.store.get_json("ledger", job_key(report_id))
        name = ledger["attachments"][0]["blob"]
        self.store.data["reports", name] = (b"corrupt", "new")
        with self.assertRaises(ControlledError):
            self.dispatcher.dispatch(report_id)
        self.assertEqual(self.mailer.calls, [])

    def test_tampered_inline_image_no_send(self):
        report_id = self.ready()
        self.approve(report_id)
        image = self.dispatcher.preview(report_id)["inlineAssets"][0]
        self.store.data[("reports", image["blob"])] = (b"corrupt", "new")
        with self.assertRaises(ControlledError):
            self.dispatcher.dispatch(report_id)
        self.assertEqual(self.mailer.calls, [])

    def test_dispatch_preserves_full_approved_html_envelope(self):
        report_id = self.ready()
        preview = self.dispatcher.preview(report_id)
        self.approve(report_id)
        self.dispatcher.dispatch(report_id)
        sent = self.mailer.calls[0][0]
        self.assertEqual(sent["htmlBody"], preview["htmlBody"])
        self.assertEqual(sent["inlineAssets"], preview["inlineAssets"])
        self.assertEqual(sha(canonical(sent)), preview["envelopeSha256"])

    def test_missing_ready_fails_no_stale_report_or_notice(self):
        with self.assertRaises(ControlledError):
            self.dispatcher.dispatch(job()["reportId"])
        ledger, _ = self.store.get_json("ledger", dispatch_key(job()["reportId"]))
        self.assertEqual(ledger["status"], "Failed")
        self.assertEqual(self.mailer.calls, [])

    def test_five_mib_never_omit_excel(self):
        self.prepare()
        with patch("runtime.merge_pdf", return_value=b"x" * MAX_ATTACHMENTS):
            with self.assertRaises(ControlledError):
                self.producer.generate(self.queue.messages[0])
        self.assertEqual(self.producer.status(job()["reportId"])["status"], "Failed")
        self.assertFalse(any(c == "reports" for c, _ in self.store.creates))

    def test_disabled_late_or_startup_timers_never_backfill(self):
        self.assertEqual(self.producer.collection_tick(True)["status"], "Skipped")
        self.producer.clock = lambda: NOW + dt.timedelta(minutes=1)
        self.assertEqual(self.producer.collection_tick()["status"], "Skipped")
        self.dispatcher.clock = lambda: NOW + dt.timedelta(minutes=6)
        self.assertEqual(self.dispatcher.dispatch_tick()["status"], "Skipped")
        self.assertEqual(self.queue.messages, [])
        self.assertEqual(self.mailer.calls, [])

    def test_preflight_once_and_past_due_skip(self):
        self.producer.clock = lambda: NOW.replace(minute=50)
        self.assertEqual(self.producer.preflight(True)["status"], "Skipped")
        self.assertEqual(self.producer.preflight()["status"], "Passed")
        self.assertEqual(self.producer.preflight()["status"], "Deduplicated")

    def test_interrupted_job_reconciles_durable_failed_on_status(self):
        self.prepare()
        self.producer.clock = lambda: NOW + dt.timedelta(minutes=16)
        self.assertEqual(self.producer.status(job()["reportId"])["status"], "Failed")
        self.assertEqual(self.producer.generate(self.queue.messages[0])["status"], "Failed")
        self.assertEqual(self.sources.calls, [])

    def test_original_pdf_and_xlsx_bytes_are_persisted_without_modification(self):
        from artifacts import merge_pdf, workbook
        originals = {}
        def original_book(*args):
            result = workbook(*args)
            originals[".xlsx"] = result[0]
            return result
        def original_pdf(*args):
            result = merge_pdf(*args)
            originals[".pdf"] = result
            return result
        with patch("runtime.workbook", side_effect=original_book), patch(
                "runtime.merge_pdf", side_effect=original_pdf):
            report_id = self.ready()
        for ending, expected in originals.items():
            actual, _ = self.dispatcher.artifact(report_id, f"HV-{report_id}{ending}")
            self.assertEqual(actual, expected)
        preview = self.dispatcher.preview(report_id)
        self.assertEqual(preview["schemaVersion"], 3)
        self.assertEqual(len(preview["attachments"]), 3)
        self.assertEqual(len(preview["inlineAssets"]), 2)
        receipt, _ = self.store.get_json("reports", report_id + "/dispatch-integrity.json")
        self.assertEqual(len(receipt["attachments"]), 3)

    def test_missing_or_changed_workbook_pdf_never_downloads_or_sends(self):
        report_id = self.ready()
        self.approve(report_id)
        attachment = next(a for a in self.dispatcher.preview(report_id)["attachments"]
                          if a["name"].endswith("-workbook.pdf"))
        key = ("reports", attachment["blob"])
        original = self.store.data[key]
        for missing in (True, False):
            if missing:
                del self.store.data[key]
            else:
                self.store.data[key] = (b"x" * attachment["size"], "changed-same-length")
            with self.assertRaisesRegex(ControlledError, "integrity"):
                self.dispatcher.artifact(report_id, attachment["name"])
            with self.assertRaisesRegex(ControlledError, "integrity"):
                self.dispatcher.dispatch(report_id)
            self.assertIsNone(self.store.get_json("ledger", dispatch_key(report_id))[0])
            self.store.data[key] = original
        self.assertEqual(self.mailer.calls, [])

    def test_removed_third_metadata_cannot_use_new_envelope_or_old_approval(self):
        report_id = self.ready()
        self.approve(report_id)
        envelope, tag = self.store.get_json("reports", report_id + "/envelope.json")
        envelope["attachments"] = [a for a in envelope["attachments"]
                                   if not a["name"].endswith("-workbook.pdf")]
        self.store.replace_json("reports", report_id + "/envelope.json", envelope, tag)
        state, tag = self.store.get_json("ledger", job_key(report_id))
        state.update(attachments=envelope["attachments"], envelopeSha256=sha(canonical(envelope)))
        self.store.replace_json("ledger", job_key(report_id), state, tag)
        with self.assertRaisesRegex(ControlledError, "count"):
            self.dispatcher.preview(report_id)
        with self.assertRaises(ControlledError):
            self.dispatcher.dispatch(report_id)
        self.assertEqual(self.mailer.calls, [])

    def test_changed_third_pdf_metadata_invalidates_existing_exact_approval(self):
        report_id = self.ready()
        self.approve(report_id)
        envelope, tag = self.store.get_json("reports", report_id + "/envelope.json")
        next(a for a in envelope["attachments"] if a["name"].endswith("-workbook.pdf"))["sha256"] = "1" * 64
        self.store.replace_json("reports", report_id + "/envelope.json", envelope, tag)
        state, tag = self.store.get_json("ledger", job_key(report_id))
        state.update(attachments=envelope["attachments"], envelopeSha256=sha(canonical(envelope)))
        self.store.replace_json("ledger", job_key(report_id), state, tag)
        with self.assertRaisesRegex(ControlledError, "approval"):
            self.dispatcher.dispatch(report_id)
        self.assertEqual(self.mailer.calls, [])

    def test_legacy_v2_pair_keeps_manual_download_and_approval_but_not_scheduled_send(self):
        report_id = self.ready()
        envelope, tag = self.store.get_json("reports", report_id + "/envelope.json")
        envelope["schemaVersion"] = 2
        envelope["attachments"] = [a for a in envelope["attachments"]
                                   if not a["name"].endswith("-workbook.pdf")]
        self.store.replace_json("reports", report_id + "/envelope.json", envelope, tag)
        state, tag = self.store.get_json("ledger", job_key(report_id))
        state.update(attachments=envelope["attachments"], envelopeSha256=sha(canonical(envelope)))
        self.store.replace_json("ledger", job_key(report_id), state, tag)
        preview = self.dispatcher.preview(report_id)
        for attachment in preview["attachments"]:
            self.dispatcher.artifact(report_id, attachment["name"])
        self.approve(report_id)
        with self.assertRaisesRegex(ControlledError, "three reports"):
            self.dispatcher.dispatch(report_id, scheduled=True)
        self.assertEqual(self.dispatcher.dispatch(report_id)["status"], "Submitted")
        self.assertEqual(len(self.mailer.calls[0][0]["attachments"]), 2)

    def test_converter_failure_is_durable_failed_and_never_omits_third_file(self):
        self.prepare()
        with patch("runtime.render_workbook_pdf", side_effect=ControlledError("No formula cache")):
            with self.assertRaisesRegex(ControlledError, "cache"):
                self.producer.generate(self.queue.messages[0])
        self.assertEqual(self.producer.status(job()["reportId"])["status"], "Failed")
        self.assertFalse(any(c == "reports" for c, _ in self.store.creates))
        self.assertTrue(self.producer.generate(self.queue.messages[0])["deduplicated"])

    def test_renderer_budget_accounts_for_original_documents_and_both_cid_images(self):
        from artifacts import merge_pdf, workbook
        from email_assets import brand_images
        from workbook_pdf import render_workbook_pdf
        totals = {}
        def original_book(*args):
            result = workbook(*args)
            totals["xlsx"] = len(result[0])
            return result
        def original_pdf(*args):
            result = merge_pdf(*args)
            totals["pdf"] = len(result)
            return result
        def converted(data, max_bytes):
            logos = sum(len(data) for _, data in brand_images())
            self.assertEqual(max_bytes, MAX_ATTACHMENTS - totals["pdf"] - totals["xlsx"] - logos)
            return render_workbook_pdf(data, max_bytes)
        with patch("runtime.workbook", side_effect=original_book), patch(
                "runtime.merge_pdf", side_effect=original_pdf), patch(
                "runtime.render_workbook_pdf", side_effect=converted):
            self.ready()
