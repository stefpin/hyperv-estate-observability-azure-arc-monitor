import copy
import datetime as dt
from html.parser import HTMLParser
import json
import unittest
from unittest.mock import patch

from domain import MACHINES
from email_template import present_email, subject
from tests.fakes import OfflineCase, evidence


class Markup(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.tags = []
        self.text = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, value):
        self.text.append(value)


class EmailTemplateTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.evidence = evidence()

    def render(self):
        return present_email(self.evidence)

    def section(self, title, result=None):
        result = result or self.render()
        return next(item for item in result["summary"]["sections"] if item["title"] == title)

    def test_fixture_contract_and_no_input_mutation(self):
        before = copy.deepcopy(self.evidence)
        with patch("builtins.open", side_effect=AssertionError("Presentation must not read files")):
            result = self.render()
        self.assertEqual(self.evidence, before)
        self.assertEqual(set(result), {"subject", "plainText", "html", "summary"})
        json.dumps(result, allow_nan=False)
        self.assertEqual(result, self.render())
        self.assertIn("Full PDF charts, Excel evidence and the workbook-content PDF are attached", result["plainText"])
        self.assertIn("Demonstration environment - not production.", result["html"])

    def test_subject_uses_lt_cutoff_date_not_boundary_date(self):
        job = self.evidence["job"]
        job.update(mode="dryrun", boundaryUtc="2026-07-25T17:02:03Z",
                   sourceEndUtc="2026-07-25T16:57:03Z",
                   sourceStartUtc="2026-07-25T09:02:03Z",
                   nominalStartUtc="2026-07-25T09:02:03Z")
        result = self.render()
        self.assertEqual(result["subject"],
                         "Hyper-V Estate - Shift Report - 25 Jul 2026 - Cutoff 23:57 LT [TEST]")
        self.assertIn("25 Jul 2026 23:57:03 LT", result["html"])
        self.assertIn("26 Jul 2026 00:02:03 LT", result["plainText"])
        self.assertIn("2026-07-25T16:57:03Z", result["plainText"])
        self.assertIn("<strong>TEST / REHEARSAL - not a scheduled shift</strong>", result["html"])

    def test_subject_across_utc_midnight_and_scheduled_not_test(self):
        self.evidence["job"]["sourceEndUtc"] = "2026-07-24T23:59:37Z"
        self.assertEqual(subject(self.evidence),
                         "Hyper-V Estate - Shift Report - 25 Jul 2026 - Cutoff 06:59 LT")
        self.assertNotIn("[TEST]", self.render()["subject"])
        self.assertNotIn("TEST / REHEARSAL", self.render()["html"])

    def test_branding_exact_visible_text_and_only_two_cid_images(self):
        result = self.render()
        markup = Markup(result["html"])
        images = [attrs for tag, attrs in markup.tags if tag == "img"]
        self.assertEqual([item["src"] for item in images], ["cid:brand-primary", "cid:brand-secondary"])
        self.assertEqual([item["alt"] for item in images], ["Hyper-V Estate Observability", "Azure Monitor"])
        visible = " ".join(markup.text)
        for text in ("Host-to-SQL observability", "Monitored with Azure Monitor"):
            self.assertIn(text, visible)
            self.assertIn(text, result["plainText"])
        self.assertIn('bgcolor="#003b70"', result["html"])
        self.assertIn('bgcolor="#ffffff"', result["html"])
        self.assertFalse({"script", "form", "iframe", "a", "link"} & {tag for tag, _ in markup.tags})
        for forbidden in ("https://", "http://", "data:", "javascript:", "var(--"):
            self.assertNotIn(forbidden, result["html"])

    def test_mobile_outlook_safe_table_layout(self):
        result = self.render()["html"]
        self.assertIn("max-width:760px", result)
        self.assertIn("width=device-width", result)
        self.assertIn("table-layout:fixed", result)
        self.assertIn("font-family:Segoe UI,Arial,sans-serif", result)
        self.assertNotIn("<style", result)
        markup = Markup(result)
        self.assertTrue(all(attrs.get("width") == "100%" and "style" in attrs
                            for tag, attrs in markup.tags if tag == "table"))
        self.assertTrue(all(attrs.get("scope") == "col" for tag, attrs in markup.tags if tag == "th"))

    def test_all_six_expected_machines_without_invented_machine_health(self):
        rows = self.section("Estate health")["rows"]
        self.assertEqual([row[0] for row in rows], list(MACHINES))
        self.assertEqual({row[1] for row in rows}, {"FRESH"})
        self.assertIn("14/14 fresh", self.render()["summary"]["freshness"])
        self.assertIn("6/6 fresh", self.render()["summary"]["freshness"])
        self.assertNotIn("Healthy", self.render()["plainText"])

    def test_missing_expected_machine_retains_row_with_na(self):
        target = "WIN2019-GUEST"
        for name in ("cpu", "memory", "summary", "data-quality"):
            self.evidence["datasets"][name] = [
                row for row in self.evidence["datasets"][name] if row.get("Computer") != target]
        self.evidence["health"].update(status="INSUFFICIENT EVIDENCE", freshSignals=12)
        row = next(row for row in self.section("Estate health")["rows"] if row[0] == target)
        self.assertEqual(row, [target, "MISSING", "N/A", "N/A", "N/A"])
        self.assertEqual(self.render()["summary"]["status"], "INSUFFICIENT EVIDENCE")
        self.assertIn("12/14 fresh", self.render()["plainText"])

    def test_stale_and_future_telemetry_never_fresh(self):
        quality = self.evidence["datasets"]["data-quality"]
        target = "RHEL94-GUEST"
        row = next(row for row in quality
                   if row["Computer"] == target and row["Stream"] == "Linux disk")
        for moment in ("2026-07-25T06:49:59Z", "2026-07-25T06:56:00Z"):
            row["Latest"] = moment
            estate = self.section("Estate health")["rows"]
            self.assertEqual(next(value[1] for value in estate if value[0] == target), "STALE")

    def test_freshness_boundary_is_relative_to_cutoff_not_clock(self):
        for row in self.evidence["datasets"]["data-quality"]:
            row["Latest"] = "2026-07-25T06:50:00Z"
        self.assertEqual({row[1] for row in self.section("Estate health")["rows"]}, {"FRESH"})
        with patch("email_template.dt.datetime", wraps=dt.datetime) as clock:
            self.render()
            clock.now.assert_not_called()

    def test_cpu_sample_weighted_average_primary_metric_and_5m_peak(self):
        self.evidence["datasets"]["cpu"] = [
            {"Computer": MACHINES[0], "Metric": "Host hypervisor CPU", "Unit": "percent",
             "TimeGenerated": "2026-07-25T06:45:00Z", "Value": 10, "Samples": 1},
            {"Computer": MACHINES[0], "Metric": "Host hypervisor CPU", "Unit": "percent",
             "TimeGenerated": "2026-07-25T06:50:00Z", "Value": 50, "Samples": 3},
            {"Computer": MACHINES[0], "Metric": "OS CPU", "Unit": "percent",
             "TimeGenerated": "2026-07-25T06:50:00Z", "Value": 99, "Samples": 50},
            {"Computer": MACHINES[0], "Metric": "Processor queue", "Unit": "count",
             "TimeGenerated": "2026-07-25T06:50:00Z", "Value": 1000, "Samples": 500},
        ]
        section = self.section("Estate health")
        self.assertEqual(section["rows"][0][2:4], ["40.0", "50.0"])
        self.assertIn("Peak 5m CPU %", section["headers"])
        self.assertIn("not a raw peak", section["note"])

    def test_guest_uses_os_cpu_only_and_missing_weights_not_unweighted_average(self):
        data = self.evidence["datasets"]
        data["cpu"] = [
            {"Computer": "SQL2019-GUEST", "Metric": "OS CPU", "Unit": "percent",
             "TimeGenerated": "2026-07-25T06:50:00Z", "Value": 18, "Samples": None},
            {"Computer": "SQL2019-GUEST", "Metric": "Host hypervisor CPU", "Unit": "percent",
             "TimeGenerated": "2026-07-25T06:50:00Z", "Value": 99, "Samples": 30},
        ]
        row = next(row for row in self.section("Estate health")["rows"] if row[0] == "SQL2019-GUEST")
        self.assertEqual(row[2:4], ["N/A", "18.0"])
        self.assertEqual(row[1], "MISSING")

    def test_latest_ram_selected_by_time_not_input_order(self):
        data = self.evidence["datasets"]
        data["memory"] = [
            {"Computer": MACHINES[0], "TimeGenerated": "2026-07-25T06:50:00Z", "UsedPercent": 72.3},
            {"Computer": MACHINES[0], "TimeGenerated": "2026-07-25T06:40:00Z", "UsedPercent": 99},
        ]
        self.assertEqual(self.section("Estate health")["rows"][0][-1], "72.3")
        self.assertIn("latest 5-minute mean", self.section("Estate health")["note"])

    def test_latest_invalid_ram_does_not_fall_back_to_older_value(self):
        self.evidence["datasets"]["memory"] = [
            {"Computer": MACHINES[0], "TimeGenerated": "2026-07-25T06:50:00Z", "UsedPercent": None},
            {"Computer": MACHINES[0], "TimeGenerated": "2026-07-25T06:45:00Z", "UsedPercent": 50},
        ]
        row = self.section("Estate health")["rows"][0]
        self.assertEqual(row[-1], "N/A")
        self.assertEqual(row[1], "MISSING")

    def test_sql_cap_from_latest_data_not_a_hardcoded_limit(self):
        self.evidence["datasets"]["sql-memory"] = [
            {"TimeGenerated": "2026-07-25T06:50:00Z", "Latest": "2026-07-25T06:54:12Z",
             "CapMiB": 768, "CommittedMiB": 300, "ProcessMiB": 900,
             "OSAvailableMiB": 1500, "CacheMiB": 200},
            {"TimeGenerated": "2026-07-25T06:45:00Z", "CapMiB": 9829},
        ]
        section = self.section("SQL memory")
        rows = dict(section["rows"])
        self.assertEqual(rows["Observed SQL memory cap"], "768.0 MiB")
        self.assertEqual(rows["SQL process memory"], "900.0 MiB")
        self.assertEqual(rows["OS available headroom"], "1,500.0 MiB")
        self.assertIn("13:54:12 LT", section["note"])
        self.assertIn("not a hard limit", section["note"])
        self.assertIn("overlap: do not add", section["note"])

    def test_sql_grant_and_use_are_paired_from_latest_bucket(self):
        self.evidence["datasets"]["sql-grants"] = [
            {"TimeGenerated": "2026-07-25T06:50:00Z", "SnapshotAt": "2026-07-25T06:52:17Z",
             "GrantedMiB": 48, "UsedMiB": 7},
            {"TimeGenerated": "2026-07-25T06:45:00Z", "SnapshotAt": "2026-07-25T06:49:50Z",
             "GrantedMiB": 200, "UsedMiB": 170},
        ]
        section = self.section("SQL memory")
        self.assertEqual(section["rows"][-1][1], "48.0 / 7.0 MiB")
        self.assertIn("13:52:17 LT", section["note"])
        self.assertIn("same peak-allocation record", section["note"])

    def test_storage_idle_direction_and_missing_iops_latency_are_na(self):
        self.evidence["datasets"]["storage"] = [
            {"Computer": "SQL2019-GUEST", "Layer": "Windows guest volume", "Device": "E:",
             "ReadIOPS": 0, "WriteIOPS": 5, "TotalIOPS": 5,
             "ReadLatencyMs": 999, "WriteLatencyMs": 4.25, "TransferLatencyMs": 4,
             "Latest": "2026-07-25T06:54:00Z"},
            {"Computer": "SQL2019-GUEST", "Layer": "Windows guest volume", "Device": "L:",
             "ReadLatencyMs": 200, "WriteLatencyMs": 300,
             "Latest": "2026-07-25T06:54:00Z"},
        ]
        rows = self.section("Storage highlights")["rows"]
        self.assertEqual(rows[0][1:], ["0.0", "5.0", "N/A", "4.2", "4.0"])
        self.assertEqual(rows[1][1:], ["N/A"] * 5)
        self.assertIn("window means", self.section("Storage highlights")["note"])
        self.assertIn("not hourly peaks", self.section("Storage highlights")["note"])

    def test_storage_bounded_diverse_selection_and_no_fabricated_volumes(self):
        self.evidence["datasets"]["storage"] = [
            {"Computer": MACHINES[0], "Layer": "Hyper-V virtual disk", "Device": f"alias{i}.vhdx",
             "ReadIOPS": 1, "ReadLatencyMs": 100 - i, "Latest": "2026-07-25T06:54:00Z"}
            for i in range(10)
        ] + [
            {"Computer": "SQL2019-GUEST", "Layer": "Windows guest volume", "Device": "D:",
             "ReadIOPS": 1, "ReadLatencyMs": 1, "Latest": "2026-07-25T06:54:00Z"},
            {"Computer": "RHEL94-GUEST", "Layer": "RHEL block device (aliases not additive)",
             "Device": "sda", "ReadIOPS": 2, "ReadLatencyMs": 2, "Latest": "2026-07-25T06:54:00Z"},
        ]
        section = self.section("Storage highlights")
        self.assertEqual(len(section["rows"]), 5)
        self.assertTrue(any("SQL2019-GUEST / D:" in row[0] for row in section["rows"]))
        self.assertTrue(any("RHEL94-GUEST / sda" in row[0] for row in section["rows"]))
        self.assertIn("12 source rows", section["note"])
        self.assertNotIn(" / E:", str(section["rows"]))
        self.assertNotIn(" / L:", str(section["rows"]))

    def test_group_uses_latest_source_aggregate_not_cross_layer_sum(self):
        self.evidence["datasets"]["cluster-storage"] = [
            {"TimeGenerated": "2026-07-25T06:50:00Z", "GroupIOPS": 22.5,
             "RateWeightedLatencyMs": 7.3, "ObservedMembers": 3, "ExpectedMembers": 3,
             "DistinctVolumes": 6},
            {"TimeGenerated": "2026-07-25T06:45:00Z", "GroupIOPS": 900,
             "RateWeightedLatencyMs": 77, "ObservedMembers": 3, "ExpectedMembers": 3,
             "DistinctVolumes": 6},
        ]
        section = self.section("Windows logical group (not WSFC)")
        self.assertEqual(section["rows"][0][1:], ["22.5", "7.3", "3 / 3", "6"])
        self.assertIn("not a sum across storage layers", section["note"])

    def test_group_missing_member_suppresses_rates_and_idle_suppresses_latency(self):
        group = {"TimeGenerated": "2026-07-25T06:50:00Z", "GroupIOPS": 40,
                 "RateWeightedLatencyMs": 500, "ObservedMembers": 2, "ExpectedMembers": 3}
        self.evidence["datasets"]["cluster-storage"] = [group]
        self.assertEqual(self.section("Windows logical group (not WSFC)")["rows"][0][1:4],
                         ["N/A", "N/A", "2 / 3"])
        group.update(ObservedMembers=3, GroupIOPS=0)
        self.assertEqual(self.section("Windows logical group (not WSFC)")["rows"][0][1:3],
                         ["0.0", "N/A"])

    def test_contention_top_three_sampled_p95_not_ready_percent(self):
        self.evidence["datasets"]["contention"] = [
            {"Guest": guest, "MeanNs": 15, "P95Ns": value, "PeakNs": 9999}
            for guest, value in (("one", 5), ("four", 400), ("two", 200), ("three", 300))
        ]
        section = self.section("CPU contention - highest sampled P95")
        self.assertEqual([row[0] for row in section["rows"]], ["four", "three", "two"])
        self.assertEqual(section["rows"][0][-1], "400")
        self.assertIn("Sampled P95 wait (ns/dispatch)", section["headers"])
        self.assertIn("not a per-operation latency percentile", section["note"])
        self.assertIn("not CPU ready %", section["note"])

    def test_html_escapes_all_dynamic_text_but_plaintext_preserves_utf8(self):
        payload = '日本語 & <script>alert("x")</script><img src="https://bad">\''
        self.evidence["job"]["reportId"] = payload
        self.evidence["health"].update(maintenance=payload, sustainedFindings=[payload])
        self.evidence["datasets"]["storage"][0].update(Device=payload, Layer=payload)
        self.evidence["datasets"]["contention"] = [{"Guest": payload, "P95Ns": 100, "MeanNs": 90}]
        result = self.render()
        self.assertIn(payload, result["plainText"])
        self.assertIn("日本語 &amp; &lt;script&gt;", result["html"])
        self.assertIn("&quot;x&quot;", result["html"])
        self.assertIn("&#x27;", result["html"])
        markup = Markup(result["html"])
        self.assertNotIn("script", {tag for tag, _ in markup.tags})
        self.assertEqual(len([tag for tag, _ in markup.tags if tag == "img"]), 2)
        self.assertNotIn("a", {tag for tag, _ in markup.tags})

    def test_nonfinite_boolean_missing_and_negative_numbers_remain_na(self):
        for bad in (None, float("nan"), float("inf"), -float("inf"), True, False, -1, "9"):
            with self.subTest(value=bad):
                self.evidence["datasets"]["sql-memory"] = [
                    {"TimeGenerated": "2026-07-25T06:50:00Z", "CapMiB": bad}]
                self.evidence["datasets"]["memory"] = [
                    {"TimeGenerated": "2026-07-25T06:50:00Z", "Computer": MACHINES[0],
                     "UsedPercent": bad}]
                result = self.render()
                self.assertEqual(self.section("SQL memory", result)["rows"][0][1], "N/A MiB")
                self.assertEqual(self.section("Estate health", result)["rows"][0][-1], "N/A")
                json.dumps(result, allow_nan=False)

    def test_empty_datasets_do_not_invent_zero_or_upgrade_authoritative_status(self):
        self.evidence["datasets"] = {}
        self.evidence["health"].update(status="INSUFFICIENT EVIDENCE", freshSignals=0)
        result = self.render()
        rows = self.section("Estate health", result)["rows"]
        self.assertTrue(all(row[1:] == ["MISSING", "N/A", "N/A", "N/A"] for row in rows))
        self.assertIn("0/14 fresh", result["plainText"])
        self.assertEqual(result["summary"]["status"], "INSUFFICIENT EVIDENCE")
        self.assertIn("not proof of health", result["plainText"])
        self.assertEqual(len(self.section("Open items and actions", result)["rows"]), 3)

    def test_central_health_status_is_authoritative_not_recomputed_from_metrics(self):
        for status in ("INSUFFICIENT EVIDENCE", "ATTENTION REQUIRED", "CRITICAL CONDITION OBSERVED"):
            self.evidence["health"]["status"] = status
            self.assertEqual(self.render()["summary"]["status"], status)
        self.evidence["health"]["freshSignals"] = True
        self.assertIn("N/A/14 fresh", self.render()["plainText"])

    def test_every_summary_table_value_and_note_is_present_in_both_bodies(self):
        result = self.render()
        visible = "".join(Markup(result["html"]).text)
        for section in result["summary"]["sections"]:
            for value in [section["title"], section["note"]] + section["headers"]:
                self.assertIn(value, result["plainText"])
                self.assertIn(value, visible)
            for row in section["rows"]:
                self.assertIn("\t".join(row), result["plainText"])
                for value in row:
                    self.assertIn(value, visible)

    def test_row_order_independence_including_latest_selection_and_equal_timestamps(self):
        data = self.evidence["datasets"]
        data["memory"].append(dict(data["memory"][-1], UsedPercent=65))
        expected = self.render()
        for rows in data.values():
            rows.reverse()
        self.assertEqual(self.render(), expected)

    def test_malformed_timestamps_fail_instead_of_disappearing_or_appearing_fresh(self):
        for invalid in ("bad", "2026-07-25T06:55:00", "2026-07-25T13:55:00+07:00"):
            with self.subTest(timestamp=invalid):
                source = copy.deepcopy(self.evidence)
                source["job"]["sourceEndUtc"] = invalid
                with self.assertRaises(ValueError):
                    present_email(source)
                source = copy.deepcopy(self.evidence)
                source["datasets"]["memory"][0]["TimeGenerated"] = invalid
                with self.assertRaises(ValueError):
                    present_email(source)

    def test_exact_seconds_and_fractional_utc_provenance_are_retained(self):
        self.evidence["freezeAtUtc"] = "2026-07-25T06:55:23.123456Z"
        self.evidence["job"]["sourceEndUtc"] = "2026-07-25T06:55:12.987654Z"
        result = self.render()
        for text in ("2026-07-25T06:55:23.123456Z", "2026-07-25T06:55:12.987654Z"):
            self.assertIn(text, result["html"])
            self.assertIn(text, result["plainText"])

    def test_exceptions_are_bounded_and_open_items_are_not_outage_claims(self):
        self.evidence["health"]["sustainedFindings"] = ["finding A", "finding B", "finding C", "finding D"]
        result = self.render()
        self.assertIn("finding C", result["plainText"])
        self.assertNotIn("finding D", result["plainText"])
        self.assertIn("+1 more in attachments", result["plainText"])
        self.assertIn("not, by themselves, proof of a current outage", result["plainText"])


if __name__ == "__main__":
    unittest.main()
