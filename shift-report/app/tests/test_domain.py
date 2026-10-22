import copy
import datetime as dt
import os
from unittest.mock import patch

from domain import (ControlledError, MACHINES, MAX_ATTACHMENTS, Settings, UTC, assess,
                    build_envelope, canonical, due_boundary, local_time, new_job, parse_utc,
                    sha, stamp, sustained, valid_id, validate_job, verify_approval)
from tests.fakes import NOW, OfflineCase, datasets, evidence, job, settings


class ShiftTests(OfflineCase):
    def test_midnight_nominal_start_and_local_time(self):
        j = job()
        self.assertEqual(j["sourceStartUtc"], "2026-07-24T23:00:00Z")
        self.assertEqual(j["sourceEndUtc"], "2026-07-25T06:55:00Z")
        self.assertEqual(local_time(j["boundaryUtc"]), "2026-07-25 14:00 LT")
        night = new_job("scheduled", NOW.replace(hour=22), "2026-07-25T23:00:00Z")
        self.assertEqual(local_time(night["boundaryUtc"]), "2026-07-26 06:00 LT")
        self.assertEqual(night["nominalStartUtc"], "2026-07-25T15:00:00Z")

    def test_all_three_boundaries_cutoff(self):
        for hour in (7, 15, 23):
            j = new_job("scheduled", NOW.replace(hour=hour-1), f"2026-07-25T{hour:02}:00:00Z")
            self.assertEqual(parse_utc(j["boundaryUtc"]) - parse_utc(j["sourceEndUtc"]), dt.timedelta(minutes=5))
            validate_job(j)

    def test_no_backfill_or_future(self):
        for now in (NOW - dt.timedelta(minutes=1), NOW + dt.timedelta(minutes=5),
                    NOW + dt.timedelta(days=1)):
            with self.assertRaises(ValueError):
                new_job("scheduled", now, "2026-07-25T07:00:00Z")
        self.assertIsNone(due_boundary(NOW + dt.timedelta(minutes=1), "collect"))
        self.assertIsNone(due_boundary(NOW.replace(hour=7, minute=1), "dispatch"))
        self.assertEqual(due_boundary(NOW, "collect"), parse_utc("2026-07-25T07:00:00Z"))

    def test_timer_phases_exact(self):
        self.assertEqual(due_boundary(NOW.replace(minute=50), "preflight"), parse_utc(job()["boundaryUtc"]))
        self.assertEqual(due_boundary(NOW.replace(hour=7, minute=0), "dispatch"), parse_utc(job()["boundaryUtc"]))
        self.assertIsNone(due_boundary(NOW, "dispatch"))

    def test_dryrun_current_clock_unique_and_labelled(self):
        a, b = new_job("dryrun", NOW), new_job("dryrun", NOW)
        self.assertNotEqual(a["reportId"], b["reportId"])
        self.assertEqual(a["boundaryUtc"], stamp(NOW))
        self.assertEqual(a["sourceEndUtc"], "2026-07-25T06:50:00Z")
        with self.assertRaises(ValueError):
            new_job("dryrun", NOW, "2026-07-24T07:00:00Z")

    def test_utc_validation_and_path_safety(self):
        for value in ("2026-07-25T07:00:00", "2026-07-25T14:00:00+07:00"):
            with self.assertRaises(ValueError):
                parse_utc(value)
        for value in ("../report", "shift-20260725T060000Z", "x", None):
            with self.assertRaises(ValueError):
                valid_id(value)
        j = job()
        j["sourceEndUtc"] = "2026-07-25T07:00:00Z"
        with self.assertRaises(ValueError):
            validate_job(j)


class HealthTests(OfflineCase):
    def test_complete_baseline_healthy(self):
        self.assertEqual(assess(datasets(), job())["status"], "MONITORED SIGNALS NORMAL")

    def test_each_of_14_missing_and_stale_never_green(self):
        for index in range(14):
            for mode in ("missing", "stale"):
                data = datasets()
                if mode == "missing":
                    data["data-quality"].pop(index)
                else:
                    data["data-quality"][index]["Latest"] = "2026-07-25T06:40:00Z"
                result = assess(data, job())
                self.assertEqual(result["status"], "INSUFFICIENT EVIDENCE")
                self.assertEqual(result["freshSignals"], 13)

    def test_empty_and_old_metric_not_healthy(self):
        for dataset, value in (("memory", []), ("cpu", [])):
            data = datasets()
            data[dataset] = value
            self.assertEqual(assess(data, job())["status"], "INSUFFICIENT EVIDENCE")
        data = datasets()
        data["cpu"] = [r for r in data["cpu"] if r["TimeGenerated"] < "2026-07-25T06:45:00Z"]
        self.assertEqual(assess(data, job())["status"], "INSUFFICIENT EVIDENCE")

    def test_plot_peak_does_not_replace_raw_alert_window_evaluation(self):
        data = datasets()
        host = [r for r in data["cpu"] if r["Computer"] == MACHINES[0]]
        host[5]["Value"] = 99.
        self.assertEqual(assess(data, job())["status"], "MONITORED SIGNALS NORMAL")
        row = next(r for r in data["alert-health"] if r["RuleName"] == "hv-host-cpu-high")
        row.update(Triggered=True, Value=81)
        self.assertEqual(assess(data, job())["status"], "ATTENTION REQUIRED")
        row = next(r for r in data["alert-health"] if r["RuleName"] == "hv-host-cpu-critical")
        row.update(Triggered=True, Value=91)
        self.assertEqual(assess(data, job())["status"], "CRITICAL CONDITION OBSERVED")

    def test_duration_gap_and_strict_threshold(self):
        rows = [{"TimeGenerated": f"2026-07-25T06:{minute:02}:00Z", "Value": 90.}
                for minute in (0, 5, 15)]
        self.assertFalse(sustained(rows, "Value", 85))
        rows[-1]["TimeGenerated"] = "2026-07-25T06:10:00Z"
        self.assertTrue(sustained(rows, "Value", 85))
        self.assertFalse(sustained(rows, "Value", 90))

    def test_sql_peak_grants_not_sustained(self):
        data = datasets()
        for r in data["sql-memory"][:3]:
            r["PendingGrants"] = 1
        self.assertEqual(assess(data, job())["status"], "MONITORED SIGNALS NORMAL")
        row = next(r for r in data["alert-health"] if r["RuleName"] == "hv-sql-grants-pending")
        row.update(Triggered=True, Value=1)
        result = assess(data, job())
        self.assertEqual(result["status"], "ATTENTION REQUIRED")
        self.assertIn("over 5m", result["sustainedFindings"][0])

    def test_missing_alert_evaluation_cannot_be_normal(self):
        data = datasets()
        data["alert-health"].pop()
        self.assertEqual(assess(data, job())["status"], "INSUFFICIENT EVIDENCE")

    def test_ct_inventory_is_open_not_required_15th(self):
        data = datasets()
        data["data-quality"].append({"Computer": "SQL2019-GUEST", "Stream": "CT service inventory",
                                      "Quality": "INVENTORY SNAPSHOT", "Samples": 1})
        result = assess(data, job())
        self.assertEqual(result["requiredSignals"], 14)
        self.assertEqual(result["status"], "MONITORED SIGNALS NORMAL")
        self.assertEqual(result["bpa"], "Not assessed yet")

    def test_sparse_required_stream_buckets_not_healthy(self):
        data = datasets()
        data["data-quality"][-1]["ObservedBuckets"] = 1
        self.assertEqual(assess(data, job())["status"], "INSUFFICIENT EVIDENCE")
        data["data-quality"][-1]["ObservedBuckets"] = None
        self.assertEqual(assess(data, job())["status"], "INSUFFICIENT EVIDENCE")

    def test_empty_supporting_report_datasets_not_green(self):
        for key in ("sql-grants", "storage", "sql-activity", "contention", "cluster-storage"):
            data = datasets()
            data[key] = []
            self.assertEqual(assess(data, job())["status"], "INSUFFICIENT EVIDENCE")


class EnvelopeTests(OfflineCase):
    def pair(self):
        return [{"name": "report.pdf", "blob": "x/report.pdf", "size": 100, "sha256": "1"*64,
                 "contentType": "application/pdf"},
                {"name": "report.xlsx", "blob": "x/report.xlsx", "size": 100, "sha256": "2"*64,
                 "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}]

    def test_exact_canonical_envelope_approval(self):
        e = build_envelope(settings(), evidence(), self.pair())
        a = {"reportId": e["reportId"], "to": e["to"], "approved": True, "envelopeSha256": sha(canonical(e))}
        verify_approval(a, e)
        e["body"] += "changed"
        with self.assertRaises(ControlledError):
            verify_approval(a, e)

    def test_individual_hash_approval(self):
        e = build_envelope(settings(), evidence(), self.pair())
        a = {"reportId": e["reportId"], "to": e["to"], "approved": True, "sender": e["sender"],
             "subjectSha256": sha(e["subject"].encode()), "bodySha256": sha(e["body"].encode()),
             "attachments": e["attachments"]}
        verify_approval(a, e)
        a["attachments"] = copy.deepcopy(a["attachments"])
        a["attachments"][0]["sha256"] = "bad"
        with self.assertRaises(ControlledError):
            verify_approval(a, e)

    def test_sender_recipient_size_and_excel_required(self):
        for s in (settings(sender=""), settings(recipients=("other@example.com",))):
            with self.assertRaises(ControlledError):
                build_envelope(s, evidence(), self.pair())
        with self.assertRaises(ControlledError):
            build_envelope(settings(), evidence(), self.pair()[:1])
        pair = self.pair()
        pair[0]["size"] = MAX_ATTACHMENTS
        with self.assertRaises(ControlledError):
            build_envelope(settings(), evidence(), pair)

    def test_rehearsal_subject_and_utc_cutoff(self):
        e = build_envelope(settings(), evidence(new_job("dryrun", NOW)), self.pair())
        self.assertIn("REHEARSAL", e["subject"])
        self.assertIn("NOT A SCHEDULED SHIFT", e["subject"])
        self.assertIn("2026-07-25T06:50:00Z", e["body"])
        self.assertEqual(e["sender"], "sender@example.com")

    def test_environment_defaults_and_fail_closed(self):
        env = {"APP_KIND": "dispatcher", "REPORT_STORAGE_ACCOUNT": "hvreports"}
        with patch.dict(os.environ, env, clear=True):
            s = Settings.load()
            self.assertFalse(s.send_enabled)
            self.assertFalse(s.schedule_enabled)
            self.assertEqual(s.recipients, ("operator@example.com",))
            os.environ["RECIPIENT_ALLOWLIST"] = "other@example.com"
            with self.assertRaises(ValueError):
                Settings.load()
        with patch.dict(os.environ, {**env, "ACS_ENDPOINT": "http://unsafe"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.load()
